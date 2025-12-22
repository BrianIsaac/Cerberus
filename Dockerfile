# Stage 1: Build dependencies
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS build

ARG DEBIAN_FRONTEND="noninteractive"

ARG NON_ROOT_USER="opsassistant"
ARG HOME_DIR="/home/${NON_ROOT_USER}"
ARG REPO_DIR="${HOME_DIR}/app"

RUN mkdir -p ${REPO_DIR}
WORKDIR ${REPO_DIR}

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev


# Stage 2: Runtime image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

ARG DEBIAN_FRONTEND="noninteractive"

ARG NON_ROOT_USER="opsassistant"
ARG NON_ROOT_UID="2222"
ARG NON_ROOT_GID="2222"
ARG HOME_DIR="/home/${NON_ROOT_USER}"
ARG REPO_DIR="${HOME_DIR}/app"

RUN useradd -l -m -s /bin/bash -u ${NON_ROOT_UID} ${NON_ROOT_USER}

RUN apt-get update -qy && \
    apt-get install -qyy --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PYTHONIOENCODING=utf8 \
    PYTHONUNBUFFERED=1 \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PATH="${HOME_DIR}/.local/bin:${REPO_DIR}/.venv/bin:$PATH" \
    DD_TRACE_ENABLED=true \
    DD_LOGS_INJECTION=true \
    DD_LLMOBS_ENABLED=1 \
    DD_LLMOBS_AGENTLESS_ENABLED=1 \
    PORT=8080

USER ${NON_ROOT_USER}
WORKDIR ${REPO_DIR}

COPY --from=build --chown=${NON_ROOT_USER}:${NON_ROOT_GID} ${REPO_DIR} ${REPO_DIR}

COPY --chown=${NON_ROOT_USER}:${NON_ROOT_GID} app/ app/

EXPOSE 8080

ENTRYPOINT ["ddtrace-run"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
