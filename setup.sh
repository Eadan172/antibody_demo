#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "错误：未找到 Python 3。请先安装 Python 3.10+。" >&2
  exit 1
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "正在创建 .venv ..."
  "$PYTHON_BIN" -m venv "$ROOT/.venv"
fi

if [[ ! -f "$ROOT/.env" ]]; then
  if [[ -z "${LLM_API_KEY:-}" ]]; then
    read -r -s -p "请输入 LLM API Key: " LLM_API_KEY
    echo
  fi
  if [[ -z "${LLM_API_KEY:-}" ]]; then
    echo "错误：API Key 不能为空。" >&2
    exit 1
  fi
  cat > "$ROOT/.env" <<EOF
LLM_API_KEY=$LLM_API_KEY
LLM_BASE_URL=${LLM_BASE_URL:-https://api.openai.com/v1}
LLM_MODEL=${LLM_MODEL:-gpt-5-mini}
EOF
  chmod 600 "$ROOT/.env"
  echo "已写入 .env（已被 Git 忽略）。"
fi

"$ROOT/.venv/bin/python" -m pip install --quiet --upgrade pip
echo "环境就绪：$ROOT/.venv"
