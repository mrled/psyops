# We make this container so that we can run litestream in it
# On Fly, we have to run everything in a single container
# <https://tip.litestream.io/guides/docker/#running-in-the-same-container>

# First, we got an approximation of the wiki.js Dockerfile
# See the readme for how I got this.
#
# ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# ENV NODE_VERSION=16.15.0
# ENV YARN_VERSION=1.22.18
# EXPOSE 3000/tcp
# EXPOSE 3443/tcp
# VOLUME /wiki/data/content
# USER node
# WORKDIR /wiki
# ENTRYPOINT ["docker-entrypoint.sh"]
# CMD ["node","server"]
#
# That shows us that we need to run the entrypoint + the cmd in our own CMD section at the bottom.
# It also shows that the 'node' user is the user that wiki.js docker image runs under.

FROM litestream/litestream AS litestream
FROM ghcr.io/requarks/wiki:2

# Now we can copy the litestream binary from the official litestream container
# So easy it feels like cheating
COPY --from=litestream /usr/local/bin/litestream /usr/local/bin/litestream

# Configure litestream
# Note that the config file is full of envirnoment variable references, which litestream understands
COPY litestream.yml /etc/litestream.yml

# Do some configuration as root
USER root
RUN true \
    && chmod 755 /usr/local/bin/litestream \
    && chown node /etc/litestream.yml \
    && touch /testfile \
    && true

USER node

ENTRYPOINT []
CMD ["/usr/local/bin/litestream", "replicate", "--exec", "/usr/local/bin/docker-entrypoint.sh node server"]

