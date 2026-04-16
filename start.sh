#!/usr/bin/env bash
set -euo pipefail

uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-4123}"
