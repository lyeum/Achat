"""나레이션 시스템 전체 플로우 테스트.

테스트 범위:
- Narrator: describe_action / describe_emotion / describe_arrival / describe_session_start
- NarrationMonitor: 트리거 판단 (ACTION_INPUT / MOOD_SHIFT / EMOTIONAL_PEAK / LOCATION_CHANGE / TIER_CROSS)
- NarrationMonitor: 쿨다운 억제 (COOLDOWN_TURNS)
- bridge.py: _ACTION_RE 패턴 감지, 세션 스냅샷 캡처

모든 테스트는 LLM을 MagicMock으로 대체해 실제 추론 없이 실행된다.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture()
def mock_llm():
    llm = MagicMock()
    llm.generate.return_value = "나레이션 텍스트."
    return llm


@pytest.fixture()
def character():
    return {
        "id":   "Haru",
        "name": "하루",
        "state": {
            "mood_default":      "neutral",
            "affection_default": 30,
            "affection_thresholds": {
                "low":  [0,  30],
                "mid":  [31, 60],
                "high": [61, 100],
            },
        },
    }


@pytest.fixture()
def world():
    return {"world_id": "test_world", "description": "테스트 세계관"}


@pytest.fixture()
def narrator(character, world, mock_llm):
    from conversation.narrator import Narrator
    return Narrator(character, world, mock_llm)


@pytest.fixture()
def session(character):
    from conversation.core.session import ConversationSession
    s = ConversationSession.from_character(character)
    return s


@pytest.fixture()
def monitor(narrator, character):
    from conversation.narration_monitor import NarrationMonitor
    return NarrationMonitor(narrator, character)


# ══════════════════════════════════════════════════════════════════════════════
# 1. Narrator 메서드 테스트
# ══════════════════════════════════════════════════════════════════════════════

class TestNarrator:
    def test_describe_action_calls_llm(self, narrator, mock_llm):
        result = narrator.describe_action("카페 창가에 앉았다", "neutral")
        assert mock_llm.generate.called
        assert isinstance(result, str) and result

    def test_describe_action_max_tokens_150(self, narrator, mock_llm):
        narrator.describe_action("자리를 잡았다", "happy")
        _, kwargs = mock_llm.generate.call_args
        assert kwargs.get("max_tokens", 0) <= 150

    def test_describe_emotion_calls_llm(self, narrator, mock_llm):
        recent = [
            {"role": "user",      "content": "오늘 힘들었어"},
            {"role": "assistant", "content": "그랬구나"},
        ]
        result = narrator.describe_emotion("touched", "mid", recent)
        assert mock_llm.generate.called
        assert isinstance(result, str) and result

    def test_describe_emotion_uses_recent_exchange(self, narrator, mock_llm):
        """recent_exchange가 프롬프트에 포함되는지 확인."""
        recent = [{"role": "user", "content": "테스트 발화"}]
        narrator.describe_emotion("sad", "low", recent)
        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt_text = messages[0]["content"]
        assert "테스트 발화" in prompt_text

    def test_describe_arrival_calls_llm(self, narrator, mock_llm):
        result = narrator.describe_arrival("카페", "조용한 분위기", "neutral")
        assert mock_llm.generate.called
        assert isinstance(result, str)

    def test_describe_session_start_calls_llm(self, narrator, mock_llm):
        result = narrator.describe_session_start("공원", "저녁 산책")
        assert mock_llm.generate.called
        assert isinstance(result, str)

    def test_describe_action_prompt_contains_action_text(self, narrator, mock_llm):
        narrator.describe_action("책상 위에 올려놓았다", "neutral")
        messages = mock_llm.generate.call_args[0][0]
        assert "책상 위에 올려놓았다" in messages[0]["content"]


# ══════════════════════════════════════════════════════════════════════════════
# 2. NarrationMonitor 트리거 테스트
# ══════════════════════════════════════════════════════════════════════════════

class TestNarrationMonitorActionInput:
    def test_action_input_triggers_immediately(self, monitor, session):
        """*...* 패턴 입력은 쿨다운 없이 즉시 나레이션을 반환한다."""
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="*카페 창가에 앉았다*",
        )
        assert result == "나레이션 텍스트."

    def test_action_input_calls_describe_action(self, character):
        """ACTION_INPUT은 describe_action()을 호출한다."""
        from conversation.core.session import ConversationSession
        from conversation.narration_monitor import NarrationMonitor

        mock_narrator = MagicMock()
        mock_narrator.describe_action.return_value = "나레이션 텍스트."
        mon = NarrationMonitor(mock_narrator, character)
        s = ConversationSession.from_character(character)

        mon.observe(
            session=s,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="*물건을 건넸다*",
        )
        mock_narrator.describe_action.assert_called_once()

    def test_action_input_updates_last_turn(self, monitor, session):
        """ACTION_INPUT 후 _last_narration_turn이 현재 turn_count로 갱신된다."""
        session.turn_count = 5
        monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="*앉았다*",
        )
        assert monitor._last_narration_turn == 5

    def test_action_input_not_matched_without_asterisks(self, monitor, session):
        """일반 텍스트는 ACTION_INPUT으로 처리되지 않는다."""
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="카페에 앉았어",
        )
        assert result is None  # 다른 트리거도 없으면 None


class TestNarrationMonitorCooldown:
    def test_cooldown_suppresses_non_action_triggers(self, monitor, session):
        """쿨다운 내에서는 MOOD_SHIFT 트리거가 억제된다."""
        # ACTION_INPUT으로 쿨다운 시작
        session.turn_count = 0
        monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="*앉았다*",
        )
        # 1턴 후 MOOD_SHIFT — 쿨다운(3턴) 이내이므로 억제
        session.mood = "happy"
        session.turn_count = 1
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="오늘 기분 좋아",
        )
        assert result is None

    def test_action_input_bypasses_cooldown(self, monitor, session):
        """ACTION_INPUT은 쿨다운 중에도 발동한다."""
        monitor._last_narration_turn = 100  # 아직 쿨다운 중
        session.turn_count = 101
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="*손을 내밀었다*",
        )
        assert result is not None

    def test_triggers_after_cooldown_passes(self, monitor, session):
        """쿨다운(3턴) 이후에는 MOOD_SHIFT 트리거가 다시 발동한다."""
        monitor._last_narration_turn = 0
        session.mood = "touched"
        session.turn_count = 3  # 정확히 COOLDOWN_TURNS — 발동 가능
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="고마워",
        )
        assert result is not None


class TestNarrationMonitorMoodShift:
    def test_mood_shift_triggers_narration(self, monitor, session):
        """mood가 neutral → 다른 값으로 바뀌면 나레이션이 발동한다."""
        session.mood = "happy"
        session.turn_count = 10  # 쿨다운 완전 해제
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="좋아",
        )
        assert result is not None

    def test_neutral_to_neutral_no_trigger(self, monitor, session):
        """neutral → neutral은 MOOD_SHIFT 트리거를 발동하지 않는다."""
        session.mood = "neutral"
        session.turn_count = 10
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="그냥",
        )
        assert result is None

    def test_emotional_peak_triggers(self, monitor, session):
        """affectionate / touched / angry는 EMOTIONAL_PEAK로 발동한다."""
        session.mood = "affectionate"
        session.turn_count = 10
        result = monitor.observe(
            session=session,
            prev_mood="affectionate",  # 같은 mood여도 peak이면 발동
            prev_affection=30,
            prev_act_id=None,
            user_input="...",
        )
        assert result is not None


class TestNarrationMonitorLocationChange:
    def test_location_change_triggers_arrival(self, monitor, session):
        """act_id가 바뀌면 LOCATION_CHANGE가 발동한다."""
        session.act_id = "cafe_act"
        session.location = "카페"
        session.turn_count = 10
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,       # None → "cafe_act" 변경
            user_input="카페 왔어",
        )
        assert result is not None

    def test_no_location_change_no_trigger(self, monitor, session):
        """act_id가 변하지 않으면 LOCATION_CHANGE가 발동하지 않는다."""
        session.act_id = "cafe_act"
        session.turn_count = 10
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id="cafe_act",  # 동일
            user_input="여기 좋다",
        )
        assert result is None


class TestNarrationMonitorTierCross:
    def test_tier_cross_triggers_narration(self, monitor, session):
        """affection이 tier 경계를 넘으면 TIER_CROSS가 발동한다."""
        session.affection = 35  # mid tier
        session.mood = "neutral"
        session.turn_count = 10
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=28,   # low tier → mid tier 경계 넘음
            prev_act_id=None,
            user_input="고마워",
        )
        assert result is not None

    def test_same_tier_no_trigger(self, monitor, session):
        """같은 tier 내에서는 TIER_CROSS가 발동하지 않는다."""
        session.affection = 35
        session.mood = "neutral"
        session.turn_count = 10
        result = monitor.observe(
            session=session,
            prev_mood="neutral",
            prev_affection=32,   # 둘 다 mid tier
            prev_act_id=None,
            user_input="오늘 뭐해",
        )
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# 3. bridge.py — _ACTION_RE 패턴 및 세션 스냅샷
# ══════════════════════════════════════════════════════════════════════════════

class TestBridgeActionPattern:
    def test_action_re_matches_asterisk_pattern(self):
        """_ACTION_RE가 *...* 패턴을 올바르게 매칭한다."""
        from ui_ux.bridge import _ACTION_RE
        m = _ACTION_RE.match("*카페에 앉았다*")
        assert m is not None
        assert m.group(1) == "카페에 앉았다"

    def test_action_re_no_match_plain_text(self):
        from ui_ux.bridge import _ACTION_RE
        assert _ACTION_RE.match("카페에 앉았다") is None

    def test_action_re_no_match_partial_asterisk(self):
        from ui_ux.bridge import _ACTION_RE
        assert _ACTION_RE.match("*카페에 앉았다") is None
        assert _ACTION_RE.match("카페에 앉았다*") is None


# ══════════════════════════════════════════════════════════════════════════════
# 4. 통합: NarrationMonitor + Narrator 플로우
# ══════════════════════════════════════════════════════════════════════════════

class TestNarrationFlow:
    @pytest.fixture()
    def mock_monitor(self, character):
        """Narrator가 MagicMock인 NarrationMonitor."""
        from conversation.narration_monitor import NarrationMonitor
        mock_narrator = MagicMock()
        mock_narrator.describe_action.return_value   = "나레이션 텍스트."
        mock_narrator.describe_emotion.return_value  = "나레이션 텍스트."
        mock_narrator.describe_arrival.return_value  = "나레이션 텍스트."
        return NarrationMonitor(mock_narrator, character)

    @pytest.fixture()
    def fresh_session(self, character):
        from conversation.core.session import ConversationSession
        return ConversationSession.from_character(character)

    def test_full_action_flow(self, mock_monitor, fresh_session):
        """ACTION_INPUT → describe_action 호출 → 나레이션 반환 전체 플로우."""
        fresh_session.turn_count = 5
        result = mock_monitor.observe(
            session=fresh_session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="*책을 펼쳤다*",
        )
        mock_monitor._narrator.describe_action.assert_called_once_with(
            "책을 펼쳤다", fresh_session.mood
        )
        assert result == "나레이션 텍스트."

    def test_mood_shift_flow_calls_describe_emotion(self, mock_monitor, fresh_session):
        """MOOD_SHIFT → describe_emotion 호출 플로우."""
        fresh_session.mood = "sad"
        fresh_session.turn_count = 10
        fresh_session.dialogue_log = [
            {"role": "user",      "content": "힘들어"},
            {"role": "assistant", "content": "..."},
        ]
        mock_monitor.observe(
            session=fresh_session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="힘들어",
        )
        mock_monitor._narrator.describe_emotion.assert_called_once()

    def test_location_change_flow_calls_describe_arrival(self, mock_monitor, fresh_session):
        """LOCATION_CHANGE → describe_arrival 호출 플로우."""
        fresh_session.act_id = "park_act"
        fresh_session.location = "공원"
        fresh_session.location_context = "나무가 많은 조용한 공원"
        fresh_session.turn_count = 10
        mock_monitor.observe(
            session=fresh_session,
            prev_mood="neutral",
            prev_affection=30,
            prev_act_id=None,
            user_input="공원 왔어",
        )
        mock_monitor._narrator.describe_arrival.assert_called_once()
        args = mock_monitor._narrator.describe_arrival.call_args[0]
        assert args[0] == "공원"
