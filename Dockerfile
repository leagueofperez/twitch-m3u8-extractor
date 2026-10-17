FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser app.py config.py twitch_extractor.py shortener.py ./
COPY --chown=appuser:appuser twitch ./twitch
COPY --chown=appuser:appuser routes ./routes
COPY --chown=appuser:appuser services ./services
COPY --chown=appuser:appuser web ./web
COPY --chown=appuser:appuser templates ./templates
COPY --chown=appuser:appuser static ./static
COPY --chown=appuser:appuser entrypoint.sh ./entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER appuser

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]