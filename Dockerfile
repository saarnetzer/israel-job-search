FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY jobsearch_il ./jobsearch_il
RUN pip install '.[web]' && useradd --create-home app
USER app

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn jobsearch_il.web.server:build --factory --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
