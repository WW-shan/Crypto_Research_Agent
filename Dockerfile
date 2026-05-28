FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --extra dev --frozen

RUN useradd --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/var \
    && chown -R app:app /app

USER app

ENTRYPOINT ["uv", "run", "--extra", "dev", "crypto-alpha-agent"]
CMD ["--help"]
