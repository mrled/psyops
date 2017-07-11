FROM alpine:latest
LABEL maintainer "me@micahrl.com"

# Configure OS packages etc. Should change fairly rarely.
RUN true \

    && apk update \
    && apk add \
        bash bash-doc \
        ca-certificates ca-certificates-doc \
        emacs-nox emacs-doc \
        file file-doc \
        git git-doc \
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
    && makewhatis \
    && update-ca-certificates --fresh \

    && python3 -m ensurepip && python3 -m pip install --upgrade pip && python3 -m pip install \
        gandi.cli \

    && install -d -o root -g root -m 755 /usr/local/bin \

    && true

# Configure other packages. Might change more frequently

# Install toilet, which is very important
# The toilet server gets mad if you hit it too hard
# Do this shit first in a separate RUN statement so it's cached
RUN true \
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
    && true

# Install doctl, the Digital Ocean cli tool
COPY ["docker/getdoctl.py", "/setup/"]
RUN true \

    && cd /setup \

    # this is some bullshit; copied from https://github.com/digitalocean/doctl/blob/master/Dockerfile
    && mkdir /lib64 && ln -s /lib/libc.musl-x86_64.so.1 /lib64/ld-linux-x86-64.so.2 \
    && python3 /setup/getdoctl.py \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -o root -g root -m 755 /setup/doctl /usr/local/bin \

    && true

# Install git-remote-crypt
RUN true \

    # We install py3-docutils, which includes `rst2man-3`, but git-remote-crypt's setup.sh expects `rst2man`, lol
    && printf '#!/bin/sh\nrst2man-3 "$@"\n' > /usr/local/bin/rst2man && chmod 755 /usr/local/bin/rst2man \
    # && alias rst2man=rst2man-3 \
    && git clone https://github.com/spwhitton/git-remote-gcrypt /setup/git-remote-crypt \
    && cd /setup/git-remote-crypt \
    && ./install.sh \

    && true

# Running makewhatis should happen after all root installation commands / only right before running as my user
RUN makewhatis

# Enable passwordless sudo
# ONLY FOR DEVELOPMENT, since a root user in your container can probably escape to be a root user on your container host
RUN true \
    && echo "mrled ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/mrled \
    && chmod 0440 /etc/sudoers.d/mrled \
    && true

# Configure my user. Changes more often
RUN true \
    && addgroup -S mrled \
    && adduser -S -G mrled -s /bin/bash mrled \
    && mkdir /home/mrled/.bashrc.d \
    && true
COPY ["dhd", "/home/mrled/.dhd"]
COPY [".", "/home/mrled/psyops"]
COPY ["docker/bashrc.d.psyops", "/home/mrled/.bashrc.d/psyops"]
COPY ["docker/bashrc.d.volumes", "/home/mrled/.bashrc.d/volumes"]
COPY ["psyops-setup.sh", "/home/mrled/"]
COPY ["docker/psyops.secret.gpg.key.asc", "/home/mrled/.psyops.secret.gpg.key.asc"]
COPY ["docker/psyops.secret.gpg.pubkey.asc", "/home/mrled/.psyops.secret.gpg.pubkey.asc"]
COPY ["docker/psyops.secret.gpg.ownertrust.db.asc", "/home/mrled/.psyops.secret.gpg.ownertrust.db.asc"]
COPY ["docker/bashrc.d.psecrets", "/home/mrled/.bashrc.d/psecrets"]
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
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.vimrc . \
    && git config --global user.email "me@micahrl.com" && git config --global user.name "Micah R Ledbetter" \
    && mkdir $HOME/.ssh \
    && ln -s .secrets/dot.config $HOME/.config \
    && ln -s ../.secrets/dot.ssh/* $HOME/.ssh/ \
    && ln -s ../.dhd/hbase/known_hosts $HOME/.ssh/known_hosts \
    && true
# Handle the secrets repo
RUN true \
    # Pull down the (public) repo over unauthenticated HTTPS, then switch it to authenticated SSH but don't fetch so as to not require a baked-in SSH key
    # && git clone https://github.com/mrled/psyops-secrets .psyops.secrets && cd .psyops.secrets && git remote set-url --add origin git@github.com/mrled/psyops.secrets.git \

    # && git clone https://github.com/mrled/psyops-secrets $HOME/.secrets \
    # && cd $HOME/.secrets \
    # && git remote add gcrypt gcrypt::git@github.com:mrled/psyops-secrets.git \
    # && git config gcrypt.gpg-args "--use-agent --passphrase-file $HOME/.gpg.passphrase --batch --no-tty" \

    && git clone --origin encrypted --no-checkout https://github.com/mrled/psyops-secrets $HOME/.secrets \

    && true

ENTRYPOINT "/bin/bash"
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
