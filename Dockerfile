FROM alpine:latest
LABEL maintainer "me@micahrl.com"

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
    && install -d -o root -g root -m 755 /psyops \
    && install -d -o root -g root -m 755 /psyops/setup \

    && cd /psyops/setup \

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
    # && alias rst2man=rst2man-3 \
    && git clone https://github.com/spwhitton/git-remote-gcrypt /setup/git-remote-crypt \
    && cd /setup/git-remote-crypt \
    && ./install.sh \

    && true

# Copy files for system-level configuration

# Install doctl, the Digital Ocean cli tool
COPY ["docker/getdoctl.py", "/setup/"]

# Run scripts for system-level configuration that rely on copied files
RUN true \

    && cd /setup \

    # this is some bullshit; copied from https://github.com/digitalocean/doctl/blob/master/Dockerfile
    && mkdir /lib64 && ln -s /lib/libc.musl-x86_64.so.1 /lib64/ld-linux-x86-64.so.2 \
    && python3 /setup/getdoctl.py --outdir /setup \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -o root -g root -m 755 /setup/doctl /usr/local/bin \

    # Enable passwordless sudo
    # ONLY FOR DEVELOPMENT, since a root user in your container can probably escape to be a root user on your container host
    && echo "mrled ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/mrled \
    && chmod 0440 /etc/sudoers.d/mrled \

    # Running makewhatis should happen after all root installation commands / only right before running as my user
    && makewhatis \

    # Configure my user
    && addgroup -S mrled \
    && adduser -S -G mrled -s /bin/bash mrled \
    && mkdir /home/mrled/.bashrc.d \


    && true


# Configure my user. Changes more often
COPY ["dhd", "/home/mrled/.dhd"]
COPY [".", "/home/mrled/psyops"]
COPY ["docker/bashrc.d.psyops", "/home/mrled/.bashrc.d/psyops"]
COPY ["psyops-setup.sh", "/home/mrled/"]
COPY ["docker/psyops.secret.gpg.key.asc", "/home/mrled/.psyops.secret.gpg.key.asc"]
COPY ["docker/psyops.secret.gpg.pubkey.asc", "/home/mrled/.psyops.secret.gpg.pubkey.asc"]
COPY ["docker/psyops.secret.gpg.ownertrust.db.asc", "/home/mrled/.psyops.secret.gpg.ownertrust.db.asc"]
COPY ["docker/id_ed25519.gpg", "/home/mrled/.ssh/id_ed25519.gpg"]
COPY ["docker/bashrc.d.psecrets", "/home/mrled/.bashrc.d/psecrets"]
COPY ["docker/bin", "/psyops/bin"]
RUN true \
    && chown -R mrled:mrled /home/mrled /setup \
    && true
# Changes (like permission changes) made to a VOLUME after it has been declared wil be *discarded*
# Contents of the volume are overwritten when it's bind-mounted
# So make permission changes before declaring, and put any file changes into scripts that run after the Docker image has been created
RUN true \
    && mkdir /psyche \
    && chown -R mrled:mrled /psyche \
    && true
VOLUME /psyche
USER mrled
WORKDIR /home/mrled

# Run commands (as my user). Changes more often
RUN true \
    && cd $HOME \
    && git clone https://github.com/mrled/psyops-secrets $HOME/.secrets \
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.vimrc . \
    && ln -sf ../.dhd/hbase/known_hosts $HOME/.ssh/known_hosts \
    && git config --global user.email "me@micahrl.com" && git config --global user.name "Micah R Ledbetter" \

    # Note that at this time .secrets exists but has not been decrypted, so these symlinks will be broken until decryption time (see bashrc.d.psecrets)
    && ln -s .secrets/dot.config $HOME/.config \

    && true

ENTRYPOINT "/bin/bash"
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
