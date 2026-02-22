# ---- Build Stage ----
FROM python:3.12.9-slim AS builder
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /usr/local/bin/uv

# 의존성 먼저 복사 (캐시 레이어)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# ---- Runtime ----
FROM python:3.12.9-slim
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY . .

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
