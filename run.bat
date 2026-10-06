@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if "%~1"=="" (
  echo Usage: run.bat ^<task-file^>
  exit /b 2
)

if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv --without-pip .venv || exit /b 1
)

if not exist ".env" (
  set /p LLM_API_KEY="LLM API Key: "
  if "!LLM_API_KEY!"=="" (
    echo API Key cannot be empty.
    exit /b 1
  )
  (
    echo LLM_API_KEY=!LLM_API_KEY!
    echo LLM_BASE_URL=https://api.openai.com/v1
    echo LLM_MODEL=gpt-5-mini
  ) > .env
)

".venv\Scripts\python.exe" -m antibody_workflow "%~1"
