# Dockerfile to build psyopsOS ISOs

# This should be the lowest version among all running psyopsOS systems
FROM alpine:3.21
LABEL maintainer "me@micahrl.com"

# Include everything necessary for building an Alpine CD image with mkimage,
# as well as prereqs for building progfiguration_blacksite.
COPY install-prereqs.sh /usr/local/sbin/install-prereqs.sh
RUN true \
    && apk update \
    && /usr/local/sbin/install-prereqs.sh \
    && true

RUN true \
    && adduser -D -G abuild build \
    && echo '%abuild ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/abuild \
    && true

# Install the psyopsOS repository signing key
# Note that the path to add to /etc/apk/repositories should match in_container_artifacts_dir in telekinesis alpine_docker_builder.py
COPY psyops@micahrl.com-62ca1973.rsa.pub /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub
RUN true \
    && chmod 644 /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub \
    && alpine_release=$(cat /etc/alpine-release) \
    && alpine_release_majmin=${alpine_release%.*} \
    && echo "/home/build/artifacts/deaddrop/apk/v$alpine_release_majmin/psyopsOS" >> /etc/apk/repositories && cat /etc/apk/repositories \
    && true

# Set up apk caching; see apk-cache(5)
VOLUME /var/cache/apk
RUN ln -s /var/cache/apk /etc/apk/cache

USER build

WORKDIR /home/build
RUN true \
    && mkdir .abuild workdir iso psyops aports \
    && true

VOLUME /home/build/workdir
VOLUME /home/build/aports
VOLUME /home/build/iso
VOLUME /home/build/psyops

# mkimg.psyopsOS.sh and genapkovl-psyopsOS.sh depend on this variable
ENV PSYOPSOS_OVERLAY=/home/build/psyops/psyopsOS/os-overlay

# We write some metadata to /etc/psyopsOS/iso.json that depends on these variables
ENV PSYOPSOS_BUILD_DATE_ISO8601=
ENV PSYOPSOS_BUILD_GIT_REVISION=
ENV PSYOPSOS_BUILD_GIT_DIRTY=

WORKDIR /home/build/aports/scripts