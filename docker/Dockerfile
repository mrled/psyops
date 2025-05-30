FROM alpine:3.19
LABEL maintainer "me@micahrl.com"

#### Development notes
#
# 1.    Multi-line RUN statements *cannot* have blank lines in them, but *can* have empty comments

ARG username=psyops
ARG groupname=psyops
ARG homedir=/home/$username
ARG PSYOPS_UID=1000
ARG PSYOPS_GID=1000
# The psyops user's password so we can sudo (generate with busybox's mkpasswd)
ARG PSYOPS_USER_PASSWORD='$6$uVLEWQVe2v.e9dzz$QhxJ6fdTcAqaYeuXV6vxNVpWLbjrhnnaimpvEpICD3zcmGpU5XCtt39Adsc1uixapmKekWqFetEgbzOkfmMMU.'

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
# Email address field for our private key
ENV PSYOPS_GPG_EMAIL="conspirator@PSYOPS"

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

# Location to decrypt secrets
ENV PSYOPS_SECRETS_DECRYPTED_PATH="$PSYOPS_SECRETS_PATH/psyops-secrets"
# The encrypted secrets file contains a script to symlink its config files into
# the homedir... if it exists, the repo was successfully decrypted
ENV PSYOPS_SECRETS_POST_DECRYPT_SCRIPT_PATH="/usr/local/bin/psecrets-postunlock"
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
    #
    # It's nice to have access to the various edge repos
    # Nothing will install from them implicitly, you have to do 'apk add whatever@edgemain'
    # First install the edge keys
    && apk add -X https://dl-cdn.alpinelinux.org/alpine/edge/main --allow-untrusted --upgrade alpine-keys \
    ## Then add the edge repos
    && echo '@edgemain       http://dl-cdn.alpinelinux.org/alpine/edge/main' >> /etc/apk/repositories \
    && echo '@edgecommunity  http://dl-cdn.alpinelinux.org/alpine/edge/community' >> /etc/apk/repositories \
    && echo '@edgetesting    http://dl-cdn.alpinelinux.org/alpine/edge/testing' >> /etc/apk/repositories \
    #
    && apk update \
    #
    && apk add \
        abuild abuild-doc \
        age age-doc \
        # For calculating a bcrypt password with htpasswd
        apache2-utils \
        alpine-sdk \
        ansible ansible-core ansible-core-doc \
        apk-tools-doc \
        aws-cli \
        bash bash-doc \
        bash-completion \
        black \
        # For dig
        bind-tools \
        busybox-doc \
        ca-certificates ca-certificates-doc \
        # I got tired of fucking with busybox's wget
        curl curl-doc \
        docker docker-doc docker-bash-completion docker-zsh-completion \
        docker-compose \
        emacs-nox emacs-doc \
        file file-doc \
        # Used for kubenrasty
        #flux@edgetesting flux-bash-completion@edgetesting flux-zsh-completion@edgetesting \
        gcc \
        git git-doc \
        gopass gopass-doc gopass-bash-completion gopass-zsh-completion \
        # Installs GPG 2.x, not 1.x (gnupg1 gnupg1-doc)
        # Sadly, Alpine doesn't offer a way to install them side by side
        gnupg gnupg-doc \
        # Required for awscli to get its documentation
        groff groff-doc \
        # For non busybox ping; busybox ping requires root privs, or setting net.ipv4.ping_group_range on the Docker *host*,
        # which is problematic on Windows/macOS which both use a Linux VM that is difficult to directly configure.
        iputils \
        jq jq-doc \
        # For matrix-docker-ansible-deploy
        just just-doc@edgecommunity just-zsh-completion \
        kubectl@edgecommunity kubectl-bash-completion@edgecommunity kubectl-zsh-completion@edgecommunity \
        # By default, busybox's less is /usr/bin/less; adding the less package makes the real less /usr/bin/less instead
        less less-doc \
        # for (at least) PyNACL
        libffi-dev \
        linux-headers \
        make \
        man-db man-db-doc man-pages \
        minisign minisign-doc \
        musl-dev \
        # provides tput
        ncurses \
        nebula \
        neovim neovim-doc \
        openssh-client openssh-doc \
        openssl openssl-dev \
        parallel parallel-doc \
        pwgen pwgen-doc \
        python3 python3-dev python3-doc \
        py3-bcrypt \
        py3-build \
        py3-boto3 \
        # The cryptography package relies on rust to build;
        # it is much easier to get it from the apk repo than build it with pip.
        py3-cryptography \
        py3-dnspython \
        # Apparently required to install my whl into a directory for apk
        # https://wiki.alpinelinux.org/wiki/APKBUILD_examples:Python
        py3-installer \
        py3-mypy \
        py3-netaddr \
        py3-passlib \
        py3-pip py3-pip-doc \
        py3-requests \
        py3-setuptools \
        py3-tz \
        py3-wheel \
        py3-yaml \
        ripgrep ripgrep-doc ripgrep-bash-completion ripgrep-zsh-completion \
        rsync rsync-doc \
        ruby \
        s3cmd \
        shadow shadow-doc \
        sops@edgecommunity \
        sqlite sqlite-doc \
        # Required for Ansible to use SSH password auth instead of public keys
        sshpass sshpass-doc \
        strace strace-doc \
        # Useful to have the 'ipsec' command when working with Algo
        strongswan strongswan-doc \
        sudo sudo-doc \
        tmux tmux-doc \
        tzdata tzdata-doc \
        wireguard-tools wireguard-tools-doc wireguard-tools-wg \
        zip zip-doc \
        zsh zsh-doc zsh-completions \
    #
    && update-ca-certificates --fresh \
    #
    # Get some Python packages that are not in apk repos
    # New versions of Alpine / Python prohibit global pip installs,
    # so we make a venv for them instead and add it to default $PATH
    && python3 -m venv /usr/local/systemvenv \
    && /usr/local/systemvenv/bin/pip install \
        gandi.cli \
        invoke \
    && echo 'case "$PATH" in *"/usr/local/systemvenv/bin"*);; *) export PATH="/usr/local/systemvenv/bin:$PATH";; esac' > /etc/profile.d/systemvenv.sh \
    && chmod 644 /etc/profile.d/systemvenv.sh \
    #
    && true

