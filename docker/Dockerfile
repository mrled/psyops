FROM alpine:latest
LABEL maintainer "me@micahrl.com"

#### Development notes
#
# 1.    Multi-line RUN statements *cannot* have blank lines in them, but *can* have empty comments

ARG username=psyops
ARG groupname=psyops
ARG homedir=/home/$username
ENV PSYOPS_UID=1000
ENV PSYOPS_GID=1000

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

# Encrypted private SSH ED25519 key path
ENV PSYOPS_SSH_ED25519_ENCRYPTED_PRIVATE_KEY_PATH="$homedir/.ssh/id_ed25519.gpg"
# Location to decrypt private ED25519 SSH key
ENV PSYOPS_SSH_ED25519_DECRYPTED_PRIVATE_KEY_PATH="$PSYOPS_SECRETS_PATH/id_ed25519"
# Unencrypted public SSH ED25519 key path
ENV PSYOPS_SSH_ED25519_PUBLIC_KEY_PATH="$homedir/.ssh/id_ed25519.pub"

# Encrypted private SSH RSA key path
ENV PSYOPS_SSH_RSA_ENCRYPTED_PRIVATE_KEY_PATH="$homedir/.ssh/id_rsa.gpg"
# Location to decrypt private RSA SSH key
ENV PSYOPS_SSH_RSA_DECRYPTED_PRIVATE_KEY_PATH="$PSYOPS_SECRETS_PATH/id_rsa"
# Unencrypted public SSH RSA key path
ENV PSYOPS_SSH_RSA_PUBLIC_KEY_PATH="$homedir/.ssh/id_rsa.pub"

# Encrypted secrets path
ENV PSYOPS_SECRETS_ENCRYPTED_PATH="$PSYOPS_VOLUME/docker/psyops-secrets.tar.gz.gpg"
# Location to decrypt secrets
ENV PSYOPS_SECRETS_DECRYPTED_PATH="$PSYOPS_SECRETS_PATH/psyops-secrets"
# The encrypted secrets file contains a script to symlink its config files into
# the homedir... if it exists, the repo was successfully decrypted
ENV PSYOPS_SECRETS_POST_DECRYPT_SCRIPT_PATH="symlink.sh"
# Allow setting the timezone at runtime
ENV PSYOPS_TIMEZONE="US/Central"


# Pre-copy root OS configuration phase
RUN true \
    #
    # Fix frustrating errors like
    #   ERROR: http://dl-cdn.alpinelinux.org/alpine/v3.6/main: temporary error (try again later)
    # See also: https://github.com/gliderlabs/docker-alpine/issues/279#issuecomment-300859312
    #&& echo http://dl-2.alpinelinux.org/alpine/v3.6/main > /etc/apk/repositories \
    #&& echo http://dl-2.alpinelinux.org/alpine/v3.6/community >> /etc/apk/repositories \
    && apk update \
    #
    && apk add \
        bash bash-doc \
        # For dig
        bind-tools \
        ca-certificates ca-certificates-doc \
        # I got tired of fucking with busybox's wget
        curl curl-doc \
        docker docker-doc docker-bash-completion \
        emacs-nox emacs-doc \
        file file-doc \
        git git-doc \
        # Installs GPG 2.x, not 1.x (gnupg1 gnupg1-doc)
        # Sadly, Alpine doesn't offer a way to install them side by side
        gnupg gnupg-doc \
        # for awscli, installed below from pip, to get its documentation
        groff groff-doc \
        # For non busybox ping; busybox ping requires root privs, or setting net.ipv4.ping_group_range on the Docker *host*,
        # which is problematic on Windows/macOS which both use a Linux VM that is difficult to directly configure.
        iputils \
        jq jq-doc \
        # By default, busybox's less is /usr/bin/less; adding the less package makes the real less /usr/bin/less instead
        less less-doc \
        man man-pages mdocml-apropos \
        # provides tput
        ncurses \
        neovim neovim-doc \
        openssh-client openssh-doc \
        openssl openssl-doc \
        parallel parallel-doc \
        python3 python3-doc \
        # For usermod. Native busybox has 'adduser' for more standard 'useradd', but there is no 'usermod' equivalent
        shadow shadow-doc \
        strace strace-doc \
        # Useful to have the 'ipsec' command when working with Algo
        strongswan strongswan-doc \
        sudo sudo-doc \
        tmux tmux-doc \
        tzdata tzdata-doc \
        zip zip-doc \
    #
    && update-ca-certificates --fresh \
    #
    # Configure Python stuff, including for later building C modules
    # (Useful to keep on the image permanently, so we can compile C modules in virtualenvs)
    # These prereqs include support for PyNACL
    && python3 -m ensurepip \
    && python3 -m pip install --upgrade pip \
    && python3 -m pip install \
        pipenv \
        virtualenv \
    && apk add \
        # general
        gcc \
        linux-headers \
        make \
        musl-dev \
        python2-dev \
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
    # Make sure basic Python2 tooling is installed too, ugh
    && python2 -m ensurepip \
    && python2 -m pip install --upgrade \
        pip \
        virtualenv \
    #
    && install -d -o root -g root -m 755 /usr/local/bin \
    #
    && true

