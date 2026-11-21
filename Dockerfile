
# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

# Install uv
RUN python -m pip install --no-cache-dir uv

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
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv

# Copy application
COPY app/ ./app/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

