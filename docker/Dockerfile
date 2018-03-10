FROM alpine:3.6
LABEL maintainer "me@micahrl.com"

#### Development notes
#
# 1.    Multi-line RUN statements *cannot* have blank lines in them, but *can* have empty comments

ARG username=psyops
ARG homedir=/home/$username

# Location where we will mount the psyops repo as a volume. Note that even
# though this is an environment variable, it's not changeable at runtime
ENV PSYOPS_VOLUME="/psyops"
# Location to store decrypted secrets, expected to be mounted on tmpfs
ENV PSYOPS_SECRETS_PATH="/secrets"
# Encrypted private GPG key path to import
ENV PSYOPS_GPG_IMPORT_SECRET_KEY="$homedir/.gnupg/psyops.secret.gpg.key.asc"
# Unencrypted public GPG key path to import
ENV PSYOPS_GPG_IMPORT_PUBLIC_KEY="$homedir/.gnupg/psyops.secret.gpg.pubkey.asc"
# Unencrypted GPG ownertrust database to import
ENV PSYOPS_GPG_IMPORT_OWNERTRUST_DB="$homedir/.gnupg/psyops.secret.gpg.ownertrust.db.asc"
# Secret GPG key ID
ENV PSYOPS_GPG_SECRET_KEY_ID="3426CF80"
# Public GPG key ID
ENV PSYOPS_GPG_PUBLIC_KEY_ID="664C82AD"
# Location to store (plaintext!) GPG passphrase
ENV PSYOPS_GPG_PLAINTEXT_PASSFILE="$PSYOPS_SECRETS_PATH/gpg-passphrase"
# Encrypted private SSH key path
ENV PSYOPS_SSH_ENCRYPTED_PRIVATE_KEY_PATH="$homedir/.ssh/id_ed25519.gpg"
# Location to decrypt private SSH key
ENV PSYOPS_SSH_DECRYPTED_PRIVATE_KEY_PATH="$PSYOPS_SECRETS_PATH/id_ed25519"
# Unencrypted public SSH key path
ENV PSYOPS_SSH_PUBLIC_KEY_PATH="$homedir/.ssh/id_ed25519.pub"
# Location to decrypt secrets repo
ENV PSYOPS_SECRETS_REPO_CHECKOUT_PATH="$PSYOPS_SECRETS_PATH/psyops-secrets"
# Branch name for encrypted commits. Must be name of both the local branch
# we'll check out AND the remote branch that is encrypted before pushing
ENV PSYOPS_SECRETS_REPO_BRANCH="master"
# Name to use for the gcrypt remote
ENV PSYOPS_SECRETS_REPO_REMOTE_NAME="origin"
# URI for the gcrypt remote
# ENV PSYOPS_SECRETS_REPO_REMOTE_URI="file://$PSYOPS_VOLUME/submod/psyops-secrets"
ENV PSYOPS_SECRETS_REPO_REMOTE_URI="git@github.com:mrled/psyops-secrets.git"
# The psyops-secrets repo has a script to symlink its config files into the
# homedir... if it exists, the repo was successfully decrypted
ENV PSYOPS_SECRETS_POST_DECRYPT_SCRIPT_PATH="symlink.sh"
# Allow setting the timezone at runtime
ENV PSYOPS_TIMEZONE="US/Central"


