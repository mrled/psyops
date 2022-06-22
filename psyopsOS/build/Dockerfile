# Dockerfile to build psyopsOS ISOs

FROM alpine:latest
LABEL maintainer "me@micahrl.com"

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
        grub-efi \
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

USER build

RUN true \
    && abuild-keygen -i -a -n \
    && ls -alF /etc/apk/keys \
    && true

WORKDIR /home/build
RUN true \
    && mkdir workdir iso psyops aports \
    # && git clone --depth=1 https://gitlab.alpinelinux.org/alpine/aports.git \
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
