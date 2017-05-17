FROM alpine:latest
LABEL maintainer "me@micahrl.com"

COPY ["./getdoctl.py", "/setup/"]

RUN true \

    && apk update \
    && apk add \
        bash bash-doc \
        ca-certificates ca-certificates-doc \
        emacs-nox emacs-doc \
        git git-doc \
        man man-pages mdocml-apropos \
        python3 python3-doc \
        sudo sudo-doc \
    && makewhatis \
    && update-ca-certificates \

    && python3 -m ensurepip && python3 -m pip install --upgrade pip && python3 -m pip install \
        gandi.cli \

    && addgroup -S mrled \
    && adduser -S -G mrled -s /bin/bash mrled \

    && true

RUN true \

    && python3 /setup/getdoctl.py \
    && cd /setup \
    && tar -zx -f doctl*.tar.gz \
    && sha256sum -c doctl*.sha256 \
    && install -D -o root -g root -m 755 /setup/doctl /usr/local/bin \

    && chown -R mrled:mrled /setup \

    && true

USER mrled

RUN true \

    && cd $HOME  \
    && git clone https://github.com/mrled/dhd .dhd \
    && ln -sf .dhd/hbase/.bashrc .dhd/hbase/.emacs .dhd/hbase/.inputrc .dhd/hbase/.profile .dhd/hbase/.screenrc .dhd/hbase/.vimrc . \
    && mkdir .ssh \
    && ln -s ../.dhd/hbase/known_hosts .ssh/known_hosts \

    && git clone https://github.com/mrled/psyops \

    && true

ENTRYPOINT "/bin/bash"
# NOTE: run with 'docker run -it <imagename>'
# You must run with -it so that it runs interactively and with a terminal assigned
