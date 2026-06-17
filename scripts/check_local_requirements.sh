#!/usr/bin/env bash
set -euo pipefail

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing: $1" >&2
    exit 1
  }
}

need bash
need git
need gh
need python3
need gcloud
need codex
need curl
need systemctl

echo "ok: bash, git, gh, python3, gcloud, codex, curl, systemctl"
