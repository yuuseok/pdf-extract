# ---- App (FastAPI) ----
FROM python:3.11-slim AS base

# Java 설치 (opendataloader-pdf가 내부적으로 Java CLI 사용)
RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jre-headless && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 의존성 먼저 설치 (캐시 활용)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 소스 코드 복사
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# uploads 디렉토리 생성
RUN mkdir -p /data/uploads

# 시작 스크립트
COPY docker/start-app.sh ./
RUN chmod +x start-app.sh

EXPOSE 8000

CMD ["./start-app.sh"]
