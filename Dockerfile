FROM alpine:3.6
LABEL maintainer "me@micahrl.com"

ARG psysetup=/psysetup
ARG username=psyops
ARG homedir=/home/psyops
ARG psyvol=/psyops
ARG gitname="Micah R Ledbetter"
ARG gitemail="me@micahrl.com"
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
        # For non-busybox ping. Busybox ping requires root privs, or setting net.ipv4.ping_group_range on the Docker *host*,
        # which is problematic on Windows/macOS which both use a Linux VM that is difficult to directly configure.
        iputils \
    && makewhatis \
    && update-ca-certificates --fresh \

    && python3 -m ensurepip && python3 -m pip install --upgrade pip && python3 -m pip install \
        gandi.cli \
        awscli \

    && install -d -o root -g root -m 755 /usr/local/bin \
    && install -d -o root -g root -m 755 "$psysetup" \

    && true

# Copy files for system-level configuration & run setup that relies on them
COPY ["docker/psysetup", "$psysetup"]
RUN true \

    # Install toilet, which is very important
    # Moved away from downloading a release tarbatll b/c the toilet server gets mad if you hit it too hard
    && apk add g++ libcaca libcaca-dev make automake autoconf \
    && cd "$psysetup/toilet" \
    && ./bootstrap \
    && ./configure \
    && make \
    && make install \
    # you have to leave libcaca itself, but it's only 4mb; the rest can go away
    && apk del g++ libcaca-dev make automake autoconf \

    # Install git-remote-crypt
    # We install py3-docutils, which includes `rst2man-3`, but git-remote-crypt's setup.sh expects `rst2man`, lol
    && printf '#!/bin/sh\nrst2man-3 "$@"\n' > /usr/local/bin/rst2man && chmod 755 /usr/local/bin/rst2man \
    && cd "$psysetup/git-remote-gcrypt" \
    && ./install.sh \

    # Install doctl, the Digital Ocean cli tool
    # this next line is some bullshit; copied from https://github.com/digitalocean/doctl/blob/master/Dockerfile
    && mkdir /lib64 && ln -s /lib/libc.musl-x86_64.so.1 /lib64/ld-linux-x86-64.so.2 \
    && "$psysetup/doctl/getdoctl" --outdir "$psysetup/doctl" \
    && cd "$psysetup/doctl" \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -o root -g root -m 755 "$psysetup/doctl/doctl" /usr/local/bin \

    # Running makewhatis should happen after all root installation commands / only right before running as my user
    && makewhatis \

    # Configure my user
    && addgroup -S "$username" \
    && adduser -S -G "$username" -s /bin/bash "$username" \

    && true

# Enable passwordless sudo
# ONLY FOR DEVELOPMENT, since a root user in your container can probably escape to be a root user on your container host
RUN if test "$enablesudo"; then  "$username ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/$username" && chmod 0440 "/etc/sudoers.d/$username"; fi

# Configure my user. Changes more often

COPY ["docker/home/", "$homedir/"]
COPY ["docker/psybin/*", "/usr/local/bin/"]

# Run this after ALL files have been placed into /usr/local/bin
# Fucking Docker uses the host's umask
# Apparently it's doing this not for the user running the docker command, but for the daemon(?)
# And so there's no easy way to even set it in some sort of wrapper script?
RUN chmod a+rX /usr/local/bin/*

RUN true \
    && mkdir "$psyvol" \
    && chown -R "$username:$username" "$homedir" "$psyvol" "$psysetup" \
    && true

# Changes (like permission changes) made to a VOLUME after it has been declared wil be *discarded*
# Contents of the volume are overwritten when it's bind-mounted
# So make permission changes before declaring, and put any file changes into scripts that run after the Docker image has been created
VOLUME $psyvol

USER $username
WORKDIR $homedir

# Run commands (as my user). Changes more often
RUN true \
    # NOTE: We clone from an encrypted git repo (which happens to be a submodule of the
    # psyops repo) at $psysetup/psyops-secrets
    # So when we push to it, it updates the encrypted submodule checked out on the host
    # Of course, the changes are not pushed to GitHub until we do so (probably from the host)
    && ln -sf "$psyvol/submod/dhd" "$HOME/.dhd" \
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.vimrc "$HOME" \
    # && ln -sf ../.dhd/hbase/known_hosts "$HOME/.ssh/known_hosts" \
    && git config --global user.email "$gitemail" && git config --global user.name "$gitname" \

    && true

CMD /bin/bash -i
ENTRYPOINT $HOME/.entrypoint.sh
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
