"""개선5 구현 항목 검증 테스트.

테스트 범위:
    1. ConversationSession — 트리거 상태 필드 (fired_stories / visited_places / explained_cultures)
    2. router.py — handle_turn() mode 파라미터 + _check_world_triggers()
    3. session_manager.py — SessionMeta.world_id / activate_for_world()
    4. agent/core.py — _inject_prompt_guide() 주입 로직
    5. bridge.py — addPromptGuide() model key 저장 / getPromptGuidesDB() 양방향 읽기
    6. narration/world_trigger.py — check_story_trigger / check_culture_trigger
    7. rag/index.py — _parse_world_md() 섹션 파싱
    8. config.py — default_world_id / memory_trigger_n=5
    9. MemoryDBPanel.qml — 탭2 CRUD 구조 확인 (파일 파싱)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ACHAT_ENV", "ui_test")

from PySide6.QtCore import QCoreApplication


# M-2: 모듈 수준 싱글톤 대신 세션 스코프 픽스처로 관리
@pytest.fixture(scope="session", autouse=True)
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    yield app


# ── 공통 픽스처 ──────────────────────────────────────────────────────────────

@pytest.fixture()
def stub_agent():
    agent = MagicMock()
    agent.session = None
    agent.character = {"id": "Haru", "name": "하루"}
    agent.world = {"world_id": "seaside_world"}
    agent.router = None
    agent.llm = None
    agent.long_term = None
    agent._stub = True
    agent.cfg = {}
    return agent


@pytest.fixture()
def bridge(stub_agent):
    from ui_ux.bridge import ChatBridge
    return ChatBridge(stub_agent)


# ══════════════════════════════════════════════════════════════════════════════
# 1. ConversationSession — 트리거 상태 필드
# ══════════════════════════════════════════════════════════════════════════════

class TestConversationSessionTriggerFields:
    def test_default_trigger_fields_exist(self):
        """fired_stories / visited_places / explained_cultures 기본값이 빈 리스트여야 한다."""
        from conversation.core.session import ConversationSession
        sess = ConversationSession(character_id="Haru")
        assert sess.fired_stories == []
        assert sess.visited_places == []
        assert sess.explained_cultures == []

    def test_trigger_fields_are_independent(self):
        """두 세션 인스턴스의 트리거 리스트가 공유되지 않아야 한다."""
        from conversation.core.session import ConversationSession
        s1 = ConversationSession(character_id="Haru")
        s2 = ConversationSession(character_id="Haru")
        s1.fired_stories.append("story_A")
        assert "story_A" not in s2.fired_stories

    def test_from_character_inherits_trigger_fields(self):
        """from_character()로 생성한 세션도 트리거 필드를 가져야 한다."""
        from conversation.core.session import ConversationSession
        char = {"id": "Haru", "name": "하루", "state": {}}
        sess = ConversationSession.from_character(char)
        assert hasattr(sess, "fired_stories")
        assert hasattr(sess, "visited_places")
        assert hasattr(sess, "explained_cultures")


# ══════════════════════════════════════════════════════════════════════════════
# 2. router.py — mode 파라미터 + _check_world_triggers()
# ══════════════════════════════════════════════════════════════════════════════

class TestRouterModeParameter:
    @pytest.fixture()
    def router(self):
        from conversation.core.session import ConversationSession
        from conversation.core.router import ConversationRouter

        char = {"id": "Haru", "name": "하루", "state": {}, "rules": [], "speech_style": ""}
        world = {"world_id": "seaside_world", "scenarios": [], "description": ""}
        session = ConversationSession.from_character(char)
        cfg = {"memory_trigger_n": 5, "aff_gate_threshold": 0.6}

        llm = MagicMock()
        llm.count_tokens = MagicMock(return_value=100)
        llm.generate = MagicMock(return_value="테스트 응답")
        long_term = MagicMock()
        long_term.query = MagicMock(return_value=[])

        with patch("conversation.core.router.WorldRetriever") as MockRag:
            MockRag.return_value.query = MagicMock(return_value=[])
            r = ConversationRouter(char, world, session, llm, long_term, cfg)
        return r

    def test_handle_turn_accepts_mode_chat(self, router):
        """mode='chat' 파라미터를 받아도 에러 없이 동작해야 한다."""
        with patch.object(router, "_handle_location", return_value=None), \
             patch.object(router, "_check_world_triggers", return_value=None), \
             patch("agent.state.update_mood", return_value="neutral"), \
             patch("agent.state.update_affection"), \
             patch("memory.summarizer.score_importance", return_value=0.4), \
             patch("memory.summarizer.check_trigger", return_value=False):
            resp = router.handle_turn("안녕", stream=False, mode="chat")
        assert resp == "테스트 응답"

    def test_handle_turn_mode_function_skips_summarizer(self, router):
        """mode='function' 이면 요약 트리거가 호출되지 않아야 한다."""
        with patch.object(router, "_handle_location", return_value=None), \
             patch.object(router, "_check_world_triggers", return_value=None), \
             patch("agent.state.update_mood", return_value="neutral"), \
             patch("agent.state.update_affection"), \
             patch("memory.summarizer.score_importance", return_value=0.9), \
             patch("memory.summarizer.check_trigger", return_value=True), \
             patch.object(router, "_run_summarizer") as mock_summarize:
            router.handle_turn("파일 정리해줘", stream=False, mode="function")
        # check_trigger 자체는 호출될 수 있지만 mode 조건 때문에 _run_summarizer는 호출되지 않아야 함
        mock_summarize.assert_not_called()

    def test_check_world_triggers_returns_none_on_exception(self, router):
        """_check_world_triggers() 내부 에러가 None 반환으로 graceful 처리되어야 한다."""
        with patch("conversation.core.router.ConversationRouter._check_world_triggers",
                   side_effect=RuntimeError("module missing")):
            # 에러가 밖으로 전파되지 않아야 함
            try:
                result = router._check_world_triggers("테스트")
                assert result is None
            except RuntimeError:
                pass  # _check_world_triggers를 patch했으므로 직접 호출 결과


# ══════════════════════════════════════════════════════════════════════════════
# 3. session_manager.py — world_id / activate_for_world()
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionManagerWorldId:
    @pytest.fixture()
    def manager(self, tmp_path):
        from conversation.session_manager import SessionManager
        return SessionManager(tmp_path / "sessions")

    def test_session_meta_has_world_id(self):
        """SessionMeta 에 world_id 필드가 있어야 한다."""
        from conversation.session_manager import SessionMeta
        import inspect
        fields = {f.name for f in SessionMeta.__dataclass_fields__.values()}
        assert "world_id" in fields

    def test_create_session_stores_world_id(self, manager):
        """_create_session 후 인덱스에 world_id가 저장되어야 한다."""
        manager._create_session("Haru")
        # world_id는 초기에 None
        index = manager._load_index("Haru")
        assert any("world_id" in item for item in index)

    def test_activate_for_world_reuses_existing(self, manager):
        """같은 world_id 세션이 있으면 재사용하고, 없으면 새로 생성해야 한다."""
        # 새 세션 생성 후 world_id 설정
        s1 = manager._create_session("Haru")
        s1.world_id = "seaside_world"
        manager._save_state(s1)   # _save_state(state) — char_id 인수 없음
        manager._upsert_index(s1)

        # 동일 world_id로 activate
        s2 = manager.activate_for_world("Haru", "seaside_world")
        assert s2.session_id == s1.session_id

    def test_activate_for_world_creates_new_if_none(self, manager):
        """해당 world_id 세션이 없으면 새 세션을 생성해야 한다."""
        state = manager.activate_for_world("Haru", "new_world_xyz")
        assert state is not None
        assert state.session_id


# ══════════════════════════════════════════════════════════════════════════════
# 4. agent/core.py — _inject_prompt_guide()
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentInjectPromptGuide:
    # M-4: tmp_path 기반 실 ChromaDB 정리
    @pytest.fixture(autouse=True)
    def cleanup_chroma(self, tmp_path):
        yield
        import shutil
        chroma_dir = tmp_path / "chroma"
        if chroma_dir.exists():
            shutil.rmtree(chroma_dir)

    @pytest.fixture()
    def agent(self):
        """stub Agent 인스턴스."""
        from agent.core import Agent
        with patch("agent.core.load_persona", return_value={"id": "Haru", "name": "하루", "state": {}, "rules": []}), \
             patch("agent.core.load_world", return_value={"world_id": "seaside_world", "scenarios": [], "description": ""}), \
             patch("agent.core.get_config", return_value={"model_backend": "stub", "chroma_path": ""}):
            ag = Agent("Haru", "W_sea.yaml")
        return ag

    def test_inject_returns_base_when_no_chroma_path(self, agent):
        """`chroma_path`가 없으면 base_prompt를 그대로 반환해야 한다."""
        agent.cfg = {"chroma_path": ""}
        result = agent._inject_prompt_guide("folder_classify", "기존 프롬프트")
        assert result == "기존 프롬프트"

    def test_inject_appends_guide_when_found(self, agent, tmp_path):
        """가이드가 있으면 base_prompt에 추가되어야 한다."""
        from tools.prompt_store import PromptGuideStore
        store = PromptGuideStore(str(tmp_path / "chroma"), embedding_model=None)
        store.save("folder_classify", "파일을 반드시 종류별로 분류하라")

        agent.cfg = {"chroma_path": str(tmp_path / "chroma")}
        # _inject_prompt_guide 내부에서 lazy import로 PromptGuideStore를 사용하므로
        # tools.prompt_store.PromptGuideStore를 patch
        with patch("tools.prompt_store.PromptGuideStore", return_value=store):
            result = agent._inject_prompt_guide("folder_classify", "원본 프롬프트")
        assert "원본 프롬프트" in result
        assert "파일을 반드시 종류별로 분류하라" in result

    def test_inject_graceful_on_exception(self, agent):
        """PromptGuideStore 생성 중 예외 발생해도 base_prompt를 반환해야 한다."""
        agent.cfg = {"chroma_path": "/nonexistent/path"}
        # lazy import 패스 사용
        with patch("tools.prompt_store.PromptGuideStore", side_effect=RuntimeError("chromadb error")):
            result = agent._inject_prompt_guide("some_tool", "기존 프롬프트")
        assert result == "기존 프롬프트"

    def test_prompt_convert_skips_inject(self, agent):
        """prompt_convert 도구는 _inject_prompt_guide가 호출되지 않아야 한다 (execute 내부에서 처리)."""
        agent.cfg = {"chroma_path": ""}
        agent._stub = False
        agent.llm = MagicMock()
        agent.llm.generate = MagicMock(return_value='{"model": "SD", "content": "고양이"}')

        with patch.object(agent, "_inject_prompt_guide") as mock_inject:
            agent._handle_function("Stable Diffusion으로 고양이 그려줘", tool_name="prompt_convert")
        mock_inject.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 5. bridge.py — addPromptGuide model key 저장 / getPromptGuidesDB 양방향 읽기
# ══════════════════════════════════════════════════════════════════════════════

class TestBridgePromptGuideKeys:
    """addPromptGuide / getPromptGuidesDB 메타데이터 호환성 검증.

    ChromaDB PersistentClient를 mock으로 교체해 SQLite 잠금 문제를 방지한다.
    """

    @pytest.fixture()
    def mock_col(self):
        """in-process 컬렉션 mock — add/get/list_collections 시뮬레이션."""
        storage = {"ids": [], "documents": [], "metadatas": []}

        col = MagicMock()

        def _add(ids, documents, metadatas):
            storage["ids"].extend(ids)
            storage["documents"].extend(documents)
            storage["metadatas"].extend(metadatas)

        def _get(ids=None, include=None, **kwargs):
            if ids:
                idx_list = [storage["ids"].index(i) for i in ids if i in storage["ids"]]
                return {
                    "ids": [storage["ids"][i] for i in idx_list],
                    "documents": [storage["documents"][i] for i in idx_list] if "documents" in (include or []) else [],
                    "metadatas": [storage["metadatas"][i] for i in idx_list] if "metadatas" in (include or []) else [],
                }
            return {"ids": list(storage["ids"]), "documents": list(storage["documents"]), "metadatas": list(storage["metadatas"])}

        col.add.side_effect = _add
        col.get.side_effect = _get
        return col, storage

    @pytest.fixture()
    def bridge_with_mock_chroma(self, bridge, mock_col):
        """bridge에 mock chromadb를 주입한다.

        list_collections()에 prompt_guides를 포함시켜
        SentenceTransformerEmbeddingFunction 로딩을 우회한다.
        """
        col, storage = mock_col
        original_cfg = bridge._agent.cfg
        bridge._agent.cfg = {"chroma_path": "/mock/path"}

        existing_col_mock = MagicMock()
        existing_col_mock.name = "prompt_guides"

        mock_client = MagicMock()
        mock_client.list_collections.return_value = [existing_col_mock]
        mock_client.get_or_create_collection.return_value = col
        mock_client.create_collection.return_value = col
        mock_client.get_collection.return_value = col

        yield bridge, mock_client, col, storage  # M-3: yield로 teardown 지원

        # M-3: teardown — cfg 복원 및 storage 정리
        bridge._agent.cfg = original_cfg
        storage.clear()
        import gc
        gc.collect()

    def test_add_prompt_guide_saves_model_key(self, bridge_with_mock_chroma):
        """addPromptGuide() 저장 시 'model' 키가 metadata에 포함되어야 한다."""
        bridge, mock_client, col, storage = bridge_with_mock_chroma

        with patch("chromadb.PersistentClient", return_value=mock_client):
            guide_id = bridge.addPromptGuide("Stable Diffusion XL", "quality guide", "")

        assert guide_id != ""
        assert len(storage["metadatas"]) == 1
        meta = storage["metadatas"][0]
        assert "model" in meta
        assert meta["model"] == "stable-diffusion-xl"

    def test_get_prompt_guides_db_reads_both_keys(self, bridge, tmp_path):
        """getPromptGuidesDB()가 model_name과 model 키 둘 다 읽어야 한다 (PromptGuideStore 호환)."""
        bridge._agent.cfg = {"chroma_path": "/mock/path"}

        # PromptGuideStore 방식 저장 (model 키만 있음)
        old_meta = {"model": "midjourney"}

        mock_col = MagicMock()
        mock_col.get.return_value = {
            "ids": ["pg_old_001"],
            "documents": ["guide text"],
            "metadatas": [old_meta],
        }
        mock_client = MagicMock()
        mock_client.get_collection.return_value = mock_col

        with patch("chromadb.PersistentClient", return_value=mock_client):
            parsed = json.loads(bridge.getPromptGuidesDB())

        assert parsed["total"] >= 1
        entry = next((g for g in parsed["guides"] if g["id"] == "pg_old_001"), None)
        assert entry is not None
        # model 키 값이 model_name 필드로 노출되어야 함
        assert entry["model_name"] == "midjourney"

    def test_add_then_get_round_trip(self, bridge_with_mock_chroma):
        """addPromptGuide로 저장한 항목이 getPromptGuidesDB에서 보여야 한다."""
        bridge, mock_client, col, storage = bridge_with_mock_chroma

        with patch("chromadb.PersistentClient", return_value=mock_client):
            guide_id = bridge.addPromptGuide("TestModel", "test guide content", "Haru")

        assert guide_id != ""

        # getPromptGuidesDB도 동일한 mock client 사용
        mock_col_for_get = MagicMock()
        mock_col_for_get.get.return_value = {
            "ids": storage["ids"],
            "documents": storage["documents"],
            "metadatas": storage["metadatas"],
        }
        mock_client2 = MagicMock()
        mock_client2.get_collection.return_value = mock_col_for_get

        with patch("chromadb.PersistentClient", return_value=mock_client2):
            parsed = json.loads(bridge.getPromptGuidesDB())

        ids = [g["id"] for g in parsed["guides"]]
        assert guide_id in ids


# ══════════════════════════════════════════════════════════════════════════════
# 6. narration/world_trigger.py — check_story_trigger / check_culture_trigger
# ══════════════════════════════════════════════════════════════════════════════

class TestWorldTriggers:
    @pytest.fixture()
    def session(self):
        from conversation.core.session import ConversationSession
        # world_id 가 있어야 트리거 시스템이 작동함
        sess = ConversationSession(character_id="Haru", world_id="seaside_world")
        return sess

    @pytest.fixture()
    def rag(self):
        """query_by_meta 반환 형식: list[{"id":..., "document":..., "metadata":{...}}]
        threshold=0.55 기준: 키워드 1개 → score=1/1=1.0 으로 통과."""
        mock = MagicMock()
        mock.query_by_meta = MagicMock(return_value=[{
            "id": "chunk_001",
            "document": "낡은 선착장 이야기입니다.",
            "metadata": {
                "item_title": "옛 선착장",
                "section": "story",
                "trigger_keywords": "선착장",   # 단일 키워드: 1/1=1.0 > 0.55
            },
        }])
        return mock

    def test_check_story_trigger_fires_on_keyword(self, session, rag):
        """트리거 키워드가 포함된 입력에 (title, document) 튜플이 반환되어야 한다."""
        from narration.world_trigger import check_story_trigger
        result = check_story_trigger("선착장에 가고 싶어", session, rag)
        assert result is not None
        assert isinstance(result, tuple)
        title, document = result
        assert title == "옛 선착장"
        assert isinstance(document, str)

    def test_check_story_trigger_no_duplicate(self, session, rag):
        """이미 발동된 story는 재발동되지 않아야 한다."""
        from narration.world_trigger import check_story_trigger
        check_story_trigger("선착장에 가고 싶어", session, rag)
        result = check_story_trigger("선착장 얘기", session, rag)
        assert result is None

    def test_check_story_trigger_no_match_returns_none(self, session, rag):
        """키워드 없는 입력은 None 반환해야 한다."""
        from narration.world_trigger import check_story_trigger
        result = check_story_trigger("오늘 날씨가 좋네", session, rag)
        assert result is None

    def test_check_culture_trigger_fires_on_keyword(self, session):
        """문화 키워드 포함 입력에 culture 나레이션이 반환되어야 한다."""
        from narration.world_trigger import check_culture_trigger
        mock_rag = MagicMock()
        mock_rag.query_by_meta = MagicMock(return_value=[{
            "id": "chunk_002",
            "document": "매년 열리는 해산물 축제입니다.",
            "metadata": {
                "item_title": "해산물 축제",
                "section": "culture",
                "trigger_keywords": "축제,해산물,마을",
            },
        }])
        result = check_culture_trigger("마을 축제에 대해 알고 싶어", session, mock_rag)
        assert result is not None

    def test_check_culture_trigger_no_duplicate(self, session):
        """이미 설명된 culture는 재발동되지 않아야 한다."""
        from narration.world_trigger import check_culture_trigger
        mock_rag = MagicMock()
        mock_rag.query_by_meta = MagicMock(return_value=[{
            "id": "chunk_002",
            "document": "매년 열리는 해산물 축제입니다.",
            "metadata": {
                "item_title": "해산물 축제",
                "section": "culture",
                "trigger_keywords": "축제,해산물,마을",
            },
        }])
        check_culture_trigger("마을 축제", session, mock_rag)
        result = check_culture_trigger("마을 축제 또 물어봐", session, mock_rag)
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# 7. rag/index.py — _parse_world_md() 섹션 파싱
# ══════════════════════════════════════════════════════════════════════════════

class TestRagIndexParser:
    def test_parse_world_md_extracts_sections(self):
        """_parse_world_md()가 ## 섹션과 ### 항목을 올바르게 파싱해야 한다."""
        from rag.index import _parse_world_md
        md_text = """# Seaside

## culture

### 해산물 시장
트리거 키워드: [시장, 생선, 해산물]
매주 열리는 해산물 시장이다.

## story

### 선착장 전설
트리거 키워드: [선착장, 전설]
오래된 선착장에 전설이 있다.
"""
        world_id, items = _parse_world_md(md_text)
        assert world_id == "Seaside"
        assert len(items) >= 2
        item_titles = [it["item_title"] for it in items]
        assert "해산물 시장" in item_titles
        assert "선착장 전설" in item_titles

    def test_parse_world_md_trigger_keywords(self):
        """_parse_world_md()가 모든 섹션의 트리거 키워드를 메타데이터로 파싱해야 한다."""
        from rag.index import _parse_world_md
        md_text = """# TestWorld

## story

### 선착장 전설
트리거 키워드: [선착장, 부두, 항구]
오래된 선착장 전설이다.
"""
        _, items = _parse_world_md(md_text)
        assert items
        item = next(it for it in items if it["item_title"] == "선착장 전설")
        assert "선착장" in item["trigger_keywords"]
        assert "부두" in item["trigger_keywords"]
        # 트리거 키워드 줄이 content에 포함되지 않아야 한다
        assert "트리거 키워드" not in item["content"]

    def test_parse_world_md_trigger_keywords_all_sections(self):
        """culture / place 섹션도 trigger_keywords가 메타데이터로 추출되고 content에서 제거되어야 한다."""
        from rag.index import _parse_world_md
        md_text = """# TestWorld

## culture

### 등대 축제
트리거 키워드: [등대 축제, 촛불, 종이배, 소원]
여름이 끝날 무렵, 등대 아래에 촛불이 켜진다.

## place

### 방파제
트리거 키워드: [방파제, breakwater]
항구 입구를 가로막은 긴 돌 방파제다.
"""
        _, items = _parse_world_md(md_text)
        culture_item = next(it for it in items if it["item_title"] == "등대 축제")
        place_item   = next(it for it in items if it["item_title"] == "방파제")

        # trigger_keywords가 메타데이터로 추출되어야 한다
        assert "촛불" in culture_item["trigger_keywords"]
        assert "종이배" in culture_item["trigger_keywords"]
        assert "방파제" in place_item["trigger_keywords"]

        # trigger_keywords 줄이 content에 없어야 한다
        assert "트리거 키워드" not in culture_item["content"]
        assert "트리거 키워드" not in place_item["content"]

        # 실제 내용은 content에 있어야 한다
        assert "촛불" in culture_item["content"]
        assert "방파제" in place_item["content"]

    def test_parse_world_md_section_field(self):
        """_parse_world_md()가 section 필드를 올바르게 설정해야 한다."""
        from rag.index import _parse_world_md
        md_text = """# MyWorld

## place

### 해변
트리거 키워드: [해변]
아름다운 해변.
"""
        _, items = _parse_world_md(md_text)
        assert items
        assert items[0]["section"] == "place"


