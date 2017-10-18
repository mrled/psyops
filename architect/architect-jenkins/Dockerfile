FROM jenkins/jenkins:lts-alpine

# Must match user ARG in the upstream Jenkins Dockerfile
ENV JENKINS_USER jenkins

# Must match the GID of the docker group on the docker *host*
# This lets us add the Jenkins user to this GID,
# and then bind-mount /var/run/docker.sock from the host
# to the same location in the container
# so that the Jenkins container can spin up new containers
# on the *host* docker engine,
# which we will use for build agents
ENV DOCKER_HOST_DOCKER_GID 1000

USER root

# docker:   Let Jenkins issue docker commands (to bring up slaves)
# shadow:   Install the usermod utility
# sudo:     Allow root to run a command as another user
#           (For some reason this won't work with 'su -l USER -c CMD' on jenkins/jenkins:lts-alpine)
RUN true \
    && apk add --no-cache \
        docker \
        shadow \
        sudo \
    && true

COPY entrypoint.sh /usr/local/bin/entrypoint.sh

# NOTE: We provide our own entrypoint.sh script
# That script runs tini with the same arguments the official script does:
#   ENTRYPOINT ["/bin/tini", "--", "/usr/local/bin/jenkins.sh"]
# See also https://github.com/jenkinsci/docker/blob/48011c8cd7b7e0a2576365aad558bb049bc1d261/Dockerfile-alpine#L71
ENTRYPOINT ["/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
