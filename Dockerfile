
# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.13.18-slim-trixie AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install uv
RUN python -m pip install --no-cache-dir uv==0.13.9

# Create virtual environment
RUN uv venv /opt/venv

# Copy project configuration
COPY pyproject.toml uv.lock ./

# Install dependencies
ARG INSTALL_DEV=false

RUN if [ "$INSTALL_DEV" = "true" ]; then \
  uv sync --locked --group dev --no-install-project; \
  else \
  uv sync --locked --no-dev --no-install-project; \
  fi


# ==========================================
# Stage 2: Runtime
# ==========================================
FROM python:3.13.18-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Create unprivileged user
RUN groupadd --system appgroup \
  && useradd --system \
  --gid appgroup \
  --home-dir /app \
  --no-create-home \
  --shell /usr/sbin/nologin \
  appuser

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv

# Copy application
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./

COPY --chmod=755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# Run as non-root
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4)"


ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
