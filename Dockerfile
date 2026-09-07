# RISKON backend + frontend, one container, one process — see
# RISKON_ARCHITECTURE.md for why this app is deployed as a single service
# rather than split frontend/backend hosting.
#
# Works unmodified on any Docker-capable host (Railway, Render, Fly.io,
# generic VPS). Platforms that build via Nixpacks/buildpacks instead of a
# Dockerfile (e.g. Railway's default) can ignore this file entirely and use
# the same two commands directly.
#
# Railway note: if the platform's "Custom Start Command" setting is used
# instead of this file's CMD, set it to plain `python3 -m uvicorn
# backend.main:app --host 0.0.0.0 --port $PORT` -- Railway substitutes bare
# $VAR references itself without a real shell, so bash's ${VAR:-default}
# fallback syntax is passed through literally and breaks uvicorn's arg
# parsing. This CMD line avoids that because it already runs through `sh -c`.
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

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8743}"]
