# Dockerfile for running Litestream + Wiki.js on Fly.io

FROM litestream/litestream AS litestream
FROM ghcr.io/requarks/wiki:2

# Now we can copy the litestream binary from the official litestream container
# So easy it feels like cheating
COPY --from=litestream /usr/local/bin/litestream /usr/local/bin/litestream

COPY litestream.yml /etc/litestream.yml
COPY start.sh /usr/local/bin/start.sh

# Do some configuration as root
USER root
RUN true \
    && chmod 755 /usr/local/bin/litestream \
    && chmod 755 /usr/local/bin/start.sh \
    && chown node /etc/litestream.yml \
    && touch /testfile \
    && true

USER node

ENTRYPOINT []
CMD ["/usr/local/bin/start.sh"]
