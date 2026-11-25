# .bashrc

# Source global definitions
if [ -f /etc/bash.bashrc ]; then
  . /etc/bash.bashrc
fi


PS1="\[\e[36m\]\W\[\e[m\] "
# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

# User specific aliases and functions

#
# HISTORY
#
HISTCONTROL=ignoreboth
HISTTIMEFORMAT="%d/%m/%y %T "
# append to the history file, don't overwrite it
shopt -s histappend
HISTFILESIZE=2000

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# PS
_prompt_git_branch() {
    local branch sha
    branch=$(git branch --show-current 2>/dev/null) || return   # nismo u repou
    if [[ -n "$branch" ]]; then
        printf ' \001\033[01;32m\002%s\001\033[00m\002' "$branch"
    else
        sha=$(git rev-parse --short HEAD 2>/dev/null) || return
        printf ' \001\033[01;31m\002HEAD detached at %s\001\033[00m\002' "$sha"
    fi
}

_terraform_workspace() {
    [[ -d .terraform ]] || return

    local workspace
    workspace=$(terraform workspace show 2>/dev/null)

    [[ -n "$workspace" ]] &&
        printf ' \033[01;33m%s\033[00m' "$workspace"
}

_kube_context() {
    local ctx
    ctx=$(kubectl config current-context 2>/dev/null)
    [[ -n "$ctx" ]] && printf ' %s' "$ctx"
}

if [[ ${EUID} == 0 ]] ; then
  PS1='\[\033[01;31m\]\h\[\033[01;34m\] \W \$\[\033[00m\] '
else
  PS1='\[\033[01;36m\]\w\[\033[00m\]$(_prompt_git_branch)$(_terraform_workspace)$(_kube_context)\n$ '
fi

export GOPATH=$HOME/go

export PATH=$PATH:$HOME/.local/bin:$GOPATH/bin:$HOME/.local/bin/k8s:$HOME/.krew/bin

#
# ALIASES
#
if [ -f ~/.aliases ]; then
  . ~/.aliases
fi

#
# VARIABLES
#
if [ -f ~/.config/variables ]; then
  . ~/.config/variables
fi

#
# FUNCTIONS
#
if [ -f ~/.functions ]; then
  . ~/.functions
fi

#
# COMPLETION
#
_load_completion() {
    local cmd="$1"; shift
    command -v "$cmd" &>/dev/null && source <("$cmd" "$@" 2>/dev/null)
}

_load_completion kubectl       completion bash
_load_completion kubectl-cnpg  completion bash
_load_completion helm          completion bash
_load_completion awless        completion bash

# tools using "complete -C" instead of script
command -v aws_completer &>/dev/null && complete -C aws_completer aws
command -v terraform     &>/dev/null && complete -C "$(command -v terraform)" terraform

[[ -s ~/.config/bunny.net/config ]] && source ~/.config/bunny.net/config

[[ -s "$HOME/.acme.sh/acme.sh.env" ]] && source "$HOME/.acme.sh/acme.sh.env"

if [ -f /usr/local/bin/virtualenvwrapper.sh ]; then
  source /usr/local/bin/virtualenvwrapper.sh
elif [ -f $HOME/.local/bin/virtualenvwrapper.sh ]; then
  source $HOME/.local/bin/virtualenvwrapper.sh
fi

# enable bash completion in interactive shells
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

if hash most 2>/dev/null ; then
  export MANPAGER=most
fi

# enable direxpand if not enabled
if [[ ! $(shopt -s | grep -w direxpand) ]]; then
  shopt -s direxpand
fi

export EDITOR=vim

if [ $(which direnv 2>/dev/null) ]; then
  eval "$(direnv hook bash)"
fi
