@echo off
chcp 65001 > nul
setlocal

set "SCRIPT_DIR=%~dp0"
set "MODEL_PATH=%SCRIPT_DIR%models\model_q4km.gguf"
set "ACHAT_ENV=deploy"

if not exist "%MODEL_PATH%" (
    echo [Error] Model file not found: %MODEL_PATH%
    echo Please copy model_q4km.gguf to the models\ folder.
    pause
    exit /b 1
)

cd /d "%SCRIPT_DIR%"

echo Starting Achat...
uv run python main.py

endlocal
