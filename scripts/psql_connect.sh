#!/usr/bin/env bash
set -euo pipefail

# psql_connect.sh
# Small helper to connect to a PostgreSQL database using psql.
# Behavior:
#  - If .env file exists in repo root, it will be sourced for PG* env vars.
#  - You can call with a full URI using: ./psql_connect.sh -u postgresql://user:pass@host:port/db
#  - Or use env vars: PGHOST PGPORT PGUSER PGPASSWORD PGDATABASE
#  - Or pass positional: HOST [PORT] [USER] [DB]

# Try to load .env (if present) into environment (ignores comment lines)
if [ -f .env ]; then
  # Export lines of the form KEY=VALUE ignoring comments
  set -a
  # shellcheck disable=SC1090
  . ./.env
  set +a
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not found in PATH. To install on Debian/Ubuntu:"
  echo "  sudo apt update && sudo apt install -y postgresql-client"
  exit 2
fi

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  cat <<'USAGE'
Usage: psql_connect.sh [options] [HOST [PORT [USER [DB]]]]
Options:
  -u <URI>        Connect using full connection URI (psql <URI>)
  -h, --help      Show this help

Environment variables supported:
  PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

Examples:
  ./scripts/psql_connect.sh -u postgresql://alice:secret@db.example.com:5432/retail_db
  PGHOST=db.example.com PGUSER=alice PGPASSWORD=secret PGDATABASE=retail_db ./scripts/psql_connect.sh
  ./scripts/psql_connect.sh db.example.com 5432 alice retail_db
USAGE
  exit 0
fi

if [ "${1:-}" = "-u" ]; then
  if [ -z "${2:-}" ]; then
    echo "Missing URI after -u"
    exit 1
  fi
  URI="$2"
  shift 2
  exec psql "$URI" "$@"
fi

# Prefer explicit env vars, otherwise fall back to positional parameters
HOST="${PGHOST:-${1:-}}"
PORT="${PGPORT:-${2:-5432}}"
USER="${PGUSER:-${3:-}}"
DB="${PGDATABASE:-${4:-}}"

if [ -z "$HOST" ]; then
  echo "Missing host. Either set PGHOST or pass HOST as first argument. See --help for usage."
  exit 1
fi

# Export PGPASSWORD if present in env so psql can use it non-interactively
: "${PGPASSWORD:=}"  # ensure variable exists (may be empty)

# Build psql arguments
PSQL_ARGS=( -h "$HOST" -p "$PORT" )
if [ -n "$USER" ]; then
  PSQL_ARGS+=( -U "$USER" )
fi
if [ -n "$DB" ]; then
  PSQL_ARGS+=( -d "$DB" )
fi

# Run psql with the constructed args
exec psql "${PSQL_ARGS[@]}" "$@"
