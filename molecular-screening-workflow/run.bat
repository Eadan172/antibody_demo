@echo off
REM 用项目 .venv 运行演示流程。环境不存在时会自动创建并安装依赖。
cd /d "%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 run_workflow.py --demo %*
) else (
  python run_workflow.py --demo %*
)
