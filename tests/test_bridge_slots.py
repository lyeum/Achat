"""Bridge 슬롯 단위 테스트.

ChatBridge의 모든 Slot을 stub 모드 agent로 직접 호출해 반환값을 검증한다.
PySide6 QApplication이 없어도 동작하도록 QCoreApplication을 사용한다.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ACHAT_ENV", "ui_test")


# ── PySide6 QCoreApplication (QObject 사용에 필요) ──────────────────────────
from PySide6.QtCore import QCoreApplication

_app = QCoreApplication.instance() or QCoreApplication(sys.argv)


# ── 테스트용 stub agent fixture ────────────────────────────────────────────────

@pytest.fixture()
def stub_agent():
    """session=None인 최소 stub agent."""
    agent = MagicMock()
    agent.session = None
    agent.character = {"id": "Haru", "name": "하루"}
    agent.world = {"world_id": "seaside_world"}
    agent.router = None
    agent.llm = None
    agent.long_term = None
    return agent


@pytest.fixture()
def bridge(stub_agent):
    from ui_ux.bridge import ChatBridge
    return ChatBridge(stub_agent)


# ══════════════════════════════════════════════════════════════════════════════
# 1. getCharacterList
# ══════════════════════════════════════════════════════════════════════════════

class TestGetCharacterList:
    def test_returns_valid_json(self, bridge):
        result = bridge.getCharacterList()
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_each_item_has_id_and_name(self, bridge):
        parsed = json.loads(bridge.getCharacterList())
        for item in parsed:
            assert "id" in item
            assert "name" in item

    def test_contains_known_characters(self, bridge):
        ids = [c["id"] for c in json.loads(bridge.getCharacterList())]
        # conversation/character/CH_Haru.yaml 기준
        assert "Haru" in ids or len(ids) >= 1, "캐릭터 목록이 비어있거나 Haru 없음"

    def test_default_character_excluded(self, bridge):
        """id='default'인 CH_default.yaml이 목록에 포함되지 않아야 한다."""
        ids = [c["id"] for c in json.loads(bridge.getCharacterList())]
        assert "default" not in ids

    def test_no_exception_on_empty_dir(self, bridge, tmp_path, monkeypatch):
        """캐릭터 디렉토리가 비어있어도 빈 배열 반환."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_CHARACTER_DIR", tmp_path)
        assert json.loads(bridge.getCharacterList()) == []


# ══════════════════════════════════════════════════════════════════════════════
# 2. getWorldList
# ══════════════════════════════════════════════════════════════════════════════

class TestGetWorldList:
    def test_returns_valid_json(self, bridge):
        result = bridge.getWorldList()
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_each_world_has_required_keys(self, bridge):
        parsed = json.loads(bridge.getWorldList())
        for world in parsed:
            assert "world_id" in world
            assert "description" in world
            assert "scenarios" in world

    def test_scenarios_have_acts(self, bridge):
        parsed = json.loads(bridge.getWorldList())
        for world in parsed:
            for sc in world["scenarios"]:
                assert "scenario_id" in sc
                assert "acts" in sc
                for act in sc["acts"]:
                    assert "act_id" in act

    def test_seaside_world_present(self, bridge):
        world_ids = [w["world_id"] for w in json.loads(bridge.getWorldList())]
        assert "seaside_world" in world_ids


# ══════════════════════════════════════════════════════════════════════════════
# 3. loadCustomization / saveCustomization
# ══════════════════════════════════════════════════════════════════════════════

