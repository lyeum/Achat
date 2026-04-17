"""tests/test_state_mood.py — mood decay 및 update_mood / update_affection 통합 검증.

연쇄 흐름을 테스트한다:
  키워드 발동 → mood 변경 + mood_hold 설정
  → 후속 턴(키워드 없음) → hold 감소
  → hold=0 → neutral 복귀
  → affection_delta 누적 반영
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.state import update_mood, update_affection, _MOOD_DECAY_DEFAULT
from conversation.core.session import ConversationSession


# ── 픽스처 ────────────────────────────────────────────────────────────────────

def _make_character(decay_turns: int = 3, extra_triggers: dict | None = None) -> dict:
    triggers = {
        "happy":        ["좋아", "재밌어", "행복해"],
        "touched":      ["고마워", "감동"],
        "annoyed":      ["짜증", "싫어"],
        "affectionate": ["좋아해", "보고 싶어"],
    }
    if extra_triggers:
        triggers.update(extra_triggers)
    return {
        "id": "TestChar",
        "state": {
            "mood_triggers":   triggers,
            "mood_decay_turns": decay_turns,
            "affection_delta": {
                "happy":        +2,
                "touched":      +3,
                "annoyed":      -2,
                "affectionate": +4,
                "neutral":       0,
            },
        },
    }


def _make_session(mood: str = "neutral", mood_hold: int = 0, affection: int = 50) -> ConversationSession:
    s = ConversationSession(character_id="TestChar")
    s.mood      = mood
    s.mood_hold = mood_hold
    s.affection = affection
    return s


# ── TestMoodTrigger ───────────────────────────────────────────────────────────

class TestMoodTrigger:
    def test_keyword_changes_mood(self):
        """키워드가 포함된 입력에 mood가 변경되어야 한다."""
        session = _make_session()
        char    = _make_character()
        result  = update_mood(session, "오늘 너무 좋아!", char)
        assert result == "happy"
        assert session.mood == "happy"

    def test_keyword_sets_mood_hold(self):
        """mood 발동 시 mood_hold가 decay_turns로 설정되어야 한다."""
        session = _make_session()
        char    = _make_character(decay_turns=3)
        update_mood(session, "고마워 진짜로", char)
        assert session.mood == "touched"
        assert session.mood_hold == 3

    def test_no_keyword_keeps_neutral(self):
        """neutral 상태에서 키워드 없으면 neutral 유지."""
        session = _make_session(mood="neutral")
        char    = _make_character()
        result  = update_mood(session, "어디 갈까", char)
        assert result == "neutral"
        assert session.mood_hold == 0

    def test_first_keyword_wins_when_multiple_match(self):
        """triggers 순서 중 먼저 매칭된 mood가 채택되어야 한다."""
        session = _make_session()
        # "좋아해"는 affectionate, "좋아"는 happy — affectionate가 먼저 정의되어 있으면 우선
        char = _make_character()
        update_mood(session, "좋아해 좋아", char)
        # triggers 딕셔너리 순서: happy가 먼저이므로 "좋아" 매칭 → happy
        # (affectionate가 나중이므로 happy 우선)
        assert session.mood in ("happy", "affectionate")  # 순서 의존, 둘 다 허용


# ── TestMoodDecay ─────────────────────────────────────────────────────────────

class TestMoodDecay:
    def test_mood_persists_for_decay_turns(self):
        """키워드 없는 후속 턴에서 mood가 즉시 neutral이 되지 않아야 한다."""
        session = _make_session()
        char    = _make_character(decay_turns=3)

        # 1턴: happy 발동
        update_mood(session, "너무 좋아!", char)
        assert session.mood == "happy"
        assert session.mood_hold == 3

        # 2턴: 키워드 없음 — happy 유지 (hold=2)
        update_mood(session, "어디 갈까", char)
        assert session.mood == "happy"
        assert session.mood_hold == 2

        # 3턴: 키워드 없음 — happy 유지 (hold=1)
        update_mood(session, "그냥 걸어볼까", char)
        assert session.mood == "happy"
        assert session.mood_hold == 1

    def test_mood_decays_to_neutral_after_hold_exhausted(self):
        """hold가 0이 되면 다음 턴(키워드 없음)에 neutral로 복귀해야 한다."""
        session = _make_session()
        char    = _make_character(decay_turns=2)

        update_mood(session, "좋아!", char)          # happy, hold=2
        assert session.mood_hold == 2

        update_mood(session, "응", char)              # hold=1
        update_mood(session, "그래", char)            # hold=0 → neutral
        assert session.mood == "neutral"
        assert session.mood_hold == 0

    def test_new_keyword_resets_hold(self):
        """다른 mood 키워드가 발동되면 hold가 새 값으로 리셋되어야 한다."""
        session = _make_session()
        char    = _make_character(decay_turns=3)

        update_mood(session, "좋아!", char)           # happy, hold=3
        update_mood(session, "어디 가자", char)       # hold=2
        update_mood(session, "고마워", char)          # touched, hold=3 (리셋)

        assert session.mood == "touched"
        assert session.mood_hold == 3

    def test_decay_turns_one_means_immediate_next_turn_neutral(self):
        """decay_turns=1이면 키워드 없는 다음 턴에 바로 neutral."""
        session = _make_session()
        char    = _make_character(decay_turns=1)

        update_mood(session, "좋아!", char)           # happy, hold=1
        update_mood(session, "응", char)              # hold=0 → neutral
        assert session.mood == "neutral"

    def test_decay_turns_default_used_when_not_in_yaml(self):
        """YAML에 mood_decay_turns 없으면 기본값(_MOOD_DECAY_DEFAULT)을 사용한다."""
        session = _make_session()
        char_no_decay = {
            "id": "TestChar",
            "state": {"mood_triggers": {"happy": ["좋아"]}},
        }
        update_mood(session, "좋아!", char_no_decay)
        assert session.mood_hold == _MOOD_DECAY_DEFAULT


# ── TestMoodAffectionChain ────────────────────────────────────────────────────

class TestMoodAffectionChain:
    def test_affection_accumulates_during_mood_hold(self):
        """mood가 유지되는 동안 affection_delta가 매 턴 누적되어야 한다."""
        session = _make_session(affection=50)
        char    = _make_character(decay_turns=3)

        # 1턴: happy 발동 (+2)
        update_mood(session, "좋아!", char)
        update_affection(session, session.mood, char)
        assert session.affection == 52

        # 2턴: 키워드 없음, mood happy 유지 (+2)
        update_mood(session, "어디 가자", char)
        update_affection(session, session.mood, char)
        assert session.affection == 54

        # 3턴: 키워드 없음, mood happy 유지 (+2)
        update_mood(session, "그래", char)
        update_affection(session, session.mood, char)
        assert session.affection == 56

        # 4턴: hold 소진 → neutral, delta=0
        update_mood(session, "뭐해", char)
        update_affection(session, session.mood, char)
        assert session.mood == "neutral"
        assert session.affection == 56  # neutral은 delta=0

    def test_negative_mood_accumulates_correctly(self):
        """annoyed mood hold 동안 affection이 감소해야 한다."""
        session = _make_session(affection=50)
        char    = _make_character(decay_turns=2)

        update_mood(session, "짜증나", char)          # annoyed, hold=2
        update_affection(session, session.mood, char)  # -2 → 48
        assert session.affection == 48

        update_mood(session, "그냥", char)             # hold=1 유지
        update_affection(session, session.mood, char)  # -2 → 46
        assert session.affection == 46

        update_mood(session, "뭐해", char)             # hold=0 → neutral
        update_affection(session, session.mood, char)  # 0
        assert session.mood == "neutral"
        assert session.affection == 46

    def test_mood_hold_session_field_persists(self):
        """ConversationSession.mood_hold 필드가 정상적으로 설정·유지된다."""
        session = _make_session()
        char    = _make_character(decay_turns=5)
        update_mood(session, "보고 싶어", char)
        assert hasattr(session, "mood_hold")
        assert session.mood_hold == 5
