#!/bin/sh
usermod --append --groups "${DOCKER_HOST_DOCKER_GID}" "${JENKINS_USER}"
exec sudo --preserve-env --user="${JENKINS_USER}" /usr/local/bin/jenkins.sh "$@"
