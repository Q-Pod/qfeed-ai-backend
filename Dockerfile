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

# HuggingFace 캐시 디렉터리를 쓰기 가능한 경로로 지정
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
ENV PATH="/app/.venv/bin:$PATH"

# 캐시 디렉터리 미리 생성
RUN mkdir -p /app/.cache/huggingface /app/.cache/sentence_transformers

# appuser 홈을 /app으로 지정 (/nonexistent 방지)
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /app appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
