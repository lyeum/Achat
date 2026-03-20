"""UI 구조 검증 테스트.

QML 파일 존재 여부, qmldir 등록, bridge 슬롯 시그니처를 검사한다.
모델/GPU 없이 실행 가능 (ACHAT_ENV=ui_test 자동 적용).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# ── 프로젝트 루트를 sys.path에 추가 ────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ACHAT_ENV", "ui_test")

QML_DIR   = ROOT / "ui_ux" / "qml"
ASSET_DIR = ROOT / "ui_ux" / "assets"


# ══════════════════════════════════════════════════════════════════════════════
# 1. QML 파일 존재 확인
# ══════════════════════════════════════════════════════════════════════════════

REQUIRED_QML_FILES = [
    "main.qml",
    "PipWindow.qml",
    "SettingsPanel.qml",
    "CharacterDisplay.qml",
    "CustomizationPanel.qml",
    "ChatBubble.qml",
    "Style.qml",
    "qmldir",
]


@pytest.mark.parametrize("filename", REQUIRED_QML_FILES)
def test_qml_file_exists(filename: str) -> None:
    assert (QML_DIR / filename).exists(), f"{filename} 파일이 없음"


# ══════════════════════════════════════════════════════════════════════════════
# 2. qmldir 등록 확인
# ══════════════════════════════════════════════════════════════════════════════

REQUIRED_QMLDIR_ENTRIES = [
    "ChatBubble",
    "PipWindow",
    "SettingsPanel",
    "CharacterDisplay",
    "CustomizationPanel",
]


def test_qmldir_has_all_components() -> None:
    qmldir = (QML_DIR / "qmldir").read_text(encoding="utf-8")
    for name in REQUIRED_QMLDIR_ENTRIES:
        assert name in qmldir, f"qmldir에 {name} 등록 없음"


# ══════════════════════════════════════════════════════════════════════════════
# 3. QML 파일 내 필수 시그널/프로퍼티 선언 확인
# ══════════════════════════════════════════════════════════════════════════════

class TestMainQml:
    src = (QML_DIR / "main.qml").read_text(encoding="utf-8")

    def test_has_isBubble(self):
        assert "isBubble" in self.src

    def test_has_pipBubbleOpen(self):
        assert "pipBubbleOpen" in self.src

    def test_has_settingsOpen(self):
        assert "settingsOpen" in self.src

    def test_has_customizationOpen(self):
        assert "customizationOpen" in self.src

    def test_has_customPartsJson(self):
        assert "customPartsJson" in self.src

    def test_has_inputReady(self):
        assert "inputReady" in self.src

    def test_has_backgroundImageUrl(self):
        assert "backgroundImageUrl" in self.src

    def test_has_currentMood(self):
        assert "currentMood" in self.src

    def test_pip_message_not_doubled(self):
        """PIP onMessageSent 핸들러에서 messageModel.append를 직접 호출하지 않음.
        bridge.sendMessage가 messageAdded emit → Connections가 처리하므로 중복 방지.
        """
        # onMessageSent 블록만 추출 (bridge.sendMessage 호출까지 약 300자)
        start = self.src.find("onMessageSent:")
        block = self.src[start:start + 300]
        # 주석이 아닌 실제 코드에서 append 호출 여부 확인
        code_lines = [
            line for line in block.splitlines()
            if line.strip() and not line.strip().startswith("//")
        ]
        code_only = "\n".join(code_lines)
        assert "messageModel.append" not in code_only, \
            "PIP onMessageSent에서 messageModel.append 직접 호출 → user 메시지 중복"

    def test_load_customization_null_guard(self):
        """_loadCustomization에서 bridge null 체크."""
        load_fn = self.src[self.src.find("function _loadCustomization"):
                            self.src.find("function _loadCustomization") + 200]
        assert "if (!bridge)" in load_fn or "if (bridge)" in load_fn, \
            "_loadCustomization에 bridge null 가드 없음"

    def test_has_settings_panel_component(self):
        assert "SettingsPanel {" in self.src

    def test_has_customization_panel_component(self):
        assert "CustomizationPanel {" in self.src

    def test_has_character_display_component(self):
        assert "CharacterDisplay {" in self.src

    def test_pip_bubble_open_not_bound(self):
        """bubbleOpen: root.pipBubbleOpen 바인딩이 제거되어야 함 (바인딩 루프)."""
        pip_block_start = self.src.find("PipWindow {")
        pip_block_end   = self.src.find("onExpandRequested", pip_block_start)
        pip_block = self.src[pip_block_start:pip_block_end]
        assert "bubbleOpen:   root.pipBubbleOpen" not in pip_block, \
            "PipWindow bubbleOpen 바인딩이 남아있음 — 바인딩 루프 발생"


class TestPipWindowQml:
    src = (QML_DIR / "PipWindow.qml").read_text(encoding="utf-8")

    def test_has_expand_requested_signal(self):
        assert "signal expandRequested" in self.src

    def test_has_message_sent_signal(self):
        assert "signal messageSent" in self.src

    def test_has_show_bubble_function(self):
        assert "function showBubble" in self.src

    def test_has_auto_close_timer(self):
        assert "autoClose" in self.src

    def test_has_bubble_open_property(self):
        assert "property bool   bubbleOpen" in self.src


class TestSettingsPanelQml:
    src = (QML_DIR / "SettingsPanel.qml").read_text(encoding="utf-8")

    def test_has_close_requested_signal(self):
        assert "signal closeRequested" in self.src

    def test_has_customization_requested_signal(self):
        assert "signal customizationRequested" in self.src

    def test_no_nested_repeater_parent_ref(self):
        """parent._wId / parent._scId 패턴이 제거되었는지 확인."""
        assert "parent._wId" not in self.src, \
            "parent._wId 참조 잔존 — Repeater delegate scope 버그"
        assert "parent._scId" not in self.src, \
            "parent._scId 참조 잔존 — Repeater delegate scope 버그"

    def test_flat_model_has_world_id(self):
        """flat 모델에서 world_id를 modelData로 직접 접근."""
        assert "modelData.world_id" in self.src
        assert "modelData.scenario_id" in self.src
        assert "modelData.act_id" in self.src


class TestCharacterDisplayQml:
    src = (QML_DIR / "CharacterDisplay.qml").read_text(encoding="utf-8")

    def test_has_character_id_property(self):
        assert "property string characterId" in self.src

    def test_has_parts_json_property(self):
        assert "property string partsJson" in self.src

    def test_has_current_mood_property(self):
        assert "property string currentMood" in self.src

    def test_has_use_icon_logic(self):
        assert "_useIcon" in self.src

    def test_no_empty_behavior_on_source(self):
        """빈 Behavior on source {} 제거 확인."""
        assert "Behavior on source { }" not in self.src and \
               "Behavior on source {}" not in self.src, \
            "빈 Behavior on source {} 잔존"

    def test_has_placeholder_rectangle(self):
        assert "_hasAnyPart" in self.src

    def test_has_seven_image_layers(self):
        """레이어 7개: icon + base/cloth/hair/eye/mouth(5 parts) + emotion."""
        assert self.src.count("Image {") >= 7

    def test_icon_path_uses_icons_dir(self):
        """icons/{characterId}/{characterId}.png 경로 사용 확인."""
        assert "assets/icons/" in self.src

    def test_emotion_path_uses_emotion_dir(self):
        """icons/{id}/emotion/{mood}.png 경로 사용 확인."""
        assert "emotion/" in self.src

    def test_parts_use_characters_dir(self):
        """characters/{type}/{file} 경로 사용 확인."""
        assert "assets/characters/" in self.src


class TestCustomizationPanelQml:
    src = (QML_DIR / "CustomizationPanel.qml").read_text(encoding="utf-8")

    def test_has_saved_signal(self):
        assert "signal saved" in self.src

    def test_has_close_requested_signal(self):
        assert "signal closeRequested" in self.src

    def test_no_delegate_parent_selected_ref(self):
        """ListView delegate 내부에서 parent._selected를 비교하는 코드가 없어야 함.
        (ListView.outerSelected 프로퍼티에 parent._selected를 할당하는 것은 허용)
        """
        # delegate 안에서의 비교 패턴: parent._selected === ...
        assert "parent._selected ===" not in self.src, \
            "ListView delegate 내부 parent._selected === 비교 잔존 — contentItem scope 버그"

    def test_uses_listview_view(self):
        """ListView.view attached property를 사용해 outer scope 접근."""
        assert "ListView.view" in self.src

    def test_has_panel_rect_click_consumer(self):
        """panelRect 내 MouseArea가 클릭 이벤트를 소비."""
        panel_section = self.src[self.src.find("id: panelRect"):
                                  self.src.find("id: panelRect") + 300]
        assert "MouseArea" in panel_section, \
            "panelRect에 클릭 이벤트 소비 MouseArea 없음"

    def test_has_save_button(self):
        assert "저장" in self.src

    def test_has_all_part_types(self):
        for part in ["base", "hair", "eye", "mouth", "cloth"]:
            assert part in self.src, f"파츠 타입 '{part}' 미포함"

    def test_no_effects_json_property(self):
        """effectsJson 프로퍼티가 제거되었는지 확인 (감정 효과는 developer 전용)."""
        assert "property string effectsJson" not in self.src


# ══════════════════════════════════════════════════════════════════════════════
# 4. 에셋 디렉토리 구조 확인
# ══════════════════════════════════════════════════════════════════════════════

REQUIRED_ASSET_DIRS = [
    "characters",
    "icons",
]


@pytest.mark.parametrize("dirname", REQUIRED_ASSET_DIRS)
def test_asset_directory_exists(dirname: str) -> None:
    assert (ASSET_DIR / dirname).exists(), f"assets/{dirname} 디렉토리 없음"


def test_character_custom_dir_or_gitkeep() -> None:
    """custom 또는 parts 디렉토리 하나 이상 존재 or .gitkeep."""
    char_dir = ASSET_DIR / "characters"
    assert char_dir.exists()
    # .gitkeep이나 하위 디렉토리 중 하나 이상 있으면 됨
    assert any(char_dir.iterdir()), "assets/characters 디렉토리가 완전히 비어있음"
