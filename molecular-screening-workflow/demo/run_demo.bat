@echo off
REM 转到仓库根目录，用 .venv 运行演示流程。
cd /d "%~dp0\.."
call run.bat %*