ARG psysetup=/setup

# Copy files for system-level configuration & run setup that relies on them
COPY ["setup", "$psysetup"]

## Configure psyops-banner prereqs
# Absolutely vital to our mission
RUN true \
    && apk add \
        figlet figlet-doc \
    && gem install \
        lolcat \
    && cp "$psysetup/figlet-fonts/"*.[ft]lf /usr/share/figlet/fonts \
    && chmod 644 /usr/share/figlet/fonts/* \
    && true

# Hashicorp doesn't recommend automatically getting the latest version but we are doing it anyway
# <https://github.com/hashicorp/terraform/issues/9803#issuecomment-257903082>
RUN true \
    && export tf_latest="$(curl -s https://checkpoint-api.hashicorp.com/v1/check/terraform | jq -r -M '.current_version')" \
    && echo "Detected latest version of terraform as: $tf_latest" \
    && export tf_url="https://releases.hashicorp.com/terraform/${tf_latest}/terraform_${tf_latest}_linux_amd64.zip" \
    && echo "Built URL for downloading latest version of terraform: $tf_url" \
    && curl -o "$psysetup/terraform.zip" "$tf_url" \
    && cd "$psysetup" \
    && unzip "terraform.zip" \
    && install -o root -g root -m 755 "$psysetup/terraform" /usr/local/bin \
    # This doesn't work
    # Linked against GNU libc
    # && export PROVIDER={all,google,aws,kubernetes} \
    # && export tfer_provider=all \
    # && export tfer_latest="$(curl -s https://api.github.com/repos/GoogleCloudPlatform/terraformer/releases/latest | jq -r -M '.tag_name')" \
    # && export tfer_url="https://github.com/GoogleCloudPlatform/terraformer/releases/download/${tfer_latest}/terraformer-${tfer_provider}-linux-amd64" \
    # && curl -o "$psysetup/terraformer" "$tfer_url" \
    # && install -o root -g root -m 755 "$psysetup/terraformer" /usr/local/bin \
    && true

# RUN true \
#     && "$psysetup/bin/get-gh-release" --outdir "$psysetup" benbjohnson/litestream '^litestream.*linux-amd64-static.tar.gz$' \
#     && cd "$psysetup" \
#     && tar -zx -f litestream*.tar.gz \
#     && install -o root -g root -m 755 "$psysetup"/litestream /usr/local/bin \
#     && true

RUN true \
    && set -x \
    # Final steps
    #
    # Allow my user to set /etc/localtime
    && addgroup -S "timekeeper" \
    && touch /etc/localtime \
    && chgrp timekeeper /etc/localtime \
    && chmod 0664 /etc/localtime \
    #
    # Configure my user
    # Forcibly install a group with the correct GID, even if there is already a group with that GID
    # && addgroup -g "$PSYOPS_GID" "$groupname" \
    && echo "${groupname}:x:${PSYOPS_GID}:" >> /etc/group \
    && adduser -D -G "$groupname" -u "$PSYOPS_UID" -s /bin/zsh "$username" \
    && usermod --password "$PSYOPS_USER_PASSWORD" "$username" \
    && echo "$username ALL=(ALL) ALL" > "/etc/sudoers.d/$username" \
    && chmod 0440 "/etc/sudoers.d/$username" \
    && adduser "$username" abuild \
    && adduser "$username" timekeeper \
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

COPY --chmod=644 "psyops@micahrl.com-62ca1973.rsa.pub" "/etc/apk/keys/psyops@micahrl.com-62ca1973.rsa.pub"

USER $username
WORKDIR $homedir

ARG gitname="Micah R Ledbetter"
ARG gitemail="me@micahrl.com"

# Install software as my user
# This stuff isn't designed for system-wide installs anyway
RUN true \
    && curl -L https://fly.io/install.sh | sh \
    && true

# Run commands (as my user). Changes more often
RUN true \
    && echo "will cite" | parallel --citation >/dev/null 2>&1 || true \
    && ln -sf "$PSYOPS_VOLUME/submod/dhd" "$HOME/.dhd" \
    && setup-psyops-dhd \
    && ln -sf "$PSYOPS_SSH_ED25519_DECRYPTED_PRIVATE_KEY_PATH" "$HOME/.ssh/" \
    && ln -sf "$PSYOPS_SSH_RSA_DECRYPTED_PRIVATE_KEY_PATH" "$HOME/.ssh/" \
    && git config --global user.email "$gitemail" \
    && git config --global user.name "$gitname" \
    && git config --global --add safe.directory "$PSYOPS_VOLUME" \
    # Useful when building on Windows hosts, which use open permissions by default
    && mkdir -p $HOME/.gnupg $HOME/.ssh \
    && chmod 700 $HOME/.gnupg $HOME/.ssh \
    && true

CMD /bin/zsh -i
ENTRYPOINT $HOME/.entrypoint.sh
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
