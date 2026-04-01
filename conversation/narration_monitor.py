"""conversation/narration_monitor.py — 나레이션 트리거 판단.

매 턴 완료 후 세션 상태 변화를 분석해 나레이션 트리거 여부를 rule-based로 판단한다.
LLM 추가 호출 없이 결정 — 나레이션 생성만 Narrator에 위임.

트리거 ID   조건                                              우선순위
-----------  ------------------------------------------------  --------
ACTION_INPUT  사용자 입력이 *...* 패턴                          1 (쿨다운 예외)
MOOD_SHIFT    prev_mood != curr_mood, curr_mood != neutral      2
EMOTIONAL_PEAK mood in {affectionate, touched, angry}          2
TIER_CROSS    affection이 tier 경계를 넘음                      3
LOCATION_CHANGE act_id 또는 location_context 변경              3
COOLDOWN      마지막 나레이션으로부터 COOLDOWN_TURNS 이내        억제
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from conversation.narrator import Narrator
    from conversation.core.session import ConversationSession

_ACTION_RE = re.compile(r"^\*(.+)\*$")

_EMOTIONAL_PEAK_MOODS = {"affectionate", "touched", "angry"}

# affection tier 경계값 기준 — threshold 설정과 독립적으로 관리
# (bridge.py에도 thresholds 파싱이 있으나 여기선 character YAML에서 직접 읽음)


class NarrationMonitor:
    """매 턴 세션 상태를 분석해 나레이션 트리거를 판단한다."""

    COOLDOWN_TURNS = 3  # 나레이션 최소 간격 (ACTION_INPUT 예외)

    def __init__(self, narrator: "Narrator", character: dict):
        self._narrator  = narrator
        self._character = character
        self._last_narration_turn: int = -self.COOLDOWN_TURNS  # 초기값: 쿨다운 없음

    # ── 공개 API ────────────────────────────────────────────────────────

    def observe(
        self,
        session: "ConversationSession",
        prev_mood: str,
        prev_affection: int,
        prev_act_id: str | None,
        user_input: str,
    ) -> str | None:
        """트리거 판단 → 해당 시 나레이션 문자열 반환, 없으면 None.

        주의: 백그라운드 스레드에서 호출되므로 session은 응답 직전 스냅샷이어야 함.
        """
        curr_turn   = session.turn_count
        curr_mood   = session.mood
        curr_aff    = session.affection
        curr_act_id = session.act_id

        # ── ACTION_INPUT: 쿨다운 예외, 즉시 발동 ────────────────────────
        action_match = _ACTION_RE.match(user_input.strip())
        if action_match:
            action_text = action_match.group(1)
            narration = self._narrator.describe_action(action_text, curr_mood)
            self._last_narration_turn = curr_turn
            logger.debug(f"[narration_monitor] ACTION_INPUT 트리거: '{action_text}'")
            return narration

        # ── 쿨다운 체크 (ACTION_INPUT 이외 트리거) ───────────────────────
        if curr_turn - self._last_narration_turn < self.COOLDOWN_TURNS:
            logger.debug(
                f"[narration_monitor] 쿨다운 억제 "
                f"(last={self._last_narration_turn}, curr={curr_turn})"
            )
            return None

        # ── LOCATION_CHANGE ─────────────────────────────────────────────
        if curr_act_id != prev_act_id and curr_act_id is not None:
            location_name    = session.location or curr_act_id
            location_context = session.location_context or ""
            narration = self._narrator.describe_arrival(
                location_name, location_context, curr_mood
            )
            self._last_narration_turn = curr_turn
            logger.debug(f"[narration_monitor] LOCATION_CHANGE 트리거: '{curr_act_id}'")
            return narration

        # ── MOOD_SHIFT / EMOTIONAL_PEAK ──────────────────────────────────
        mood_shifted = (prev_mood != curr_mood) and (curr_mood != "neutral")
        emotional_peak = curr_mood in _EMOTIONAL_PEAK_MOODS

        if mood_shifted or emotional_peak:
            affection_tier = self._get_affection_tier(curr_aff)
            recent = session.dialogue_log[-6:]  # 최근 3턴 (user+assistant 쌍)
            narration = self._narrator.describe_emotion(
                curr_mood, affection_tier, recent
            )
            self._last_narration_turn = curr_turn
            trigger_name = "EMOTIONAL_PEAK" if emotional_peak else "MOOD_SHIFT"
            logger.debug(
                f"[narration_monitor] {trigger_name} 트리거: "
                f"{prev_mood} → {curr_mood}"
            )
            return narration

        # ── TIER_CROSS ───────────────────────────────────────────────────
        prev_tier = self._get_affection_tier(prev_affection)
        curr_tier = self._get_affection_tier(curr_aff)
        if prev_tier != curr_tier:
            affection_tier = curr_tier
            recent = session.dialogue_log[-6:]
            narration = self._narrator.describe_emotion(
                curr_mood, affection_tier, recent
            )
            self._last_narration_turn = curr_turn
            logger.debug(
                f"[narration_monitor] TIER_CROSS 트리거: "
                f"{prev_tier} → {curr_tier}"
            )
            return narration

        return None

    # ── 내부 유틸 ────────────────────────────────────────────────────────

    def _get_affection_tier(self, affection: int) -> str:
        thresholds: dict = (
            self._character.get("state", {}).get("affection_thresholds", {})
        )
        for tier, bounds in thresholds.items():
            if bounds[0] <= affection <= bounds[1]:
                return tier
        return "mid"
