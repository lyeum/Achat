# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec — Achat.exe 빌드
#
# 사전 준비:
#   1. ui_ux/assets/icons/app.ico 파일 필요
#      (없으면 icon= 줄을 제거하거나 PNG → ICO 변환 후 배치)
#   2. build_installer.bat에서 자동 호출됨; 직접 빌드 시:
#      pyinstaller deploy/achat.spec --distpath deploy/dist --workpath deploy/build
#

import sys
from pathlib import Path

root = Path(SPECPATH).parent          # 프로젝트 루트 (deploy/ 한 단계 위)
icon_path = root / "ui_ux" / "assets" / "icons" / "app.ico"

a = Analysis(
    [str(root / "deploy" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "ctypes",
        "ctypes.wintypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 개발 전용 패키지 — launcher.py에서는 사용 안 함
        "torch",
        "transformers",
        "peft",
        "PySide6",
        "llama_cpp",
        "chromadb",
        "numpy",
        "pandas",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Achat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                            # 콘솔 창 없음 (Windows GUI 앱)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
    version=None,
)
