@echo off
:: run.bat — Achat Windows 배포 실행 스크립트
::
:: 사전 조건:
::   - Python 3.10+ 설치
::   - uv 설치: pip install uv
::   - 의존성 설치: uv sync  (pyproject.toml 기준)
::   - 모델 파일: models\model_q4km.gguf (약 2GB)
::
:: 배포 패키지에서는 pyproject-deploy.toml 이 pyproject.toml 로 복사되어 있어야 함

setlocal

set "SCRIPT_DIR=%~dp0"
set "MODEL_PATH=%SCRIPT_DIR%models\model_q4km.gguf"

:: deploy 환경 강제 지정 (config.py _detect_env()가 이 값을 우선 읽음)
set "ACHAT_ENV=deploy"

:: 모델 파일 존재 확인
if not exist "%MODEL_PATH%" (
    echo [오류] 모델 파일이 없습니다: %MODEL_PATH%
    echo models\ 폴더에 model_q4km.gguf 를 복사해주세요.
    pause
    exit /b 1
)

:: 스크립트 위치로 이동 (상대 경로 기준 통일)
cd /d "%SCRIPT_DIR%"

echo Achat 시작 중...
uv run python main.py

endlocal