## Third party software that doesn't require the /setup dir

RUN true \
    # Install Ansible
    # Required for Ansible scripts and/or the EC2 inventory script
    && python3 -m pip install \
        ansible \
        boto \
        boto3 \
        dnspython \
        mitogen \
        netaddr \
    && apk add \
        # Required for Ansible to use SSH password auth instead of public keys
        sshpass sshpass-doc \
    && true

ARG psysetup=/setup

# Copy files for system-level configuration & run setup that relies on them
COPY ["setup", "$psysetup"]

RUN true \
    && "$psysetup/bin/get-gh-release" --outdir "$psysetup" BurntSushi/ripgrep '^ripgrep.*linux-musl.tar.gz$' \
    && cd "$psysetup" \
    && tar -zx -f ripgrep*.tar.gz \
    && install -o root -g root -m 755 "$psysetup"/ripgrep*linux-musl/rg /usr/local/bin \
    && true

RUN true \
    && set -x \
    # Final steps
    #
    # Running makewhatis should happen after all root installation commands / only right before running as my user
    && makewhatis \
    #
    # Allow my user to set /etc/localtime
    && addgroup -S "timekeeper" \
    && touch /etc/localtime \
    && chgrp timekeeper /etc/localtime \
    && chmod 0664 /etc/localtime \
    #
    # Configure my user
    && addgroup -g "$PSYOPS_GID" "$groupname" \
    && adduser -D -G "$groupname" -u "$PSYOPS_UID" -s /bin/bash "$username" \
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
    && chown -R "$username:$groupname" "$homedir" "$PSYOPS_VOLUME" "$psysetup" \
    && true

# Changes (like permission changes) made to a VOLUME after it has been declared wil be *discarded*
# Contents of the volume are overwritten when it's bind-mounted
# So make permission changes before declaring, and put any file changes into scripts that run after the Docker image has been created
VOLUME $PSYOPS_VOLUME

RUN chown "$username:$groupname" "$PSYOPS_VOLUME"

USER $username
WORKDIR $homedir

ARG gitname="Micah R Ledbetter"
ARG gitemail="me@micahrl.com"

# Run commands (as my user). Changes more often
RUN true \
    && echo "will cite" | parallel --citation \
    && ln -sf "$PSYOPS_VOLUME/submod/dhd" "$HOME/.dhd" \
    && setup-psyops-dhd \
    && ln -sf "$PSYOPS_SSH_ED25519_DECRYPTED_PRIVATE_KEY_PATH" "$HOME/.ssh/" \
    && ln -sf "$PSYOPS_SSH_RSA_DECRYPTED_PRIVATE_KEY_PATH" "$HOME/.ssh/" \
    && ln -s "$PSYOPS_VOLUME/.home.psyops.local" "$HOME/.local" \
    && git config --global user.email "$gitemail" && git config --global user.name "$gitname" \
    # Useful when building on Windows hosts, which use open permissions by default
    && mkdir -p $HOME/.gnupg $HOME/.ssh \
    && chmod 700 $HOME/.gnupg $HOME/.ssh \
    && true

CMD /bin/bash -i
ENTRYPOINT $HOME/.entrypoint.sh
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