# Pre-copy root OS configuration phase
RUN true \
    #
    # Fix frustrating errors like
    #   ERROR: http://dl-cdn.alpinelinux.org/alpine/v3.6/main: temporary error (try again later)
    # See also: https://github.com/gliderlabs/docker-alpine/issues/279#issuecomment-300859312
    && echo http://dl-2.alpinelinux.org/alpine/v3.6/main > /etc/apk/repositories \
    && echo http://dl-2.alpinelinux.org/alpine/v3.6/community >> /etc/apk/repositories \
    && apk update \
    #
    && apk add \
        bash bash-doc \
        ca-certificates ca-certificates-doc \
        # I got tired of fucking with busybox's wget
        curl curl-doc \
        docker docker-doc docker-bash-completion \
        emacs-nox emacs-doc \
        file file-doc \
        git git-doc \
        gnupg1 gnupg1-doc \
        # for awscli, installed below from pip, to get its documentation
        groff groff-doc \
        # For non busybox ping; busybox ping requires root privs, or setting net.ipv4.ping_group_range on the Docker *host*,
        # which is problematic on Windows/macOS which both use a Linux VM that is difficult to directly configure.
        iputils \
        # By default, busybox's less is /usr/bin/less; adding the less package makes the real less /usr/bin/less instead
        less less-doc \
        man man-pages mdocml-apropos \
        # provides tput
        ncurses \
        openssh-client openssh-doc \
        openssl openssl-doc \
        python3 python3-doc \
        # For usermod. Native busybox has 'adduser' for more standard 'useradd', but there is no 'usermod' equivalent
        shadow shadow-doc \
        # Useful to have the 'ipsec' command when working with Algo
        strongswan strongswan-doc \
        sudo sudo-doc \
        tmux tmux-doc \
        tzdata tzdata-doc \
    #
    && update-ca-certificates --fresh \
    #
    # Configure Python stuff, including for later building C modules
    # (Useful to keep on the image permanently, so we can compile C modules in virtualenvs)
    # These prereqs include support for PyNACL
    && python3 -m ensurepip \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install virtualenv \
    && apk add \
        # general
        gcc \
        make \
        musl-dev \
        python3-dev \
        # for (at least) PyNACL
        libffi-dev \
        openssl-dev \
    #
    # Get AWS and Gandi command line tools
    && python3 -m pip install \
        awscli \
        gandi.cli \
    #
    && install -d -o root -g root -m 755 /usr/local/bin \
    #
    && true

## Third party software that doesn't require the /setup dir

RUN true \
    # Install Azure CLI
    # Azure requires this python3->python link because it is... bad
    && ln -s ../../bin/python3 /usr/local/bin/python \
    && python3 -m pip install azure azure-cli \
    && true

RUN true \
    # Install Ansible
    && apk add \
        ansible ansible-doc \
    # Required for Ansible scripts and/or the EC2 inventory script
    && python -m pip install \
        ansible \
        boto \
        boto3 \
    && true

ARG psysetup=/setup

# Copy files for system-level configuration & run setup that relies on them
COPY ["setup", "$psysetup"]

RUN true \
    # Install toilet, which is very important
    # Moved away from downloading a release tarbatll b/c the toilet server gets mad if you hit it too hard
    # you have to leave libcaca itself, but it's only 4mb; the rest can go away
    && apk add libcaca \
    && apk add --virtual=BUILDTOILET g++ libcaca-dev automake autoconf \
    && cd "$psysetup/toilet" \
    && ./bootstrap \
    && ./configure \
    && make \
    && make install \
    && apk del --purge BUILDTOILET \
    && true

RUN true \
    # Install git-remote-crypt
    && apk add \
        # for rst2man
        py3-docutils \
    # We install py3-docutils, which includes `rst2man-3`, but git-remote-crypt's setup.sh expects `rst2man`, lol
    && printf '#!/bin/sh\nrst2man-3 "$@"\n' > /usr/local/bin/rst2man && chmod 755 /usr/local/bin/rst2man \
    && cd "$psysetup/git-remote-gcrypt" \
    && ./install.sh 2>&1 \
    && true

RUN true \
    # Install doctl, the Digital Ocean cli tool
    # this next line is some bullshit; copied from https://github.com/digitalocean/doctl/blob/master/Dockerfile
    && mkdir /lib64 && ln -s ../lib/libc.musl-x86_64.so.1 /lib64/ld-linux-x86-64.so.2 \
    && "$psysetup/bin/get-gh-release" --outdir "$psysetup" digitalocean/doctl '^doctl.*linux.*amd64.*tar.gz$' \
    && "$psysetup/bin/get-gh-release" --outdir "$psysetup" digitalocean/doctl '^doctl.*linux.*amd64.*sha256$' \
    && cd "$psysetup" \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -o root -g root -m 755 "$psysetup/doctl" /usr/local/bin \
    && true

