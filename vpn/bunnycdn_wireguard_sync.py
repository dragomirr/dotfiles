#!/usr/bin/env python3
"""
BunnyCDN + AWS EC2/ALB → local WireGuard Route Sync
====================================================
Fetches BunnyCDN edge server IPs, AWS EC2 public IPs and office-use ALB IPs,
aggregates them into CIDR ranges and syncs them as local routes via the
WireGuard interface (split tunnel). All other traffic bypasses the VPN.

Requirements:
  - Linux with iproute2, Python 3.6+, boto3 (pip install boto3)
  - WireGuard config must NOT install a default route. In /etc/wireguard/wg0.conf:
        [Interface]
        Table = off            # wg-quick won't add any routes
        [Peer]
        AllowedIPs = 0.0.0.0/0 # fine with Table = off, only permits traffic
    (alternatively: AllowedIPs = <narrow list> without Table = off)

Usage:
  sudo -E python3 bunnycdn_wireguard_sync.py             (needs root for `ip route`)
  python3 bunnycdn_wireguard_sync.py --dry-run           (show changes, no root needed
                                                          if the interface is up)
  sudo -E python3 bunnycdn_wireguard_sync.py --flush     (remove all managed routes)
  sudo -E python3 bunnycdn_wireguard_sync.py --loop

Run it after `wg-quick up wg0`. Routes disappear automatically when the
interface goes down; managed routes are tagged with `proto 99` so only
those are ever touched.

To run automatically on connect, add to wg0.conf [Interface]:
  PostUp = /usr/bin/python3 /path/to/bunnycdn_wireguard_sync.py
"""

import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import List, Set

try:
    import boto3
    import botocore.exceptions
except ImportError:
    print("✗ Missing boto3. Install with: pip install boto3")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════

BUNNYCDN_URL = "https://bunnycdn.com/api/system/edgeserverlist"

WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")
ROUTE_PROTO  = "99"                # Routing protocol tag marking routes we manage

# Extra CIDRs/IPs that should always go through the VPN
EXTRA_ROUTES: List[str] = [
    # "10.20.0.0/16",
]

# Comma-separated, per VPN instance (see wg-route-sync@.service / env files)
AWS_REGIONS = [r.strip() for r in os.getenv("AWS_REGIONS", "eu-west-1").split(",") if r.strip()]

# Set INCLUDE_BUNNYCDN=false on all but one VPN: the same prefix can't be routed
# via two interfaces, the syncs would keep overwriting each other.
INCLUDE_BUNNYCDN = os.getenv("INCLUDE_BUNNYCDN", "true").lower() == "true"

SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "3600"))

_EMR_TAG_KEYS = {
    "aws:elasticmapreduce:job-flow-id",
    "aws:elasticmapreduce:instance-group-role",
}

# ══════════════════════════════════════════════════════════════


def ip_cmd(*args: str, stdin: str = None) -> subprocess.CompletedProcess:
    cmd = ["ip", *args]
    if os.geteuid() != 0:
        cmd = ["sudo", *cmd]
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True)


def interface_exists(name: str) -> bool:
    return subprocess.run(["ip", "link", "show", name], capture_output=True).returncode == 0


def get_managed_routes() -> Set[str]:
    """Returns the set of CIDRs currently routed via WG_INTERFACE with our proto tag"""
    res = subprocess.run(
        ["ip", "-4", "route", "show", "dev", WG_INTERFACE, "proto", ROUTE_PROTO],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"  ✗ Could not read routes: {res.stderr.strip()}")
        sys.exit(1)
    routes = set()
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        dst = line.split()[0]
        # `ip route` prints /32 hosts without prefix length
        routes.add(str(ipaddress.ip_network(dst, strict=False)))
    return routes


def apply_routes(add: Set[str], remove: Set[str]) -> None:
    lines = [f"route del {c} dev {WG_INTERFACE} proto {ROUTE_PROTO}" for c in sorted(remove)]
    lines += [f"route replace {c} dev {WG_INTERFACE} proto {ROUTE_PROTO}" for c in sorted(add)]
    # -force keeps going if a single line fails
    res = ip_cmd("-4", "-force", "-batch", "-", stdin="\n".join(lines) + "\n")
    if res.returncode != 0:
        print(f"  ✗ ip batch reported errors:\n{res.stderr.strip()}")
    else:
        print(f"  ✓ Added {len(add)}, removed {len(remove)}")


def fetch_bunnycdn_ips() -> List[str]:
    print("▶ Fetching BunnyCDN IP list...")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(BUNNYCDN_URL, context=ctx, timeout=15) as resp:
            raw = resp.read()
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    ips = [str(item).strip() for item in data if str(item).strip()]
                elif isinstance(data, dict):
                    for key in ("ips", "addresses", "servers", "data"):
                        if key in data and isinstance(data[key], list):
                            ips = [str(i).strip() for i in data[key]]
                            break
                    else:
                        print(f"  ✗ Unknown JSON format: {list(data.keys())}")
                        sys.exit(1)
                else:
                    print(f"  ✗ Unexpected type: {type(data)}")
                    sys.exit(1)
            except json.JSONDecodeError:
                ips = [l.strip() for l in raw.decode().splitlines() if l.strip()]
        print(f"  ✓ Fetched {len(ips)} IP addresses")
        return ips
    except urllib.error.URLError as e:
        print(f"  ✗ Error: {e.reason}")
        sys.exit(1)


