"""대화 품질 개선 관련 단위 테스트.

대화개선.md 항목 A~G에서 수정된 코드의 동작을 검증한다.
LLM / GPU / ChromaDB 불필요. 파일 I/O는 tmp_path 사용.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ACHAT_ENV", "ui_test")

_CHAR_DIR = ROOT / "conversation" / "character"
_HARU_YAML = _CHAR_DIR / "CH_Haru.yaml"
_SEONJAE_YAML = _CHAR_DIR / "CH_Seonjae.yaml"
_HARU_STRANGER = ROOT / "data" / "lora" / "conversation" / "haru_stranger.jsonl"


# ══════════════════════════════════════════════════════════════════════════════
# A. character_load.py — default YAML 필수 필드 검사 제외
# ══════════════════════════════════════════════════════════════════════════════

class TestCharacterLoad:
    @pytest.fixture
    def loguru_sink(self):
        """loguru 로그를 리스트에 캡처하는 픽스처."""
        from loguru import logger
        messages: list[str] = []
        sink_id = logger.add(lambda msg: messages.append(msg), level="WARNING")
        yield messages
        logger.remove(sink_id)

    def test_default_yaml_no_warning(self, loguru_sink):
        """CH_default.yaml 로드 시 '누락 필드' 경고가 출력되지 않아야 한다."""
        from conversation.loader.character_load import load_character
        data = load_character(_CHAR_DIR / "CH_default.yaml")
        assert data["id"] == "default"
        assert not any("누락 필드" in m for m in loguru_sink)

    def test_normal_character_missing_field_warns(self, tmp_path, loguru_sink):
        """필수 필드가 없는 일반 캐릭터 YAML은 경고를 출력해야 한다."""
        from conversation.loader.character_load import load_character
        incomplete = tmp_path / "CH_TestChar.yaml"
        incomplete.write_text("id: TestChar\nname: 테스트\n", encoding="utf-8")
        load_character(incomplete)
        assert any("누락 필드" in m for m in loguru_sink)

    def test_haru_loads_without_error(self):
        """CH_Haru.yaml 로드가 오류 없이 완료된다."""
        from conversation.loader.character_load import load_character
        data = load_character(_HARU_YAML)
        assert data["id"] == "Haru"

    def test_seonjae_loads_without_error(self):
        """CH_Seonjae.yaml 로드가 오류 없이 완료된다."""
        from conversation.loader.character_load import load_character
        data = load_character(_SEONJAE_YAML)
        assert data["id"] == "Seonjae"


# ══════════════════════════════════════════════════════════════════════════════
# C & G. CH_Haru.yaml / CH_Seonjae.yaml 규칙 강화 검증
# ══════════════════════════════════════════════════════════════════════════════

class TestCharacterYamlRules:
    @pytest.fixture(params=["CH_Haru.yaml", "CH_Seonjae.yaml"])
    def char_data(self, request):
        with open(_CHAR_DIR / request.param, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_speech_style_has_korean_only_rule(self, char_data):
        """rules에 '한국어가 아닌 다른 언어' 관련 문장이 포함되어야 한다.
        (스키마 변경: 언어 규칙은 speech → rules로 이동)
        """
        rules = char_data.get("rules", [])
        rules_text = " ".join(str(r) for r in rules)
        assert "한국어" in rules_text and "다른 언어" in rules_text, \
            f"rules에 언어 규칙 없음: {rules_text[:120]}"

    def test_speech_style_no_emotional_questions_to_strangers(self, char_data):
        """rules에 처음 만난 상대 감정 질문 금지 지시가 있어야 한다.
        (스키마 변경: stranger 제약은 speech → rules로 이동)
        """
        rules = char_data.get("rules", [])
        rules_text = " ".join(str(r) for r in rules)
        assert "처음 만난" in rules_text, \
            f"rules에 stranger 감정 질문 금지 없음: {rules_text[:120]}"

    def test_rules_contain_no_other_languages(self, char_data):
        """rules 목록에 다른 언어 금지 규칙이 있어야 한다."""
        rules = char_data.get("rules", [])
        assert any("다른 언어" in str(r) for r in rules), \
            "rules에 '다른 언어' 금지 항목 없음"

    def test_rules_contain_grammar_rule(self, char_data):
        """rules 목록에 조사 문법 규칙이 있어야 한다."""
        rules = char_data.get("rules", [])
        assert any("조사" in str(r) for r in rules), \
            "rules에 조사 문법 규칙 없음"

    def test_rules_contain_stranger_tier_restriction(self, char_data):
        """rules 목록에 stranger tier 감정 질문 금지가 있어야 한다."""
        rules = char_data.get("rules", [])
        assert any("stranger" in str(r) or "처음 만난" in str(r) for r in rules), \
            "rules에 stranger tier 감정 질문 금지 없음"


# ══════════════════════════════════════════════════════════════════════════════
# D. memory/summarizer.py — 이름 importance 보완
# ══════════════════════════════════════════════════════════════════════════════

class TestSummarizerImportance:
    @pytest.fixture(autouse=True)
    def import_fn(self):
        from memory.summarizer import score_importance
        self.score = score_importance

    def test_name_colon_format_scores_high(self):
        """'이름: X' 형태는 최고 중요도(1.0)를 받아야 한다."""
        assert self.score("사용자의 이름: 김철수라고 밝혔다.") == 1.0

    def test_name_eun_scores_high(self):
        """'이름은' 키워드 → 1.0."""
        assert self.score("이름은 민지라고 했다.") == 1.0

    def test_name_i_scores_high(self):
        """'이름이' 키워드 → 1.0."""
        assert self.score("이름이 뭔지 물어봤다.") == 1.0

    def test_plain_name_scores_high(self):
        """'이름' 단독 키워드 → 1.0."""
        assert self.score("자신의 이름을 소개했다.") == 1.0

    def test_promise_scores_high(self):
        """'약속' 키워드 → 0.85."""
        assert self.score("다음에 만나기로 약속했다.") == 0.85

    def test_mid_keyword_scores_mid(self):
        """high 키워드 없고 mid 키워드만 있으면 0.6을 반환해야 한다."""
        assert self.score("취미가 독서라고 했다.") == 0.6

    def test_mid_keyword_feeling_scores_mid(self):
        """'감정' mid 키워드 → 0.6."""
        assert self.score("오늘 기분이 좋다고 말했다.") == 0.6

    def test_no_keyword_scores_default(self):
        """키워드 없는 일반 대화 → 기본값 0.5 반환."""
        assert self.score("날씨 얘기를 했다.") == 0.5

    def test_high_keyword_overrides_mid(self):
        """이름 키워드가 있으면 mid 키워드 무관하게 1.0을 반환해야 한다."""
        assert self.score("이름은 민지. 취미는 독서.") == 1.0


# ══════════════════════════════════════════════════════════════════════════════
# E. training/scripts/build_sft_from_feedback.py 변환 검증
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildSftFromFeedback:
    @pytest.fixture
    def feedback_dir(self, tmp_path):
        """단일 feedback_pos JSONL 파일이 있는 임시 디렉토리."""
        entry = {
            "messages": [
                {"role": "user", "content": "안녕"},
                {"role": "assistant", "content": "어."},
            ],
            "character_id": "Haru",
            "affection": "low",
        }
        f = tmp_path / "test_session.jsonl"
        f.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
        return tmp_path

    def test_convert_returns_records(self, feedback_dir):
        """변환 결과가 1개 이상의 레코드를 포함해야 한다."""
        import training.scripts.build_sft_from_feedback as mod
        with patch.object(mod, "_FEEDBACK_POS_DIR", feedback_dir):
            records = mod.convert()
        assert len(records) == 1

    def test_sft_entry_has_messages_key(self, feedback_dir):
        """변환 결과 각 항목은 'messages' 키를 가져야 한다."""
        import training.scripts.build_sft_from_feedback as mod
        with patch.object(mod, "_FEEDBACK_POS_DIR", feedback_dir):
            records = mod.convert()
        assert "messages" in records[0]

    def test_first_message_is_system(self, feedback_dir):
        """messages[0]의 role은 'system'이어야 한다."""
        import training.scripts.build_sft_from_feedback as mod
        with patch.object(mod, "_FEEDBACK_POS_DIR", feedback_dir):
            records = mod.convert()
        assert records[0]["messages"][0]["role"] == "system"

    def test_system_prompt_contains_character_name(self, feedback_dir):
        """시스템 프롬프트에 캐릭터 이름(하루)이 포함되어야 한다."""
        import training.scripts.build_sft_from_feedback as mod
        with patch.object(mod, "_FEEDBACK_POS_DIR", feedback_dir):
            records = mod.convert()
        system_content = records[0]["messages"][0]["content"]
        assert "하루" in system_content

    def test_affection_low_maps_to_stranger(self, feedback_dir):
        """affection='low' → stranger tier tone_guide가 시스템 프롬프트에 포함된다."""
        import training.scripts.build_sft_from_feedback as mod
        with patch.object(mod, "_FEEDBACK_POS_DIR", feedback_dir):
            records = mod.convert()
        system_content = records[0]["messages"][0]["content"]
        assert "처음 만난" in system_content or "경계" in system_content

    def test_reviewed_only_filters_unreviewed(self, feedback_dir):
        """--reviewed_only 옵션 시 reviewed=true 항목만 포함된다."""
        import training.scripts.build_sft_from_feedback as mod
        with patch.object(mod, "_FEEDBACK_POS_DIR", feedback_dir):
            records = mod.convert(reviewed_only=True)
        assert len(records) == 0  # 픽스처 항목은 reviewed 없음

    def test_reviewed_only_includes_reviewed_entry(self, tmp_path):
        """reviewed=true인 항목은 --reviewed_only 시에도 포함된다."""
        import training.scripts.build_sft_from_feedback as mod
        entry = {
            "messages": [{"role": "user", "content": "안녕"}, {"role": "assistant", "content": "응."}],
            "character_id": "Haru",
            "affection": "mid",
            "reviewed": True,
        }
        f = tmp_path / "reviewed.jsonl"
        f.write_text(json.dumps(entry, ensure_ascii=False) + "\n", encoding="utf-8")
        with patch.object(mod, "_FEEDBACK_POS_DIR", tmp_path):
            records = mod.convert(reviewed_only=True)
        assert len(records) == 1

    def test_empty_dir_returns_empty_list(self, tmp_path):
        """빈 디렉토리는 빈 리스트를 반환한다."""
        import training.scripts.build_sft_from_feedback as mod
        with patch.object(mod, "_FEEDBACK_POS_DIR", tmp_path):
            records = mod.convert()
        assert records == []

    def test_save_writes_jsonl(self, tmp_path):
        """save()가 올바른 JSONL을 파일에 기록한다."""
        import training.scripts.build_sft_from_feedback as mod
        records = [{"messages": [{"role": "system", "content": "test"}]}]
        out = tmp_path / "out.jsonl"
        mod.save(records, out)
        lines = out.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["messages"][0]["role"] == "system"


# ══════════════════════════════════════════════════════════════════════════════
# F. data/lora/conversation/haru_stranger.jsonl 구조 검증
# ══════════════════════════════════════════════════════════════════════════════

class TestHaruStrangerJsonl:
    @pytest.fixture(scope="class")
    def records(self):
        assert _HARU_STRANGER.exists(), f"haru_stranger.jsonl 없음: {_HARU_STRANGER}"
        result = []
        with open(_HARU_STRANGER, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    result.append(json.loads(line))
        return result

    def test_minimum_record_count(self, records):
        """최소 10개 이상의 대화 예시가 있어야 한다."""
        assert len(records) >= 10, f"레코드 수 부족: {len(records)}"

    def test_all_have_messages_key(self, records):
        for i, rec in enumerate(records):
            assert "messages" in rec, f"레코드 {i}: 'messages' 키 없음"

    def test_first_message_is_system(self, records):
        for i, rec in enumerate(records):
            assert rec["messages"][0]["role"] == "system", \
                f"레코드 {i}: 첫 메시지가 system 아님"

    def test_system_prompt_has_stranger_tone(self, records):
        """시스템 프롬프트에 stranger tier 톤 지시가 포함되어야 한다."""
        for i, rec in enumerate(records):
            sys_content = rec["messages"][0]["content"]
            assert "처음 만난" in sys_content or "경계" in sys_content, \
                f"레코드 {i}: stranger 톤 지시 없음"

    def test_has_user_and_assistant_turns(self, records):
        """system 이후에 user, assistant 메시지가 번갈아 나와야 한다."""
        for i, rec in enumerate(records):
            turns = rec["messages"][1:]  # system 제외
            assert len(turns) >= 2, f"레코드 {i}: 대화 턴 부족"
            roles = [m["role"] for m in turns]
            assert "user" in roles and "assistant" in roles, \
                f"레코드 {i}: user/assistant 턴 없음"

    def test_assistant_responses_are_short(self, records):
        """stranger tier 응답은 짧아야 한다 (평균 20자 이하)."""
        for i, rec in enumerate(records):
            assistant_msgs = [m["content"] for m in rec["messages"] if m["role"] == "assistant"]
            if assistant_msgs:
                avg_len = sum(len(m) for m in assistant_msgs) / len(assistant_msgs)
                assert avg_len <= 25, \
                    f"레코드 {i}: assistant 응답 평균 {avg_len:.1f}자 (기대 ≤ 25자)"


# ══════════════════════════════════════════════════════════════════════════════
# prompt_build.py — YAML rules 포함 및 이름 형식 검증
# ══════════════════════════════════════════════════════════════════════════════

class TestPromptBuildLayerA:
    @pytest.fixture
    def builder(self):
        from conversation.core.prompt_build import PromptBuilder
        from conversation.loader.character_load import load_character
        from conversation.core.session import ConversationSession

        char = load_character(_HARU_YAML)
        world = {"description": "테스트 세계관", "scenarios": []}
        session = ConversationSession.__new__(ConversationSession)
        session.mood = "neutral"
        session.affection = 5          # stranger tier
        session.scenario_id = None
        session.act_id = None
        session.location_context = ""
        return PromptBuilder(char, world, session)

    def test_name_format_is_naneun(self, builder):
        """시스템 프롬프트가 '너는 하루이다.' 형식으로 시작해야 한다."""
        layer_a = builder._layer_a()
        assert layer_a.startswith("너는 하루이다."), \
            f"이름 형식 불일치: {layer_a[:40]}"

    def test_rules_in_system_prompt(self, builder):
        """YAML rules의 내용이 시스템 프롬프트에 포함되어야 한다."""
        layer_a = builder._layer_a()
        # 새로 추가된 규칙 확인
        assert "다른 언어" in layer_a, "언어 금지 규칙이 Layer A에 없음"
        assert "조사" in layer_a, "조사 문법 규칙이 Layer A에 없음"

    def test_speech_style_in_system_prompt(self, builder):
        """speech_style 내용이 시스템 프롬프트에 포함되어야 한다."""
        layer_a = builder._layer_a()
        assert "반말" in layer_a

    def test_stranger_tone_in_system_prompt(self, builder):
        """affection=5 → stranger tier 톤 지시가 포함되어야 한다."""
        layer_a = builder._layer_a()
        assert "처음 만난" in layer_a or "경계" in layer_a


# ══════════════════════════════════════════════════════════════════════════════
# H. Affection 관리자 조절 + 잠금 (기능개선.md 1번)
# ══════════════════════════════════════════════════════════════════════════════

class TestAffectionAdminControl:
    """agent/state.py + conversation/core/session.py 잠금 동작 검증."""

    @pytest.fixture
    def session(self):
        from conversation.core.session import ConversationSession
        s = ConversationSession(character_id="Haru")
        s.affection = 50
        return s

    def test_lock_fields_default(self, session):
        """기본 세션은 잠금 해제 상태여야 한다."""
        assert session.affection_locked is False
        assert session.affection_lock_value is None

    def test_update_affection_normal(self, session):
        """잠금 없이 정상 update_affection 동작."""
        from agent.state import update_affection
        session.mood = "happy"
        result = update_affection(session, "happy")
        assert result == session.affection
        assert session.affection == 53  # +3

    def test_lock_prevents_update(self, session):
        """잠금 상태에서 update_affection은 lock_value로 고정한다."""
        from agent.state import update_affection
        session.affection_locked = True
        session.affection_lock_value = 40
        session.affection = 40
        # happy mood(+3)를 줘도 변화 없어야 함
        result = update_affection(session, "happy")
        assert result == 40
        assert session.affection == 40

    def test_lock_clamps_to_range(self, session):
        """lock_value가 범위를 벗어나면 클램핑된다."""
        from agent.state import update_affection
        session.affection_locked = True
        session.affection_lock_value = 150  # 범위 초과
        session.affection = 50
        update_affection(session, "happy")
        assert session.affection == 100

    def test_unlock_resumes_update(self, session):
        """잠금 해제 후 정상 update_affection이 재개된다."""
        from agent.state import update_affection
        session.affection_locked = True
        session.affection_lock_value = 40
        session.affection = 40
        # 잠금 해제
        session.affection_locked = False
        session.affection_lock_value = None
        result = update_affection(session, "affectionate")  # +5
        assert result == 45
        assert session.affection == 45

    def test_lock_without_lock_value_keeps_current(self, session):
        """lock_value=None인 잠금 상태: 현재값을 그대로 유지한다."""
        from agent.state import update_affection
        session.affection = 60
        session.affection_locked = True
        session.affection_lock_value = None
        result = update_affection(session, "angry")  # -5이지만 잠금
        assert result == 60
        assert session.affection == 60


# ══════════════════════════════════════════════════════════════════════════════
# I. Semantic Score 기반 Affection 게이팅 (기능개선.md 2번)
# ══════════════════════════════════════════════════════════════════════════════

class TestAffectionSemanticGating:
    """score_importance 게이팅 동작 및 config 키 검증."""

    def test_config_has_aff_gate_threshold(self):
        """모든 환경 config에 aff_gate_threshold가 존재해야 한다."""
        from config import _CONFIGS
        for env_name, cfg in _CONFIGS.items():
            assert "aff_gate_threshold" in cfg, f"{env_name} config에 aff_gate_threshold 없음"

    def test_router_reads_aff_gate_from_config(self):
        """ConversationRouter가 config에서 aff_gate_threshold를 읽어야 한다."""
        from unittest.mock import MagicMock
        from conversation.core.router import ConversationRouter
        from conversation.core.session import ConversationSession

        char = {"id": "Haru", "name": "하루", "state": {}, "rules": [], "speech_style": ""}
        world = {"world_id": "W1", "scenarios": []}
        session = ConversationSession(character_id="Haru")
        llm = MagicMock()
        lt = MagicMock()
        lt.query.return_value = []
        cfg = {"aff_gate_threshold": 0.75, "memory_trigger_n": 10, "chroma_path": "./chroma_dev"}

        with patch("rag.retrieve.WorldRetriever.__init__", return_value=None), \
             patch("rag.retrieve.WorldRetriever.query", return_value=[]):
            router = ConversationRouter(char, world, session, llm, lt, cfg)
        assert router._aff_gate == 0.75

    def test_low_importance_suppresses_affection(self):
        """잡담(importance=0.5) 발화는 affection을 변화시키지 않는다."""
        from memory.summarizer import score_importance
        # 키워드 없는 잡담
        score = score_importance("오늘 날씨 좋다")
        assert score == 0.5  # low → 게이팅

    def test_mid_importance_allows_affection(self):
        """감정 표현(importance>=0.6) 발화는 affection 변화를 허용한다."""
        from memory.summarizer import score_importance
        score = score_importance("요즘 기분이 좀 슬퍼")
        assert score >= 0.6  # mid → 게이팅 통과

    def test_high_importance_allows_affection(self):
        """이름(importance=1.0) 발화는 반드시 affection 변화를 허용한다."""
        from memory.summarizer import score_importance
        score = score_importance("내 이름은 민준이야")
        assert score >= 0.6  # high → 게이팅 통과