RUN true \
    # Install pt, the_platinum_searcher
    && "$psysetup/bin/get-gh-release" --outdir "$psysetup" monochromegane/the_platinum_searcher '^pt_linux_amd64.*.tar.gz$' \
    && cd "$psysetup" \
    && tar -zx -f pt_linux_amd64*.tar.gz \
    && install -o root -g root -m 755 "$psysetup/pt_linux_amd64/pt" /usr/local/bin \
    && true

RUN true \
    # Final steps
    #
    # Running makewhatis should happen after all root installation commands / only right before running as my user
    && makewhatis \
    #
    # Allow my user to set /etc/localtime
    && addgroup -S "timekeeper" \
    && chgrp timekeeper /etc/localtime \
    && chmod 0664 /etc/localtime \
    #
    # Configure my user
    && addgroup -S "$username" \
    && adduser -S -G "$username" -s /bin/bash "$username" \
    && usermod --append --groups timekeeper "$username" \
    #
    && true

# Passwordless sudo. DEVELOPMENT ONLY PLEASE.
ARG enablesudo=
RUN if test "$enablesudo"; then true \
        && echo "ENABLING PASSWORDLESS SUDO" >&2 \
        && echo "sudo should only be enabled in development, since root privs in your container can probably be leveraged to root privs on your host" >&2 \
        && echo "$username ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/$username" \
        && chmod 0440 "/etc/sudoers.d/$username" \
    ; fi

# Configure my user. Changes more often

COPY ["home/", "$homedir/"]
COPY ["usrlocalbin/*", "/usr/local/bin/"]
# So we can use it in scripts at login time, even if $PSYOPS_VOLUME did not mount properly
#COPY ["submod/dhd/opt/bin/ansi", "/usr/local/bin/"]

# Run this after ALL files have been placed into /usr/local/bin
# Fucking Docker uses the host's umask
# Apparently it's doing this not for the user running the docker command, but for the daemon(?)
# And so there's no easy way to even set it in some sort of wrapper script?
RUN chmod a+rX /usr/local/bin/*

RUN true \
    && mkdir "$PSYOPS_VOLUME" \
    && chown -R "$username:$username" "$homedir" "$PSYOPS_VOLUME" "$psysetup" \
    && true

# Changes (like permission changes) made to a VOLUME after it has been declared wil be *discarded*
# Contents of the volume are overwritten when it's bind-mounted
# So make permission changes before declaring, and put any file changes into scripts that run after the Docker image has been created
VOLUME $PSYOPS_VOLUME

USER $username
WORKDIR $homedir

ARG gitname="Micah R Ledbetter"
ARG gitemail="me@micahrl.com"

# Run commands (as my user). Changes more often
RUN true \
    # NOTE: We clone from an encrypted git repo (which happens to be a submodule of the
    # psyops repo) at $psysetup/psyops-secrets
    # So when we push to it, it updates the encrypted submodule checked out on the host
    # Of course, the changes are not pushed to GitHub until we do so (probably from the host)
    && ln -sf "$PSYOPS_VOLUME/submod/dhd" "$HOME/.dhd" \
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.tmux.conf .dhd/hbase/.vimrc "$HOME" \
    && ln -sf "$PSYOPS_VOLUME/submod/dhd/hbase/known_hosts" "$HOME/.ssh/known_hosts" \
    && ln -sf "$PSYOPS_SSH_DECRYPTED_PRIVATE_KEY_PATH" "$HOME/.ssh/" \
    && git config --global user.email "$gitemail" && git config --global user.name "$gitname" \
    && true

CMD /bin/bash -i
ENTRYPOINT $HOME/.entrypoint.sh
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
