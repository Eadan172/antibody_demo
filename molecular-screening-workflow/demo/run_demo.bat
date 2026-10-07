@echo off
REM 从仓库根目录运行演示流程。不训练模型，不访问网络。
cd /d "%~dp0\.."

python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python 3.8+
    exit /b 1
)

python -c "import pandas, yaml" >nul 2>&1
if errorlevel 1 (
    echo 请先安装: pip install pandas pyyaml
    exit /b 1
)

echo 训练数据: demo/data/sample_training.csv
echo 待筛选分子: demo/data/sample_molecules.csv
python run_workflow.py --demo
if errorlevel 1 exit /b 1

echo 结果:
dir results\01_generated.csv results\02_qsar.csv results\03_admet.csv results\04_docking.csv results\05_sa.csv results\evaluation_summary.png