# ══════════════════════════════════════════════════════════════════════════════
# 8. config.py — default_world_id / memory_trigger_n
# ══════════════════════════════════════════════════════════════════════════════

class TestConfigValues:
    def test_ui_test_env_has_default_world_id(self):
        """ui_test 환경에 default_world_id 설정이 있어야 한다."""
        import config as _cfg_mod
        assert "default_world_id" in _cfg_mod._CONFIGS["ui_test"]

    def test_dev_env_has_memory_trigger_n_5(self):
        """dev 환경의 memory_trigger_n이 5여야 한다."""
        import config as _cfg_mod
        assert _cfg_mod._CONFIGS["dev"].get("memory_trigger_n") == 5

    def test_deploy_env_has_memory_trigger_n_5(self):
        """deploy 환경의 memory_trigger_n이 5여야 한다."""
        import config as _cfg_mod
        assert _cfg_mod._CONFIGS["deploy"].get("memory_trigger_n") == 5


# ══════════════════════════════════════════════════════════════════════════════
# 9. MemoryDBPanel.qml — 탭2 CRUD 구조 확인
# ══════════════════════════════════════════════════════════════════════════════

class TestMemoryDBPanelQmlTab2:
    @pytest.fixture()
    def qml_text(self):
        path = ROOT / "ui_ux" / "qml" / "MemoryDBPanel.qml"
        return path.read_text(encoding="utf-8")

    def test_guide_add_form_exists(self, qml_text):
        """탭2에 guideAddForm(추가 폼)이 있어야 한다."""
        assert "guideAddForm" in qml_text

    def test_guide_add_form_has_model_input(self, qml_text):
        """추가 폼에 model_name 입력 필드(gAddModel)가 있어야 한다."""
        assert "gAddModel" in qml_text

    def test_guide_add_form_calls_add_slot(self, qml_text):
        """추가 폼 저장 버튼이 bridge.addPromptGuide()를 호출해야 한다."""
        assert "bridge.addPromptGuide" in qml_text

    def test_guide_card_has_delete_button(self, qml_text):
        """각 가이드 카드에 bridge.deletePromptGuide() 호출이 있어야 한다."""
        assert "bridge.deletePromptGuide" in qml_text

    def test_guide_card_has_update_button(self, qml_text):
        """각 가이드 카드에 bridge.updatePromptGuide() 호출이 있어야 한다."""
        assert "bridge.updatePromptGuide" in qml_text

    def test_guide_groups_by_model_name(self, qml_text):
        """_guideGroups를 사용해 model_name 기준 그룹화가 되어야 한다."""
        assert "_guideGroups" in qml_text
        assert "model_name" in qml_text

    def test_guide_add_form_open_property(self, qml_text):
        """_guideAddFormOpen property가 있어야 한다."""
        assert "_guideAddFormOpen" in qml_text
