from __future__ import annotations

import json
import platform
import re
import subprocess as _subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QRunnable, QThreadPool, QUrl, Signal, Slot
from PySide6.QtWidgets import QApplication

_ACTION_RE    = re.compile(r"^\*(.+)\*$")
_SPLIT_RE     = re.compile(r"\*\*(.+?)\*\*|\*([^*\n]+)\*", re.DOTALL)


def _split_narration(text: str, default_role: str) -> list[tuple[str, str]]:
    """**...**와 *...* 로 둘러싸인 부분을 narrator, 나머지를 default_role로 순서대로 분리한다.

    **...**  — 세계관/분위기 묘사 (narrator 버블)
    *...*    — 행동/동작 묘사   (narrator 버블)
    """
    parts: list[tuple[str, str]] = []
    last = 0
    for m in _SPLIT_RE.finditer(text):
        before = text[last:m.start()].strip()
        if before:
            parts.append((default_role, before))
        narr = (m.group(1) or m.group(2) or "").strip()
        if narr:
            parts.append(("narrator", narr))
        last = m.end()
    after = text[last:].strip()
    if after:
        parts.append((default_role, after))
    return parts if parts else [(default_role, text)]


# ── 플랫폼 감지 헬퍼 ──────────────────────────────────────────────────────────

def _is_wsl() -> bool:
    return platform.system() == "Linux" and "microsoft" in platform.uname().release.lower()


def _is_windows() -> bool:
    return platform.system() == "Windows"

from conversation.session_manager import SessionManager, SessionState
from ui_ux.chat_panel import LLMWorker

_ASSETS         = Path(__file__).resolve().parent / "assets"
_CHARACTER_DIR  = Path(__file__).resolve().parent.parent / "conversation" / "character"
_WORLD_DIR      = Path(__file__).resolve().parent.parent / "conversation" / "world"
_ICONS_DIR      = _ASSETS / "icons"         # icons/{CharId}/{CharId}.png + emotion/
_CHAR_PARTS_DIR = _ASSETS / "characters"    # characters/{type}/*.png (base/hair/eye/mouth/cloth)
_BG_DIR         = _ASSETS / "background"    # background/{world_id}/{location}.png
_PREFS_PATH     = _ASSETS / "preferences.json"   # UI 환경설정 (테마 등)


