#!/usr/bin/env bash
# 在当前项目目录创建 .venv、安装依赖，并运行抗体设计流水线。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "需要 Python 3.9 或更高版本。" >&2
  exit 1
fi

PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "正在当前目录创建 .venv ……"
  python3 -m venv "$ROOT/.venv"
fi

STAMP="$ROOT/.venv/.requirements.stamp"
if [[ ! -f "$STAMP" || "$ROOT/requirements.txt" -nt "$STAMP" ]]; then
  echo "正在安装依赖 ……"
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r "$ROOT/requirements.txt"
  touch "$STAMP"
fi

exec "$PY" -m antibody_pipeline "$@"
