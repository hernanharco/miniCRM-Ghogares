# =============================================================================
# Dockerfile — CRM Bayiva
# =============================================================================
# Usa multi-stage build para mantener la imagen final liviana.
#
# Build:
#   docker build -t minicrm .
#
# Run:
#   docker run -p 8002:8002 -v ./mini_crm.db:/app/mini_crm.db minicrm
# =============================================================================

FROM python:3.12-slim AS builder

WORKDIR /app

# Solo instalar dependencias primero (capa cacheable)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# =============================================================================
FROM python:3.12-slim

WORKDIR /app

# Copiar dependencias desde builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Instalar Docker CLI para ejecutar scrapers como contenedores
# Usamos el repo oficial de Docker (docker-ce-cli + compose plugin)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    docker-ce-cli \
    docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Copiar el código de la aplicación
COPY app/ ./app/
COPY run.sh .

# Puerto por defecto
EXPOSE 8002

# Variables de entorno
ENV PORT=8002
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/')" || exit 1

# Comando de arranque
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
