FROM python:3.13-slim

WORKDIR /app

# No compiler: every dependency installs as a ready-made wheel (checked with
# uv 0.12.10 on python:3.13-slim), and the image stays smaller without one.
RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Built from the repository root (see docker-compose.yml).
COPY backend/pyproject.toml ./
# Use the official uv binary, at a fixed version: :latest would change the
# installer under a rebuild without anyone noticing.
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /uv/bin/uv
ENV PATH="/uv/bin:$PATH"

COPY backend/app/ ./app/
# The MCP server, served at /mcp, and the docs its explain() tool reads.
COPY mcp_server/ /opt/mcp_server/
COPY docs/ /opt/docs/
ENV HEATTRANSPLAN_DOCS=/opt/docs

# Use uv pip to install into the system site-packages (Note: uv pip is a Rust implementation, NOT legacy pip)
RUN uv pip install --system . /opt/mcp_server --no-cache-dir

# An ordinary user, never root. Only /tmp is writable (docker-compose.yml
# mounts it, in memory): uploads in transit and matplotlib's font cache.
RUN useradd --system --uid 10001 --no-create-home app
ENV HOME=/tmp MPLCONFIGDIR=/tmp/matplotlib XDG_CACHE_HOME=/tmp/cache
# The activity log (app/services/activity_log.py): docker-compose.yml mounts a
# volume here, which takes this folder's owner, so it survives a rebuild.
RUN mkdir /app/logs && chown app /app/logs
ENV ACTIVITY_LOG=/app/logs/activity.sqlite
# The COP model's many small matrix products lose more to thread start-up than
# they gain from all cores: 2 BLAS threads per request are ~4x faster than the
# default (one per core), and parallel requests do not fight over the cores.
ENV OPENBLAS_NUM_THREADS=2
USER app

EXPOSE 8000

# Behind Caddy: the visitor's address comes from X-Forwarded-For, which Caddy
# sets. Trusted from anyone, as only Caddy reaches this port (not published).
# No access log: it would keep every visitor's address and project ids; the
# anonymous activity log (app/services/activity_log.py) records use instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
