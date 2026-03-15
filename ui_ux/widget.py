from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine

from ui_ux.bridge import ChatBridge

_QML_DIR = Path(__file__).resolve().parent / "qml"


class UIEngine:
    """QQmlApplicationEngine 래퍼.

    ChatBridge를 QML context property 'bridge'로 등록하고
    main.qml을 로드한다.

    Usage:
        engine = UIEngine(agent)
        engine.show()
    """

    def __init__(self, agent):
        self.bridge = ChatBridge(agent)
        self.engine = QQmlApplicationEngine()

        # QML에서 ChatBubble.qml을 import 경로로 참조할 수 있도록 등록
        self.engine.addImportPath(str(_QML_DIR))

        # bridge를 QML context property로 노출
        self.engine.rootContext().setContextProperty("bridge", self.bridge)

        qml_path = _QML_DIR / "main.qml"
        self.engine.load(QUrl.fromLocalFile(str(qml_path)))

        if not self.engine.rootObjects():
            raise RuntimeError(f"QML 로드 실패: {qml_path}")

    def root_window(self):
        """메인 QML Window 객체를 반환한다."""
        return self.engine.rootObjects()[0]

    def show(self) -> None:
        self.root_window().show()

    def hide(self) -> None:
        self.root_window().hide()
