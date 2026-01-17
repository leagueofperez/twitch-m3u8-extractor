FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

# 1. Copia requirements primero (para caché eficiente)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 2. ¡Copia TODO el código, incluido entrypoint.sh!
COPY . .

# 3. Ahora sí puedes dar permisos y cambiar propietario
RUN chmod +x /app/entrypoint.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

ENTRYPOINT ["/app/entrypoint.sh"]