"""conversation/narration_monitor.py — 키워드 기반 하드코딩 나레이션 트리거.

LLM 나레이션(Narrator)은 제거됨.
캐릭터 응답 자체가 *묘사* 대사 형식으로 생성되므로 별도 LLM 호출이 불필요.

현재 남아있는 기능:
  KEYWORD_TRIGGER — 사용자 입력에 장소/날씨/사물 키워드가 포함될 때,
                    하드코딩된 짧은 분위기 텍스트를 반환한다.
                    LLM 호출 없음. 세션 내 키워드당 1회만 발동.
"""

from __future__ import annotations

from loguru import logger
from conversation.narration_hardcoded import find_trigger


class NarrationMonitor:
    """사용자 입력에서 키워드를 감지해 하드코딩 나레이션 텍스트를 반환한다."""

    def __init__(self):
        self._fired_keywords: set[str] = set()  # 세션 내 이미 발동된 키워드

    def check_keyword(self, user_input: str) -> str | None:
        """user_input에 키워드가 있고 이번 세션에 처음이면 나레이션 텍스트를 반환.

        없거나 이미 발동된 키워드면 None.
        """
        result = find_trigger(user_input)
        if result is None:
            return None
        kw, text = result
        if kw in self._fired_keywords:
            return None
        self._fired_keywords.add(kw)
        logger.debug(f"[narration_monitor] KEYWORD_TRIGGER: '{kw}'")
        return text
