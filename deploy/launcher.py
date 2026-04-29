"""
Achat 런처 — PyInstaller로 Achat.exe 빌드 시 진입점.

역할:
  1. 설치 디렉토리를 자동으로 찾는다 (exe 위치 기준).
  2. models/model_q4km.gguf 존재 여부를 확인하고 없으면 안내 메시지를 띄운다.
  3. uv run python main.py 를 실행해 앱을 기동한다.
"""

import os
import sys
import subprocess


def _install_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _show_error(title: str, msg: str) -> None:
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x30)  # MB_ICONWARNING
    except Exception:
        print(f"[{title}] {msg}")


def main() -> None:
    base = _install_dir()
    uv   = os.path.join(base, "uv.exe")
    main_py = os.path.join(base, "main.py")
    model   = os.path.join(base, "models", "model_q4km.gguf")

    if not os.path.exists(uv):
        _show_error(
            "Achat — 초기화 오류",
            f"uv.exe를 찾을 수 없습니다:\n{uv}\n\n"
            "AchatSetup.exe로 재설치해주세요."
        )
        sys.exit(1)

    if not os.path.exists(model):
        _show_error(
            "Achat — 모델 파일 없음",
            f"모델 파일을 찾을 수 없습니다:\n{model}\n\n"
            "models 폴더에 model_q4km.gguf를 복사한 뒤 다시 실행해주세요.\n"
            "(파일 크기 약 2GB)"
        )
        sys.exit(1)

    os.environ["ACHAT_ENV"] = "deploy"

    result = subprocess.run(
        [uv, "run", "python", main_py],
        cwd=base,
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
