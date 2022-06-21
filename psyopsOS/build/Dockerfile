# Dockerfile to build psyopsOS ISOs

FROM alpine:latest
LABEL maintainer "me@micahrl.com"

RUN true \
    && apk update \
    && apk add \
        # abuild-doc \
        age \
        # age-doc \
        alpine-conf \
        alpine-sdk \
        alpine-sdk \
        apk-tools \
        bash \
        bind-tools \
        build-base \
        busybox \
        dosfstools \
        fakeroot \
        git \
        gpg \
        grub-efi \
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
        squashfs-tools \
        sqlite \
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

# WORKDIR /home/build
# RUN true \
#     && git clone --depth=1 https://gitlab.alpinelinux.org/alpine/aports.git \
#     && true

VOLUME /home/build/bldtmp
VOLUME /home/build/aports
VOLUME /home/build/iso
VOLUME /home/build/psyops

# mkimg.psyopsOS.sh and genapkovl-psyopsOS.sh depend on this variable
ENV PSYOPSOS_OVERLAY=/home/build/psyops/psyopsOS/os-overlay

WORKDIR /home/build/aports/scripts
