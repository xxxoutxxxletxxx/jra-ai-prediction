#!/bin/bash
cd "$(dirname "$0")"
exec bash "scripts/run_all.sh" "$@"