class TestCustomization:
    def test_load_returns_valid_json(self, bridge):
        result = bridge.loadCustomization()
        parsed = json.loads(result)
        assert "parts" in parsed
        assert "icon_url" in parsed
        assert "char_id" in parsed

    def test_load_empty_when_no_files(self, bridge, monkeypatch, tmp_path):
        """icons 디렉토리가 비어있으면 parts={}, icon_url="" 반환."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_ICONS_DIR", tmp_path)
        parsed = json.loads(bridge.loadCustomization())
        assert parsed["parts"] == {}
        assert parsed["icon_url"] == ""

    def test_load_char_id_matches_agent(self, bridge):
        parsed = json.loads(bridge.loadCustomization())
        assert parsed["char_id"] == "Haru"

    def test_save_creates_parts_json(self, bridge, monkeypatch, tmp_path):
        """saveCustomization → icons/{char_id}/parts.json 생성."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_ICONS_DIR", tmp_path)
        parts = {"base": "base_01.png", "eye": "eye_01.png"}
        bridge.saveCustomization(json.dumps({"parts": parts}))
        parts_path = tmp_path / "Haru" / "parts.json"
        assert parts_path.exists()
        saved = json.loads(parts_path.read_text(encoding="utf-8"))
        assert saved == parts

    def test_save_load_roundtrip(self, bridge, monkeypatch, tmp_path):
        """저장 후 불러오면 동일한 parts 반환."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_ICONS_DIR", tmp_path)
        original_parts = {"base": "base_02.png", "hair": "hair_01.png"}
        bridge.saveCustomization(json.dumps({"parts": original_parts}))
        loaded = json.loads(bridge.loadCustomization())
        assert loaded["parts"] == original_parts

    def test_save_invalid_json_does_not_crash(self, bridge):
        """잘못된 JSON 입력 시 예외 없이 처리 (messageAdded emit)."""
        bridge.saveCustomization("not valid json{{{")  # noqa

    def test_no_char_id_returns_empty(self, stub_agent, monkeypatch):
        """characterId가 없으면 빈 구조 반환."""
        stub_agent.character = {}
        from ui_ux.bridge import ChatBridge
        b = ChatBridge(stub_agent)
        parsed = json.loads(b.loadCustomization())
        assert parsed["char_id"] == ""
        assert parsed["parts"] == {}


# ══════════════════════════════════════════════════════════════════════════════
# 4. getAllPartsList
# ══════════════════════════════════════════════════════════════════════════════

class TestGetAllPartsList:
    EXPECTED_TYPES = ["base", "hair", "eye", "mouth", "cloth"]

    def test_returns_valid_json(self, bridge):
        result = bridge.getAllPartsList()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_all_part_types(self, bridge):
        parsed = json.loads(bridge.getAllPartsList())
        for pt in self.EXPECTED_TYPES:
            assert pt in parsed, f"파츠 타입 '{pt}' 누락"

    def test_each_type_is_list(self, bridge):
        parsed = json.loads(bridge.getAllPartsList())
        for pt, files in parsed.items():
            assert isinstance(files, list), f"{pt} 값이 list가 아님"

    def test_empty_dir_returns_empty_list(self, bridge, monkeypatch, tmp_path):
        """파츠 디렉토리 없으면 빈 배열 반환."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_CHAR_PARTS_DIR", tmp_path)
        parsed = json.loads(bridge.getAllPartsList())
        for pt in self.EXPECTED_TYPES:
            assert parsed[pt] == []

    def test_only_png_files_included(self, bridge, monkeypatch, tmp_path):
        """PNG 파일만 포함, 다른 확장자 제외."""
        import ui_ux.bridge as bmod
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        (base_dir / "base_01.png").touch()
        (base_dir / "readme.txt").touch()
        (base_dir / "base_02.PNG").touch()   # 대문자 확장자도 포함

        monkeypatch.setattr(bmod, "_CHAR_PARTS_DIR", tmp_path)
        parsed = json.loads(bridge.getAllPartsList())
        assert "readme.txt" not in parsed["base"]
        assert "base_01.png" in parsed["base"]

    def test_files_sorted(self, bridge, monkeypatch, tmp_path):
        """파일 목록이 정렬되어 반환."""
        import ui_ux.bridge as bmod
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        for name in ["base_03.png", "base_01.png", "base_02.png"]:
            (base_dir / name).touch()
        monkeypatch.setattr(bmod, "_CHAR_PARTS_DIR", tmp_path)
        files = json.loads(bridge.getAllPartsList())["base"]
        assert files == sorted(files)


# ══════════════════════════════════════════════════════════════════════════════
# 5. snapToEdge (기존 슬롯 회귀 방지 — 스크린 mock 사용)
# ══════════════════════════════════════════════════════════════════════════════

class TestSnapToEdge:
    """snapToEdge는 QApplication.primaryScreen()이 필요하므로 mock으로 처리."""

    @pytest.fixture(autouse=True)
    def mock_screen(self, monkeypatch):
        from unittest.mock import MagicMock
        from PySide6.QtWidgets import QApplication
        screen = MagicMock()
        screen.availableGeometry.return_value = MagicMock(
            left=lambda: 0, right=lambda: 1920,
            top=lambda: 0,  bottom=lambda: 1080,
        )
        monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: screen))

    def test_returns_list_of_two(self, bridge):
        result = bridge.snapToEdge(100, 100, 360, 520)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_snaps_to_left(self, bridge):
        x, y = bridge.snapToEdge(10, 100, 360, 520)
        assert x == 0  # SNAP=30, x=10 → left(0)에 스냅

    def test_no_snap_in_middle(self, bridge):
        x, y = bridge.snapToEdge(500, 300, 360, 520)
        assert x == 500  # 중앙 → 스냅 없음


# ══════════════════════════════════════════════════════════════════════════════
# 6. changeWorld — stub 모드에서 session=None 시 안전하게 종료
# ══════════════════════════════════════════════════════════════════════════════

