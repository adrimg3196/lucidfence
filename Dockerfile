# LucidFence — Fly.io deployment (100% free, always-on VM)
#
# Estrategia: una sola VM free (shared-CPU) corre DOS procesos en el
# contenedor:
#   1) MoA local  (IA, OpenAI-compatible, 127.0.0.1:8085)
#   2) LucidFence SaaS + engine (127.0.0.1:8765)
# El engine ya consume MoA via core/ai.py (http.client a 127.0.0.1:8085).
# El email sale por Atomic Mail Agentic (sin SMTP propio) y el dominio
# del tenant es DigitalPlat FreeDomain (whitelabel). $0 en todos lados.
#
# Free tier Fly.io: hasta 3 VMs shared-CPU siempre encendidas + 3GB RAM.
#
# Despliegue (el agente ejecuta, tu cuenta aparte):
#   flyctl auth login          # tu cuenta, fuera de sesion
#   flyctl launch --no-deploy      # crea la app, no despliega
#   flyctl deploy                  # sube esta imagen
#   flyctl status                 # confirma que corre 24/7
#
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MOA_PORT=8085 \
    LUCIDFENCE_PORT=8765 \
    LUCIDFENCE_HOST=0.0.0.0 \
    LUCIDFENCE_TLS=1

WORKDIR /app

# Dependencias del sistema para scrypt (PoW de Atomic Mail) y build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos primero para aprovechar la cache de capas.
COPY requirements.txt requirements.lock /app/
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Codigo fuente.
COPY . /app

# Volumen persistente para la SQLite de tenants y credenciales Atomic Mail.
VOLUME ["/app/data"]

# Arranque unificado: MoA + SaaS.
COPY docker_start.sh /app/docker_start.sh
RUN chmod +x /app/docker_start.sh

EXPOSE 8765
CMD ["/app/docker_start.sh"]
