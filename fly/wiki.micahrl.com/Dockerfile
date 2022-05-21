# We make this container so that we can run litestream in it
# On Fly, we have to run everything in a single container
# <https://tip.litestream.io/guides/docker/#running-in-the-same-container>
# We can use the fly.io litestream base image
# <https://github.com/fly-apps/litestream-base>

# First, we got an approximation of the wiki.js Dockerfile
# ... this is fucking annoying bc nowhere in the repo is their actual Dockerfile
# I assume you can get it eventually by going through their fucking deranged build process.
# But I cheated instead.
# <https://stackoverflow.com/questions/48716536/how-to-show-a-dockerfile-of-image-docker>
# <https://stackoverflow.com/questions/19104847/how-to-generate-a-dockerfile-from-an-image/48444917#48444917>
# All we needed was the basics anyway.
# That shows us something like this Dockerfile:
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
# And THAT shows us that we need to run the entrypoint + the cmd in our own CMD section at the bottom

FROM flyio/litestream-base AS litestream
FROM ghcr.io/requarks/wiki:2

COPY --from=litestream /litestream /litestream

EXPOSE 3000/tcp

# Litestream was failing bc it did not have permissions to write to the /etc/litestream.yml file
#
# I found the user that we were running under by temporarily replacing the real CMD section with:
# CMD ["/bin/sh", "-c", "whoami && exit 1"]
#
# TODO: it's probably fucked up to chown node /etc
USER root
RUN chown node /etc
USER node

# Pass
CMD ["/litestream/start.sh", "/usr/local/bin/docker-entrypoint.sh node server"]
