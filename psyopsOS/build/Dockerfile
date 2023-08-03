# Dockerfile to build psyopsOS ISOs

# This should be the lowest version among all running psyopsOS systems
FROM alpine:3.16
LABEL maintainer "me@micahrl.com"

# Include everything necessary for building an Alpine CD image with mkimage,
# as well as prereqs for building progfiguration_blacksite.
RUN true \
    && apk update \
    && apk add \
        abuild \
        # abuild-doc \
        age \
        # age-doc \
        alpine-base \
        alpine-conf \
        alpine-sdk \
        apk-tools \
        bash \
        bind-tools \
        build-base \
        busybox \
        dosfstools \
        e2fsprogs \
        e2fsprogs-extra \
        fakeroot \
        git \
        gpg \
        # This package is broken in Docker, and leaves apk in a weird state.
        # Don't install it here, but do install it in the mkimage task.
        #grub-efi \
        linux-firmware-intel \
        linux-firmware-mediatek \
        linux-firmware-rtl_bt \
        linux-lts \
        lsblk \
        make \
        # man-db \
        # man-pages \
        minisign \
        mtools \
        ncurses \
        openssh \
        openssl \
        python3 \
        py3-build \
        py3-installer \
        py3-pip \
        py3-requests \
        py3-setuptools \
        py3-tz \
        py3-wheel \
        ripgrep \
        rsync \
        shadow \
        sqlite \
        squashfs-tools \
        sudo \
        syslinux \
        tmux \
        vim \
        wget \
        xorriso \
    && true

RUN true \
    && adduser -D -G abuild build \
    && echo '%abuild ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/abuild \
    && true

# Install the psyopsOS repository signing key
COPY psyops@micahrl.com-62ca1973.rsa.pub /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub
RUN true \
    && chmod 644 /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub \
    && echo "/home/build/psyops/psyopsOS/public/apk/psyopsOS" >> /etc/apk/repositories && cat /etc/apk/repositories \
    && true

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
