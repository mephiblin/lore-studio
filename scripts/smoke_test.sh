#!/usr/bin/env sh
set -eu

API="${LORE_STUDIO_API:-http://localhost:8000/api/v1}"
curl -fsS "$API/health"
echo
python scripts/seed_demo.py --generate
