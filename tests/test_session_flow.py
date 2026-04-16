"""세션 흐름 통합 테스트.

각 테스트는 "설정 → 동작 → 검증" 을 연쇄적으로 검증한다.
단일 메서드를 고립 검증하는 것이 아니라, 여러 컴포넌트가 협력하는 전체 흐름을 다룬다.

검증 범위:
    1. getSessionHistory — 대화 기록 분할 (** / * 마커 포함)
    2. 세션 저장 → 복원 라운드트립 (_init_session + dialogue.json)
    3. changeCharacter — chatReset emit + 이전 기록 복원 연쇄
    4. changeWorld (world_changed=True) — chatReset emit + 새 세션 기록 복원 연쇄
    5. changeWorld (same world) — dialogue_log 보존 연쇄
    6. _rebuild_agent — dialogue_log 복원 연쇄
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
_app = QCoreApplication.instance() or QCoreApplication(sys.argv)


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


def _make_dialogue(pairs: list[tuple[str, str]]) -> list[dict]:
    """(role, content) 쌍으로 dialogue_log 형식을 만든다."""
    return [{"role": r, "content": c} for r, c in pairs]


# ══════════════════════════════════════════════════════════════════════════════
# 1. getSessionHistory — 대화 기록 슬롯 검증
# ══════════════════════════════════════════════════════════════════════════════

class TestGetSessionHistory:
    """getSessionHistory()가 dialogue_log를 QML이 소비할 수 있는 형식으로 변환하는지 검증.

    흐름: dialogue_log 설정 → getSessionHistory() 호출 → 반환값 형식 검증
    """

    def test_empty_session_returns_empty_list(self, bridge):
        """세션이 없으면 빈 리스트를 반환한다."""
        bridge._agent.session = None
        result = bridge.getSessionHistory()
        assert result == []

    def test_returns_recent_turns_only(self, bridge):
        """_HISTORY_DISPLAY_TURNS(10) * 2 메시지만 반환한다.

        흐름: 25턴(50메시지) dialogue_log 설정 → getSessionHistory() → 최근 20메시지만 반환
        """
        session = MagicMock()
        session.dialogue_log = _make_dialogue(
            [(("user", f"msg{i}") if i % 2 == 0 else ("assistant", f"resp{i}"))
             for i in range(50)]
        )
        bridge._agent.session = session

        result = bridge.getSessionHistory()
        max_msgs = bridge._HISTORY_DISPLAY_TURNS * 2
        assert len(result) <= max_msgs

    def test_assistant_response_with_double_asterisk_split(self, bridge):
        """assistant 응답의 **...** 가 narrator 버블로 분리되어 반환된다.

        흐름: **나레이션** 포함 응답 저장 → getSessionHistory() → narrator/assistant 순으로 분리
        """
        session = MagicMock()
        session.dialogue_log = _make_dialogue([
            ("user", "안녕"),
            ("assistant", "잠깐. **하루의 눈이 흔들렸다.** 뭐야, 갑자기."),
        ])
        bridge._agent.session = session

        result = bridge.getSessionHistory()
        roles = [item["role"] for item in result]
        contents = [item["content"] for item in result]

        assert "narrator" in roles
        assert "assistant" in roles
        assert any("하루의 눈이 흔들렸다." in c for c in contents)
        assert any("잠깐." in c for c in contents)

    def test_assistant_response_with_single_asterisk_split(self, bridge):
        """assistant 응답의 *...* 가 narrator 버블로 분리되어 반환된다.

        흐름: *행동* 포함 응답 저장 → getSessionHistory() → narrator로 분리
        """
        session = MagicMock()
        session.dialogue_log = _make_dialogue([
            ("user", "뭐해?"),
            ("assistant", "*창가를 바라본다* 그냥."),
        ])
        bridge._agent.session = session

        result = bridge.getSessionHistory()
        roles = [item["role"] for item in result]
        assert "narrator" in roles

    def test_user_messages_are_not_split(self, bridge):
        """user 발화는 narrator 분리 없이 그대로 반환된다.

        흐름: 일반 user 발화 저장 → getSessionHistory() → user role 그대로 반환
        """
        session = MagicMock()
        session.dialogue_log = _make_dialogue([
            ("user", "오늘 바다 보러 갈까?"),
            ("assistant", "좋아."),
        ])
        bridge._agent.session = session

        result = bridge.getSessionHistory()
        user_msgs = [item for item in result if item["role"] == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0]["content"] == "오늘 바다 보러 갈까?"

    def test_empty_content_messages_are_skipped(self, bridge):
        """content가 빈 메시지는 반환값에서 제외된다."""
        session = MagicMock()
        session.dialogue_log = [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": "응."},
            {"role": "user", "content": "안녕"},
        ]
        bridge._agent.session = session

        result = bridge.getSessionHistory()
        assert all(item["content"] for item in result)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 세션 저장 → 복원 라운드트립
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionPersistenceRoundtrip:
    """대화 기록이 저장되고 복원되는 전체 흐름을 검증.

    흐름: dialogue 저장 → load_dialogue → _restore_session_from_state → dialogue_log 복원
    """

    def test_save_and_load_dialogue_roundtrip(self, tmp_path):
        """save_dialogue → load_dialogue 라운드트립: 저장한 내용이 그대로 복원된다.

        흐름: 대화 기록 저장 → 앱 재시작 시뮬레이션(load_dialogue) → 동일 내용 확인
        """
        from conversation.session_manager import SessionManager

        sm = SessionManager(tmp_path)
        original_dialogue = _make_dialogue([
            ("user", "안녕"),
            ("assistant", "어. 왔어?"),
            ("user", "오늘 날씨 좋다"),
            ("assistant", "그래."),
        ])

        sm.save_dialogue("Haru", "s_test_001", original_dialogue)
        loaded = sm.load_dialogue("Haru", "s_test_001")

        assert loaded == original_dialogue

    def test_restore_session_from_state_loads_dialogue(self, bridge, tmp_path):
        """_restore_session_from_state가 dialogue.json에서 dialogue_log를 복원한다.

        흐름:
          1. dialogue.json에 대화 기록 저장
          2. SessionManager + 새 세션 설정
          3. _restore_session_from_state 호출
          4. session.dialogue_log가 복원되었는지 확인
        """
        from conversation.session_manager import SessionManager, SessionState

        sm = SessionManager(tmp_path)
        char_id = "Haru"
        session_id = "s_20260416_abc123"

        saved_dialogue = _make_dialogue([
            ("user", "반가워"),
            ("assistant", "어. 뭐야."),
        ])
        sm.save_dialogue(char_id, session_id, saved_dialogue)

        state = SessionState(
            session_id=session_id, char_id=char_id,
            mood="neutral", affection=30, turn_count=1,
        )

        mock_session = MagicMock()
        mock_session.dialogue_log = []
        bridge._agent.session = mock_session
        bridge._agent.character = {"id": char_id}
        bridge._session_manager = sm

        bridge._restore_session_from_state(state)

        assert mock_session.dialogue_log == saved_dialogue

    def test_restore_session_copies_all_state_fields(self, bridge, tmp_path):
        """_restore_session_from_state가 mood / affection / turn_count / 트리거 상태를 복원한다.

        흐름: SessionState 설정 → _restore_session_from_state → 각 필드 검증
        """
        from conversation.session_manager import SessionManager, SessionState

        sm = SessionManager(tmp_path)
        state = SessionState(
            session_id="s_test_fields",
            char_id="Haru",
            mood="happy",
            affection=75,
            turn_count=12,
            location="beach",
            scenario_id="morning_walk",
            act_id="act_1",
            fired_stories=["등대 전설"],
            visited_places=["beach"],
            explained_cultures=["해산물 축제"],
        )

        mock_session = MagicMock()
        mock_session.dialogue_log = []
        bridge._agent.session = mock_session
        bridge._agent.character = {"id": "Haru"}
        bridge._session_manager = sm

        bridge._restore_session_from_state(state)

        assert mock_session.session_id == "s_test_fields"
        assert mock_session.mood       == "happy"
        assert mock_session.affection  == 75
        assert mock_session.turn_count == 12
        assert mock_session.fired_stories      == ["등대 전설"]
        assert mock_session.visited_places     == ["beach"]
        assert mock_session.explained_cultures == ["해산물 축제"]


# ══════════════════════════════════════════════════════════════════════════════
# 3. _rebuild_agent — dialogue_log 복원 연쇄
# ══════════════════════════════════════════════════════════════════════════════

class TestRebuildAgentDialogueRestore:
    """_rebuild_agent() 호출 후 dialogue_log가 복원되는 연쇄 흐름.

    흐름: dialogue.json 저장 → _rebuild_agent() → agent.session.dialogue_log 확인
    """

    def test_rebuild_agent_restores_dialogue_log(self, tmp_path):
        """swap_character() 후 dialogue.json에서 dialogue_log가 자동 복원된다.

        흐름:
          1. dialogue.json에 대화 저장
          2. _rebuild_agent() 호출 (swap_character mock)
          3. agent.session.dialogue_log가 복원되었는지 확인
        """
        from ui_ux.bridge import ChatBridge
        from conversation.session_manager import SessionManager, SessionState

        sm = SessionManager(tmp_path)
        saved_dialogue = _make_dialogue([
            ("user", "안녕"),
            ("assistant", "어."),
        ])
        sm.save_dialogue("Haru", "s_restore_test", saved_dialogue)

        state = SessionState(
            session_id="s_restore_test", char_id="Haru",
            mood="neutral", affection=30, turn_count=1,
        )

        mock_session = MagicMock()
        mock_session.dialogue_log = []

        fake_agent = MagicMock()
        fake_agent.character = {"id": "Haru", "name": "하루"}
        fake_agent.session = mock_session
        fake_agent.swap_character = MagicMock()

        bridge_inst = ChatBridge.__new__(ChatBridge)
        bridge_inst._agent = fake_agent
        bridge_inst._session_manager = sm
        bridge_inst._conv_logger = None

        bridge_inst._rebuild_agent.__func__

        with patch.object(bridge_inst, "_resolve_initial_location", return_value=""):
            bridge_inst._rebuild_agent(state)

        # swap_character 호출 후 dialogue_log가 복원되어야 함
        assert fake_agent.session.dialogue_log == saved_dialogue

    def test_rebuild_agent_skips_dialogue_when_empty(self, tmp_path):
        """dialogue.json이 없으면 dialogue_log를 덮어쓰지 않는다.

        흐름: dialogue.json 없음 → _rebuild_agent() → 기존 dialogue_log 유지
        """
        from ui_ux.bridge import ChatBridge
        from conversation.session_manager import SessionManager, SessionState

        sm = SessionManager(tmp_path)  # dialogue.json 없음
        state = SessionState(
            session_id="s_no_dialogue", char_id="Haru",
            mood="neutral", affection=30, turn_count=0,
        )

        existing_dialogue = _make_dialogue([("user", "기존 기록")])
        mock_session = MagicMock()
        mock_session.dialogue_log = existing_dialogue

        fake_agent = MagicMock()
        fake_agent.character = {"id": "Haru", "name": "하루"}
        fake_agent.session = mock_session
        fake_agent.swap_character = MagicMock()

        bridge_inst = ChatBridge.__new__(ChatBridge)
        bridge_inst._agent = fake_agent
        bridge_inst._session_manager = sm
        bridge_inst._conv_logger = None

        with patch.object(bridge_inst, "_resolve_initial_location", return_value=""):
            bridge_inst._rebuild_agent(state)

        # 빈 dialogue를 로드했으므로 기존 dialogue_log가 그대로여야 함
        # (load_dialogue가 [] 반환 → if dialogue: 조건 미충족 → 덮어쓰기 없음)
        assert mock_session.dialogue_log == existing_dialogue


# ══════════════════════════════════════════════════════════════════════════════
# 4. changeCharacter — chatReset emit 연쇄
# ══════════════════════════════════════════════════════════════════════════════

class TestChangeCharacterChatReset:
    """changeCharacter() 호출 시 chatReset이 emit되고 이전 기록이 포함되는 전체 흐름.

    흐름: 이전 대화 저장 → changeCharacter() → chatReset emit → history에 이전 기록 포함
    """

    def test_chat_reset_emitted_on_character_change(self, bridge, tmp_path, monkeypatch):
        """changeCharacter() 호출 시 chatReset 시그널이 emit된다.

        흐름:
          1. 세션 + dialogue_log 설정
          2. changeCharacter() 호출 (실 파일 I/O 없이 mock)
          3. chatReset 시그널이 1회 emit되었는지 확인
        """
        import ui_ux.bridge as bmod

        reset_calls: list[list] = []
        bridge.chatReset.connect(lambda h: reset_calls.append(list(h)))

        sm_mock = MagicMock()
        sm_mock.activate.return_value = MagicMock(
            session_id="s_new", char_id="MookHyeon",
            mood="neutral", affection=30, world_id=None,
            scenario_id=None, act_id=None, location="",
            fired_stories=[], visited_places=[], explained_cultures=[],
            turn_count=0,
        )
        bridge._session_manager = sm_mock
        bridge._agent._stub = False

        with patch.object(bridge, "_sync_session_state"), \
             patch.object(bridge, "_rebuild_agent"), \
             patch.object(bridge, "_build_bg_url", return_value=""), \
             patch.object(bridge, "_read_mood", return_value="neutral"):
            bridge.changeCharacter("MookHyeon")

        assert len(reset_calls) == 1, \
            f"chatReset이 1회 emit되어야 함 (실제: {len(reset_calls)}회)"

    def test_chat_reset_history_contains_previous_dialogue(self, bridge, tmp_path):
        """changeCharacter() 후 chatReset에 전달된 history가 이전 대화를 포함한다.

        흐름:
          1. 새 캐릭터 세션에 dialogue.json 저장
          2. changeCharacter() 호출
          3. chatReset에 전달된 history가 해당 대화를 포함하는지 확인
        """
        from conversation.session_manager import SessionManager

        sm = SessionManager(tmp_path)
        new_dialogue = _make_dialogue([
            ("user", "처음 만나네"),
            ("assistant", "어. 그래."),
        ])
        target_state = sm.activate("MookHyeon")
        sm.save_dialogue("MookHyeon", target_state.session_id, new_dialogue)

        # 새 캐릭터의 세션으로 activate하도록 session_manager 교체
        bridge._session_manager = sm
        bridge._agent._stub = False

        reset_calls: list[list] = []
        bridge.chatReset.connect(lambda h: reset_calls.append(list(h)))

        with patch.object(bridge, "_sync_session_state"), \
             patch.object(bridge, "_rebuild_agent") as mock_rebuild, \
             patch.object(bridge, "_build_bg_url", return_value=""), \
             patch.object(bridge, "_read_mood", return_value="neutral"):

            # _rebuild_agent 호출 후 session.dialogue_log를 설정해 getSessionHistory가 읽을 수 있게
            def fake_rebuild(state):
                mock_session = MagicMock()
                mock_session.dialogue_log = new_dialogue
                bridge._agent.session = mock_session

            mock_rebuild.side_effect = fake_rebuild
            bridge.changeCharacter("MookHyeon")

        assert len(reset_calls) == 1
        history = reset_calls[0]
        contents = [item["content"] for item in history]
        assert any("처음 만나네" in c for c in contents)

    def test_chat_reset_not_emitted_in_stub_mode(self, bridge):
        """stub 모드에서 changeCharacter()는 아무것도 하지 않는다 (chatReset 미emit).

        흐름: _stub=True 상태로 changeCharacter() 호출 → chatReset 미발생
        """
        bridge._agent._stub = True

        reset_calls: list[list] = []
        bridge.chatReset.connect(lambda h: reset_calls.append(list(h)))

        bridge.changeCharacter("Haru")

        assert len(reset_calls) == 0


# ══════════════════════════════════════════════════════════════════════════════
# 5. changeWorld — world_changed=True 시 chatReset emit 연쇄
# ══════════════════════════════════════════════════════════════════════════════

class TestChangeWorldChatReset:
    """changeWorld() 호출 시 세계관 변경 여부에 따른 chatReset 동작 검증.

    흐름:
      - world_changed=True:  chatReset emit (채팅창 초기화 + 새 세션 기록)
      - world_changed=False: chatReset 미emit (같은 세션 유지)
    """

    def _make_mock_session(self, world_id: str, dialogue: list | None = None) -> MagicMock:
        s = MagicMock()
        s.world_id   = world_id
        s.session_id = "s_current"
        s.dialogue_log = dialogue or []
        return s

    def test_chat_reset_emitted_when_world_changes(self, bridge, tmp_path):
        """다른 세계관으로 변경 시 chatReset이 emit된다.

        흐름:
          1. 현재 세션: world_id="seaside_world"
          2. changeWorld("new_world", ...) 호출
          3. chatReset emit 확인
        """
        from conversation.session_manager import SessionManager
        from conversation.loader.world_load import load_world
        import ui_ux.bridge as bmod

        sm = SessionManager(tmp_path)
        bridge._session_manager = sm
        bridge._agent._stub    = False
        bridge._agent.session  = self._make_mock_session("seaside_world")
        bridge._agent.router   = None

        reset_calls: list = []
        bridge.chatReset.connect(lambda h: reset_calls.append(h))

        # 실제 YAML 로딩을 우회해 changeWorld 내부 로직만 실행
        fake_world = {
            "world_id": "new_world",
            "scenarios": [],
            "description": "",
        }
        fake_act = {"location": "forest"}

        with patch("conversation.loader.world_load.load_world", return_value=fake_world), \
             patch("conversation.loader.world_load.get_act", return_value=fake_act), \
             patch.object(bridge, "_sync_session_state"), \
             patch.object(bridge, "_rebuild_agent"), \
             patch.object(bridge, "_build_bg_url", return_value=""), \
             patch.object(bridge, "_read_mood", return_value="neutral"), \
             patch("ui_ux.bridge._WORLD_DIR") as mock_dir:
            # _WORLD_DIR.glob이 하나의 fake yaml 경로를 반환하도록 설정
            fake_path = MagicMock()
            mock_dir.glob.return_value = [fake_path]
            bridge.changeWorld("new_world", "scenario_1", "act_1")

        assert len(reset_calls) == 1, \
            f"world_changed=True 시 chatReset이 1회 emit되어야 함 (실제: {len(reset_calls)}회)"

    def test_chat_reset_not_emitted_when_same_world(self, bridge, tmp_path):
        """같은 세계관 내 act 변경 시 chatReset이 emit되지 않는다.

        흐름:
          1. 현재 세션: world_id="seaside_world"
          2. changeWorld("seaside_world", ...) 호출 (같은 world_id)
          3. chatReset 미발생 확인
        """
        from conversation.session_manager import SessionManager
        from conversation.core.session import ConversationSession

        sm = SessionManager(tmp_path)
        bridge._session_manager = sm
        bridge._agent._stub    = False
        bridge._agent.session  = self._make_mock_session("seaside_world")

        reset_calls: list = []
        bridge.chatReset.connect(lambda h: reset_calls.append(h))

        fake_world = {
            "world_id": "seaside_world",
            "scenarios": [],
            "description": "",
            "character_overrides": None,
        }
        fake_act = {"location": "harbor"}

        with patch("conversation.loader.world_load.load_world", return_value=fake_world), \
             patch("conversation.loader.world_load.get_act", return_value=fake_act), \
             patch("agent.persona.swap_persona", return_value=(
                 {"id": "Haru"},
                 ConversationSession.from_character({"id": "Haru", "state": {}})
             )), \
             patch.object(bridge, "_sync_session_state"), \
             patch.object(bridge, "_build_bg_url", return_value=""), \
             patch.object(bridge, "_read_mood", return_value="neutral"), \
             patch("ui_ux.bridge._WORLD_DIR") as mock_dir:
            fake_path = MagicMock()
            mock_dir.glob.return_value = [fake_path]
            bridge.changeWorld("seaside_world", "scenario_1", "act_2")

        assert len(reset_calls) == 0, \
            f"world_changed=False 시 chatReset이 emit되면 안 됨 (실제: {len(reset_calls)}회)"


# ══════════════════════════════════════════════════════════════════════════════
# 6. changeWorld (same world) — dialogue_log 보존 연쇄
# ══════════════════════════════════════════════════════════════════════════════

class TestChangeWorldSameWorldDialoguePreservation:
    """같은 세계관 내 act 변경 시 dialogue_log가 새 세션으로 이전되는 흐름.

    흐름:
      1. 현재 세션에 dialogue_log 설정
      2. 같은 world_id로 changeWorld() (act만 변경)
      3. 새 세션의 dialogue_log가 기존 기록을 그대로 가지는지 확인
    """

    def test_dialogue_log_preserved_on_same_world_act_change(self, bridge, tmp_path):
        """같은 세계관 act 변경 후 새 세션이 기존 dialogue_log를 가진다.

        흐름:
          1. 현재 session.dialogue_log = [("user","안녕"), ("assistant","어.")]
          2. 같은 world_id로 changeWorld (act만 변경)
          3. 교체된 new_session.dialogue_log == 기존 대화 기록
        """
        from conversation.session_manager import SessionManager
        from conversation.core.session import ConversationSession

        sm = SessionManager(tmp_path)
        bridge._session_manager = sm
        bridge._agent._stub = False

        original_dialogue = _make_dialogue([
            ("user", "안녕"),
            ("assistant", "어."),
            ("user", "오늘 어디 가?"),
            ("assistant", "*창가를 바라보며* 몰라."),
        ])

        current_session = MagicMock()
        current_session.world_id   = "seaside_world"
        current_session.session_id = "s_original"
        current_session.dialogue_log = original_dialogue
        bridge._agent.session = current_session

        new_session_holder: list = []

        def fake_swap_persona(**kwargs):
            new_char = {"id": "Haru"}
            new_sess = ConversationSession.from_character({"id": "Haru", "state": {}})
            # swap_persona 자체는 dialogue_log를 초기화한다 (빈 리스트)
            return new_char, new_sess

        fake_world = {
            "world_id": "seaside_world",
            "scenarios": [],
            "description": "",
            "character_overrides": None,
        }
        fake_act = {"location": "harbor"}

        with patch("conversation.loader.world_load.load_world", return_value=fake_world), \
             patch("conversation.loader.world_load.get_act", return_value=fake_act), \
             patch("agent.persona.swap_persona", side_effect=fake_swap_persona), \
             patch.object(bridge, "_sync_session_state"), \
             patch.object(bridge, "_build_bg_url", return_value=""), \
             patch.object(bridge, "_read_mood", return_value="neutral"), \
             patch("ui_ux.bridge._WORLD_DIR") as mock_dir:
            fake_path = MagicMock()
            mock_dir.glob.return_value = [fake_path]
            bridge.changeWorld("seaside_world", "scenario_1", "act_2")

        # changeWorld 후 agent.session이 new_session으로 교체됨
        new_sess = bridge._agent.session
        assert new_sess.dialogue_log == original_dialogue, \
            f"dialogue_log가 보존되지 않음. 실제: {new_sess.dialogue_log}"

    def test_session_id_preserved_on_same_world_act_change(self, bridge, tmp_path):
        """같은 세계관 act 변경 후 session_id가 유지된다.

        흐름:
          1. 현재 session.session_id = "s_original"
          2. 같은 world_id로 changeWorld
          3. 새 세션의 session_id == "s_original"
        """
        from conversation.session_manager import SessionManager
        from conversation.core.session import ConversationSession

        sm = SessionManager(tmp_path)
        bridge._session_manager = sm
        bridge._agent._stub = False

        current_session = MagicMock()
        current_session.world_id   = "seaside_world"
        current_session.session_id = "s_original_id"
        current_session.dialogue_log = []
        bridge._agent.session = current_session

        fake_world = {
            "world_id": "seaside_world",
            "scenarios": [],
            "description": "",
            "character_overrides": None,
        }
        fake_act = {"location": "beach"}

        with patch("conversation.loader.world_load.load_world", return_value=fake_world), \
             patch("conversation.loader.world_load.get_act", return_value=fake_act), \
             patch("agent.persona.swap_persona", return_value=(
                 {"id": "Haru"},
                 ConversationSession.from_character({"id": "Haru", "state": {}})
             )), \
             patch.object(bridge, "_sync_session_state"), \
             patch.object(bridge, "_build_bg_url", return_value=""), \
             patch.object(bridge, "_read_mood", return_value="neutral"), \
             patch("ui_ux.bridge._WORLD_DIR") as mock_dir:
            fake_path = MagicMock()
            mock_dir.glob.return_value = [fake_path]
            bridge.changeWorld("seaside_world", "scenario_1", "act_2")

        assert bridge._agent.session.session_id == "s_original_id"
