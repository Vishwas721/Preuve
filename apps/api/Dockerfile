# syntax=docker/dockerfile:1
# Preuve API image (Phase 5D). One image, three commands: the API (default), the arq worker
# (`arq app.workers.settings.WorkerSettings`) and migrations (`alembic upgrade head`).

ARG PYTHON_IMAGE=python:3.11-slim-bookworm

FROM ghcr.io/astral-sh/uv:0.12.8 AS uv

# ---------- build: dependencies from the lockfile only ----------
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /srv/app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# ---------- runtime: no build tools, non-root ----------
FROM ${PYTHON_IMAGE} AS runtime
RUN groupadd --system --gid 10001 preuve \
 && useradd --system --uid 10001 --gid preuve --home-dir /srv/app --shell /usr/sbin/nologin preuve
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=preuve:preuve /srv/app /srv/app
WORKDIR /srv/app
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    LOG_FORMAT=json
USER preuve
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
# --no-access-log: our access log never prints query strings (they can hold personal data).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
