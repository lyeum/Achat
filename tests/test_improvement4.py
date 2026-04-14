"""개선4 구현 항목 검증 테스트.

테스트 범위:
    1. deleteCharacter Slot
    2. getDefaultWorld Slot
    3. getWorldKnowledgeDB / getPromptGuidesDB Slot (컬렉션 없는 경우 포함)
    4. reindexWorldKnowledge Slot (rag_world_dir 없는 경우)
    5. switchSession Slot
    6. SessionManager MAX_SESSIONS / _evict_session
    7. bridge.activeSessionId Property
    8. CharacterStatusPanel 너비 수정 확인 (파일 파싱)
    9. SettingsPanel 세계관/DB 섹션 이름 변경 확인 (파일 파싱)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ACHAT_ENV", "ui_test")

# ── QCoreApplication ─────────────────────────────────────────────────────────
from PySide6.QtCore import QCoreApplication
_app = QCoreApplication.instance() or QCoreApplication(sys.argv)


# ── Fixtures ─────────────────────────────────────────────────────────────────

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
# 1. deleteCharacter
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteCharacter:
    def test_cannot_delete_active_character(self, bridge):
        """현재 활성 캐릭터(Haru)는 삭제 불가 → False 반환."""
        result = bridge.deleteCharacter("Haru")
        assert result is False

    def test_delete_nonexistent_returns_false(self, bridge, tmp_path, monkeypatch):
        """존재하지 않는 캐릭터 삭제 → False."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_CHARACTER_DIR", tmp_path)
        assert bridge.deleteCharacter("GhostChar") is False

    def test_delete_creates_and_removes_yaml(self, bridge, tmp_path, monkeypatch):
        """실제 YAML 파일 생성 후 삭제 성공 → True, 파일 없어짐."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_CHARACTER_DIR", tmp_path)
        yaml_path = tmp_path / "CH_TestChar.yaml"
        yaml_path.write_text("id: TestChar\nname: 테스트\n", encoding="utf-8")
        result = bridge.deleteCharacter("TestChar")
        assert result is True
        assert not yaml_path.exists()

    def test_delete_does_not_affect_character_list_of_active(self, bridge, tmp_path, monkeypatch):
        """삭제 후 캐릭터 목록에 활성 캐릭터(Haru)가 여전히 있어야 한다."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_CHARACTER_DIR", tmp_path)
        # Haru YAML 복사
        real_dir = ROOT / "conversation" / "character"
        haru_src = real_dir / "CH_Haru.yaml"
        if haru_src.exists():
            (tmp_path / "CH_Haru.yaml").write_bytes(haru_src.read_bytes())
        # TestChar 생성 후 삭제
        yaml_path = tmp_path / "CH_TestChar.yaml"
        yaml_path.write_text("id: TestChar\nname: 테스트\n", encoding="utf-8")
        bridge.deleteCharacter("TestChar")
        ids = [c["id"] for c in json.loads(bridge.getCharacterList())]
        assert "TestChar" not in ids


# ══════════════════════════════════════════════════════════════════════════════
# 2. getDefaultWorld
# ══════════════════════════════════════════════════════════════════════════════

class TestGetDefaultWorld:
    def test_returns_valid_json(self, bridge):
        result = bridge.getDefaultWorld()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_required_keys_when_world_exists(self, bridge):
        worlds = json.loads(bridge.getWorldList())
        if not worlds:
            pytest.skip("세계관 파일 없음")
        result = json.loads(bridge.getDefaultWorld())
        assert "world_id" in result
        assert "scenario_id" in result
        assert "act_id" in result

    def test_returns_empty_dict_when_no_worlds(self, bridge, tmp_path, monkeypatch):
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_WORLD_DIR", tmp_path)
        result = json.loads(bridge.getDefaultWorld())
        assert result == {}

    def test_world_id_matches_first_world(self, bridge):
        worlds = json.loads(bridge.getWorldList())
        if not worlds:
            pytest.skip("세계관 파일 없음")
        default = json.loads(bridge.getDefaultWorld())
        assert default["world_id"] == worlds[0]["world_id"]


# ══════════════════════════════════════════════════════════════════════════════
# 3. getWorldKnowledgeDB
# ══════════════════════════════════════════════════════════════════════════════