class ChatBridge(QObject):
    """QML ↔ Python 통신 브리지.

    QML에서 호출하는 Slot과 QML에 알리는 Signal을 정의한다.
    QML에서는 context property 'bridge'로 접근한다.

    Signals (Python → QML):
        messageAdded(role, content)  : 새 메시지 추가 (role: "user" | "assistant")
        statusChanged(status)        : "thinking" | "ready"
        characterNameChanged(name)   : 캐릭터 이름 변경
        backgroundChanged(url)       : act 변경 시 배경 이미지 URL (없으면 "")
        moodChanged(mood)            : mood 변경 시 감정 상태 문자열

    Slots (QML → Python):
        sendMessage(text)            : 사용자 메시지 전송
        snapToEdge(x, y, w, h)      : 화면 모서리 스냅 좌표 계산
        changeCharacter(char_id)     : 캐릭터 핫스왑
    """

    messageAdded         = Signal(str, str)          # role, content
    messageReplaced      = Signal(int, "QVariantList") # index, [{role, content}, ...]
    statusChanged        = Signal(str)               # "thinking" | "ready"
    characterNameChanged = Signal(str)
    backgroundChanged    = Signal(str)               # file URL or ""
    moodChanged          = Signal(str)               # neutral | happy | annoyed | sad
    affectionChanged     = Signal(int)               # 0~100 — admin 조작 or 잠금 해제 시 emit
    imageImported        = Signal(str, str)          # slot_type, result (icon→URL, parts→filename)
    memoryChanged        = Signal()                  # DB CRUD 성공 시 emit → QML 자동 갱신
    chatReset            = Signal("QVariantList")    # 캐릭터/세계관 변경 시 채팅창 초기화 + 이전 기록 로드

    def __init__(self, agent):
        super().__init__()
        self._agent = agent
        self._worker: LLMWorker | None = None
        self._character_name: str = agent.character.get("name", "")

        # SessionManager 초기화
        cfg = getattr(agent, "cfg", {})
        session_dir = Path(cfg.get("session_dir", "./data/sessions"))
        self._session_manager = SessionManager(session_dir)

        # stub 모드가 아니면 세션 ID를 SessionManager와 연동
        if not getattr(agent, "_stub", True) and agent.session is not None:
            self._init_session()

        # 학습 데이터 로거 (enable_play_log=True인 환경에서만 활성화)
        self._conv_logger = None
        if cfg.get("enable_play_log", False) and not getattr(agent, "_stub", True):
            from training.log.conversation_logger import ConversationLogger
            char_id = agent.character.get("id", "unknown")
            self._conv_logger = ConversationLogger(character_id=char_id)

        # 현재 act 위치 — session 없는 stub 모드에서도 배경 추적
        self._location: str = self._resolve_initial_location()

        # 초기 배경/mood 상태
        self._current_bg: str = self._build_bg_url()
        self._current_mood: str = self._read_mood()


    # ── Property ──────────────────────────────────────────────────────────────

    @Property(str, notify=characterNameChanged)
    def characterName(self) -> str:
        return self._character_name

    @Property(str, notify=characterNameChanged)
    def characterId(self) -> str:
        """캐릭터 id (폴더명 / 파일명 기준). icons/{id}/{id}.png 경로에 사용."""
        return self._agent.character.get("id", "") if self._agent.character else ""

    @Property(str, notify=backgroundChanged)
    def currentBackground(self) -> str:
        return self._current_bg

    @Property(str, notify=moodChanged)
    def currentMood(self) -> str:
        return self._current_mood

    @Property(int, notify=affectionChanged)
    def currentAffection(self) -> int:
        session = getattr(self._agent, "session", None)
        return session.affection if session else 30

    @Property(bool, notify=affectionChanged)
    def affectionLocked(self) -> bool:
        session = getattr(self._agent, "session", None)
        return session.affection_locked if session else False

    @Property(str, notify=statusChanged)
    def activeSessionId(self) -> str:
        """현재 활성 세션 ID."""
        session = getattr(self._agent, "session", None)
        return session.session_id if session else ""

    # ── 세션 관리 내부 헬퍼 ──────────────────────────────────────────────────

    def _init_session(self) -> None:
        """앱 시작 시 SessionManager와 ConversationSession을 연동한다.

        이전 세션이 있으면 전체 상태(mood / affection / turn_count / location /
        scenario_id / act_id / 트리거 상태)를 복원하고, 대화 기록도 불러온다.
        없으면 새 세션을 생성한다.
        """
        char_id = self._agent.character.get("id", "")
        active = self._session_manager.get_active()
        if active and active.char_id == char_id:
            self._restore_session_from_state(active)
        else:
            world_id = getattr(self._agent.session, "world_id", None)
            if world_id:
                state = self._session_manager.activate_for_world(char_id, world_id)
            else:
                state = self._session_manager.activate(char_id)
            self._restore_session_from_state(state)

    def _restore_session_from_state(self, state) -> None:
        """SessionState의 모든 필드를 ConversationSession에 복원한다.

        대화 기록(dialogue_log)도 디스크에서 불러온다.
        """
        session = self._agent.session
        if session is None:
            return
        session.session_id = state.session_id
        session.mood       = state.mood
        session.mood_hold  = getattr(state, "mood_hold", 0)
        session.affection  = state.affection
        session.turn_count = state.turn_count
        if state.location:
            session.location = state.location
        if getattr(state, "scenario_id", None):
            session.scenario_id = state.scenario_id
        if getattr(state, "act_id", None):
            session.act_id = state.act_id
        session.fired_stories      = list(getattr(state, "fired_stories",      []) or [])
        session.visited_places     = list(getattr(state, "visited_places",     []) or [])
        session.explained_cultures = list(getattr(state, "explained_cultures", []) or [])
        session.session_context    = getattr(state, "session_context", "") or ""

        # 대화 기록 복원
        char_id = self._agent.character.get("id", "")
        dialogue = self._session_manager.load_dialogue(char_id, state.session_id)
        if dialogue:
            session.dialogue_log = dialogue

    _HISTORY_DISPLAY_TURNS = 10  # 재시작/캐릭터 전환 시 표시할 최근 턴 수

    @Slot(result="QVariantList")
    def getSessionHistory(self) -> list:
        """현재 세션의 최근 대화 기록을 QML에 반환한다.

        최대 _HISTORY_DISPLAY_TURNS 턴(= 턴수 × 2 메시지)을 반환한다.
        assistant 응답 안의 **...**/*...* 는 narrator 버블로 분리한다.
        """
        session = getattr(self._agent, "session", None)
        if session is None or not getattr(session, "dialogue_log", None):
            return []
        max_msgs = self._HISTORY_DISPLAY_TURNS * 2
        recent_log = session.dialogue_log[-max_msgs:]
        result: list[dict] = []
        for msg in recent_log:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "assistant":
                for r, c in _split_narration(content, "assistant"):
                    result.append({"role": r, "content": c})
            else:
                result.append({"role": role, "content": content})
        return result

    def _sync_session_state(self) -> None:
        """ConversationSession의 현재 상태를 SessionState에 동기화해 저장한다."""
        session = getattr(self._agent, "session", None)
        if session is None or session.session_id is None:
            return
        state = self._session_manager.get_active()
        if state is None:
            return
        state.turn_count  = session.turn_count
        state.mood        = session.mood
        state.mood_hold   = getattr(session, "mood_hold", 0)
        state.affection   = session.affection
        state.location    = session.location    or state.location
        state.act_id      = session.act_id      or state.act_id
        state.scenario_id = session.scenario_id or state.scenario_id
        state.world_id    = session.world_id    or state.world_id
        # 세계관 트리거 상태 동기화
        state.fired_stories      = list(getattr(session, "fired_stories", []) or [])
        state.visited_places     = list(getattr(session, "visited_places", []) or [])
        state.explained_cultures = list(getattr(session, "explained_cultures", []) or [])
        state.session_context    = getattr(session, "session_context", "") or ""
        self._session_manager.save_state(state)

        # 대화 기록 저장 (dialogue_log가 없는 SessionState 호환 포함)
        char_id = self._agent.character.get("id", "")
        dialogue = getattr(session, "dialogue_log", []) or []
        self._session_manager.save_dialogue(char_id, session.session_id, dialogue)

    def _unload_llm(self) -> None:
        """현재 Agent의 LLM 모델을 메모리에서 해제한다.

        캐릭터 전환 / 새 세션 / 초기화 시 새 LLM을 로드하기 직전에 반드시 호출해야 한다.
        해제하지 않으면 기존 모델과 신규 모델이 동시에 메모리에 적재되어 OOM이 발생한다.

        - llama_cpp : Llama.close() 호출 (내부 C 힙 해제)
        - transformers : del model + torch.cuda.empty_cache()
        """
        import gc

        llm = getattr(self._agent, "llm", None)
        if llm is None:
            return

        backend = getattr(llm, "backend", "")
        model   = getattr(llm, "_model", None)

        if backend == "llama_cpp" and model is not None:
            try:
                model.close()
            except Exception:
                pass

        if backend == "transformers" and model is not None:
            try:
                import torch
                del llm._model
                llm._model = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        # Python 참조 해제 후 GC 강제 실행
        del model
        gc.collect()

    def _rebuild_agent(self, state: SessionState) -> None:
        """SessionState로부터 캐릭터 / 세션 / 라우터를 교체한다.

        LLM은 유지된다 — 모든 캐릭터가 동일한 어댑터를 공유하므로 재로드 불필요.
        """
        self._agent.swap_character(state.char_id, state.world_id, state)
        self._character_name = self._agent.character.get("name", state.char_id)
        self._location = self._resolve_initial_location()

        # swap_character가 새 session을 만든 뒤 dialogue_log를 복원한다
        if self._agent.session is not None and state.session_id:
            dialogue = self._session_manager.load_dialogue(state.char_id, state.session_id)
            if dialogue:
                self._agent.session.dialogue_log = dialogue

        # 캐릭터/세션 교체 시 ConversationLogger도 새 캐릭터로 재시작
        if self._conv_logger is not None:
            self._conv_logger.flush_remaining()
            from training.log.conversation_logger import ConversationLogger
            self._conv_logger = ConversationLogger(character_id=state.char_id)

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _resolve_initial_location(self) -> str:
        """초기화 시 YAML에서 location을 읽어온다 (session 없는 stub 모드 대응)."""
        session = getattr(self._agent, "session", None)
        if session and session.location:
            return session.location
        world   = getattr(self._agent, "world", {})
        s_id = getattr(session, "scenario_id", None) if session else None
        a_id = getattr(session, "act_id",      None) if session else None
        if s_id and a_id:
            from conversation.loader.world_load import get_act
            act = get_act(world, s_id, a_id)
            return act.get("location", "") if act else ""
        return ""

    def _build_bg_url(self) -> str:
        """self._location과 world_id로 배경 이미지 file URL을 반환한다.
        파일이 없으면 빈 문자열을 반환한다.
        탐색 경로: background/{world_id}/{location}.png
        """
        world_id = getattr(self._agent, "world", {}).get("world_id", "")
        if not world_id or not self._location:
            return ""
        path = _BG_DIR / world_id / f"{self._location}.png"
        return QUrl.fromLocalFile(str(path)).toString() if path.exists() else ""

    def _read_mood(self) -> str:
        session = getattr(self._agent, "session", None)
        return session.mood if session else "neutral"

    def _sync_state(self) -> None:
        """응답 후 act/mood/affection 변화를 감지하고 변경 시 시그널을 emit한다."""
        # session.location이 router에 의해 바뀌었을 수 있으므로 동기화
        session = getattr(self._agent, "session", None)
        if session and session.location:
            self._location = session.location

        new_bg = self._build_bg_url()
        if new_bg != self._current_bg:
            self._current_bg = new_bg
            self.backgroundChanged.emit(new_bg)

        new_mood = self._read_mood()
        if new_mood != self._current_mood:
            self._current_mood = new_mood
            self.moodChanged.emit(new_mood)

        if session:
            self.affectionChanged.emit(session.affection)

    # ── Slots (QML → Python) ──────────────────────────────────────────────────

    # 파일 탐색기(폴더)가 필요한 기능 모드 도구 집합
    # file_rename / image_convert / folder_classify / local_search는 전용 다이얼로그로 분리
    _PATH_TOOLS: frozenset[str] = frozenset()
    # 파일 선택 옵션 패널이 필요한 도구 집합 (QML에서 browseFilesForOptions 호출)
    _FILE_OPTION_TOOLS: frozenset[str] = frozenset({"file_convert"})

    @Slot(str, str, str)
    def sendMessage(self, text: str, mode: str = "chat", tool_name: str = "") -> None:
        """QML 입력창에서 메시지를 전송할 때 호출된다.

        Parameters
        ----------
        text : str
            사용자 입력 텍스트.
        mode : str
            "chat" | "function" — QML currentMode 값을 그대로 전달한다.
        tool_name : str
            기능 모드에서 선택된 태그 이름. 빈 문자열이면 키워드 감지 폴백.
        """
        if not text.strip() or self._worker is not None:
            return

        # ── 전체 문자열이 *...* 인 경우 → dialogue_log/LLM용 텍스트 변환 ──
        action_match = _ACTION_RE.match(text.strip())
        if action_match:
            action_text = action_match.group(1)
            text = f"(행동: {action_text})"

        # ── **...** / *...* 혼합 패턴 처리 ────────────────────────────────
        # UI: 순서대로 user/narrator 버블로 분리 emit
        # LLM: **...**→(나레이션: ...), *...*→(행동: ...) 로 변환
        has_narration = bool(_SPLIT_RE.search(text))
        if has_narration:
            llm_text = _SPLIT_RE.sub(
                lambda m: f"(나레이션: {m.group(1)})" if m.group(1) else f"(행동: {m.group(2)})",
                text,
            )
        else:
            llm_text = text

        # 경로가 필요한 도구는 OS 파일 탐색기로 먼저 디렉토리를 선택
        selected_path = ""
        if mode == "function" and tool_name in self._PATH_TOOLS:
            from PySide6.QtWidgets import QFileDialog
            selected_path = QFileDialog.getExistingDirectory(
                None, "작업할 폴더 선택", str(Path.home())
            )
            if not selected_path:
                return  # 사용자가 취소

        if has_narration:
            for role, content in _split_narration(text, "user"):
                self.messageAdded.emit(role, content)
        else:
            self.messageAdded.emit("user", text)
        self.statusChanged.emit("thinking")

        self._worker = LLMWorker(
            self._agent, llm_text, mode=mode,
            tool_name=tool_name, selected_path=selected_path,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    # 복원 시 표시할 최대 턴 수 (1턴 = user + assistant 2개 메시지)
    _HISTORY_DISPLAY_TURNS = 10

    @Slot(result="QVariantList")
    def getSessionHistory(self) -> list:
        """이전 세션의 대화 기록을 QML 모델용 리스트로 반환한다.

        최근 _HISTORY_DISPLAY_TURNS(10턴)만 반환한다.
        반환 형식: [{"role": "user"|"assistant"|"narrator", "content": "..."}, ...]

        QML Component.onCompleted에서 호출해 messageModel을 초기화한다.
        PIP 버블 자동 표시를 일으키지 않는 방식(직접 모델 추가)으로 사용된다.
        """
        session = getattr(self._agent, "session", None)
        if session is None or not session.dialogue_log:
            return []

        # 최근 N턴(= N*2 메시지)만 표시
        max_msgs = self._HISTORY_DISPLAY_TURNS * 2
        recent_log = session.dialogue_log[-max_msgs:]

        result: list[dict] = []
        for msg in recent_log:
            role    = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            # assistant 응답은 **/*/묘사 패턴이 있으면 재분할
            if role == "assistant":
                for r, c in _split_narration(content, "assistant"):
                    result.append({"role": r, "content": c})
            else:
                result.append({"role": role, "content": content})
        return result

    @Slot(int, int, int, int, result="QVariantList")
    def snapToEdge(self, x: int, y: int, w: int, h: int) -> list[int]:
        """드래그 종료 시 화면 모서리 스냅 좌표를 반환한다.

        QML의 MouseArea.onReleased에서 호출:
            var snapped = bridge.snapToEdge(root.x, root.y, root.width, root.height)
            root.x = snapped[0]; root.y = snapped[1]
        """
        SNAP = 30
        screen = QApplication.primaryScreen().availableGeometry()

        snapped_x = x
        snapped_y = y

        if abs(x - screen.left()) <= SNAP:
            snapped_x = screen.left()
        elif abs(x + w - screen.right()) <= SNAP:
            snapped_x = screen.right() - w

        if abs(y - screen.top()) <= SNAP:
            snapped_y = screen.top()
        elif abs(y + h - screen.bottom()) <= SNAP:
            snapped_y = screen.bottom() - h

        return [snapped_x, snapped_y]

    @Slot(str, result=bool)
    def deleteCharacter(self, char_id: str) -> bool:
        """캐릭터 YAML을 삭제한다.

        현재 활성 캐릭터는 삭제 불가.
        """
        if char_id == (self._agent.character or {}).get("id", ""):
            return False
        target = _CHARACTER_DIR / f"CH_{char_id}.yaml"
        if not target.exists():
            return False
        target.unlink()
        return True

    @Slot(result=str)
    def getCharacterList(self) -> str:
        """사용 가능한 캐릭터 목록을 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``[{"id": "Haru", "name": "하루"}, ...]`` 형태의 JSON.
        """
        import json

        from conversation.loader.character_load import load_character

        result = []
        for path in sorted(_CHARACTER_DIR.glob("CH_*.yaml")):
            try:
                char = load_character(path)
                if char.get("id") == "default":
                    continue
                result.append({"id": char["id"], "name": char.get("name", char["id"])})
            except Exception:  # noqa: BLE001
                pass
        return json.dumps(result, ensure_ascii=False)

    @Slot(result=str)
    def getDefaultWorld(self) -> str:
        """세계관 목록의 첫 번째 world/scenario/act를 반환한다.

        Returns
        -------
        str
            ``{"world_id": ..., "scenario_id": ..., "act_id": ...}`` 형태의 JSON.
            세계관이 없으면 빈 dict.
        """
        import json
        worlds = json.loads(self.getWorldList())
        if not worlds:
            return json.dumps({}, ensure_ascii=False)
        w = worlds[0]
        sc = w["scenarios"][0] if w.get("scenarios") else {}
        act = sc["acts"][0] if sc.get("acts") else {}
        return json.dumps({
            "world_id":    w["world_id"],
            "scenario_id": sc.get("scenario_id", ""),
            "act_id":      act.get("act_id", ""),
        }, ensure_ascii=False)

    @Slot(result=str)
    def getWorldList(self) -> str:
        """세계관 + 시나리오 목록을 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``[{"world_id": ..., "description": ..., "scenarios": [...]}]`` 형태의 JSON.
        """
        import json

        from conversation.loader.world_load import load_world

        result = []
        for path in sorted(_WORLD_DIR.glob("W_*.yaml")):
            try:
                world = load_world(path)
                scenarios = []
                for sc in world.get("scenarios", []):
                    acts = [
                        {
                            "act_id":       a["act_id"],
                            "location":     a.get("location", ""),
                            "display_name": a.get("display_name", ""),
                        }
                        for a in sc.get("acts", [])
                    ]
                    scenarios.append({"scenario_id": sc["scenario_id"], "acts": acts})
                result.append({
                    "world_id": world["world_id"],
                    "description": world.get("description", "").strip(),
                    "scenarios": scenarios,
                })
            except Exception:  # noqa: BLE001
                pass
        return json.dumps(result, ensure_ascii=False)

    @Slot(result=str)
    def loadCustomization(self) -> str:
        """현재 캐릭터의 커스터마이징 설정을 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``{"parts": {...}, "icon_url": "file:///...", "char_id": "Haru"}`` 형태의 JSON.
            파일이 없으면 빈 dict / 빈 문자열.

        저장 경로: icons/{char_id}/parts.json
        아이콘:    icons/{char_id}/{char_id}.png
        """
        import json

        char_id = self.characterId
        if not char_id:
            return json.dumps({"parts": {}, "icon_url": "", "char_id": ""}, ensure_ascii=False)

        icon_dir  = _ICONS_DIR / char_id
        parts_path = icon_dir / "parts.json"
        icon_png   = icon_dir / f"{char_id}.png"

        parts    = json.loads(parts_path.read_text("utf-8")) if parts_path.exists() else {}
        icon_url = QUrl.fromLocalFile(str(icon_png)).toString() if icon_png.exists() else ""

        return json.dumps(
            {"parts": parts, "icon_url": icon_url, "char_id": char_id},
            ensure_ascii=False,
        )

    @Slot(str)
    def saveCustomization(self, json_data: str) -> None:
        """현재 캐릭터의 커스터마이징 파츠 선택을 저장한다.

        Parameters
        ----------
        json_data : str
            ``{"parts": {...}}`` 형태의 JSON.
            저장 경로: icons/{char_id}/parts.json
        """
        import json

        char_id = self.characterId
        if not char_id:
            return

        icon_dir = _ICONS_DIR / char_id
        icon_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(json_data)
        except Exception as e:  # noqa: BLE001
            self.messageAdded.emit("system", f"[커스터마이징 저장 실패] {e}")
            return

        if "parts" in data:
            (icon_dir / "parts.json").write_text(
                json.dumps(data["parts"], ensure_ascii=False, indent=2), encoding="utf-8"
            )

    @Slot(str, str)
    def saveCustomizationFor(self, char_id: str, json_data: str) -> None:
        """지정한 캐릭터의 커스터마이징 파츠 선택을 저장한다.

        Parameters
        ----------
        char_id : str
            저장 대상 캐릭터 ID.
        json_data : str
            ``{"parts": {...}}`` 형태의 JSON.
            저장 경로: icons/{char_id}/parts.json
        """
        import json

        if not char_id:
            return

        icon_dir = _ICONS_DIR / char_id
        icon_dir.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(json_data)
        except Exception as e:  # noqa: BLE001
            self.messageAdded.emit("system", f"[커스터마이징 저장 실패] {e}")
            return

        if "parts" in data:
            (icon_dir / "parts.json").write_text(
                json.dumps(data["parts"], ensure_ascii=False, indent=2), encoding="utf-8"
            )

    @Slot(str, str, str, result=bool)
    def exportCompositeAsPng(self, char_id: str, slot_type: str, parts_json: str) -> bool:
        """파츠 합성 결과를 PNG로 내보낸다.

        Parameters
        ----------
        char_id : str
            대상 캐릭터 ID.
        slot_type : str
            "icon"           → icons/{char_id}/{char_id}.png 저장 + parts.json 갱신
            "emotion_{mood}" → icons/{char_id}/emotion/{mood}.png 저장
        parts_json : str
            {"base": "file.png", "hair": "file.png", ...} 형태의 JSON.

        Returns
        -------
        bool
            저장 성공 여부.
        """
        import json

        from PySide6.QtCore import QUrl
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QImage, QPainter

        try:
            parts = json.loads(parts_json)
        except Exception:
            return False

        render_order = ["base", "eye", "eyebrow", "nose", "mouth", "emotion", "hair", "cloth"]

        # 캔버스 크기: 첫 유효 레이어 기준, 기본 512
        canvas = 512
        for pt in render_order:
            fn = parts.get(pt, "")
            if fn:
                probe = QImage(str(_CHAR_PARTS_DIR / pt / fn))
                if not probe.isNull():
                    canvas = max(probe.width(), probe.height())
                    break

        out_img = QImage(canvas, canvas, QImage.Format.Format_ARGB32)
        out_img.fill(0)
        painter = QPainter(out_img)

        for pt in render_order:
            fn = parts.get(pt, "")
            if not fn:
                continue
            path = _CHAR_PARTS_DIR / pt / fn
            if not path.exists():
                continue
            layer = QImage(str(path))
            if layer.isNull():
                continue
            if layer.width() != canvas or layer.height() != canvas:
                layer = layer.scaled(
                    canvas, canvas,
                    _Qt.AspectRatioMode.KeepAspectRatio,
                    _Qt.TransformationMode.SmoothTransformation,
                )
            x = (canvas - layer.width()) // 2
            y = (canvas - layer.height()) // 2
            painter.drawImage(x, y, layer)

        painter.end()

        icon_dir = _ICONS_DIR / char_id
        icon_dir.mkdir(parents=True, exist_ok=True)

        if slot_type == "icon":
            out_path = icon_dir / f"{char_id}.png"
            (icon_dir / "parts.json").write_text(
                json.dumps(parts, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        elif slot_type.startswith("emotion_"):
            mood = slot_type[len("emotion_"):]
            if not mood:
                return False
            emo_dir = icon_dir / "emotion"
            emo_dir.mkdir(parents=True, exist_ok=True)
            out_path = emo_dir / f"{mood}.png"
        else:
            return False

        ok = out_img.save(str(out_path), "PNG")
        if ok:
            self.imageImported.emit(slot_type, QUrl.fromLocalFile(str(out_path)).toString())
        return ok

    @Slot(result=str)
    def getAllPartsList(self) -> str:
        """파츠 타입별 사용 가능한 파일 목록을 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``{"base": ["base_01.png", ...], "hair": [...], ...}`` 형태의 JSON.

        파츠 폴더: characters/{type}/*.png
        타입: base / hair / eye / eyebrow / nose / mouth / cloth
        """
        import json

        part_types = ["base", "hair", "eye", "eyebrow", "nose", "mouth", "emotion", "cloth"]
        result: dict[str, list[str]] = {}
        for pt in part_types:
            d = _CHAR_PARTS_DIR / pt
            result[pt] = sorted(f.name for f in d.iterdir() if f.suffix.lower() == ".png") \
                         if d.exists() else []
        return json.dumps(result, ensure_ascii=False)

    # ── 이미지 임포트 ─────────────────────────────────────────────────────────

    _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}

    def _import_image(self, slot_type: str, source_path: str) -> str:
        """이미지 파일을 해당 슬롯 경로에 복사하고 결과를 반환한다.

        Returns
        -------
        str
            icon  → file URL (``file:///...``)
            parts → 복사된 파일명 (``hair_01.png`` 등)
            실패  → ""
        """
        import shutil
        from pathlib import Path as _P

        src = _P(source_path)
        if not src.exists() or src.suffix.lower() not in self._IMAGE_EXTS:
            return ""

        char_id = self.characterId

        if slot_type == "icon":
            if not char_id:
                return ""
            dest_dir = _ICONS_DIR / char_id
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{char_id}.png"
            shutil.copy2(str(src), str(dest))
            return QUrl.fromLocalFile(str(dest)).toString()

        if slot_type in ("base", "hair", "eye", "eyebrow", "mouth", "cloth"):
            dest_dir = _CHAR_PARTS_DIR / slot_type
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / src.name
            shutil.copy2(str(src), str(dest))
            return src.name

        if slot_type.startswith("emotion_"):
            mood = slot_type[len("emotion_"):]
            if not char_id or not mood:
                return ""
            dest_dir = _ICONS_DIR / char_id / "emotion"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{mood}.png"
            shutil.copy2(str(src), str(dest))
            return QUrl.fromLocalFile(str(dest)).toString()

        return ""

    @Slot(str)
    def browseImage(self, slot_type: str) -> None:
        """네이티브 파일 다이얼로그를 열어 이미지를 선택·임포트한다."""
        from PySide6.QtWidgets import QFileDialog

        img_filter = (
            "이미지 파일 (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tiff *.tif);;"
            "모든 파일 (*)"
        )
        path, _ = QFileDialog.getOpenFileName(None, "이미지 선택", "", img_filter)
        if path:
            result = self._import_image(slot_type, path)
            if result:
                self.imageImported.emit(slot_type, result)

    @Slot(str, str)
    def importImageFromDrop(self, slot_type: str, file_url: str) -> None:
        """드래그&드롭 file URL을 받아 이미지를 임포트한다."""
        local = QUrl(file_url).toLocalFile() if file_url.startswith("file") else file_url
        if local:
            result = self._import_image(slot_type, local)
            if result:
                self.imageImported.emit(slot_type, result)

    @Slot(str, str, str)
    def changeWorld(self, world_id: str, scenario_id: str, act_id: str) -> None:
        """세계관 / 시나리오 / act를 전환한다.

        세계관(world_id)이 실제로 바뀌면 (char_id, world_id) 쌍에 해당하는
        세션을 찾거나 새로 생성한다. act/scenario만 바뀌면 현재 세션을 유지한다.
        stub 모드에서는 배경만 전환.
        """
        from conversation.loader.world_load import get_act, load_world

        for path in _WORLD_DIR.glob("W_*.yaml"):
            try:
                world = load_world(path)
            except Exception:  # noqa: BLE001
                continue
            if world.get("world_id") != world_id:
                continue

            try:
                # location 갱신 (session 유무 관계없이)
                act_data = get_act(world, scenario_id, act_id)
                self._location = act_data.get("location", "") if act_data else ""
                self._agent.world = world

                if self._agent.session is not None:
                    cur_world_id = getattr(self._agent.session, "world_id", None)
                    world_changed = cur_world_id != world_id

                    if world_changed:
                        # 세계관이 바뀌면 (char_id, world_id) 전용 세션으로 전환
                        self._sync_session_state()
                        char_id = self._agent.character.get("id", "")
                        new_state = self._session_manager.activate_for_world(char_id, world_id)
                        new_state.world_id    = world_id
                        new_state.scenario_id = scenario_id
                        new_state.act_id      = act_id
                        new_state.location    = self._location
                        # 세계관 진입 시 트리거 상태 초기화 → 장소/스토리 나레이션 재발동 보장
                        new_state.visited_places    = []
                        new_state.fired_stories     = []
                        new_state.explained_cultures = []
                        self._session_manager.save_state(new_state)
                        self._rebuild_agent(new_state)
                    else:
                        # 같은 세계관 내 act/scenario 교체 → session_id + dialogue_log 유지
                        from conversation.core.prompt_build import PromptBuilder
                        old_session_id = self._agent.session.session_id
                        old_dialogue   = list(getattr(self._agent.session, "dialogue_log", []) or [])
                        from agent.persona import swap_persona
                        new_char, new_session = swap_persona(
                            session=self._agent.session,
                            new_character_id=self._agent.character["id"],
                            world_id=world_id,
                            scenario_id=scenario_id,
                            act_id=act_id,
                        )
                        new_session.location    = self._location
                        new_session.session_id  = old_session_id  # session_id 유지
                        new_session.dialogue_log = old_dialogue    # 대화 기록 유지
                        # 세계관 character_overrides.rules 재적용
                        _ov = (world.get("character_overrides") or {}).get("rules") or []
                        if _ov:
                            new_char["rules"] = list(new_char.get("rules") or []) + list(_ov)
                        self._agent.character = new_char
                        self._agent.session   = new_session
                        if self._agent.router is not None:
                            self._agent.router.character = new_char
                            self._agent.router.session   = new_session
                            self._agent.router.builder   = PromptBuilder(
                                new_char, world, new_session,
                                count_tokens_fn=self._agent.llm.count_tokens,
                            )
                        self._sync_session_state()

                # 배경/mood emit
                new_bg = self._build_bg_url()
                self._current_bg = new_bg
                self.backgroundChanged.emit(new_bg)
                new_mood = self._read_mood()
                self._current_mood = new_mood
                self.moodChanged.emit(new_mood)

                # 세계관 변경 시 채팅창 초기화 후 해당 세션 기록 복원
                if self._agent.session is not None and world_changed:
                    self.chatReset.emit(self.getSessionHistory())

                # 초기 장소 나레이션 emit (첫 진입 or 세계관 변경 시)
                if self._location and not getattr(self._agent, "_stub", True):
                    try:
                        from narration.world_trigger import check_place_trigger
                        session = getattr(self._agent, "session", None)
                        rag = getattr(getattr(self._agent, "router", None), "rag", None)
                        if session and rag:
                            narr = check_place_trigger(self._location, session, rag)
                            if narr:
                                _title, document = narr
                                self.messageAdded.emit("narrator", document)
                    except Exception:
                        pass
            except Exception as e:  # noqa: BLE001
                self.messageAdded.emit("system", f"[세계관 변경 실패] {e}")
            return

        self.messageAdded.emit("system", f"[세계관 변경 실패] world_id='{world_id}' 없음")

    @Slot(str)
    def changeCharacter(self, char_id: str) -> None:
        """캐릭터를 전환하고 해당 캐릭터의 마지막 세션을 재개한다."""
        if getattr(self._agent, "_stub", True):
            return

        # 현재 세션 상태 저장
        self._sync_session_state()

        # 대상 캐릭터의 세션 활성화
        state = self._session_manager.activate(char_id.strip())

        try:
            self._rebuild_agent(state)
        except Exception as e:
            self.messageAdded.emit("system", f"[캐릭터 변경 실패] {e}")
            return

        self.characterNameChanged.emit(self._character_name)

        new_bg = self._build_bg_url()
        self._current_bg = new_bg
        self.backgroundChanged.emit(new_bg)

        new_mood = self._read_mood()
        self._current_mood = new_mood
        self.moodChanged.emit(new_mood)

        # 채팅창 초기화 후 새 캐릭터의 이전 대화 기록 복원
        self.chatReset.emit(self.getSessionHistory())

    @Slot(bool)
    def newSession(self, keep_memory: bool = False) -> None:
        """현재 캐릭터의 새 세션을 시작한다.

        Parameters
        ----------
        keep_memory : True이면 이전 세션의 에피소딕 기억을 보존한다.
                      False이면 삭제한다 (기본값).
        """
        if getattr(self._agent, "_stub", True):
            return

        # 현재 세션 상태 저장
        self._sync_session_state()

        char_id = self._agent.character.get("id", "")
        cur_world_id = getattr(self._agent.session, "world_id", None) if self._agent.session else None
        new_state, old_session_id = self._session_manager.new_session(char_id, keep_memory)
        # 현재 세계관 정보를 새 세션에 복사
        if cur_world_id:
            new_state.world_id = cur_world_id
            self._session_manager.save_state(new_state)

        # 에피소딕 기억 삭제 (keep_memory=False 시)
        if old_session_id and self._agent.long_term is not None:
            self._agent.long_term.clear_session(char_id, old_session_id)

        try:
            self._rebuild_agent(new_state)
        except Exception as e:
            self.messageAdded.emit("system", f"[새 세션 시작 실패] {e}")
            return

        new_bg = self._build_bg_url()
        self._current_bg = new_bg
        self.backgroundChanged.emit(new_bg)

        new_mood = self._read_mood()
        self._current_mood = new_mood
        self.moodChanged.emit(new_mood)

        self.chatReset.emit([])

    @Slot(str, result=str)
    def listSessions(self, char_id: str) -> str:
        """해당 캐릭터의 세션 목록을 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``[{"session_id": "...", "char_id": "...", "world_id": "...",
               "created_at": "...", "last_active": "...", "display_name": "하루-seaside_world"}]``
        """
        metas = self._session_manager.list_sessions(char_id)
        # 캐릭터 이름 조회 (display_name 구성용)
        char_name = char_id
        try:
            chars = json.loads(self.getCharacterList())
            for c in chars:
                if c.get("id") == char_id:
                    char_name = c.get("name", char_id)
                    break
        except Exception:  # noqa: BLE001
            pass

        items = []
        for m in metas:
            wid = m.world_id or ""
            display = f"{char_name}-{wid}" if wid else char_name
            items.append({
                "session_id":  m.session_id,
                "char_id":     m.char_id,
                "world_id":    m.world_id,
                "created_at":  m.created_at,
                "last_active": m.last_active,
                "display_name": display,
            })
        return json.dumps(items, ensure_ascii=False)

    @Slot(str, result=bool)
    def switchSession(self, session_id: str) -> bool:
        """지정한 session_id로 세션을 전환한다.

        - 현재 세션 상태를 저장
        - SessionManager.activate() 로 해당 세션 복원
        - dialogue_log를 포함한 전체 세션 상태 복원
        - mood / affection Signal emit
        """
        char_id = (self._agent.character or {}).get("id", "")
        if not char_id or not session_id:
            return False

        # 현재 세션 저장
        self._sync_session_state()

        new_state = self._session_manager.activate(char_id, session_id)
        if new_state is None:
            return False

        # ConversationSession을 재생성하고 SessionState를 복원
        from conversation.core.session import ConversationSession
        world_id = new_state.world_id or (self._agent.world or {}).get("world_id")
        new_session = ConversationSession.from_character(
            self._agent.character,
            world_id=world_id,
            scenario_id=new_state.scenario_id,
            act_id=new_state.act_id,
        )
        self._agent.session = new_session
        # router 세션 참조 갱신
        if self._agent.router is not None:
            self._agent.router.session = new_session

        self._restore_session_from_state(new_state)

        self.affectionChanged.emit(new_session.affection)
        self.moodChanged.emit(new_session.mood)
        # 채팅창을 새 세션 기록으로 교체
        history = self.getSessionHistory()
        self.chatReset.emit(history)
        return True

    @Slot(str, result=bool)
    def deleteSession(self, session_id: str) -> bool:
        """지정한 session_id의 세션을 삭제한다.

        현재 활성 세션은 삭제할 수 없다.
        """
        char_id = (self._agent.character or {}).get("id", "")
        if not char_id or not session_id:
            return False

        current_session = getattr(self._agent, "session", None)
        if current_session and getattr(current_session, "session_id", None) == session_id:
            return False  # 현재 활성 세션 삭제 불가

        try:
            self._session_manager._evict_session(char_id, session_id)
            return True
        except Exception:  # noqa: BLE001
            return False

    @Slot(result=bool)
    def resetSession(self) -> bool:
        """현재 세션의 대화 기록과 상태를 초기화한다 (세션 ID는 유지).

        - dialogue_log 초기화
        - session_context / mood / affection / turn_count 초기화
        - VDB 에피소딕 기억은 보존 (세션 ID 유지이므로)
        - chatReset 시그널 emit
        """
        if getattr(self._agent, "_stub", True):
            return False

        char_id = self._agent.character.get("id", "")
        new_state = self._session_manager.reset_current(char_id)
        if new_state is None:
            return False

        session = getattr(self._agent, "session", None)
        if session:
            session.turn_count       = 0
            session.mood             = "neutral"
            session.mood_hold        = 0
            session.affection        = new_state.affection  # 초기값 유지
            session.session_context  = ""
            session.dialogue_log     = []
            session.fired_stories    = []
            session.visited_places   = []
            session.explained_cultures = []

        self.affectionChanged.emit(getattr(session, "affection", 30))
        self.moodChanged.emit("neutral")
        self.chatReset.emit([])
        return True

    @Slot(result=str)
    def getCharacterStatus(self) -> str:
        """현재 캐릭터의 상태를 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``{"char_name": "하루", "mood": "neutral", "affection": 30,
               "tier": "acquaintance", "turn_count": 0}`` 형태의 JSON.
        """
        session   = getattr(self._agent, "session",   None)
        character = getattr(self._agent, "character", {}) or {}

        mood        = session.mood        if session else "neutral"
        affection   = session.affection   if session else 0
        turn_count  = session.turn_count  if session else 0

        thresholds: dict = character.get("state", {}).get("affection_thresholds", {})
        tier = "unknown"
        for tier_name, bounds in thresholds.items():
            if bounds[0] <= affection <= bounds[1]:
                tier = tier_name
                break

        return json.dumps({
            "char_name":  character.get("name", ""),
            "mood":       mood,
            "affection":  affection,
            "tier":       tier,
            "turn_count": turn_count,
        }, ensure_ascii=False)

    @Slot(str, result=bool)
    def resetCharacter(self, char_id: str) -> bool:
        """해당 캐릭터의 세션 상태와 장기 기억을 전부 초기화한다.

        - data/sessions/{char_id}/ 디렉토리 삭제 (세션 기록 전체)
        - VDB 장기 기억 삭제 (clear_all)
        - 현재 대화 중인 캐릭터라면 에이전트도 즉시 초기화

        Parameters
        ----------
        char_id : str
            초기화할 캐릭터 ID.

        Returns
        -------
        bool
            성공이면 True, 실패이면 False.
        """
        import shutil

        try:
            # 1. 세션 디렉토리 전체 삭제
            char_session_dir = self._session_manager._char_dir(char_id)
            if char_session_dir.exists():
                shutil.rmtree(char_session_dir)

            # 2. active.json이 이 캐릭터를 가리키면 초기화
            active = self._session_manager._load_active()
            if active and active.get("char_id") == char_id:
                active_path = self._session_manager._active_path()
                if active_path.exists():
                    active_path.unlink()

            # 3. VDB 장기 기억 전체 삭제
            if getattr(self._agent, "long_term", None) is not None:
                try:
                    self._agent.long_term.clear_all(char_id)
                except Exception:
                    pass

            # 4. 현재 활성 캐릭터이면 에이전트 초기화
            current_id = (self._agent.character or {}).get("id", "")
            if current_id == char_id and not getattr(self._agent, "_stub", True):
                new_state = self._session_manager.activate(char_id)
                self._rebuild_agent(new_state)
                self.characterNameChanged.emit(self._character_name)
                self.moodChanged.emit(self._read_mood())

            return True

        except Exception as e:  # noqa: BLE001
            self.messageAdded.emit("system", f"[캐릭터 초기화 실패] {e}")
            return False

    @Slot(result=str)
    def browseCharacterYaml(self) -> str:
        """네이티브 파일 다이얼로그로 CH_*.yaml을 선택해 캐릭터 디렉토리에 복사한다.

        Returns
        -------
        str
            추가된 캐릭터의 id 문자열. 실패 시 빈 문자열.
        """
        import shutil

        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            None, "캐릭터 YAML 선택", "", "YAML 파일 (*.yaml *.yml);;모든 파일 (*)"
        )
        if not path:
            return ""

        import yaml as _yaml

        src = Path(path)
        try:
            data = _yaml.safe_load(src.read_text(encoding="utf-8"))
            char_id = data.get("id", "")
            if not char_id:
                return ""
            dest = _CHARACTER_DIR / f"CH_{char_id}.yaml"
            shutil.copy2(str(src), str(dest))
            return char_id
        except Exception:  # noqa: BLE001
            return ""

    # ── 파일 옵션 (파일이름 변경 / 확장자 변경) ──────────────────────────────────

    # 이미지 포맷 변환이 가능한 확장자 집합
    _IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

    @Slot(result=str)
    def browseFilesForOptions(self) -> str:
        """파일 선택 다이얼로그를 열어 선택된 경로 목록을 JSON으로 반환한다.

        Returns
        -------
        str
            ``["/path/to/file1.png", ...]`` 형태의 JSON.
            취소하면 ``"[]"`` 반환.
        """
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            None, "파일 선택", str(Path.home()), "모든 파일 (*)"
        )
        return json.dumps(paths, ensure_ascii=False)

    @Slot(str, str, str, result=str)
    def applyFileOptions(self, paths_json: str, rename_to: str, new_ext: str) -> str:
        """선택된 파일에 이름 변경 / 확장자 변경을 적용한다.

        Parameters
        ----------
        paths_json : str
            JSON 배열 — 선택된 파일 경로 목록.
        rename_to : str
            새 파일명 (확장자 제외). 비면 이름 유지.
            복수 파일이면 "{rename_to}_001", "{rename_to}_002" 형태로 시퀀스 부여.
        new_ext : str
            변환할 확장자 ("png", "jpg" 등). 비면 확장자 유지.
            이미지 포맷 간 변환은 Pillow를 사용.

        Returns
        -------
        str
            결과 메시지 (채팅창에 표시됨).
        """
        try:
            paths = [Path(p) for p in json.loads(paths_json) if p]
        except Exception as e:
            return f"오류: 경로 파싱 실패 — {e}"

        if not paths:
            return "선택된 파일이 없습니다."

        rename_to = rename_to.strip()
        new_ext   = new_ext.strip().lstrip(".")

        results: list[str] = []
        for i, src in enumerate(paths):
            if not src.exists():
                results.append(f"없음: {src.name}")
                continue

            # 최종 대상 경로 계산
            if rename_to:
                stem = rename_to if len(paths) == 1 else f"{rename_to}_{i+1:03d}"
            else:
                stem = src.stem
            ext_str = ("." + new_ext) if new_ext else src.suffix
            dst = src.parent / (stem + ext_str)

            if dst == src:
                results.append(f"변경 없음: {src.name}")
                continue
            if dst.exists():
                results.append(f"건너뜀 (충돌): {dst.name}")
                continue

            # 이미지 포맷 변환 (Pillow)
            if new_ext and src.suffix.lower() in self._IMG_EXTS and ext_str.lower() in self._IMG_EXTS:
                try:
                    from PIL import Image
                    _FORMAT_MAP = {
                        ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
                        ".webp": "WEBP", ".bmp": "BMP", ".tiff": "TIFF", ".tif": "TIFF",
                    }
                    fmt = _FORMAT_MAP.get(ext_str.lower(), ext_str.upper().lstrip("."))
                    with Image.open(src) as img:
                        if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        # 이름 변경도 함께 처리
                        img.save(dst, fmt)
                    if rename_to and dst.name != src.with_suffix(ext_str).name:
                        pass  # dst는 이미 rename_to 적용 완료
                    results.append(f"변환: {src.name} → {dst.name}")
                except ImportError:
                    return "오류: Pillow가 설치되지 않았습니다. (`uv add Pillow`)"
                except Exception as e:
                    results.append(f"실패: {src.name} — {e}")
            else:
                # 일반 파일 이름/확장자 변경
                try:
                    src.rename(dst)
                    results.append(f"완료: {src.name} → {dst.name}")
                except Exception as e:
                    results.append(f"실패: {src.name} — {e}")

        return "\n".join(results)

    # ── 폴더 분류 ─────────────────────────────────────────────────────────────

    @Slot(result=str)
    def browseFolderForClassify(self) -> str:
        """폴더 선택 다이얼로그를 열어 선택된 경로를 반환한다.

        Returns
        -------
        str
            선택된 폴더 경로 문자열. 취소하면 빈 문자열.
        """
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(None, "분류할 폴더 선택", str(Path.home()))
        return path or ""

    @Slot(str, str, bool, result=str)
    def applyFolderClassify(self, folder_path: str, rule: str, dry_run: bool) -> str:
        """ClassifierTool을 직접 실행하고 결과를 반환한다.

        Parameters
        ----------
        folder_path : str
            분류할 폴더 경로.
        rule : str
            "종류별" | "확장자별"
        dry_run : bool
            True이면 미리보기만 수행, False이면 실제 이동.

        Returns
        -------
        str
            분류 결과 메시지.
        """
        from tools.folder.classifier import ClassifierTool
        tool = ClassifierTool()
        return tool.execute({
            "target": folder_path,
            "rule":   rule or "종류별",
            "dry_run": dry_run,
        })

    # ── 파일 검색 ─────────────────────────────────────────────────────────────

    @Slot(result=str)
    def browseSearchDirectory(self) -> str:
        """검색할 디렉토리 선택 다이얼로그를 열어 경로를 반환한다."""
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(None, "검색할 폴더 선택", str(Path.home()))
        return path or ""

    @Slot(str, str, str, result=str)
    def searchFiles(self, query: str, folder_path: str, ext: str) -> str:
        """LocalSearchTool을 직접 실행하고 결과를 JSON 문자열로 반환한다.

        Parameters
        ----------
        query : str
            검색어.
        folder_path : str
            검색할 디렉토리 경로. 빈 문자열이면 홈 디렉토리 사용.
        ext : str
            확장자 필터 (쉼표 구분, 예: "py,txt"). 빈 문자열이면 기본 확장자.

        Returns
        -------
        str
            JSON 문자열: [{"path": "...", "snippet": "..."}, ...] 또는 {"error": "..."}
        """
        import json as _json
        from tools.search.local_search import _get_conn, _index_directory, _search, DEFAULT_EXTS
        from pathlib import Path as _Path

        if not query.strip():
            return _json.dumps({"error": "검색어가 없습니다."})

        root = _Path(folder_path).expanduser().resolve() if folder_path else _Path.home()
        if not root.exists() or not root.is_dir():
            return _json.dumps({"error": f"디렉토리가 존재하지 않습니다: {root}"})

        if ext:
            allowed_exts = {
                ("." + e.strip().lstrip(".")).lower()
                for e in ext.split(",") if e.strip()
            }
        else:
            allowed_exts = DEFAULT_EXTS

        try:
            conn = _get_conn()
            _index_directory(conn, root, allowed_exts, False)
            results = _search(conn, query.strip(), root=root)
            conn.close()
        except Exception as e:  # noqa: BLE001
            return _json.dumps({"error": f"검색 오류: {e}"})

        # 전역 DB에 다른 경로 파일이 있을 수 있으므로 지정 폴더 내 결과만 반환
        root_str = str(root)
        results = [(p, s) for p, s in results if p.startswith(root_str)]

        return _json.dumps(
            [{"path": p, "snippet": s} for p, s in results],
            ensure_ascii=False,
        )

    @Slot(str)
    def openFile(self, path: str) -> None:
        """OS 기본 앱으로 파일을 연다.

        WSL2: cmd.exe /c start 는 UNC 경로(\\\\wsl.localhost\\...)를 지원하지 않아
        PNG 등 이미지 열기에 실패한다. PowerShell Invoke-Item을 사용해야 한다.
        Windows native: os.startfile().
        Linux/macOS: xdg-open / open.
        """
        from pathlib import Path as _Path

        p = str(_Path(path).resolve())

        if _is_windows():
            import os
            try:
                os.startfile(p)  # type: ignore[attr-defined]
            except Exception:
                pass
            return

        if _is_wsl():
            # wslpath로 Windows 경로 변환 → PowerShell Invoke-Item
            try:
                win_path = _subprocess.check_output(
                    ["wslpath", "-w", p], stderr=_subprocess.DEVNULL
                ).decode().strip()
                # PowerShell 문자열 리터럴 내 single-quote 이스케이프 (' → '')
                safe = win_path.replace("'", "''")
                _subprocess.Popen([
                    "powershell.exe", "-NoProfile", "-NonInteractive",
                    "-Command", f"Invoke-Item '{safe}'",
                ], stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
            except (FileNotFoundError, _subprocess.CalledProcessError):
                pass
            return

        # Linux / macOS
        for cmd in (["xdg-open", p], ["open", p]):
            try:
                _subprocess.Popen(cmd)
                return
            except FileNotFoundError:
                continue

        # 최후 폴백
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl as _QUrl
        QDesktopServices.openUrl(_QUrl.fromLocalFile(p))

    @Slot(str)
    def openUrl(self, url: str) -> None:
        """브라우저로 URL을 연다.

        WSL2: Qt.openUrlExternally 는 브라우저 감지 실패로 무음 실패한다.
        cmd.exe /c start는 HTTP URL에는 UNC 이슈가 없어 정상 작동한다.
        Windows: os.startfile(url).
        Linux/macOS: xdg-open / open.
        """
        if _is_windows():
            import os
            try:
                os.startfile(url)  # type: ignore[attr-defined]
            except Exception:
                _subprocess.Popen(["cmd.exe", "/c", "start", "", url],
                                   stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
            return

        if _is_wsl():
            _subprocess.Popen(
                ["cmd.exe", "/c", "start", "", url],
                stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL,
            )
            return

        for cmd in (["xdg-open", url], ["open", url]):
            try:
                _subprocess.Popen(cmd)
                return
            except FileNotFoundError:
                continue

    # ── Admin: Affection 직접 조절 ────────────────────────────────────────────

    @Slot(int)
    def setAffection(self, value: int) -> None:
        """관리자 직접 설정. affection을 0~100 범위로 즉시 변경한다."""
        session = getattr(self._agent, "session", None)
        if session is None:
            return
        session.affection = max(0, min(100, value))
        self.affectionChanged.emit(session.affection)

    @Slot(int)
    def lockAffection(self, value: int) -> None:
        """특정 수치에 affection을 고정한다. 이후 update_affection() 호출은 무시된다."""
        session = getattr(self._agent, "session", None)
        if session is None:
            return
        clamped = max(0, min(100, value))
        session.affection_locked     = True
        session.affection_lock_value = clamped
        session.affection            = clamped
        self.affectionChanged.emit(session.affection)

    @Slot()
    def unlockAffection(self) -> None:
        """affection 잠금을 해제한다. 이후 정상적인 update_affection() 동작이 재개된다."""
        session = getattr(self._agent, "session", None)
        if session is None:
            return
        session.affection_locked     = False
        session.affection_lock_value = None
        self.affectionChanged.emit(session.affection)

    @Slot(str)
    def setMood(self, mood: str) -> None:
        """관리자 직접 설정. mood를 즉시 변경한다."""
        valid = {"neutral", "happy", "affectionate", "touched", "curious",
                 "sad", "embarrassed", "annoyed", "angry"}
        if mood not in valid:
            return
        session = getattr(self._agent, "session", None)
        if session is None:
            return
        session.mood = mood
        self._current_mood = mood
        self.moodChanged.emit(mood)

    # ── 테마 설정 ─────────────────────────────────────────────────────────────

    @Slot(result=str)
    def getTheme(self) -> str:
        """저장된 테마 ID를 반환한다. 저장값이 없으면 'dark'."""
        try:
            if _PREFS_PATH.exists():
                saved = json.loads(_PREFS_PATH.read_text(encoding="utf-8")).get("theme", "ocean")
                return saved if saved in ("ocean", "solar", "forest") else "ocean"
        except Exception:  # noqa: BLE001
            pass
        return "ocean"

    @Slot(str)
    def saveTheme(self, theme_id: str) -> None:
        """테마 ID를 preferences.json에 저장한다."""
        try:
            data: dict = {}
            if _PREFS_PATH.exists():
                data = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
            data["theme"] = theme_id
            _PREFS_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    @Slot(result=int)
    def getWindowScale(self) -> int:
        """저장된 창 크기 인덱스를 반환한다. 0=소형, 1=중형(기본), 2=대형."""
        try:
            if _PREFS_PATH.exists():
                val = json.loads(_PREFS_PATH.read_text(encoding="utf-8")).get("window_scale", 1)
                return int(val) if val in (0, 1, 2) else 1
        except Exception:  # noqa: BLE001
            pass
        return 1

    @Slot(int)
    def saveWindowScale(self, scale: int) -> None:
        """창 크기 인덱스를 preferences.json에 저장한다."""
        try:
            data: dict = {}
            if _PREFS_PATH.exists():
                data = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
            data["window_scale"] = scale
            _PREFS_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    # ── 도움말 / 최초 안내 ──────────────────────────────────────────────────────

    _HELP_TEXT: dict[str, str] = {
        "file_convert":   "#파일 변환 — 파일명 변경 또는 확장자(jpg/png/webp 등) 변환",
        "prompt_convert": "#프롬프트 변환 — ChromaDB 가이드 기반 프롬프트 자동 변환",
        "folder_classify": "#폴더 분류 — 날짜/확장자별로 파일을 하위 폴더로 자동 정리",
        "local_search":   "#파일 검색 — 폴더 내 파일명·내용 키워드 검색 (서브폴더 포함)",
        "help":           "#? — 각 기능에 대한 간략한 설명을 표시합니다",
    }

    _HELP_DETAIL: list[dict] = [
        {
            "keys": ["프롬프트", "prompt"],
            "text": (
                "#프롬프트 변환\n"
                "사용자가 사용하려는 모델과 입력하고 싶은 내용을 전달하면, 해당 모델에 대한 DB 지식을 활용해 프롬프트 형태로 가공해주는 기능입니다.\n"
                "예) \"Flux 모델로 카페 창가에 앉아 커피 마시는 여성 이미지 만들어줘\""
            ),
        },
        {
            "keys": ["폴더", "분류", "정리", "folder"],
            "text": (
                "#폴더 정리\n"
                "사용자가 선택한 폴더 범주 안에서 지정한 기준에 맞춰 폴더를 정리해주는 기능입니다.\n"
                "예) \"Downloads 폴더를 확장자별로 분류해줘\""
            ),
        },
        {
            "keys": ["검색", "찾기", "search", "로컬"],
            "text": (
                "#로컬 검색\n"
                "사용자가 지정한 폴더 범위에서 검색하려는 내용에 맞는 문서, 스크립트 파일을 검색해주는 기능입니다.\n"
                "예) \"Documents 폴더에서 '프로젝트 보고서' 관련 파일 찾아줘\""
            ),
        },
        {
            "keys": ["파일", "이름", "rename", "확장자", "변경", "변환"],
            "text": (
                "#파일 이름 변환\n"
                "일괄적으로 파일의 이름을 변경할 수 있게 해주는 기능입니다.\n"
                "예) \"선택한 파일들 이름을 모두 소문자로 바꿔줘\""
            ),
        },
    ]

    @Slot(str, result=str)
    def getHelpText(self, key: str) -> str:
        """기능 키에 해당하는 한 줄 도움말을 반환한다."""
        return self._HELP_TEXT.get(key, "")

    @Slot(str, result=str)
    def getHelpByKeyword(self, keyword: str) -> str:
        """사용자가 입력한 키워드로 기능 도움말을 검색해 반환한다.

        매칭 없으면 전체 기능 목록을 반환한다.
        매칭 점수가 가장 높은 항목(키 일치 수 최다)을 반환한다.
        """
        kw = keyword.lower().strip()
        best, best_score = None, 0
        for item in self._HELP_DETAIL:
            score = sum(1 for k in item["keys"] if k in kw)
            if score > best_score:
                best, best_score = item, score
        if best_score > 0:
            return best["text"]
        # 매칭 없으면 전체 목록
        lines = [
            "사용 가능한 기능 목록:\n",
            "• 프롬프트 변환 — 모델용 프롬프트 자동 가공",
            "• 폴더 정리 — 기준에 맞춰 파일 자동 분류",
            "• 로컬 검색 — 폴더 내 문서/스크립트 검색",
            "• 파일 이름 변환 — 파일명 일괄 변경",
            "\n궁금한 기능 이름을 입력하면 자세한 설명을 드릴게요.",
        ]
        return "\n".join(lines)

    @Slot(result=bool)
    def getShownTagIntro(self) -> bool:
        """최초 기능 안내 팝업을 이미 표시했는지 여부를 반환한다."""
        try:
            if _PREFS_PATH.exists():
                return json.loads(
                    _PREFS_PATH.read_text(encoding="utf-8")
                ).get("shown_tag_intro", False)
        except Exception:  # noqa: BLE001
            pass
        return False

    @Slot(result=str)
    def getPipBubbleDir(self) -> str:
        """PIP 말풍선 방향을 반환한다. 'random' | 'left' | 'right'."""
        try:
            if _PREFS_PATH.exists():
                val = json.loads(_PREFS_PATH.read_text(encoding="utf-8")).get("pip_bubble_dir", "random")
                return val if val in ("random", "left", "right") else "random"
        except Exception:  # noqa: BLE001
            pass
        return "random"

    @Slot(str)
    def savePipBubbleDir(self, direction: str) -> None:
        """PIP 말풍선 방향을 preferences.json에 저장한다."""
        try:
            data: dict = {}
            if _PREFS_PATH.exists():
                data = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
            data["pip_bubble_dir"] = direction
            _PREFS_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    @Slot(bool)
    def setShownTagIntro(self, value: bool) -> None:
        """최초 기능 안내 팝업 표시 여부를 preferences.json에 저장한다."""
        try:
            data: dict = {}
            if _PREFS_PATH.exists():
                data = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
            data["shown_tag_intro"] = value
            _PREFS_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    # ── 내부 콜백 ─────────────────────────────────────────────────────────────

    # ── ChromaDB 뷰어 ────────────────────────────────────────────────────────

    @Slot(result=str)
    def getMemoryDB(self) -> str:
        """현재 캐릭터의 장기 기억 DB 전체를 JSON으로 반환 (MemoryDBPanel용)."""
        char_id = (self._agent.character or {}).get("id", "")
        long_term = getattr(self._agent, "long_term", None)
        if long_term is None or not char_id:
            return json.dumps({"collection": "", "total": 0, "sessions": {}}, ensure_ascii=False)
        try:
            return json.dumps(long_term.get_all(char_id), ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"error": str(e), "total": 0, "sessions": {}}, ensure_ascii=False)

    @Slot(str, result=str)
    def searchMemoryPreview(self, query: str) -> str:
        """현재 DB에서 유사 기억 검색 미리보기를 JSON으로 반환."""
        if not query.strip():
            return json.dumps([], ensure_ascii=False)
        char_id = (self._agent.character or {}).get("id", "")
        long_term = getattr(self._agent, "long_term", None)
        if long_term is None or not char_id:
            return json.dumps([], ensure_ascii=False)
        try:
            return json.dumps(long_term.query_preview(query, char_id), ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps([], ensure_ascii=False)

    # ── ChromaDB CRUD ─────────────────────────────────────────────────────────

    def _long_term_and_char(self):
        """(long_term, char_id) 쌍을 반환. 없으면 (None, "")."""
        char_id = (self._agent.character or {}).get("id", "")
        long_term = getattr(self._agent, "long_term", None)
        return long_term, char_id

    @Slot(str, result=bool)
    def deleteMemoryEntry(self, entry_id: str) -> bool:
        """항목을 ID로 삭제한다. 성공하면 memoryChanged emit."""
        long_term, char_id = self._long_term_and_char()
        if long_term is None or not char_id:
            return False
        ok = long_term.delete_entry(char_id, entry_id)
        if ok:
            self.memoryChanged.emit()
        return ok

    @Slot(str, str, result=str)
    def addMemoryEntry(self, content: str, meta_json: str) -> str:
        """새 항목을 추가한다. 성공하면 memoryChanged emit. 반환: 생성된 entry_id."""
        long_term, char_id = self._long_term_and_char()
        if long_term is None or not char_id or not content.strip():
            return ""
        try:
            metadata = json.loads(meta_json) if meta_json.strip() else {}
        except Exception:  # noqa: BLE001
            metadata = {}
        entry_id = long_term.add_entry(char_id, content.strip(), metadata)
        if entry_id:
            self.memoryChanged.emit()
        return entry_id

    @Slot(str, str, str, result=bool)
    def updateMemoryEntry(self, entry_id: str, new_content: str, meta_json: str) -> bool:
        """기존 항목을 수정한다. 성공하면 memoryChanged emit."""
        long_term, char_id = self._long_term_and_char()
        if long_term is None or not char_id or not entry_id:
            return False
        try:
            metadata = json.loads(meta_json) if meta_json.strip() else {}
        except Exception:  # noqa: BLE001
            metadata = {}
        ok = long_term.update_entry(char_id, entry_id, new_content.strip(), metadata)
        if ok:
            self.memoryChanged.emit()
        return ok

    # ── 세계관 RAG / 프롬프트 가이드 DB 조회 ────────────────────────────────

    @Slot(result=str)
    def getWorldKnowledgeDB(self) -> str:
        """world_knowledge ChromaDB 컬렉션 전체 청크를 JSON으로 반환."""
        import chromadb
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col = client.get_collection("world_knowledge")
            result = col.get(include=["documents", "metadatas"])
            chunks = []
            for i, doc in enumerate(result["documents"] or []):
                meta = (result["metadatas"] or [])[i] if result["metadatas"] else {}
                chunks.append({
                    "id":               result["ids"][i],
                    "content":          doc,
                    "source":           meta.get("source", ""),
                    "world_id":         meta.get("world_id", ""),
                    "section":          meta.get("section", ""),
                    "item_title":       meta.get("item_title", ""),
                    "trigger_keywords": meta.get("trigger_keywords", ""),
                })
            return json.dumps({"total": len(chunks), "chunks": chunks}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"total": 0, "chunks": [], "error": str(e)}, ensure_ascii=False)

    @Slot(result=bool)
    def reindexWorldKnowledge(self) -> bool:
        """rag/sources/world/ 디렉토리를 force=True로 재인덱싱한다."""
        from rag.index import index_world
        cfg = getattr(self._agent, "cfg", {})
        rag_dir   = Path(cfg.get("rag_world_dir", "./rag/sources/world"))
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        embed_model = cfg.get("embedding_model", "BAAI/bge-m3")
        try:
            index_world(rag_dir, chroma_path, embed_model, force=True)
            return True
        except Exception:  # noqa: BLE001
            return False

    @Slot(result=str)
    def getPromptGuidesDB(self) -> str:
        """prompt_guides ChromaDB 컬렉션 전체를 JSON으로 반환."""
        import chromadb
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col = client.get_collection("prompt_guides")
            result = col.get(include=["documents", "metadatas"])
            guides = []
            for i, doc in enumerate(result["documents"] or []):
                meta = (result["metadatas"] or [])[i] if result["metadatas"] else {}
                guides.append({
                    "id":           result["ids"][i],
                    "content":      doc,
                    # bridge 저장(model_name) 과 PromptGuideStore 저장(model) 양쪽 호환
                    "model_name":   meta.get("model_name") or meta.get("model", ""),
                    "character_id": meta.get("character_id", ""),
                })
            return json.dumps({"total": len(guides), "guides": guides}, ensure_ascii=False)
        except Exception as e:  # noqa: BLE001
            return json.dumps({"total": 0, "guides": [], "error": str(e)}, ensure_ascii=False)

    @Slot(result=str)
    def getPromptModelList(self) -> str:
        """prompt_guides DB에 있는 model_name 목록을 중복 제거하여 JSON 배열로 반환."""
        try:
            parsed = json.loads(self.getPromptGuidesDB())
            models = list(dict.fromkeys(
                g["model_name"] for g in parsed.get("guides", []) if g.get("model_name")
            ))
            return json.dumps(models, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            return "[]"

    # ── 세계관 RAG CRUD ──────────────────────────────────────────────────────

    @Slot(str, str, str, str, str, result=str)
    def addWorldKnowledge(
        self,
        world_id: str,
        section: str,
        item_title: str,
        content: str,
        trigger_keywords: str = "",
    ) -> str:
        """세계관 RAG 항목을 ChromaDB에 직접 추가하고 소스 .md 파일을 갱신한다.

        재인덱싱은 호출자가 필요 시 수행한다 (배치 추가 후 1회 reindex 패턴).

        Returns
        -------
        str : 생성된 chunk_id, 실패 시 빈 문자열
        """
        import chromadb
        import re as _re
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col_name = "world_knowledge"
            existing_cols = [c.name for c in client.list_collections()]
            if col_name in existing_cols:
                col = client.get_collection(col_name)
            else:
                from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
                embed_model = cfg.get("embedding_model", "BAAI/bge-m3")
                ef = SentenceTransformerEmbeddingFunction(model_name=embed_model)
                col = client.create_collection(
                    name=col_name,
                    embedding_function=ef,
                    metadata={"hnsw:space": "cosine"},
                )

            chunk_id = _re.sub(r"[^\w가-힣-]", "_", f"{world_id}_{section}_{item_title}")
            src_filename = self._get_world_md_filename(world_id)
            meta = {
                "world_id":         world_id,
                "section":          section,
                "item_title":       item_title,
                "trigger_keywords": trigger_keywords,
                "source":           src_filename,
            }
            # content만 저장 (index_world 파서와 일치)
            col.upsert(ids=[chunk_id], documents=[content], metadatas=[meta])

            # 소스 .md 파일을 ChromaDB 기준으로 재생성 (단일 소스 동기화)
            self._rebuild_world_md(world_id)
            return chunk_id
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[bridge] addWorldKnowledge 실패: {e}")
            return ""

    @Slot(str, str, result=bool)
    def updateWorldKnowledge(self, chunk_id: str, content: str) -> bool:
        """세계관 RAG 항목 내용을 수정하고 소스 파일을 갱신한 뒤 재인덱싱한다."""
        import chromadb
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col = client.get_collection("world_knowledge")
            existing = col.get(ids=[chunk_id], include=["metadatas"])
            if not existing["ids"]:
                return False
            meta = existing["metadatas"][0]
            world_id = meta.get("world_id", "")
            # content만 저장 (index_world 파서와 일치)
            col.update(ids=[chunk_id], documents=[content])
            # 소스 파일 동기화 후 재인덱싱 (임베딩 갱신)
            self._rebuild_world_md(world_id)
            self.reindexWorldKnowledge()
            return True
        except Exception:  # noqa: BLE001
            return False

    @Slot(str, result=bool)
    def deleteWorldKnowledge(self, chunk_id: str) -> bool:
        """세계관 RAG 항목을 ChromaDB에서 삭제하고 소스 파일을 갱신한 뒤 재인덱싱한다."""
        import chromadb
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col = client.get_collection("world_knowledge")
            existing = col.get(ids=[chunk_id], include=["metadatas"])
            if not existing["ids"]:
                return False
            world_id = existing["metadatas"][0].get("world_id", "")
            col.delete(ids=[chunk_id])
            # 삭제 후 소스 파일 재생성 → 재인덱싱 (소스 파일이 먼저 갱신되어야 reindex가 정확함)
            self._rebuild_world_md(world_id)
            self.reindexWorldKnowledge()
            return True
        except Exception:  # noqa: BLE001
            return False

    def _get_world_md_filename(self, world_id: str) -> str:
        """world_id에 해당하는 .md 파일명을 반환한다 (없으면 '{world_id}.md')."""
        cfg = getattr(self._agent, "cfg", {})
        rag_dir = Path(cfg.get("rag_world_dir", "./rag/sources/world"))
        for md_path in rag_dir.glob("*.md"):
            try:
                first = md_path.read_text(encoding="utf-8").split("\n")[0].strip()
                if first == f"# {world_id}":
                    return md_path.name
            except Exception:
                pass
        return f"{world_id}.md"

    def _rebuild_world_md(self, world_id: str) -> None:
        """ChromaDB의 world_id 항목으로 소스 .md 파일을 완전히 재생성한다.

        소스 파일은 ChromaDB의 단순 직렬화이므로 항상 ChromaDB가 기준이 된다.
        재인덱싱(`reindexWorldKnowledge`)을 별도 호출해야 임베딩이 갱신된다.
        """
        import chromadb
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        rag_dir = Path(cfg.get("rag_world_dir", "./rag/sources/world"))
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            existing = [c.name for c in client.list_collections()]
            if "world_knowledge" not in existing:
                return
            col = client.get_collection("world_knowledge")
            results = col.get(
                where={"world_id": world_id},
                include=["documents", "metadatas"],
            )
            if not results.get("ids"):
                return

            sections_order = ["culture", "place", "story"]
            groups: dict[str, list] = {s: [] for s in sections_order}
            for doc, meta in zip(results["documents"], results["metadatas"]):
                sec = meta.get("section", "")
                if sec in groups:
                    groups[sec].append({
                        "item_title":       meta.get("item_title", ""),
                        "trigger_keywords": meta.get("trigger_keywords", ""),
                        "content":          doc,
                    })

            lines: list[str] = [f"# {world_id}", ""]
            for sec in sections_order:
                items = groups[sec]
                if not items:
                    continue
                lines += [f"## {sec}", ""]
                for it in items:
                    lines.append(f"### {it['item_title']}")
                    kw = it["trigger_keywords"].strip()
                    if kw:
                        lines.append(f"트리거 키워드: [{kw}]")
                    lines.append(it["content"].strip())
                    lines.append("")

            # 기존 파일 경로 탐색 (없으면 world_id.md 생성)
            src_path: Path | None = None
            for md_path in rag_dir.glob("*.md"):
                try:
                    first = md_path.read_text(encoding="utf-8").split("\n")[0].strip()
                    if first == f"# {world_id}":
                        src_path = md_path
                        break
                except Exception:
                    pass
            if src_path is None:
                src_path = rag_dir / f"{world_id}.md"

            src_path.write_text("\n".join(lines), encoding="utf-8")
            logger.debug(f"[bridge] world md 재생성: {src_path.name} ({len(results['ids'])}개 항목)")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[bridge] _rebuild_world_md 실패 ({world_id}): {e}")

    # ── 프롬프트 가이드 CRUD ─────────────────────────────────────────────────

    @Slot(str, str, str, result=str)
    def addPromptGuide(self, model_name: str, content: str, character_id: str = "") -> str:
        """프롬프트 가이드를 ChromaDB에 추가한다.

        Returns
        -------
        str : 생성된 guide_id, 실패 시 빈 문자열
        """
        import chromadb
        import re as _re
        import uuid as _uuid
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col_name = "prompt_guides"
            existing_cols = [c.name for c in client.list_collections()]
            if col_name in existing_cols:
                col = client.get_collection(col_name)
            else:
                from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
                embed_model = cfg.get("embedding_model", "BAAI/bge-m3")
                ef = SentenceTransformerEmbeddingFunction(model_name=embed_model)
                col = client.create_collection(
                    name=col_name,
                    embedding_function=ef,
                    metadata={"hnsw:space": "cosine"},
                )

            import re as _re2
            model_key = _re2.sub(r"[\s_]+", "-", model_name.strip().lower())
            guide_id = f"pg_{_re.sub(r'[^\\w]', '_', model_name)}_{_uuid.uuid4().hex[:6]}"
            meta = {
                "model_name":   model_name,
                "model":        model_key,   # PromptGuideStore.query() 호환 키
                "character_id": character_id,
            }
            col.add(ids=[guide_id], documents=[content], metadatas=[meta])
            return guide_id
        except Exception:  # noqa: BLE001
            return ""

    @Slot(str, str, result=bool)
    def updatePromptGuide(self, guide_id: str, content: str) -> bool:
        """프롬프트 가이드 내용을 수정한다."""
        import chromadb
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col = client.get_collection("prompt_guides")
            existing = col.get(ids=[guide_id])
            if not existing["ids"]:
                return False
            col.update(ids=[guide_id], documents=[content])
            return True
        except Exception:  # noqa: BLE001
            return False

    @Slot(str, result=bool)
    def deletePromptGuide(self, guide_id: str) -> bool:
        """프롬프트 가이드를 ChromaDB에서 삭제한다."""
        import chromadb
        cfg = getattr(self._agent, "cfg", {})
        chroma_path = cfg.get("chroma_path", "./chroma_dev")
        try:
            client = chromadb.PersistentClient(path=chroma_path)
            col = client.get_collection("prompt_guides")
            existing = col.get(ids=[guide_id])
            if not existing["ids"]:
                return False
            col.delete(ids=[guide_id])
            return True
        except Exception:  # noqa: BLE001
            return False

    # ── 대화 파라미터 관리자 ──────────────────────────────────────────────────

    @Slot(result=str)
    def getConvParams(self) -> str:
        """현재 캐릭터의 conversation 파라미터를 JSON으로 반환."""
        char = getattr(self._agent, "character", None) or {}
        return json.dumps(char.get("conversation", {}), ensure_ascii=False)

    @Slot(str, str, float)
    def setConvParam(self, param: str, tier_or_key: str, value: float) -> None:
        """대화 파라미터를 메모리에서 즉시 변경한다 (YAML 비저장).

        param        : "response_length" | "openness" | "directness"
        tier_or_key  : tier명 (response_length/openness) 또는 "_" (directness 단일값)
        value        : 0.0 ~ 1.0
        """
        char = getattr(self._agent, "character", None)
        if char is None:
            return
        conv = char.setdefault("conversation", {})
        value = max(0.0, min(1.0, float(value)))
        if param in ("response_length", "openness"):
            if not isinstance(conv.get(param), dict):
                conv[param] = {}
            conv[param][tier_or_key] = value
        elif param == "directness":
            conv["directness"] = value
        # router.builder가 character 참조를 공유하므로 다음 assemble()에 즉시 반영

    # ── 캐릭터 생성 ───────────────────────────────────────────────────────────

    @Slot(str, result=str)
    def saveNewCharacter(self, json_data: str) -> str:
        """JSON으로 캐릭터 정의를 받아 CH_{id}.yaml로 저장한다.

        Returns: 저장된 char_id (성공), "" (실패)
        """
        import yaml as _yaml
        try:
            data = json.loads(json_data)
            char_id = data.get("id", "").strip()
            if not char_id:
                return ""
            dest = _CHARACTER_DIR / f"CH_{char_id}.yaml"
            dest.write_text(
                _yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            return char_id
        except Exception as e:  # noqa: BLE001
            self.messageAdded.emit("system", f"[캐릭터 저장 실패] {e}")
            return ""

    def _on_response(self, response: str) -> None:
        # assistant 응답 먼저 표시 → 나레이션은 그 뒤에 표시
        for role, content in _split_narration(response, "assistant"):
            self.messageAdded.emit(role, content)

        router = getattr(self._agent, "router", None)
        if router is not None:
            narration_data = getattr(router, "_pending_narration", None)
            if narration_data:
                _title, document = narration_data
                self.messageAdded.emit("narrator", document)
                router._pending_narration = None
        self._sync_state()
        self._sync_session_state()  # 턴 종료 시 세션 상태 디스크 동기화

        # 학습 데이터 로깅 (enable_play_log=True 환경)
        if self._conv_logger is not None:
            session = getattr(self._agent, "session", None)
            if session is not None:
                # 마지막으로 추가된 user 발화 복원 (dialogue_log[-2])
                log = session.dialogue_log
                user_text = log[-2]["content"] if len(log) >= 2 else ""
                self._conv_logger.on_turn(
                    user_input=user_text,
                    assistant_response=response,
                    mood=session.mood,
                    affection=session.affection,
                )

    @Slot(int, str, str)
    def editMessage(self, qml_index: int, old_content: str, new_content: str) -> None:
        """사용자가 수정한 assistant/narrator 메시지를 세션 로그와 학습 데이터에 반영한다.

        **...**가 포함된 경우 QML 버블을 재분할한다:
          "안녕. **그가 웃었다.** 잘 지냈어?"
          → [assistant: "안녕."] [narrator: "그가 웃었다."] [assistant: "잘 지냈어?"]

        Parameters
        ----------
        qml_index:
            messageModel 내 메시지 인덱스 (QML에서 전달).
        old_content:
            수정 전 원본 텍스트.
        new_content:
            수정 후 텍스트.
        """
        if old_content == new_content:
            return

        # 1. session.dialogue_log 업데이트
        session = getattr(self._agent, "session", None)
        if session is not None:
            for msg in session.dialogue_log:
                if msg.get("role") in ("assistant", "narrator") and msg.get("content") == old_content:
                    msg["content"] = new_content
                    break

        # 2. conversation_logger 버퍼 및 저장 파일 업데이트
        if self._conv_logger is not None:
            self._conv_logger.edit_turn(old_content, new_content)

        # 3. **...** / *...* 포함 시 QML 버블 재분할
        if _SPLIT_RE.search(new_content):
            segments = [
                {"role": r, "content": c}
                for r, c in _split_narration(new_content, "assistant")
            ]
            self.messageReplaced.emit(qml_index, segments)

    def _on_error(self, msg: str) -> None:
        self.messageAdded.emit("system", f"[오류] {msg}")

    def _on_done(self) -> None:
        self._worker = None
        self.statusChanged.emit("ready")

