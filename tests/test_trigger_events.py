"""trigger_events 동작 검증 테스트.

테스트 범위:
- check_trigger_events(): 키워드 감지, aff_set/aff_delta, mood 전환
- cooldown_turns: 재발동 방지
- 발동 시 True 반환 (일반 update_mood/update_affection 건너뜀)
- trigger_events 없는 경우 False 반환
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _make_session(aff: int = 50, mood: str = "neutral"):
    from conversation.core.session import ConversationSession
    session = ConversationSession(
        character_id="TestChar",
        world_id=None,
        scenario_id=None,
        act_id=None,
    )
    session.affection = aff
    session.mood = mood
    return session


def _make_character(trigger_events: dict) -> dict:
    return {
        "id": "TestChar",
        "name": "테스트",
        "state": {
            "mood_default": "neutral",
            "affection_default": 30,
            "affection_thresholds": {
                "stranger": [0, 15], "acquaintance": [16, 30],
                "familiar": [31, 50], "friendly": [51, 70],
                "close": [71, 85], "intimate": [86, 100],
            },
            "mood_triggers": {},
            "affection_delta": {},
            "trigger_events": trigger_events,
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
class TestCheckTriggerEvents:

    def test_no_trigger_events_returns_false(self):
        from agent.state import check_trigger_events
        session = _make_session()
        char = _make_character({})
        assert check_trigger_events(session, "좋아해", char) is False

    def test_keyword_match_returns_true(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=50)
        char = _make_character({
            "confession": {"keywords": ["좋아해"], "aff_delta": 10, "mood": "embarrassed"}
        })
        result = check_trigger_events(session, "나 너 좋아해", char)
        assert result is True

    def test_no_keyword_match_returns_false(self):
        from agent.state import check_trigger_events
        session = _make_session()
        char = _make_character({
            "confession": {"keywords": ["좋아해"], "aff_delta": 10}
        })
        assert check_trigger_events(session, "그냥 잡담", char) is False

    def test_aff_delta_applied(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=50)
        char = _make_character({
            "panic": {"keywords": ["귀엽다"], "aff_delta": 5}
        })
        check_trigger_events(session, "너 진짜 귀엽다", char)
        assert session.affection == 55

    def test_aff_delta_negative(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=50)
        char = _make_character({
            "betrayal": {"keywords": ["배신했어"], "aff_delta": -20}
        })
        check_trigger_events(session, "배신했어 진짜", char)
        assert session.affection == 30

    def test_aff_set_overrides_delta(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=30)
        char = _make_character({
            "confession": {"keywords": ["사랑해"], "aff_set": 85}
        })
        check_trigger_events(session, "사랑해", char)
        assert session.affection == 85

    def test_mood_changed(self):
        from agent.state import check_trigger_events
        session = _make_session(mood="neutral")
        char = _make_character({
            "tease": {"keywords": ["귀엽다"], "aff_delta": 3, "mood": "embarrassed"}
        })
        check_trigger_events(session, "귀엽다", char)
        assert session.mood == "embarrassed"

    def test_mood_unchanged_when_not_specified(self):
        from agent.state import check_trigger_events
        session = _make_session(mood="happy")
        char = _make_character({
            "event": {"keywords": ["테스트"], "aff_delta": 1}
        })
        check_trigger_events(session, "테스트야", char)
        assert session.mood == "happy"

    def test_aff_clamped_to_100(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=98)
        char = _make_character({
            "big_event": {"keywords": ["최고야"], "aff_delta": 10}
        })
        check_trigger_events(session, "너 최고야", char)
        assert session.affection == 100

    def test_aff_clamped_to_0(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=5)
        char = _make_character({
            "betrayal": {"keywords": ["배신"], "aff_delta": -50}
        })
        check_trigger_events(session, "배신이야", char)
        assert session.affection == 0

    def test_cooldown_prevents_refiring(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=50)
        char = _make_character({
            "tease": {"keywords": ["귀엽다"], "aff_delta": 5, "cooldown_turns": 3}
        })
        r1 = check_trigger_events(session, "귀엽다", char)
        assert r1 is True
        assert session.affection == 55

        # 쿨다운 중 — 재발동 안 됨
        r2 = check_trigger_events(session, "귀엽다", char)
        assert r2 is False
        assert session.affection == 55  # 변화 없음

    def test_cooldown_expires_after_n_turns(self):
        from agent.state import check_trigger_events
        session = _make_session(aff=50)
        char = _make_character({
            "tease": {"keywords": ["귀엽다"], "aff_delta": 5, "cooldown_turns": 2}
        })
        check_trigger_events(session, "귀엽다", char)  # 발동, cooldown=2
        check_trigger_events(session, "무관한 말", char)  # cooldown=1
        check_trigger_events(session, "무관한 말", char)  # cooldown=0 → 만료
        r = check_trigger_events(session, "귀엽다", char)  # 재발동 가능
        assert r is True

    def test_only_one_event_fires_per_turn(self):
        """동일 턴에 두 이벤트 키워드가 모두 포함돼도 하나만 발동."""
        from agent.state import check_trigger_events
        session = _make_session(aff=50)
        char = _make_character({
            "event_a": {"keywords": ["A야"], "aff_delta": 10},
            "event_b": {"keywords": ["B야"], "aff_delta": 20},
        })
        check_trigger_events(session, "A야 B야", char)
        # 첫 번째 이벤트만 발동 → +10 또는 +20 (순서 의존)
        assert session.affection in (60, 70)
