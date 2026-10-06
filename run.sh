#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ne 1 ]]; then
  echo "用法：./run.sh <需求文本文件>" >&2
  echo "示例：./run.sh examples/抗体需求示例.txt" >&2
  exit 2
fi

if [[ ! -x "$ROOT/.venv/bin/python" || ! -f "$ROOT/.env" ]]; then
  "$ROOT/setup.sh"
fi

cd "$ROOT"
exec "$ROOT/.venv/bin/python" -m antibody_workflow "$1"
