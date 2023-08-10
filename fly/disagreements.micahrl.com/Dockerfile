# Dockerfile for running Litestream + Isso on Fly.io

FROM litestream/litestream AS litestream
FROM umputun/remark42:latest

# Now we can copy the litestream binary from the official litestream container
# So easy it feels like cheating
COPY --from=litestream /usr/local/bin/litestream /usr/local/bin/litestream

COPY litestream.yml /etc/litestream.yml
COPY start.sh /usr/local/bin/start.sh

USER root
RUN true \
    && chmod 755 /usr/local/bin/litestream \
    && chmod 755 /usr/local/bin/start.sh \
    && chown app /etc/litestream.yml \
    && touch /etc/isso.cfg \
    && chown app /etc/isso.cfg \
    && true

USER app

ENTRYPOINT []
CMD ["/usr/local/bin/start.sh"]
