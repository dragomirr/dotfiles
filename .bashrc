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
  PS1="\[\033[01;34m\]\w (\$(git branch 2>/dev/null | grep '^*' | colrm 1 2))$\[\033[00m\] "
fi

#
# ALIASES
#
if [ -f ~/.bash_aliases ]; then
  . ~/.bash_aliases
fi

#
# VARIABLES
#
if [ -f ~/.bash_variables ]; then
  . ~/.bash_variables
fi

if [ -f ~/.ci_variables ]; then
  . ~/.ci_variables
fi
#
# FUNCTIONS
#
if [ -f ~/.bash_functions ]; then
  . ~/.bash_functions
fi

# The next line updates PATH for the Google Cloud SDK.
if [ -f ${HOME}/.local/bin/google-cloud-sdk/path.bash.inc ]; then
  source "${HOME}/.local/bin/google-cloud-sdk/path.bash.inc"
fi

#
# COMPLETION
#
# The next line enables shell command completion for gcloud.
if [ -f /usr/share/google-cloud-sdk/completion.bash.inc ]; then
  source '/usr/share/google-cloud-sdk/completion.bash.inc'
fi

if [ $(which kubectl) ]; then
  . <(kubectl completion bash)
fi

if [ $(which aws) ]; then
  . $(which aws_bash_completer)
fi

if [ $(which terraform) ]; then
  complete -C $(which terraform) terraform
fi

if [ $(which awless) ]; then
  . <(awless completion bash)
fi


export GOPATH=~/go

export PATH=${PATH}:${HOME}/.local/bin:${GOPATH}/bin

if [ -f /usr/local/bin/virtualenvwrapper.sh ]; then
  source /usr/local/bin/virtualenvwrapper.sh
elif [ -f /home/dragomir/.local/bin/virtualenvwrapper.sh ]; then
  source /home/dragomir/.local/bin/virtualenvwrapper.sh
fi

# enable bash completion in interactive shells
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

# enable direxpand if not enabled
if [[ ! $(shopt -s | grep -w direxpand) ]]; then
  shopt -s direxpand
fi
