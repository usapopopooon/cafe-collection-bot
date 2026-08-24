FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src/ src/
COPY scripts/ scripts/

RUN pip install --no-cache-dir .
RUN chmod +x scripts/*.sh

RUN useradd --create-home --uid 10001 app
USER app

CMD ["./scripts/start-bot.sh"]
