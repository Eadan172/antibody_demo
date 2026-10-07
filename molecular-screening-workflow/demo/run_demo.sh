#!/bin/bash
# 转到仓库根目录，用 .venv 运行演示流程。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/run.sh" "$@"
