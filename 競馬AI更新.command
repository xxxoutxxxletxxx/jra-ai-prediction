#!/bin/bash
cd "$(dirname "$0")"
TOMORROW="$(date -v+1d +%Y-%m-%d)"
exec bash "scripts/run_all.sh" --skip-jv --start-date "$TOMORROW" --days 2 "$@"
