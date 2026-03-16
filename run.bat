@echo off
:: run.bat — Achat Windows 배포 실행 스크립트
::
:: 사전 조건:
::   - Python 3.10+ 설치
::   - uv 설치: pip install uv
::   - 의존성 설치: uv sync --project pyproject-deploy.toml
::   - 모델 파일: models\model_q4km.gguf (약 2GB)

setlocal

set "SCRIPT_DIR=%~dp0"
set "MODEL_PATH=%SCRIPT_DIR%models\model_q4km.gguf"

:: 모델 파일 존재 확인
if not exist "%MODEL_PATH%" (
    echo [오류] 모델 파일이 없습니다: %MODEL_PATH%
    echo models\ 폴더에 model_q4km.gguf 를 복사해주세요.
    pause
    exit /b 1
)

:: 실행
echo Achat 시작 중...
uv run --project pyproject-deploy.toml python main.py --env deploy --model "%MODEL_PATH%"

endlocal