def test_change_world_stub_mode_no_crash(bridge):
    """stub 모드(session=None)에서 changeWorld 호출 시 예외 없이 early return."""
    bridge.changeWorld("seaside_world", "morning_walk", "act_1")  # must not raise


def test_change_character_stub_mode_no_crash(bridge):
    """stub 모드에서 changeCharacter 호출 시 예외 없이 early return."""
    bridge.changeCharacter("Haru")  # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# 7. getCharacterStatus
# ══════════════════════════════════════════════════════════════════════════════

class TestGetCharacterStatus:
    def test_returns_valid_json(self, bridge):
        result = bridge.getCharacterStatus()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_required_keys(self, bridge):
        parsed = json.loads(bridge.getCharacterStatus())
        for key in ("char_name", "mood", "affection", "tier", "turn_count"):
            assert key in parsed, f"키 '{key}' 누락"

    def test_no_session_defaults(self, bridge):
        """session=None일 때 affection=0, turn_count=0."""
        parsed = json.loads(bridge.getCharacterStatus())
        assert parsed["affection"] == 0
        assert parsed["turn_count"] == 0

    def test_char_name_from_agent(self, bridge):
        parsed = json.loads(bridge.getCharacterStatus())
        assert parsed["char_name"] in ("하루", "Haru", "")


# ══════════════════════════════════════════════════════════════════════════════
# 8. resetCharacter
# ══════════════════════════════════════════════════════════════════════════════

def test_reset_character_nonexistent_no_crash(bridge):
    """존재하지 않는 캐릭터 ID 초기화 시 예외 없이 True 반환."""
    result = bridge.resetCharacter("NonExistentChar_xyz")
    assert result is True


def test_reset_character_returns_bool(bridge):
    result = bridge.resetCharacter("Haru")
    assert isinstance(result, bool)


# ══════════════════════════════════════════════════════════════════════════════
# BUG-02: _unload_llm — LLM 이중 적재 OOM 방지
# ══════════════════════════════════════════════════════════════════════════════

class TestUnloadLlm:
    """_unload_llm() 이 LLM 객체를 올바르게 해제하는지 검증 (BUG-02-A)."""

    def _make_agent_with_llm(self, backend: str):
        """테스트용 가짜 agent + llm을 반환한다."""
        fake_model = MagicMock()
        fake_llm = MagicMock()
        fake_llm.backend = backend
        fake_llm._model = fake_model
        agent = MagicMock()
        agent.session = None
        agent.character = {"id": "Haru", "name": "하루"}
        agent.world = {}
        agent.llm = fake_llm
        agent._stub = False
        return agent, fake_model

    def test_unload_llama_cpp_calls_close(self):
        """llama_cpp 백엔드에서 model.close()가 호출되어야 한다."""
        from ui_ux.bridge import ChatBridge

        agent, fake_model = self._make_agent_with_llm("llama_cpp")
        bridge_inst = ChatBridge.__new__(ChatBridge)
        bridge_inst._agent = agent

        bridge_inst._unload_llm()
        fake_model.close.assert_called_once()

    def test_unload_transformers_deletes_model(self, monkeypatch):
        """transformers 백엔드에서 _model이 None으로 설정되어야 한다."""
        from ui_ux.bridge import ChatBridge

        agent, fake_model = self._make_agent_with_llm("transformers")

        # torch mock — CUDA 없는 환경 대응
        fake_torch = MagicMock()
        fake_torch.cuda.is_available.return_value = False
        monkeypatch.setattr("ui_ux.bridge.torch", fake_torch, raising=False)

        import sys
        sys.modules.setdefault("torch", fake_torch)

        bridge_inst = ChatBridge.__new__(ChatBridge)
        bridge_inst._agent = agent
        bridge_inst._unload_llm()

        assert agent.llm._model is None

    def test_unload_no_crash_when_llm_is_none(self):
        """llm=None인 agent(stub 모드)에서도 예외 없이 동작해야 한다."""
        from ui_ux.bridge import ChatBridge

        agent = MagicMock()
        agent.llm = None
        agent.session = None

        bridge_inst = ChatBridge.__new__(ChatBridge)
        bridge_inst._agent = agent
        bridge_inst._unload_llm()  # must not raise

    def test_unload_called_before_rebuild(self, monkeypatch):
        """_rebuild_agent()가 _unload_llm()을 먼저 호출하는지 확인한다 (BUG-02-A 핵심)."""
        from ui_ux.bridge import ChatBridge
        from conversation.session_manager import SessionState

        call_order: list[str] = []

        bridge_inst = ChatBridge.__new__(ChatBridge)
        bridge_inst._agent = MagicMock()
        bridge_inst._agent.llm = None
        bridge_inst._agent.cfg = {"model_backend": "stub"}
        bridge_inst._agent.character = {"id": "Haru", "name": "하루"}
        bridge_inst._conv_logger = None

        def fake_unload():
            call_order.append("unload")

        def fake_agent_from_session(state, cfg):
            call_order.append("load")
            a = MagicMock()
            a.character = {"id": state.char_id, "name": state.char_id}
            a.session = None
            a.world = {}
            a.llm = None
            return a

        monkeypatch.setattr(bridge_inst, "_unload_llm", fake_unload)
        monkeypatch.setattr(bridge_inst, "_resolve_initial_location", lambda: "")

        import ui_ux.bridge as bmod
        monkeypatch.setattr(
            bmod.__import__("agent.core", fromlist=["Agent"]) if False else
            __import__("agent.core", fromlist=["Agent"]),
            "Agent",
            type("A", (), {"from_session": staticmethod(fake_agent_from_session)})(),
            raising=False,
        )

        # agent.core.Agent.from_session 패치
        import agent.core as acore
        monkeypatch.setattr(acore.Agent, "from_session", staticmethod(fake_agent_from_session))

        state = SessionState(
            char_id="Haru", session_id="s1", world_id="w",
            scenario_id=None, act_id=None, location=None,
            mood="neutral", affection=30, turn_count=0,
            created_at="", last_active="",
        )
        bridge_inst._rebuild_agent(state)

        assert call_order == ["unload", "load"], \
            f"_unload_llm이 먼저 호출되어야 함. 실제 순서: {call_order}"


