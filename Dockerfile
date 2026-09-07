# RISKON backend + frontend, one container, one process — see
# RISKON_ARCHITECTURE.md for why this app is deployed as a single service
# rather than split frontend/backend hosting.
#
# Works unmodified on any Docker-capable host (Railway, Render, Fly.io,
# generic VPS). Platforms that build via Nixpacks/buildpacks instead of a
# Dockerfile (e.g. Railway's default) can ignore this file entirely and use
# the same two commands directly.
#
# CMD runs backend/main.py directly (plain Python, no shell) rather than
# `uvicorn ... --port ${PORT:-8743}` through `sh -c`, because Railway's
# Dockerfile-based deploys were observed NOT expanding that shell syntax --
# uvicorn received the literal, unexpanded string as its --port value and
# refused to start. backend/main.py's __main__ block already reads the PORT
# env var in Python (see backend/config.py's `port` setting), so this
# sidesteps shell variable expansion entirely.
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .

# The synthetic demo database (database/riskon.db) and the pre-built
# frontend (frontend/riskon.html) are committed to git and copied in above —
# no build step regenerates them at deploy time, for reproducibility, and to
# avoid silently reshuffling the demo dataset on every deploy.

ENV PYTHONUNBUFFERED=1
EXPOSE 8743

CMD ["python3", "-m", "backend.main"]
