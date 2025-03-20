FROM ghcr.io/astral-sh/uv:debian
LABEL maintainer "me@micahrl.com"

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
ADD ["uv.lock", "pyproject.toml", "./"]
RUN true \
    && pwd \
    && ls -alF \
    && uv sync --frozen --no-install-project --no-dev \
    && rm -rf /root/.cache/uv \
    && true

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
ADD . /app
RUN true \
    && pwd \
    && ls -alF \
    && uv sync --frozen --no-dev \
    && rm -rf /root/.cache/uv \
    && true

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT ["/app/.venv/bin/knpl_macrofactor"]
