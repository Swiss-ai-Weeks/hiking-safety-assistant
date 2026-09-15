#!/usr/bin/env bash
# Update the VM deployment: pull, rebuild the frontend, sync backend deps, restart the service.
set -euo pipefail
cd "$(dirname "$0")/.."

git pull --ff-only
pnpm install --frozen-lockfile
pnpm build
uv sync --directory backend --no-dev --frozen
sudo systemctl restart hiking-safety-assistant
systemctl --no-pager --lines=5 status hiking-safety-assistant