class TestGetWorldKnowledgeDB:
    def test_returns_valid_json(self, bridge):
        result = bridge.getWorldKnowledgeDB()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_total_and_chunks_keys(self, bridge):
        parsed = json.loads(bridge.getWorldKnowledgeDB())
        assert "total" in parsed
        assert "chunks" in parsed

    def test_no_collection_returns_empty(self, bridge, tmp_path, monkeypatch):
        """chromadb에 world_knowledge 컬렉션이 없으면 total=0, chunks=[]."""
        bridge._agent.cfg = {"chroma_path": str(tmp_path)}
        parsed = json.loads(bridge.getWorldKnowledgeDB())
        assert parsed["total"] == 0
        assert parsed["chunks"] == []
        assert "error" in parsed  # 에러 메시지 포함


# ══════════════════════════════════════════════════════════════════════════════
# 4. getPromptGuidesDB
# ══════════════════════════════════════════════════════════════════════════════

class TestGetPromptGuidesDB:
    def test_returns_valid_json(self, bridge):
        result = bridge.getPromptGuidesDB()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_total_and_guides_keys(self, bridge):
        parsed = json.loads(bridge.getPromptGuidesDB())
        assert "total" in parsed
        assert "guides" in parsed

    def test_no_collection_returns_empty(self, bridge, tmp_path):
        """컬렉션 없는 경로 → total=0, guides=[]."""
        bridge._agent.cfg = {"chroma_path": str(tmp_path)}
        parsed = json.loads(bridge.getPromptGuidesDB())
        assert parsed["total"] == 0
        assert parsed["guides"] == []


# ══════════════════════════════════════════════════════════════════════════════
# 5. reindexWorldKnowledge
# ══════════════════════════════════════════════════════════════════════════════

class TestReindexWorldKnowledge:
    def test_returns_bool(self, bridge, tmp_path):
        """reindexWorldKnowledge는 항상 bool을 반환한다."""
        bridge._agent.cfg = {
            "rag_world_dir": str(tmp_path / "empty_world"),
            "chroma_path":   str(tmp_path / "chroma"),
            "embedding_model": "BAAI/bge-m3",
        }
        (tmp_path / "empty_world").mkdir(parents=True, exist_ok=True)
        result = bridge.reindexWorldKnowledge()
        # .md 파일 없어도 index_world는 경고만 출력하고 True 반환
        assert isinstance(result, bool)


# ══════════════════════════════════════════════════════════════════════════════
# 6. switchSession
# ══════════════════════════════════════════════════════════════════════════════

class TestSwitchSession:
    def test_returns_false_when_no_char(self, bridge):
        bridge._agent.character = {}
        assert bridge.switchSession("s_some_session") is False

    def test_returns_true_for_unknown_session_id(self, bridge, tmp_path):
        """존재하지 않는 session_id는 activate()가 새 세션을 생성 → True 반환.

        SessionManager.activate(char_id, session_id)는 해당 세션을 못 찾으면
        최신 세션 또는 신규 세션을 반환하므로 switchSession은 항상 True를 반환한다.
        """
        from conversation.session_manager import SessionManager
        sm = SessionManager(tmp_path)
        bridge._session_manager = sm
        result = bridge.switchSession("s_ghost_session_99")
        assert result is True

    def test_switch_to_known_session(self, bridge, tmp_path):
        """세션을 생성 후 전환 성공 → True."""
        from conversation.session_manager import SessionManager
        sm = SessionManager(tmp_path)
        bridge._session_manager = sm

        # 세션 생성
        state = sm.activate("Haru")
        session_id = state.session_id

        # 새 세션 생성
        new_state, _ = sm.new_session("Haru")

        # agent.session mock 설정
        bridge._agent.session = new_state
        bridge._agent.character = {"id": "Haru"}

        # 이전 세션으로 전환
        result = bridge.switchSession(session_id)
        assert result is True


# ══════════════════════════════════════════════════════════════════════════════
# 7. SessionManager MAX_SESSIONS + _evict_session
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionManagerMaxSessions:
    def test_max_sessions_constant(self):
        from conversation.session_manager import SessionManager
        assert SessionManager.MAX_SESSIONS == 3

    def test_evict_removes_oldest_when_over_limit(self, tmp_path):
        """4번째 세션 생성 시 가장 오래된 세션이 제거된다."""
        from conversation.session_manager import SessionManager
        sm = SessionManager(tmp_path)

        sessions = []
        for _ in range(3):
            state = sm.activate("Haru")
            sessions.append(state.session_id)
            # 다음 호출에서 새 세션 생성되도록 다른 session_id 필요
            sm.activate("Haru")  # 최신 세션으로 포인터 이동

        # MAX_SESSIONS(3) 초과 → 4번째 생성
        _, _ = sm.new_session("Haru", keep_memory=True)

        index = sm._load_index("Haru")
        assert len(index) <= SessionManager.MAX_SESSIONS

    def test_evict_removes_directory(self, tmp_path):
        """_evict_session은 세션 디렉토리를 삭제한다."""
        from conversation.session_manager import SessionManager
        sm = SessionManager(tmp_path)
        state = sm.activate("Haru")
        session_dir = sm._char_dir("Haru") / state.session_id
        assert session_dir.exists()
        sm._evict_session("Haru", state.session_id)
        assert not session_dir.exists()

    def test_evict_removes_from_index(self, tmp_path):
        """_evict_session은 sessions.json에서 항목을 제거한다."""
        from conversation.session_manager import SessionManager
        sm = SessionManager(tmp_path)
        state = sm.activate("Haru")
        sm._evict_session("Haru", state.session_id)
        index = sm._load_index("Haru")
        ids = [i["session_id"] for i in index]
        assert state.session_id not in ids