# ══════════════════════════════════════════════════════════════════════════════
# 9. applyFileOptions (파일이름 변경 / 확장자 변경)
# ══════════════════════════════════════════════════════════════════════════════

class TestApplyFileOptions:
    """bridge.applyFileOptions() — 실제 파일 I/O를 tmp_path로 검증."""

    @pytest.fixture
    def txt_files(self, tmp_path):
        files = []
        for i in range(3):
            f = tmp_path / f"sample_{i}.txt"
            f.write_text(f"content {i}")
            files.append(str(f))
        return files, tmp_path

    def test_rename_single_file(self, bridge, tmp_path):
        src = tmp_path / "old_name.txt"
        src.write_text("hello")
        result = bridge.applyFileOptions(
            json.dumps([str(src)]), "new_name", ""
        )
        assert "완료" in result
        assert (tmp_path / "new_name.txt").exists()
        assert not src.exists()

    def test_rename_multiple_files_with_prefix(self, bridge, txt_files):
        files, tmp_path = txt_files
        result = bridge.applyFileOptions(json.dumps(files), "photo", "")
        assert "완료" in result
        assert (tmp_path / "photo_001.txt").exists()
        assert (tmp_path / "photo_002.txt").exists()
        assert (tmp_path / "photo_003.txt").exists()

    def test_empty_paths_returns_error(self, bridge):
        result = bridge.applyFileOptions("[]", "new", "")
        assert "없습니다" in result

    def test_invalid_paths_json_returns_error(self, bridge):
        result = bridge.applyFileOptions("not json", "new", "")
        assert "오류" in result

    def test_no_rename_no_ext_no_change(self, bridge, tmp_path):
        src = tmp_path / "file.txt"
        src.write_text("x")
        result = bridge.applyFileOptions(json.dumps([str(src)]), "", "")
        # rename_to="" + new_ext="" → 변경 없음
        assert "변경 없음" in result
        assert src.exists()

    def test_ext_change_non_image(self, bridge, tmp_path):
        src = tmp_path / "data.txt"
        src.write_text("x")
        result = bridge.applyFileOptions(json.dumps([str(src)]), "", "csv")
        assert "완료" in result
        assert (tmp_path / "data.csv").exists()

    def test_rename_and_ext_together(self, bridge, tmp_path):
        src = tmp_path / "old.txt"
        src.write_text("x")
        result = bridge.applyFileOptions(json.dumps([str(src)]), "renamed", "csv")
        assert "완료" in result
        assert (tmp_path / "renamed.csv").exists()


# ══════════════════════════════════════════════════════════════════════════════
# 10. applyFolderClassify (폴더 분류)
# ══════════════════════════════════════════════════════════════════════════════

