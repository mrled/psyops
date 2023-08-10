# Dockerfile for running Litestream + Isso on Fly.io

FROM litestream/litestream AS litestream
FROM ghcr.io/isso-comments/isso:latest

# Now we can copy the litestream binary from the official litestream container
# So easy it feels like cheating
COPY --from=litestream /usr/local/bin/litestream /usr/local/bin/litestream

COPY isso.cfg.template /etc/isso.cfg.template
COPY litestream.yml /etc/litestream.yml
COPY start.sh /usr/local/bin/start.sh

RUN true \
    && adduser -s /bin/sh -S isso \
    && chmod 755 /usr/local/bin/litestream \
    && chmod 755 /usr/local/bin/start.sh \
    && chown isso /etc/litestream.yml \
    && touch /etc/isso.cfg \
    && chown isso /etc/isso.cfg \
    && true

USER isso

ENTRYPOINT []
CMD ["/usr/local/bin/start.sh"]
