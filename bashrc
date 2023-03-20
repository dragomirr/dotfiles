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

#
# PS
#
if [[ ${EUID} == 0 ]] ; then
  PS1='\[\033[01;31m\]\h\[\033[01;34m\] \W \$\[\033[00m\] '
else
  PS1="\[\033[01;36m\]\w\[\033[00m\] \$(git branch 2>/dev/null | grep '^*' | colrm 1 2) \[\033[01;33m\]\$( if [[ -d .terraform ]]; then terraform workspace show; fi)\[\033[00m\]\n$ "
fi

export GOPATH=$HOME/go

export PATH=$PATH:$HOME/.local/bin:$GOPATH/bin:$HOME/.local/bin/k8s

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
if [ -f ~/.bash_functions ]; then
  . ~/.bash_functions
fi

#
# COMPLETION
#
if [ $(which kubectl 2>/dev/null) ]; then
  . <(kubectl completion bash)
fi

if [ $(which terraform 2>/dev/null) ]; then
  complete -C $(which terraform) terraform
fi

if [ $(which aws 2>/dev/null) ]; then
  if [ $(which aws_completer 2>/dev/null) ]; then
    complete -C $(which aws_completer) aws
  fi
fi

if [ $(which awless 2>/dev/null) ]; then
  . <(awless completion bash)
fi

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
