# Dockerfile to build psyopsOS ISOs

# This should be the lowest version among all running psyopsOS systems
FROM alpine:3.18
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
        parted \
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
    # Install grub without running its package scripts.
    # Grub tries to run grub-probe, which fails in Docker with an error like this:
    #     (2/2) Installing grub-efi (2.06-r2)
    #     Executing busybox-1.35.0-r17.trigger
    #     Executing grub-2.06-r2.trigger
    #     /usr/sbin/grub-probe: error: failed to get canonical path of `overlay'.
    #     ERROR: grub-2.06-r2.trigger: script exited with error 1
    # We need the grub binaries installed to build a bootable ISO,
    # but we don't need it to actually work on the Docker system, so we skip these.
    && apk add grub-efi --no-scripts \
    && true

RUN true \
    && adduser -D -G abuild build \
    && echo '%abuild ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/abuild \
    && true

# Install the psyopsOS repository signing key
# Note that the path to add to /etc/apk/repositories should match incontainer_apks_path_prefix in tasks/contstants.py.
COPY psyops@micahrl.com-62ca1973.rsa.pub /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub
RUN true \
    && chmod 644 /etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub \
    && alpine_release=$(cat /etc/alpine-release) \
    && alpine_release_majmin=${alpine_release%.*} \
    && echo "/home/build/psyops/psyopsOS/public/apk/v$alpine_release_majmin/psyopsOS" >> /etc/apk/repositories && cat /etc/apk/repositories \
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