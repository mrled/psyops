FROM alpine:3.6
LABEL maintainer "me@micahrl.com"

ARG psysetup=/psysetup
ARG username=psyops
ARG homedir=/home/psyops
ARG psyvol=/psyops
ARG enablesudo=

# Pre-copy root OS configuration phase
RUN true \

    && apk update \
    && apk add \
        bash bash-doc \
        ca-certificates ca-certificates-doc \
        emacs-nox emacs-doc \
        file file-doc \
        git git-doc \
        # By default, busybox's less is /usr/bin/less; adding the less package makes the real less /usr/bin/less instead
        less less-doc \
        gnupg1 gnupg1-doc \
        man man-pages mdocml-apropos \
        # provides tput
        ncurses \
        openssh-client openssh-doc \
        openssl openssl-doc \
        python3 python3-doc \
        # for rst2man, used by git-remote-crypt
        py3-docutils \
        sudo sudo-doc \
        # for awscli, installed below from pip, to get its documentation
        groff groff-doc \
    && makewhatis \
    && update-ca-certificates --fresh \

    && python3 -m ensurepip && python3 -m pip install --upgrade pip && python3 -m pip install \
        gandi.cli \
        awscli \

    && install -d -o root -g root -m 755 /usr/local/bin \
    && install -d -o root -g root -m 755 "$psysetup" \

    && cd "$psysetup" \

    # Install toilet, which is very important
    # Moved away from downloading a release tarbatll b/c the toilet server gets mad if you hit it too hard
    && apk add g++ libcaca libcaca-dev make automake autoconf \
    && git clone https://github.com/cacalabs/toilet \
    && cd toilet \
    && ./bootstrap \
    && ./configure \
    && make \
    && make install \
    # you have to leave libcaca, but it's only 4mb
    # && apk del g++ libcaca libcaca-dev make \
    && apk del g++ libcaca-dev make automake autoconf \

    # Install git-remote-crypt
    # We install py3-docutils, which includes `rst2man-3`, but git-remote-crypt's setup.sh expects `rst2man`, lol
    && printf '#!/bin/sh\nrst2man-3 "$@"\n' > /usr/local/bin/rst2man && chmod 755 /usr/local/bin/rst2man \
    && git clone https://github.com/spwhitton/git-remote-gcrypt "$psysetup/git-remote-crypt" \
    && cd "$psysetup/git-remote-crypt" \
    && ./install.sh \

    && true

# Copy files for system-level configuration

# Install doctl, the Digital Ocean cli tool
COPY ["docker/psysetup/*", "/usr/local/bin/"]

# Run scripts for system-level configuration that rely on copied files
RUN true \

    && cd "$psysetup" \

    # this is some bullshit; copied from https://github.com/digitalocean/doctl/blob/master/Dockerfile
    && mkdir /lib64 && ln -s /lib/libc.musl-x86_64.so.1 /lib64/ld-linux-x86-64.so.2 \

    && getdoctl --outdir "$psysetup" \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -o root -g root -m 755 "$psysetup/doctl" /usr/local/bin \

    # Enable passwordless sudo
    # ONLY FOR DEVELOPMENT, since a root user in your container can probably escape to be a root user on your container host
    && if test "$enablesudo"; then true \
        && echo "$username ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/$username" \
        && chmod 0440 "/etc/sudoers.d/$username" \
    ;  fi \

    # Running makewhatis should happen after all root installation commands / only right before running as my user
    && makewhatis \

    # Configure my user
    && addgroup -S "$username" \
    && adduser -S -G "$username" -s /bin/bash "$username" \

    && true


# Configure my user. Changes more often

# Get psyops submodules (to be processed by submodule2repo later)
COPY ["dhd", "$homedir/.dhd"]
COPY [".git/modules/dhd", "$homedir/.dhd/.git.new"]

COPY ["docker/psyops.secret.gpg.key.asc",           "$homedir/.gnupg/psyops.secret.gpg.key.asc"]
COPY ["docker/psyops.secret.gpg.pubkey.asc",        "$homedir/.gnupg/psyops.secret.gpg.pubkey.asc"]
COPY ["docker/psyops.secret.gpg.ownertrust.db.asc", "$homedir/.gnupg/psyops.secret.gpg.ownertrust.db.asc"]
COPY ["docker/id_ed25519.gpg",                      "$homedir/.ssh/id_ed25519.gpg"]

COPY ["docker/bashrc.d", "$homedir/.bashrc.d"]

COPY ["docker/psybin/*", "/usr/local/bin/"]

RUN true \
    && mkdir "$psyvol" \
    && chown -R "$username:$username" "$homedir" "$psyvol" \
    && true

# Changes (like permission changes) made to a VOLUME after it has been declared wil be *discarded*
# Contents of the volume are overwritten when it's bind-mounted
# So make permission changes before declaring, and put any file changes into scripts that run after the Docker image has been created
VOLUME $psyvol

USER $username
WORKDIR $homedir

# Run commands (as my user). Changes more often
RUN true \
    && cd "$HOME" \
    && submodule2repo "$HOME/.dhd" "$HOME/.dhd/.git.new" \
    && git clone https://github.com/mrled/psyops-secrets "$HOME/.secrets" \
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.vimrc . \
    && ln -sf ../.dhd/hbase/known_hosts "$HOME/.ssh/known_hosts" \
    && git config --global user.email "me@micahrl.com" && git config --global user.name "Micah R Ledbetter" \

    && true

ENTRYPOINT "/bin/bash"
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
