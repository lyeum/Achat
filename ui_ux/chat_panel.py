from __future__ import annotations

from PySide6.QtCore import QThread, Signal


class LLMWorker(QThread):
    """Agent.chat()을 별도 스레드에서 실행해 UI 블로킹을 방지한다.

    스트리밍은 현재 LLMClient 구조상 전체 응답 반환 방식으로 처리.
    (Phase 5 이후 token_callback 방식으로 교체 가능)
    """

    response_ready = Signal(str)   # 응답 완성 시
    error_occurred = Signal(str)   # 오류 발생 시

    def __init__(self, agent, user_input: str):
        super().__init__()
        self._agent = agent
        self._user_input = user_input

    def run(self) -> None:
        try:
            response = self._agent.chat(self._user_input, stream=False)
            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))
