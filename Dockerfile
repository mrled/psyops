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
        gnupg gnupg-doc \
        man man-pages mdocml-apropos \
        # provides tput
        ncurses \
        openssh-client openssh-doc \
        openssl openssl-doc \
        python3 python3-doc \
        sudo sudo-doc \
    && makewhatis \
    && update-ca-certificates --fresh \

    && python3 -m ensurepip && python3 -m pip install --upgrade pip && python3 -m pip install \
        gandi.cli \

    && true

# Configure other packages. Might change more frequently

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

COPY ["docker/getdoctl.py", "/setup/"]
RUN true \

    && cd /setup \

    # this is some bullshit; copied from https://github.com/digitalocean/doctl/blob/master/Dockerfile
    && mkdir /lib64 && ln -s /lib/libc.musl-x86_64.so.1 /lib64/ld-linux-x86-64.so.2 \
    && python3 /setup/getdoctl.py \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -D -o root -g root -m 755 /setup/doctl /usr/local/bin \

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
COPY ["docker/psyops.secret.key.asc", "/home/mrled/.psyops.secret.key.asc"]
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
    # Pull down the (public) repo over unauthenticated HTTPS, then switch it to authenticated SSH but don't fetch so as to not require a baked-in SSH key
    && git clone https://github.com/mrled/psyops.secrets .psyops.secrets && cd .psyops.secrets && git remote set-url --add origin git@github.com/mrled/psyops.secrets.git \
    && true

ENTRYPOINT "/bin/bash"
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
