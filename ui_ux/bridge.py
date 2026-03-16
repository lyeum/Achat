from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtWidgets import QApplication

from ui_ux.chat_panel import LLMWorker


class ChatBridge(QObject):
    """QML ↔ Python 통신 브리지.

    QML에서 호출하는 Slot과 QML에 알리는 Signal을 정의한다.
    QML에서는 context property 'bridge'로 접근한다.

    Signals (Python → QML):
        messageAdded(role, content) : 새 메시지 추가 (role: "user" | "assistant")
        statusChanged(status)       : "thinking" | "ready"
        characterNameChanged(name)  : 캐릭터 이름 변경

    Slots (QML → Python):
        sendMessage(text)           : 사용자 메시지 전송
        snapToEdge(x, y, w, h)     : 화면 모서리 스냅 좌표 계산
        changeCharacter(char_id)    : 캐릭터 핫스왑
    """

    messageAdded        = Signal(str, str)   # role, content
    statusChanged       = Signal(str)        # "thinking" | "ready"
    characterNameChanged = Signal(str)

    def __init__(self, agent):
        super().__init__()
        self._agent = agent
        self._worker: LLMWorker | None = None
        self._character_name: str = agent.character.get("name", "")

    # ── Property ──────────────────────────────────────────────────────────────

    @Property(str, notify=characterNameChanged)
    def characterName(self) -> str:
        return self._character_name

    # ── Slots (QML → Python) ──────────────────────────────────────────────────

    @Slot(str)
    def sendMessage(self, text: str) -> None:
        """QML 입력창에서 메시지를 전송할 때 호출된다."""
        if not text.strip() or self._worker is not None:
            return

        self.messageAdded.emit("user", text)
        self.statusChanged.emit("thinking")

        self._worker = LLMWorker(self._agent, text)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    @Slot(int, int, int, int, result="QVariantList")
    def snapToEdge(self, x: int, y: int, w: int, h: int) -> list[int]:
        """드래그 종료 시 화면 모서리 스냅 좌표를 반환한다.

        QML의 MouseArea.onReleased에서 호출:
            var snapped = bridge.snapToEdge(root.x, root.y, root.width, root.height)
            root.x = snapped[0]; root.y = snapped[1]
        """
        SNAP = 30
        screen = QApplication.primaryScreen().availableGeometry()

        snapped_x = x
        snapped_y = y

        if abs(x - screen.left()) <= SNAP:
            snapped_x = screen.left()
        elif abs(x + w - screen.right()) <= SNAP:
            snapped_x = screen.right() - w

        if abs(y - screen.top()) <= SNAP:
            snapped_y = screen.top()
        elif abs(y + h - screen.bottom()) <= SNAP:
            snapped_y = screen.bottom() - h

        return [snapped_x, snapped_y]

    @Slot(str)
    def changeCharacter(self, char_id: str) -> None:
        """캐릭터를 핫스왑하고 이름 변경 시그널을 emit한다."""
        if self._agent.session is None:   # stub / ui_test 모드
            return

        from agent.persona import swap_persona
        from conversation.core.prompt_build import PromptBuilder
        try:
            new_char, new_session = swap_persona(
                session=self._agent.session,
                new_character_id=char_id.strip(),
            )
            self._agent.character = new_char
            self._agent.session   = new_session

            # router와 builder도 새 character / session 으로 교체
            if self._agent.router is not None:
                self._agent.router.character = new_char
                self._agent.router.session   = new_session
                self._agent.router.builder   = PromptBuilder(
                    new_char,
                    self._agent.world,
                    new_session,
                    count_tokens_fn=self._agent.llm.count_tokens,
                )

            self._character_name = new_char.get("name", char_id)
            self.characterNameChanged.emit(self._character_name)
        except FileNotFoundError as e:
            self.messageAdded.emit("system", f"[캐릭터 변경 실패] {e}")

    # ── 내부 콜백 ─────────────────────────────────────────────────────────────

    def _on_response(self, response: str) -> None:
        self.messageAdded.emit("assistant", response)

    def _on_error(self, msg: str) -> None:
        self.messageAdded.emit("system", f"[오류] {msg}")

    def _on_done(self) -> None:
        self._worker = None
        self.statusChanged.emit("ready")