class TestApplyFolderClassify:
    """bridge.applyFolderClassify() — ClassifierTool 기반 폴더 분류."""

    def test_empty_path_returns_string(self, bridge):
        """빈 경로는 CWD로 해석되어 문자열을 반환한다 (오류 또는 결과)."""
        result = bridge.applyFolderClassify("", "종류별", True)
        assert isinstance(result, str)

    def test_nonexistent_path_returns_error(self, bridge):
        result = bridge.applyFolderClassify("/nonexistent/path/xyz_abc_123", "종류별", False)
        assert "오류" in result

    def test_dry_run_does_not_move_files(self, bridge, tmp_path):
        """dry_run=True 시 파일 이동 없이 미리보기 반환."""
        (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff")  # minimal JPEG header
        result = bridge.applyFolderClassify(str(tmp_path), "종류별", True)
        assert result  # 결과 문자열 반환
        assert (tmp_path / "photo.jpg").exists()  # 파일 이동 안 됨

    def test_returns_string(self, bridge, tmp_path):
        (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4")
        result = bridge.applyFolderClassify(str(tmp_path), "확장자별", True)
        assert isinstance(result, str)

    def test_invalid_rule_returns_error_or_default(self, bridge, tmp_path):
        """잘못된 rule 값도 예외 없이 처리."""
        result = bridge.applyFolderClassify(str(tmp_path), "없는규칙", False)
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# 11. searchFiles / openFile
# ══════════════════════════════════════════════════════════════════════════════

class TestSearchFiles:
    """bridge.searchFiles() — 파일명 + FTS5 내용 통합 검색."""

    def test_empty_query_returns_error_json(self, bridge):
        result = bridge.searchFiles("", str(Path.home()), "")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_nonexistent_dir_returns_error_json(self, bridge):
        result = bridge.searchFiles("hello", "/nonexistent_xyz_abc", "")
        parsed = json.loads(result)
        assert "error" in parsed

    def test_returns_json_array(self, bridge, tmp_path):
        (tmp_path / "hello_note.txt").write_text("some content")
        result = bridge.searchFiles("hello", str(tmp_path), "")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_found_file_has_path_and_snippet(self, bridge, tmp_path):
        (tmp_path / "greet.txt").touch()
        result = bridge.searchFiles("greet", str(tmp_path), "")
        parsed = json.loads(result)
        assert len(parsed) >= 1
        assert "path" in parsed[0]
        assert "snippet" in parsed[0]

    def test_finds_by_korean_filename(self, bridge, tmp_path):
        """한국어 파일명 검색."""
        (tmp_path / "보고서_2026.txt").touch()
        result = bridge.searchFiles("보고서", str(tmp_path), "")
        parsed = json.loads(result)
        assert any("보고서" in r["path"] for r in parsed)

    def test_finds_binary_by_extension_keyword(self, bridge, tmp_path):
        """'png' 검색 → .png 파일이 결과에 포함된다."""
        (tmp_path / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        result = bridge.searchFiles("png", str(tmp_path), "")
        parsed = json.loads(result)
        assert any("screenshot.png" in r["path"] for r in parsed)

    def test_no_results_returns_empty_list(self, bridge, tmp_path):
        (tmp_path / "unrelated.txt").write_text("completely different content")
        result = bridge.searchFiles("xyzzy_nonexistent_99999", str(tmp_path), "")
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 0


def test_open_file_no_crash(bridge, tmp_path, monkeypatch):
    """openFile은 subprocess를 mock해서 실제 파일을 열지 않고 예외 없이 동작해야 한다."""
    import ui_ux.bridge as bmod

    monkeypatch.setattr(bmod._subprocess, "Popen", lambda *a, **kw: MagicMock())
    monkeypatch.setattr(bmod._subprocess, "check_output", lambda *a, **kw: b"C:\\dummy.txt")
    f = tmp_path / "dummy.txt"
    f.write_text("hi")
    bridge.openFile(str(f))  # must not raise


class TestOpenFileWsl2:
    """openFile() WSL2 환경에서 powershell.exe Invoke-Item 호출 확인."""

    def _make_fake_subprocess(self, calls: list, win_path: bytes = b"C:\\test\\dummy.txt"):
        """check_output + Popen을 가로채는 mock subprocess 네임스페이스."""
        fake = MagicMock()

        def fake_check_output(args, **kw):
            if args and args[0] == "wslpath":
                return win_path
            raise FileNotFoundError

        fake.check_output = fake_check_output
        fake.DEVNULL = -1
        fake.CalledProcessError = __import__("subprocess").CalledProcessError

        def fake_popen(args, **kw):
            calls.append(list(args))
            return MagicMock()

        fake.Popen = fake_popen
        return fake

    def test_wsl2_uses_powershell(self, bridge, tmp_path, monkeypatch):
        """WSL2 환경에서 powershell.exe Invoke-Item을 사용해야 한다."""
        import ui_ux.bridge as bmod

        calls: list[list] = []
        monkeypatch.setattr(bmod, "_is_wsl", lambda: True)
        monkeypatch.setattr(bmod, "_is_windows", lambda: False)
        monkeypatch.setattr(bmod, "_subprocess", self._make_fake_subprocess(calls))

        f = tmp_path / "dummy.txt"
        f.write_text("hi")
        bridge.openFile(str(f))

        assert any("powershell.exe" in str(c) for c in calls), "powershell.exe 호출 없음"
        assert any("Invoke-Item" in str(c) for c in calls), "Invoke-Item 호출 없음"
        assert not any("cmd.exe" in str(c) and "start" in str(c) for c in calls), \
            "cmd.exe /c start 사용하면 안 됨 (UNC 경로 미지원)"

    def test_wsl2_no_cmd_start(self, bridge, tmp_path, monkeypatch):
        """WSL2에서 cmd.exe /c start는 openFile 시 호출하지 않아야 한다."""
        import ui_ux.bridge as bmod

        calls: list[list] = []
        monkeypatch.setattr(bmod, "_is_wsl", lambda: True)
        monkeypatch.setattr(bmod, "_is_windows", lambda: False)
        monkeypatch.setattr(bmod, "_subprocess",
                            self._make_fake_subprocess(calls, b"C:\\path\\image.png"))

        f = tmp_path / "image.png"
        f.write_bytes(b"\x89PNG")
        bridge.openFile(str(f))

        for c in calls:
            assert not ("cmd.exe" in c and "start" in c), "cmd.exe /c start 호출 금지"


class TestOpenUrl:
    """openUrl() 슬롯 테스트."""

    def _make_fake_subprocess(self, calls: list):
        fake = MagicMock()
        fake.DEVNULL = -1
        fake.CalledProcessError = __import__("subprocess").CalledProcessError

        def fake_popen(args, **kw):
            calls.append(list(args))
            return MagicMock()

        fake.Popen = fake_popen
        return fake

    def test_no_crash_on_http(self, bridge, monkeypatch):
        """HTTP URL에 대해 예외 없이 동작."""
        import ui_ux.bridge as bmod
        calls: list = []
        monkeypatch.setattr(bmod, "_subprocess", self._make_fake_subprocess(calls))
        bridge.openUrl("https://example.com")  # must not raise

    def test_wsl2_uses_cmd_start_for_url(self, bridge, monkeypatch):
        """WSL2에서 HTTP URL은 cmd.exe /c start로 열어야 한다."""
        import ui_ux.bridge as bmod

        calls: list[list] = []
        monkeypatch.setattr(bmod, "_is_wsl", lambda: True)
        monkeypatch.setattr(bmod, "_is_windows", lambda: False)
        monkeypatch.setattr(bmod, "_subprocess", self._make_fake_subprocess(calls))

        bridge.openUrl("https://example.com")

        assert any("cmd.exe" in c for c in calls), "cmd.exe 호출 없음"
        assert any("start" in c for c in calls), "start 명령 없음"


# ══════════════════════════════════════════════════════════════════════════════
# 12. getHelpText / getShownTagIntro / setShownTagIntro
# ══════════════════════════════════════════════════════════════════════════════

class TestHelpAndTagIntro:
    def test_get_help_text_known_key(self, bridge):
        text = bridge.getHelpText("web_search")
        assert "#웹 검색" in text

    def test_get_help_text_file_convert(self, bridge):
        text = bridge.getHelpText("file_convert")
        assert "#파일 변환" in text

    def test_get_help_text_unknown_key(self, bridge):
        assert bridge.getHelpText("nonexistent_key") == ""

    def test_shown_tag_intro_default_false(self, bridge, tmp_path, monkeypatch):
        """preferences.json이 없으면 False 반환."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_PREFS_PATH", tmp_path / "prefs.json")
        assert bridge.getShownTagIntro() is False

    def test_set_and_get_shown_tag_intro(self, bridge, tmp_path, monkeypatch):
        """setShownTagIntro(True) 후 getShownTagIntro()가 True를 반환해야 한다."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_PREFS_PATH", tmp_path / "prefs.json")
        bridge.setShownTagIntro(True)
        assert bridge.getShownTagIntro() is True

    def test_set_preserves_existing_prefs(self, bridge, tmp_path, monkeypatch):
        """setShownTagIntro가 기존 preferences(theme 등)를 덮어쓰지 않아야 한다."""
        import ui_ux.bridge as bmod
        import json as _json
        prefs_path = tmp_path / "prefs.json"
        prefs_path.write_text(_json.dumps({"theme": "solar"}), encoding="utf-8")
        monkeypatch.setattr(bmod, "_PREFS_PATH", prefs_path)
        bridge.setShownTagIntro(True)
        saved = _json.loads(prefs_path.read_text(encoding="utf-8"))
        assert saved["theme"] == "solar"
        assert saved["shown_tag_intro"] is True


# ══════════════════════════════════════════════════════════════════════════════
# 13. getMemoryDB
# ══════════════════════════════════════════════════════════════════════════════

class TestGetMemoryDB:
    def test_returns_valid_json(self, bridge):
        result = bridge.getMemoryDB()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_has_required_keys(self, bridge):
        parsed = json.loads(bridge.getMemoryDB())
        for key in ("collection", "total", "sessions"):
            assert key in parsed, f"키 '{key}' 누락"

    def test_total_is_int(self, bridge):
        parsed = json.loads(bridge.getMemoryDB())
        assert isinstance(parsed["total"], int)

    def test_sessions_is_dict(self, bridge):
        parsed = json.loads(bridge.getMemoryDB())
        assert isinstance(parsed["sessions"], dict)

    def test_no_crash_when_long_term_unavailable(self, stub_agent):
        """long_term 모듈이 없어도 예외 없이 빈 구조 반환."""
        stub_agent.character = {"id": "Ghost", "name": "고스트"}
        from ui_ux.bridge import ChatBridge
        b = ChatBridge(stub_agent)
        result = b.getMemoryDB()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)


# ══════════════════════════════════════════════════════════════════════════════
# 14. searchMemoryPreview
# ══════════════════════════════════════════════════════════════════════════════

class TestSearchMemoryPreview:
    def test_returns_valid_json(self, bridge):
        result = bridge.searchMemoryPreview("테스트 검색어")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_empty_query_returns_empty_list(self, bridge):
        result = bridge.searchMemoryPreview("")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_result_items_have_content(self, bridge):
        """결과가 있는 경우 각 항목에 content 키가 있어야 한다."""
        result = bridge.searchMemoryPreview("이름")
        parsed = json.loads(result)
        for item in parsed:
            assert "content" in item, "content 키 누락"

    def test_result_items_have_similarity(self, bridge):
        """결과가 있는 경우 각 항목에 similarity 키가 있어야 한다."""
        result = bridge.searchMemoryPreview("이름")
        parsed = json.loads(result)
        for item in parsed:
            assert "similarity" in item, "similarity 키 누락"


# ══════════════════════════════════════════════════════════════════════════════
# 15. getConvParams
# ══════════════════════════════════════════════════════════════════════════════

class TestGetConvParams:
    def test_returns_valid_json(self, bridge):
        result = bridge.getConvParams()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_returns_empty_dict_when_no_conversation(self, stub_agent):
        """character에 'conversation' 키가 없으면 {} 반환."""
        stub_agent.character = {"id": "Haru", "name": "하루"}
        from ui_ux.bridge import ChatBridge
        b = ChatBridge(stub_agent)
        parsed = json.loads(b.getConvParams())
        assert isinstance(parsed, dict)

    def test_returns_conversation_dict_when_present(self, stub_agent):
        """character에 'conversation' 키가 있으면 그 내용을 반환한다."""
        stub_agent.character = {
            "id": "Haru",
            "name": "하루",
            "conversation": {"response_length": 0.5, "openness": 0.3, "directness": 0.6},
        }
        from ui_ux.bridge import ChatBridge
        b = ChatBridge(stub_agent)
        parsed = json.loads(b.getConvParams())
        assert parsed.get("response_length") == 0.5
        assert parsed.get("directness") == 0.6


# ══════════════════════════════════════════════════════════════════════════════
# 16. setConvParam
# ══════════════════════════════════════════════════════════════════════════════

class TestSetConvParam:
    @pytest.fixture
    def bridge_with_conv(self, stub_agent):
        stub_agent.character = {
            "id": "Haru",
            "name": "하루",
            "conversation": {
                "response_length": {"stranger": 0.3, "acquaintance": 0.4},
                "openness": {"stranger": 0.2},
                "directness": 0.5,
            },
        }
        from ui_ux.bridge import ChatBridge
        return ChatBridge(stub_agent)

    def test_set_response_length_tier(self, bridge_with_conv):
        """response_length의 특정 tier 값을 변경한다."""
        bridge_with_conv.setConvParam("response_length", "stranger", 0.8)
        conv = bridge_with_conv._agent.character["conversation"]
        assert conv["response_length"]["stranger"] == pytest.approx(0.8)

    def test_set_openness_tier(self, bridge_with_conv):
        bridge_with_conv.setConvParam("openness", "stranger", 0.7)
        conv = bridge_with_conv._agent.character["conversation"]
        assert conv["openness"]["stranger"] == pytest.approx(0.7)

    def test_set_directness_scalar(self, bridge_with_conv):
        """directness는 tier 없이 스칼라로 저장한다."""
        bridge_with_conv.setConvParam("directness", "_", 0.9)
        conv = bridge_with_conv._agent.character["conversation"]
        assert conv["directness"] == pytest.approx(0.9)

    def test_set_unknown_param_no_crash(self, bridge_with_conv):
        """알 수 없는 param도 예외 없이 처리."""
        bridge_with_conv.setConvParam("unknown_param", "stranger", 0.5)  # must not raise

    def test_set_creates_conversation_key_if_missing(self, stub_agent):
        """character에 conversation 키가 없어도 동작한다."""
        stub_agent.character = {"id": "Haru", "name": "하루"}
        from ui_ux.bridge import ChatBridge
        b = ChatBridge(stub_agent)
        b.setConvParam("directness", "_", 0.7)  # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# 17. saveNewCharacter
# ══════════════════════════════════════════════════════════════════════════════

class TestSaveNewCharacter:
    _VALID_CHAR = {
        "id": "TestHero",
        "name": "테스트 히어로",
        "speech_style": "반말을 사용한다.",
        "rules": ["AI임을 언급하지 않는다."],
        "memory_voice": "담담하게",
        "state": {"mood_default": "neutral", "affection_default": 0},
    }

    def test_valid_json_returns_char_id(self, bridge, tmp_path, monkeypatch):
        """유효한 JSON → 캐릭터 파일 생성 후 char_id 반환."""
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_CHARACTER_DIR", tmp_path)
        result = bridge.saveNewCharacter(json.dumps(self._VALID_CHAR))
        assert result == "TestHero"
        assert (tmp_path / "CH_TestHero.yaml").exists()

    def test_yaml_content_is_correct(self, bridge, tmp_path, monkeypatch):
        """저장된 YAML에 name 필드가 올바르게 포함된다."""
        import yaml as _yaml
        import ui_ux.bridge as bmod
        monkeypatch.setattr(bmod, "_CHARACTER_DIR", tmp_path)
        bridge.saveNewCharacter(json.dumps(self._VALID_CHAR))
        saved = _yaml.safe_load((tmp_path / "CH_TestHero.yaml").read_text(encoding="utf-8"))
        assert saved["name"] == "테스트 히어로"

    def test_invalid_json_returns_empty_string(self, bridge):
        """잘못된 JSON → "" 반환."""
        result = bridge.saveNewCharacter("not json {{{")
        assert result == ""

    def test_missing_id_returns_empty_string(self, bridge):
        """id 필드 없는 JSON → "" 반환."""
        data = dict(self._VALID_CHAR)
        del data["id"]
        result = bridge.saveNewCharacter(json.dumps(data))
        assert result == ""

    def test_empty_id_returns_empty_string(self, bridge):
        """id가 빈 문자열 → "" 반환."""
        data = dict(self._VALID_CHAR)
        data["id"] = "   "
        result = bridge.saveNewCharacter(json.dumps(data))
        assert result == ""


# ══════════════════════════════════════════════════════════════════════════════
# editMessage
# ══════════════════════════════════════════════════════════════════════════════

class TestEditMessage:
    def test_no_op_when_content_unchanged(self, bridge):
        """old_content == new_content면 아무것도 하지 않는다."""
        bridge.editMessage(0, "같은 내용", "같은 내용")  # must not raise

    def test_updates_session_dialogue_log(self, stub_agent):
        """session.dialogue_log에서 일치하는 assistant 메시지를 교체한다."""
        from conversation.core.session import ConversationSession
        from unittest.mock import MagicMock
        from ui_ux.bridge import ChatBridge

        stub_agent.session = MagicMock()
        stub_agent.session.dialogue_log = [
            {"role": "user",      "content": "안녕"},
            {"role": "assistant", "content": "원본 응답"},
        ]
        b = ChatBridge(stub_agent)
        b.editMessage(1, "원본 응답", "수정된 응답")
        assert stub_agent.session.dialogue_log[1]["content"] == "수정된 응답"

    def test_does_not_update_user_messages(self, stub_agent):
        """role=user 메시지는 변경하지 않는다."""
        from unittest.mock import MagicMock
        from ui_ux.bridge import ChatBridge

        stub_agent.session = MagicMock()
        stub_agent.session.dialogue_log = [
            {"role": "user",      "content": "원본 응답"},
            {"role": "assistant", "content": "다른 내용"},
        ]
        b = ChatBridge(stub_agent)
        b.editMessage(0, "원본 응답", "바뀐 내용")
        # user 메시지는 바뀌지 않아야 함
        assert stub_agent.session.dialogue_log[0]["content"] == "원본 응답"

    def test_no_crash_without_session(self, bridge):
        """session=None이어도 예외 없이 종료한다."""
        bridge.editMessage(0, "원본", "수정")  # must not raise
