#!/usr/bin/env bash
# Hit every real source (and, with --app URL, the running service) once from this machine.
# See backend/scripts/smoke_live.py for what is checked. Reads backend/.env like the service does.
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec uv run python -m scripts.smoke_live "$@"