def fetch_ec2_ips() -> List[str]:
    """Public IPs of running EC2 instances (excluding EMR and VPN instances)"""
    print(f"▶ Fetching EC2 IP addresses ({', '.join(AWS_REGIONS)})...")
    ips = []
    skipped = 0
    for region in AWS_REGIONS:
        try:
            ec2 = boto3.client("ec2", region_name=region)
            pages = ec2.get_paginator("describe_instances").paginate(
                Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
            )
            for page in pages:
                for reservation in page["Reservations"]:
                    for instance in reservation["Instances"]:
                        tags = {t["Key"]: t.get("Value", "") for t in instance.get("Tags", [])}
                        if _EMR_TAG_KEYS & set(tags.keys()) or tags.get("Role") == "vpn":
                            skipped += 1
                            continue
                        ip = instance.get("PublicIpAddress")
                        if ip:
                            ips.append(ip)
        except botocore.exceptions.NoCredentialsError:
            print(f"  ✗ AWS credentials not configured (region: {region})")
            sys.exit(1)
        except botocore.exceptions.ClientError as e:
            print(f"  ✗ AWS error ({region}): {e}")
            sys.exit(1)
    print(f"  ✓ Fetched {len(ips)} EC2 IP addresses (skipped {skipped} instances)")
    return ips


def fetch_alb_ips() -> List[str]:
    """IPs of ALBs tagged Tier=office-use, resolved from their DNS names"""
    print(f"▶ Fetching ALB IP addresses ({', '.join(AWS_REGIONS)})...")
    ips = []
    for region in AWS_REGIONS:
        try:
            elb = boto3.client("elbv2", region_name=region)
            lbs = {}
            for page in elb.get_paginator("describe_load_balancers").paginate():
                for lb in page["LoadBalancers"]:
                    lbs[lb["LoadBalancerArn"]] = lb["DNSName"]
            if not lbs:
                continue

            arns = list(lbs.keys())
            matched_dns = []
            for i in range(0, len(arns), 20):
                resp = elb.describe_tags(ResourceArns=arns[i:i + 20])
                for td in resp["TagDescriptions"]:
                    tags = {t["Key"]: t["Value"] for t in td["Tags"]}
                    if tags.get("Tier") == "office-use":
                        matched_dns.append(lbs[td["ResourceArn"]])

            for dns in matched_dns:
                try:
                    resolved = {
                        addr[4][0]
                        for addr in socket.getaddrinfo(dns, None, socket.AF_INET)
                    }
                    ips.extend(resolved)
                    print(f"  ✓ {dns} → {', '.join(sorted(resolved))}")
                except socket.gaierror as e:
                    print(f"  ✗ DNS resolution failed for {dns}: {e}")
        except botocore.exceptions.NoCredentialsError:
            print(f"  ✗ AWS credentials not configured (region: {region})")
            sys.exit(1)
        except botocore.exceptions.ClientError as e:
            print(f"  ✗ AWS error ({region}): {e}")
            sys.exit(1)
    print(f"  ✓ Fetched {len(ips)} ALB IP addresses")
    return ips


def aggregate_to_cidr(ips: List[str]) -> Set[str]:
    """Aggregates IPs/CIDRs into a minimal set of IPv4 CIDR ranges"""
    networks = []
    skipped = 0
    for ip in ips:
        try:
            net = ipaddress.ip_network(ip, strict=False)
            if net.version == 4:
                networks.append(net)
            else:
                skipped += 1
        except ValueError:
            skipped += 1
    if skipped:
        print(f"  ⚠ Skipped {skipped} invalid/IPv6 entries")
    collapsed = list(ipaddress.collapse_addresses(sorted(networks)))
    print(f"  ✓ Aggregated into {len(collapsed)} CIDR ranges")
    return {str(n) for n in collapsed}


def sync(dry_run: bool = False, flush: bool = False):
    print("=" * 55)
    print("  BunnyCDN + EC2 → WireGuard Route Sync")
    print("=" * 55)

    if not interface_exists(WG_INTERFACE):
        print(f"✗ Interface {WG_INTERFACE} not found. Connect the VPN first (wg-quick up {WG_INTERFACE}).")
        sys.exit(1)

    existing = get_managed_routes()
    print(f"  ✓ Found {len(existing)} existing managed routes on {WG_INTERFACE}")

    if flush:
        desired: Set[str] = set()
    else:
        raw_ips = (fetch_bunnycdn_ips() if INCLUDE_BUNNYCDN else []) + fetch_ec2_ips() + fetch_alb_ips() + EXTRA_ROUTES
        desired = aggregate_to_cidr(raw_ips)

    to_add = desired - existing
    to_remove = existing - desired

    print(f"\n{'─'*40}")
    print(f"  To add:       {len(to_add):4d}")
    print(f"  To remove:    {len(to_remove):4d}")
    print(f"  Unchanged:    {len(desired & existing):4d}")
    print(f"{'─'*40}")

    if not to_add and not to_remove:
        print("\n✓ All routes are up to date, no changes needed.")
        return

    if dry_run:
        print("\n[DRY RUN] No changes applied.\n")
        for c in sorted(to_add):
            print(f"  + {c}")
        for c in sorted(to_remove):
            print(f"  - {c}")
        return

    apply_routes(to_add, to_remove)
    print("\n✓ Sync complete.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    flush = "--flush" in sys.argv
    if dry_run:
        print("[DRY RUN mode - no changes will be applied]\n")

    if "--loop" in sys.argv:
        print(f"[LOOP mode - syncing every {SYNC_INTERVAL_SECONDS}s]\n")
        while True:
            try:
                sync(dry_run=dry_run)
            except SystemExit:
                print("  ⚠ Sync attempt failed, will retry next interval.")
            print(f"\nSleeping {SYNC_INTERVAL_SECONDS}s...\n")
            time.sleep(SYNC_INTERVAL_SECONDS)
    else:
        sync(dry_run=dry_run, flush=flush)
