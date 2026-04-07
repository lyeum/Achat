"""나레이션 시스템 테스트.

LLM 기반 Narrator는 제거됨 — 캐릭터 응답이 *묘사* 대사 형식을 직접 생성.

테스트 범위:
- NarrationMonitor.check_keyword(): 키워드 감지 / 세션 1회 제한
- narration_hardcoded.find_trigger(): 키워드 매칭
- bridge.py: _ACTION_RE 패턴 감지
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ══════════════════════════════════════════════════════════════════════════════
# 1. narration_hardcoded — find_trigger
# ══════════════════════════════════════════════════════════════════════════════

class TestFindTrigger:
    def test_returns_tuple_on_match(self):
        from conversation.narration_hardcoded import find_trigger
        result = find_trigger("오늘 카페에 갔어")
        assert result is not None
        kw, text = result
        assert kw == "카페"
        assert isinstance(text, str) and text

    def test_returns_none_on_no_match(self):
        from conversation.narration_hardcoded import find_trigger
        result = find_trigger("그냥 얘기하자")
        assert result is None

    def test_longer_keyword_matched_first(self):
        """'도서관'(3글자)이 '바다'(2글자)보다 길므로 '도서관'이 먼저 매칭된다."""
        from conversation.narration_hardcoded import find_trigger
        result = find_trigger("도서관에서 바다 내음이 났어")
        assert result is not None
        kw, _ = result
        assert kw == "도서관"

    def test_weather_keyword_matched(self):
        from conversation.narration_hardcoded import find_trigger
        result = find_trigger("비가 오는 날이야")
        assert result is not None
        assert result[0] == "비"

    def test_object_keyword_matched(self):
        from conversation.narration_hardcoded import find_trigger
        result = find_trigger("커피 한 잔 마셨어")
        assert result is not None
        assert result[0] == "커피"


# ══════════════════════════════════════════════════════════════════════════════
# 2. NarrationMonitor.check_keyword — 세션 1회 제한
# ══════════════════════════════════════════════════════════════════════════════

class TestNarrationMonitorKeyword:
    @pytest.fixture()
    def monitor(self):
        from conversation.narration_monitor import NarrationMonitor
        return NarrationMonitor()

    def test_first_trigger_returns_text(self, monitor):
        result = monitor.check_keyword("오늘 카페에 갔어")
        assert result is not None
        assert isinstance(result, str) and result

    def test_second_trigger_same_keyword_returns_none(self, monitor):
        monitor.check_keyword("카페에서 만나")
        result = monitor.check_keyword("카페 가자")  # 동일 키워드
        assert result is None

    def test_different_keywords_both_trigger(self, monitor):
        r1 = monitor.check_keyword("카페에서")
        r2 = monitor.check_keyword("공원에서")
        assert r1 is not None
        assert r2 is not None

    def test_no_match_returns_none(self, monitor):
        assert monitor.check_keyword("그냥 얘기나 하자") is None

    def test_fired_keywords_accumulate(self, monitor):
        monitor.check_keyword("카페 갔어")
        monitor.check_keyword("공원 갔어")
        assert "카페" in monitor._fired_keywords
        assert "공원" in monitor._fired_keywords

    def test_new_monitor_instance_resets_state(self):
        from conversation.narration_monitor import NarrationMonitor
        m1 = NarrationMonitor()
        m1.check_keyword("카페 갔어")
        assert m1.check_keyword("카페 또") is None  # m1에서는 이미 발동

        m2 = NarrationMonitor()
        assert m2.check_keyword("카페 가자") is not None  # m2는 새 세션


# ══════════════════════════════════════════════════════════════════════════════
# 3. bridge.py — _ACTION_RE 패턴 및 (행동:) 변환
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

    def test_action_converts_to_action_text(self):
        """*...* 입력이 (행동: ...) 형식으로 변환된다."""
        import re
        _ACTION_RE = re.compile(r"^\*(.+)\*$")
        text = "*창가에 앉았다*"
        m = _ACTION_RE.match(text.strip())
        assert m is not None
        converted = f"(행동: {m.group(1)})"
        assert converted == "(행동: 창가에 앉았다)"
