FROM alpine:latest
LABEL maintainer "me@micahrl.com"

RUN true \
    && apk add \
        transmission transmission-cli transmission-daemon transmission-doc \
    && adduser transmission transmission \
    && mkdir /watch && chmod 1777 /watch \
    && true

USER transmission
EXPOSE 9091 51413
VOLUME /config

#COPY entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT transmission-daemon \
    --foreground \
    --log-debug \
    --config-dir /config
