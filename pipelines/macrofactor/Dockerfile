FROM ghcr.io/astral-sh/uv:debian
LABEL maintainer "me@micahrl.com"

WORKDIR /app

# The package version to hardcode
ARG KNPL_MACROFACTOR_BUILD_VERSION="0.1.0"

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    true \
    && pwd \
    && ls -alF \
    && uv sync --frozen --no-install-project --no-dev \
    && true

# Then, add the rest of the project source code and install it
# Installing separately from its dependencies allows optimal layer caching
ADD . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    true \
    && pwd \
    && ls -alF \
    uv sync --frozen --no-dev \
    && true

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Reset the entrypoint, don't invoke `uv`
ENTRYPOINT ["/app/.venv/bin/knpl_macrofactor"]
