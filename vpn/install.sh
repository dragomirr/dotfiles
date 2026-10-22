#!/bin/bash

set -e

sudo install -d -o root -g root -m 0755 /usr/local/libexec/wg-route-sync
sudo install -o root -g root -m 0755 bunnycdn_wireguard_sync.py /usr/local/libexec/wg-route-sync/
sudo restorecon -Rv /usr/local/libexec/wg-route-sync
sudo install -o root -g root -m 0755 90-wg-sync /etc/NetworkManager/dispatcher.d/90-wg-sync
sudo restorecon -v /etc/NetworkManager/dispatcher.d/90-wg-sync
sudo install -m 0644 wg-route-sync@.service wg-route-sync@.timer /etc/systemd/system/
sudo install -d /etc/wg-route-sync && sudo install -m 0644 wg-route-sync.d/*.env /etc/wg-route-sync/
sudo systemctl daemon-reload
