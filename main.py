"""프로젝트 루트 진입점 — QML + PySide6 플로팅 UI 실행."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QApplication

from agent.core import Agent
from config import get_config
from ui_ux.tray import AppTrayIcon
from ui_ux.widget import UIEngine

ROOT = Path(__file__).resolve().parent

CHARACTER_ID = "Haru"
WORLD_PATH   = ROOT / "conversation/world/W_sea.yaml"
SCENARIO_ID  = "morning_walk"
ACT_ID       = "act_1"


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # 트레이만 남아도 종료 안 함

    cfg = get_config()

    logger.info("Agent 초기화 중...")
    agent = Agent(
        character_id=CHARACTER_ID,
        world_path=str(WORLD_PATH),
        scenario_id=SCENARIO_ID,
        act_id=ACT_ID,
        config=cfg,
    )

    # QML 엔진 + 브리지
    ui = UIEngine(agent)

    # 트레이 아이콘
    tray = AppTrayIcon(ui_engine=ui, bridge=ui.bridge)
    tray.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
