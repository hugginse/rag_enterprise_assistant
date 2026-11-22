FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

# 层缓存：先只拷依赖清单
COPY pyproject.toml uv.lock ./
ENV UV_HTTP_TIMEOUT=120
RUN uv sync --frozen --no-dev --no-install-project

# 再拷源码
COPY . .
RUN uv sync --frozen --no-dev

RUN useradd -m -u 10001 appuser \
    && mkdir -p /app/uploads /app/chroma_data \
    && chown -R appuser:appuser /app
USER appuser

ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
