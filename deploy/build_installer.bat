@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0.."

:: ============================================================
::  Achat 설치 파일 빌드 스크립트 (Windows)
::  실행 위치: 프로젝트 루트 또는 deploy\ 폴더 — 어디서든 동작
::
::  출력:  deploy\dist\AchatSetup.exe
::  필요:  Python 3.10+, pip, Inno Setup 6
:: ============================================================

echo [1/4] 빌드 환경 준비...

:: deploy\dist 폴더 생성
if not exist "deploy\dist" mkdir "deploy\dist"
if not exist "deploy\build" mkdir "deploy\build"

:: ── uv.exe 다운로드 ───────────────────────────────────────────────────────────
if not exist "deploy\dist\uv.exe" (
    echo      uv.exe 다운로드 중...
    set UV_URL=https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip
    curl -L --silent --output "deploy\dist\uv.zip" "!UV_URL!"
    if errorlevel 1 (
        echo [오류] uv.exe 다운로드 실패. 네트워크 연결을 확인하세요.
        exit /b 1
    )
    powershell -NoProfile -Command ^
        "Expand-Archive -Path 'deploy\dist\uv.zip' -DestinationPath 'deploy\dist\uv_tmp' -Force; ^
         Move-Item 'deploy\dist\uv_tmp\uv.exe' 'deploy\dist\uv.exe' -Force; ^
         Remove-Item 'deploy\dist\uv_tmp','deploy\dist\uv.zip' -Recurse -Force"
    if not exist "deploy\dist\uv.exe" (
        echo [오류] uv.exe 압축 해제 실패.
        exit /b 1
    )
    echo      uv.exe 준비 완료
) else (
    echo      uv.exe 이미 존재 — 스킵
)

:: ── PyInstaller 설치 확인 ─────────────────────────────────────────────────────
echo.
echo [2/4] PyInstaller로 Achat.exe 빌드 중...

python -m pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo      PyInstaller 설치 중...
    python -m pip install --quiet pyinstaller
)

:: PyInstaller 빌드
python -m pyinstaller deploy\achat.spec ^
    --distpath deploy\dist ^
    --workpath deploy\build ^
    --noconfirm

if not exist "deploy\dist\Achat.exe" (
    echo [오류] Achat.exe 빌드 실패.
    exit /b 1
)
echo      Achat.exe 빌드 완료

:: ── Inno Setup 컴파일 ─────────────────────────────────────────────────────────
echo.
echo [3/4] Inno Setup으로 AchatSetup.exe 생성 중...

:: 일반적인 Inno Setup 설치 경로 탐색
set ISCC=""
for %%P in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
) do (
    if exist %%P set ISCC=%%P
)

:: PATH에서도 탐색
if !ISCC!=="" (
    where ISCC.exe >nul 2>&1
    if not errorlevel 1 set ISCC=ISCC.exe
)

if !ISCC!=="" (
    echo [오류] Inno Setup 6를 찾을 수 없습니다.
    echo        https://jrsoftware.org/isdl.php 에서 설치 후 재실행하세요.
    exit /b 1
)

!ISCC! "deploy\achat_setup.iss"

if not exist "deploy\dist\AchatSetup.exe" (
    echo [오류] AchatSetup.exe 생성 실패.
    exit /b 1
)

:: ── 완료 ─────────────────────────────────────────────────────────────────────
echo.
echo [4/4] 완료!
echo.
echo   출력 파일: deploy\dist\AchatSetup.exe
echo.
echo   배포 시 사용자에게 제공할 파일:
echo     - AchatSetup.exe    (설치 마법사 — 이것만 배포)
echo     - model_q4km.gguf   (약 2GB, 별도 배포)
echo.
pause
