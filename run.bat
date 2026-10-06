@echo off
setlocal
cd /d "%~dp0"
set "PY=%CD%\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo 正在当前目录创建 .venv ...
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
if not exist ".venv\.requirements.stamp" (
  echo 正在安装依赖 ...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r requirements.txt
  type nul > ".venv\.requirements.stamp"
)
"%PY%" -m antibody_pipeline %*
exit /b %ERRORLEVEL%
