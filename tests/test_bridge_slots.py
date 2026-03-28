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
