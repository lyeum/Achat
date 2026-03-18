"""프로젝트 루트 진입점 — QML + PySide6 플로팅 UI 실행."""

from __future__ import annotations

import faulthandler
import os
import signal
import sys
from pathlib import Path

faulthandler.enable()

# Qt 초기화 전 ibus 입력기 환경변수 설정 (WSL2 한글 입력)
os.environ.setdefault("QT_IM_MODULE", "ibus")
os.environ.setdefault("GTK_IM_MODULE", "ibus")
os.environ.setdefault("XMODIFIERS", "@im=ibus")
os.environ.setdefault("IBUS_USE_PORTAL", "0")

from loguru import logger

from agent.core import Agent
from config import get_config

ROOT = Path(__file__).resolve().parent

CHARACTER_ID = "Haru"
WORLD_PATH   = ROOT / "conversation/world/W_sea.yaml"
SCENARIO_ID  = "morning_walk"
ACT_ID       = "act_1"


_PID_FILE = Path("/tmp/achat.pid")


def _cleanup_previous() -> None:
    """이전 Achat 프로세스가 남아있으면 종료한다."""
    if not _PID_FILE.exists():
        return
    try:
        old_pid = int(_PID_FILE.read_text().strip())
        os.kill(old_pid, signal.SIGTERM)
        logger.info(f"[startup] 이전 프로세스 종료 (PID {old_pid})")
    except (ProcessLookupError, ValueError):
        pass  # 이미 종료됨
    finally:
        _PID_FILE.unlink(missing_ok=True)


def _check_vram(min_free_mb: int = 3000) -> None:
    """CUDA 사용 가능 시 잔여 VRAM을 확인하고 부족하면 경고한다."""
    try:
        import torch
        if not torch.cuda.is_available():
            return
        free, total = torch.cuda.mem_get_info(0)
        free_mb  = free  // (1024 ** 2)
        total_mb = total // (1024 ** 2)
        logger.info(f"[VRAM] 여유: {free_mb} MB / {total_mb} MB")
        if free_mb < min_free_mb:
            logger.warning(
                f"[VRAM] 여유 메모리가 {min_free_mb} MB 미만입니다 ({free_mb} MB). "
                "이전 프로세스가 남아있을 수 있습니다. "
                "`nvidia-smi`로 확인 후 `kill -9 <PID>` 로 정리하세요."
            )
    except Exception:
        pass  # torch 미설치 환경(deploy)에서는 무시


def main() -> None:
    # ── torch를 Qt보다 먼저 로드 (shared library 충돌 방지) ──────────────────
    _cleanup_previous()
    _PID_FILE.write_text(str(os.getpid()))

    cfg = get_config()
    _check_vram()

    logger.info("Agent 초기화 중...")
    agent = Agent(
        character_id=CHARACTER_ID,
        world_path=str(WORLD_PATH),
        scenario_id=SCENARIO_ID,
        act_id=ACT_ID,
        config=cfg,
    )

    # ── Qt는 torch 로드 완료 후 import + 초기화 ──────────────────────────────
    from PySide6.QtWidgets import QApplication
    from ui_ux.tray import AppTrayIcon
    from ui_ux.widget import UIEngine

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # QML 엔진 + 브리지
    ui = UIEngine(agent)

    # 트레이 아이콘
    tray = AppTrayIcon(ui_engine=ui, bridge=ui.bridge)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
