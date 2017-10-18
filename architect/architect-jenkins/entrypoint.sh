#!/bin/sh

usermod --append --groups "${DOCKER_HOST_DOCKER_GID}" "${JENKINS_USER}"

# Since we pass --preserve-env to sudo below,
# try to at least set $HOME correctly
HOME=$(grep "^${JENKINS_USER}:x:" /etc/passwd | cut -d: -f6)
if test -z "$HOME"; then
    echo "Could not determine home directory for '${JENKINS_USER}'"
    exit 1
else
    echo "Set \$HOME to ${HOME}"
fi

exec sudo --preserve-env --user="${JENKINS_USER}" /usr/local/bin/jenkins.sh "$@"
