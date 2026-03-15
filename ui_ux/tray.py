from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QMessageBox, QSystemTrayIcon

from ui_ux.bridge import ChatBridge


def _make_default_icon(color: str = "#4A90D9", size: int = 32) -> QIcon:
    """캐릭터 아이콘 파일이 없을 때 사용하는 단색 원형 기본 아이콘."""
    pix = QPixmap(size, size)
    pix.fill(QColor("transparent"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor("transparent"))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    painter.end()
    return QIcon(pix)


class AppTrayIcon(QSystemTrayIcon):
    """시스템 트레이 아이콘.

    메뉴:
    - 열기 / 숨기기  → QML Window show/hide
    - 캐릭터 변경    → bridge.changeCharacter()
    - 종료           → QApplication.quit()
    """

    def __init__(self, ui_engine, bridge: ChatBridge, parent=None):
        super().__init__(parent)
        self._engine = ui_engine
        self._bridge = bridge

        self.setIcon(_make_default_icon())
        self.setToolTip(f"Achat — {bridge.characterName}")
        self._build_menu()
        self.activated.connect(self._on_activated)

        # 캐릭터 이름 변경 시 툴팁 업데이트
        bridge.characterNameChanged.connect(
            lambda name: self.setToolTip(f"Achat — {name}")
        )

    def _build_menu(self) -> None:
        menu = QMenu()

        self._toggle_action = menu.addAction("숨기기")
        self._toggle_action.triggered.connect(self._toggle_window)

        menu.addSeparator()

        change_char = menu.addAction("캐릭터 변경")
        change_char.triggered.connect(self._change_character)

        menu.addSeparator()

        quit_action = menu.addAction("종료")
        quit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_window()

    def _toggle_window(self) -> None:
        win = self._engine.root_window()
        if win.isVisible():
            win.hide()
            self._toggle_action.setText("열기")
        else:
            win.show()
            win.raise_()
            self._toggle_action.setText("숨기기")

    def _change_character(self) -> None:
        char_id, ok = QInputDialog.getText(None, "캐릭터 변경", "캐릭터 ID 입력:")
        if ok and char_id.strip():
            self._bridge.changeCharacter(char_id.strip())
