if [ "$BASH_VERSION" ]; then
  PS1='\[\e[37m\]\t \[\e[33m\]\u \[\e[31m\]中文房间 \[\e[32m\]\w \[\e[34m\]\$ \[\e[0m\]'
  export PS1
elif [ "$ZSH_VERSION" ]; then
  PROMPT='%F{white}%* %F{yellow}%n %F{red}中文房间 %F{green}%~ %F{blue}$ %f'
else
  PS1='\t \u 中文房间 \w \$ '
  export PS1
fi
