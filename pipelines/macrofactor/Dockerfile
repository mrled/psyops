# A small docker container that contains knpl_macrofactor code.
#
# * Installing psycopg2-binary requires debian (doesn't work on musl)
# * Installing psycopg2 from source requiers a build environment etc
# * debian UV image was like 1.5GB? How is that possible
# * py3-pip would be 18MB, we sidestep that with the zipapp
# * Ensure .dockerignore keeps out everything
# * py3-pandas is huge, but we can remove 20MB (!!) of included tests
#   (as of py3-pandas-2.2.3-r0)
# * py3-openpyxl and py3-numpy are also big

FROM alpine:latest
LABEL maintainer "me@micahrl.com"

WORKDIR /app

# Install (and cache) the deps first
RUN true \
    && apk add --no-cache python3 py3-psycopg2 py3-pandas py3-openpyxl \
    && rm -rf /usr/lib/python3.12/site-pacakges/pandas/tests \
    && true

# Install the app itself
ADD . /app
RUN true \
    && find . \
    && python3 -m zipapp src -o /usr/bin/knpl_macrofactor -m "knpl_macrofactor.cli:main" -p "/usr/bin/env python3" \
    && true

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT ["/usr/bin/knpl_macrofactor"]
