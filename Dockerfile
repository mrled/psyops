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
        man man-pages mdocml-apropos \
        # provides tput
        ncurses \
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
    && apk add g++ libcaca libcaca-dev make \
    && wget http://caca.zoy.org/raw-attachment/wiki/toilet/toilet-0.3.tar.gz \
    && tar zxf toilet-0.3.tar.gz \
    && cd toilet-0.3 \
    && ./configure \
    && make \
    && make install \
    # you have to leave libcaca, but it's only 4mb
    # && apk del g++ libcaca libcaca-dev make \
    && apk del g++ libcaca-dev make \
    && true

COPY ["getdoctl.py", "/setup/"]
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
COPY ["opt.bin.ppsyops", "/home/mrled/opt/bin/ppsyops"]
COPY ["bashrc.d.psyops", "/home/mrled/.bashrc.d/psyops"]
COPY ["psyops-setup.sh", "/home/mrled/"]
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

    && cd $HOME  \
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.vimrc . \
    && mkdir .ssh \
    && ln -s ../.dhd/hbase/known_hosts .ssh/known_hosts \

    && echo "mkdir -p ../../psyche/dot.config && ln -sf ../../psyche/dot.config /home/mrled/.config" > $HOME/.bashrc.d/volumes \

    && true

ENTRYPOINT "/bin/bash"
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
