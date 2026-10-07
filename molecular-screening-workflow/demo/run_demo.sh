#!/bin/bash
# 从仓库根目录运行演示流程。不训练模型，不访问网络。

set -e
cd "$(dirname "$0")/.."

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "错误: 未找到 Python 3.8+"
  exit 1
fi

echo "Python: $($PY --version)"
$PY -c "import pandas, yaml" || {
  echo "请先安装: pip install pandas pyyaml"
  exit 1
}

echo "训练数据: demo/data/sample_training.csv"
echo "待筛选分子: demo/data/sample_molecules.csv"
$PY run_workflow.py --demo

echo "结果:"
ls -la results/01_generated.csv results/02_qsar.csv results/03_admet.csv results/04_docking.csv results/05_sa.csv results/evaluation_summary.png