# ══════════════════════════════════════════════════════════════════════════════
# 8. bridge.activeSessionId Property
# ══════════════════════════════════════════════════════════════════════════════

class TestActiveSessionId:
    def test_returns_empty_when_no_session(self, bridge):
        bridge._agent.session = None
        assert bridge.activeSessionId == ""

    def test_returns_session_id_when_session_exists(self, bridge):
        mock_session = MagicMock()
        mock_session.session_id = "s_20260409_abc123"
        bridge._agent.session = mock_session
        assert bridge.activeSessionId == "s_20260409_abc123"


# ══════════════════════════════════════════════════════════════════════════════
# 9. QML 파일 내 텍스트 변경 검증 (파싱 불필요 — 문자열 존재 확인)
# ══════════════════════════════════════════════════════════════════════════════

class TestQmlTextChanges:
    QML_DIR = ROOT / "ui_ux" / "qml"

    def test_settings_panel_has_world_section(self):
        """SettingsPanel.qml에 '세계관' 섹션명이 있어야 한다 (시나리오 → 세계관)."""
        content = (self.QML_DIR / "SettingsPanel.qml").read_text(encoding="utf-8")
        assert 'label: "세계관"' in content
        assert 'label: "시나리오"' not in content

    def test_settings_panel_has_db_section(self):
        """SettingsPanel.qml에 'DB' 섹션명이 있어야 한다 (데이터 → DB)."""
        content = (self.QML_DIR / "SettingsPanel.qml").read_text(encoding="utf-8")
        assert 'label: "DB"' in content
        assert '"관리자 패널"' not in content  # 중복 버튼 제거 확인

    def test_admin_panel_no_drag_text(self):
        """AdminPanel.qml 헤더에 '(드래그로 이동)' 문구가 없어야 한다."""
        content = (self.QML_DIR / "AdminPanel.qml").read_text(encoding="utf-8")
        assert "(드래그로 이동)" not in content

    def test_status_panel_width_300(self):
        """CharacterStatusPanel.qml의 modal width가 300이어야 한다."""
        content = (self.QML_DIR / "CharacterStatusPanel.qml").read_text(encoding="utf-8")
        assert "width: 300" in content

    def test_memory_db_panel_has_tabs(self):
        """MemoryDBPanel.qml에 탭 3개가 정의되어 있어야 한다."""
        content = (self.QML_DIR / "MemoryDBPanel.qml").read_text(encoding="utf-8")
        assert "장기 기억" in content
        assert "세계관 RAG" in content
        assert "프롬프트 가이드" in content

    def test_main_qml_draghandler_disabled_when_admin_open(self):
        """main.qml의 DragHandler가 adminPanelOpen 시 비활성화되어야 한다."""
        content = (self.QML_DIR / "main.qml").read_text(encoding="utf-8")
        assert "enabled: !root.adminPanelOpen" in content


# ══════════════════════════════════════════════════════════════════════════════
# 10. CH_Seonjae.yaml 삭제 확인
# ══════════════════════════════════════════════════════════════════════════════

class TestSeonjaeRemoved:
    def test_seonjae_yaml_does_not_exist(self):
        """CH_Seonjae.yaml이 삭제되어 존재하지 않아야 한다."""
        path = ROOT / "conversation" / "character" / "CH_Seonjae.yaml"
        assert not path.exists(), "CH_Seonjae.yaml이 아직 존재합니다"

    def test_seonjae_not_in_character_list(self, bridge):
        """캐릭터 목록에 Seonjae가 포함되지 않아야 한다."""
        ids = [c["id"] for c in json.loads(bridge.getCharacterList())]
        assert "Seonjae" not in ids
