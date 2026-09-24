# =============================================================================
# NCRB Criminal Network Analysis System
#
# Single-image deployment. The whole platform — relational store, full-text
# index, graph engine, ML scoring and blockchain audit ledger — runs in this one
# container. There is no database server, search cluster or message broker to
# provision, which is the point: it deploys inside an air-gapped police network.
#
#   docker build -t ncrb-cnas .
#   docker run -p 8000:8000 -v ncrb-data:/app/runtime ncrb-cnas
#   open http://localhost:8000/app
# =============================================================================

# --- Stage 1: build the dashboard -------------------------------------------
FROM node:22-alpine AS ui
WORKDIR /ui
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Stage 2: runtime --------------------------------------------------------
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY data/ ./data/
COPY --from=ui /ui/dist ./frontend/dist

# Writable location for the SQLite database; mount a volume here to persist it.
RUN mkdir -p /app/runtime \
    && adduser --disabled-password --gecos "" ncrb \
    && chown -R ncrb:ncrb /app
USER ncrb

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
