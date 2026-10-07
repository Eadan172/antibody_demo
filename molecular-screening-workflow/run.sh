#!/usr/bin/env bash
# 用项目 .venv 运行演示流程。环境不存在时会自动创建并安装依赖。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "错误: 未找到 Python 3.8+" >&2
  exit 1
fi

exec "$PY" run_workflow.py --demo "$@"
