#!/usr/bin/env bash
set -euo pipefail

# create_pgpass.sh
# Create or update ~/.pgpass with a single entry.
# Usage: create_pgpass.sh HOST PORT DATABASE USER PASSWORD
# Example: ./scripts/create_pgpass.sh db.example.com 5432 retail_db alice s3cr3t

if [ "$#" -lt 5 ]; then
  echo "Usage: $0 HOST PORT DATABASE USER PASSWORD"
  exit 1
fi
HOST="$1"
PORT="$2"
DB="$3"
USER="$4"
PASS="$5"

LINE="${HOST}:${PORT}:${DB}:${USER}:${PASS}"

mkdir -p "${HOME}"
printf '%s
' "$LINE" > "${HOME}/.pgpass"
chmod 600 "${HOME}/.pgpass"

echo "Wrote ~/.pgpass (permissions set to 600)."