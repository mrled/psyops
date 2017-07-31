FROM alpine:3.6
LABEL maintainer "me@micahrl.com"

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

# Pre-copy root OS configuration phase
RUN true \

    && apk update \
    && apk add \
        bash bash-doc \
        ca-certificates ca-certificates-doc \
        # I got tired of fucking with busybox's wget
        curl curl-doc \
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
        # for rst2man, used by git-remote-crypt
        py3-docutils \
        python3 python3-doc \
        sudo sudo-doc \
    && makewhatis \
    && update-ca-certificates --fresh \

    && python3 -m ensurepip && python3 -m pip install --upgrade pip && python3 -m pip install \
        gandi.cli \
        awscli \

    && install -d -o root -g root -m 755 /usr/local/bin \

    && true

ARG psysetup=/setup

# Copy files for system-level configuration & run setup that relies on them
COPY ["docker/setup", "$psysetup"]

RUN true \
    # Install toilet, which is very important
    # Moved away from downloading a release tarbatll b/c the toilet server gets mad if you hit it too hard
    # you have to leave libcaca itself, but it's only 4mb; the rest can go away
    && apk add libcaca \
    && apk add --virtual=BUILDTOILET g++ libcaca-dev make automake autoconf \
    && cd "$psysetup/toilet" \
    && ./bootstrap \
    && ./configure \
    && make \
    && make install \
    && apk del --purge BUILDTOILET \
    && true

RUN true \
    # Install git-remote-crypt
    # We install py3-docutils, which includes `rst2man-3`, but git-remote-crypt's setup.sh expects `rst2man`, lol
    && printf '#!/bin/sh\nrst2man-3 "$@"\n' > /usr/local/bin/rst2man && chmod 755 /usr/local/bin/rst2man \
    && cd "$psysetup/git-remote-gcrypt" \
    && ./install.sh \
    && true

RUN true \
    # Install doctl, the Digital Ocean cli tool
    # this next line is some bullshit; copied from https://github.com/digitalocean/doctl/blob/master/Dockerfile
    && mkdir /lib64 && ln -s /lib/libc.musl-x86_64.so.1 /lib64/ld-linux-x86-64.so.2 \
    && "$psysetup/doctl/getdoctl" --outdir "$psysetup/doctl" \
    && cd "$psysetup/doctl" \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -o root -g root -m 755 "$psysetup/doctl/doctl" /usr/local/bin \
    && true

RUN true \
    # Install Azure CLI
    && apk add --virtual=BUILDAZURECLI gcc libffi-dev musl-dev openssl-dev python3-dev make \
    # Azure requires this because it is... bad
    && ln -s ../../bin/python3 /usr/local/bin/python \
    && python3 -m pip install azure-cli \
    && apk del --purge BUILDAZURECLI \
    && true

RUN true \
    # Final steps

    # Running makewhatis should happen after all root installation commands / only right before running as my user
    && makewhatis \

    # Configure my user
    && addgroup -S "$username" \
    && adduser -S -G "$username" -s /bin/bash "$username" \

    && true

# Enable passwordless sudo
# ONLY FOR DEVELOPMENT, since a root user in your container can probably escape to be a root user on your container host
ARG enablesudo=
RUN if test "$enablesudo"; then echo "$username ALL=(ALL) NOPASSWD: ALL" > "/etc/sudoers.d/$username" && chmod 0440 "/etc/sudoers.d/$username"; fi

# Configure my user. Changes more often

COPY ["docker/home/", "$homedir/"]
COPY ["docker/usrlocalbin/*", "/usr/local/bin/"]
# So we can use it in scripts at login time, even if $PSYOPS_VOLUME did not mount properly
COPY ["submod/dhd/opt/bin/ansi", "/usr/local/bin/"]

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
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.vimrc "$HOME" \
    && ln -sf "$PSYOPS_VOLUME/submod/dhd/hbase/known_hosts" "$HOME/.ssh/known_hosts" \
    && ln -sf "$PSYOPS_SSH_DECRYPTED_PRIVATE_KEY_PATH" "$HOME/.ssh/" \
    && git config --global user.email "$gitemail" && git config --global user.name "$gitname" \

    && true

CMD /bin/bash -i
ENTRYPOINT $HOME/.entrypoint.sh
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
