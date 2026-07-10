#!/usr/bin/env bash
# Restarts the ARQ worker automatically if it dies -- local dev only. The
# worker's Redis connection (Upstash, over the public internet) has dropped
# from local network blips repeatedly during development; this just keeps
# it running instead of silently sitting dead until someone notices.
# Production should use a real process supervisor (systemd/pm2/etc) instead.
cd "$(dirname "$0")/.."

while true; do
  echo "[supervisor] starting worker at $(date)"
  ./.venv/Scripts/python.exe -m arq app.worker.worker_settings.WorkerSettings
  echo "[supervisor] worker exited with code $? -- restarting in 3s"
  sleep 3
done
