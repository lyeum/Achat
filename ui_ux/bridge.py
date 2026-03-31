from __future__ import annotations

import json
import platform
import subprocess as _subprocess
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtWidgets import QApplication


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

    messageAdded         = Signal(str, str)   # role, content
    statusChanged        = Signal(str)        # "thinking" | "ready"
    characterNameChanged = Signal(str)
    backgroundChanged    = Signal(str)        # file URL or ""
    moodChanged          = Signal(str)        # neutral | happy | annoyed | sad
    affectionChanged     = Signal(int)        # 0~100 — admin 조작 or 잠금 해제 시 emit
    imageImported        = Signal(str, str)   # slot_type, result (icon→URL, parts→filename)

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

    # ── 세션 관리 내부 헬퍼 ──────────────────────────────────────────────────

    def _init_session(self) -> None:
        """앱 시작 시 SessionManager와 ConversationSession을 연동한다.

        이전 세션이 있으면 mood / affection / turn_count를 복원하고,
        없으면 새 세션을 생성해 session_id를 부여한다.
        """
        char_id = self._agent.character.get("id", "")
        active = self._session_manager.get_active()
        if active and active.char_id == char_id:
            self._agent.session.session_id = active.session_id
            self._agent.session.mood       = active.mood
            self._agent.session.affection  = active.affection
            self._agent.session.turn_count = active.turn_count
            if active.location:
                self._agent.session.location = active.location
        else:
            state = self._session_manager.activate(char_id)
            self._agent.session.session_id = state.session_id

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
        state.affection   = session.affection
        state.location    = session.location    or state.location
        state.act_id      = session.act_id      or state.act_id
        state.scenario_id = session.scenario_id or state.scenario_id
        state.world_id    = session.world_id    or state.world_id
        self._session_manager.save_state(state)

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
        """SessionState로부터 새 Agent를 구성하고 self._agent를 교체한다.

        새 LLM 로드 전 반드시 기존 LLM을 해제(_unload_llm)해야 한다.
        해제 없이 로드하면 기존 모델이 GC되기 전까지 두 모델이 동시에 메모리에
        올라가 OOM이 발생한다. (Qwen2.5-3B bfloat16 기준 순간 ~12 GB)
        """
        from agent.core import Agent

        # 기존 LLM 먼저 해제 — OOM 방지 핵심
        self._unload_llm()

        cfg = getattr(self._agent, "cfg", None)
        self._agent = Agent.from_session(state, cfg)
        self._character_name = self._agent.character.get("name", state.char_id)
        self._location = self._resolve_initial_location()

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

        # 경로가 필요한 도구는 OS 파일 탐색기로 먼저 디렉토리를 선택
        selected_path = ""
        if mode == "function" and tool_name in self._PATH_TOOLS:
            from PySide6.QtWidgets import QFileDialog
            selected_path = QFileDialog.getExistingDirectory(
                None, "작업할 폴더 선택", str(Path.home())
            )
            if not selected_path:
                return  # 사용자가 취소

        self.messageAdded.emit("user", text)
        self.statusChanged.emit("thinking")

        self._worker = LLMWorker(
            self._agent, text, mode=mode,
            tool_name=tool_name, selected_path=selected_path,
        )
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

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
                        {"act_id": a["act_id"], "location": a.get("location", "")}
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

    @Slot(result=str)
    def getAllPartsList(self) -> str:
        """파츠 타입별 사용 가능한 파일 목록을 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``{"base": ["base_01.png", ...], "hair": [...], ...}`` 형태의 JSON.

        파츠 폴더: characters/{type}/*.png
        타입: base / hair / eye / mouth / cloth
        """
        import json

        part_types = ["base", "hair", "eye", "eyebrow", "mouth", "cloth"]
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
        """세계관 / 시나리오 / act를 전환한다. stub 모드에서는 배경만 전환."""
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
                    # 세계관/시나리오/act를 세션에 반영 (session_id 유지)
                    from conversation.core.prompt_build import PromptBuilder
                    old_session_id = self._agent.session.session_id
                    from agent.persona import swap_persona
                    new_char, new_session = swap_persona(
                        session=self._agent.session,
                        new_character_id=self._agent.character["id"],
                        world_id=world_id,
                        scenario_id=scenario_id,
                        act_id=act_id,
                    )
                    new_session.location   = self._location
                    new_session.session_id = old_session_id  # session_id 유지
                    self._agent.character = new_char
                    self._agent.session   = new_session
                    if self._agent.router is not None:
                        self._agent.router.character = new_char
                        self._agent.router.session   = new_session
                        self._agent.router.builder   = PromptBuilder(
                            new_char, world, new_session,
                            count_tokens_fn=self._agent.llm.count_tokens,
                        )
                    # 변경된 world/scenario/act를 SessionState에 반영
                    self._sync_session_state()

                # 항상 배경/mood emit
                new_bg = self._build_bg_url()
                self._current_bg = new_bg
                self.backgroundChanged.emit(new_bg)
                new_mood = self._read_mood()
                self._current_mood = new_mood
                self.moodChanged.emit(new_mood)
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
        new_state, old_session_id = self._session_manager.new_session(char_id, keep_memory)

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

        label = "새 세션이 시작되었습니다." if not keep_memory else "새 세션 시작 (기억 유지)."
        self.messageAdded.emit("system", label)

    @Slot(str, result=str)
    def listSessions(self, char_id: str) -> str:
        """해당 캐릭터의 세션 목록을 JSON 문자열로 반환한다.

        Returns
        -------
        str
            ``[{"session_id": "...", "char_id": "...", "created_at": "...", "last_active": "..."}]``
        """
        metas = self._session_manager.list_sessions(char_id)
        return json.dumps(
            [{"session_id": m.session_id, "char_id": m.char_id,
              "created_at": m.created_at, "last_active": m.last_active}
             for m in metas],
            ensure_ascii=False,
        )

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

    # ── 도움말 / 최초 안내 ──────────────────────────────────────────────────────

    _HELP_TEXT: dict[str, str] = {
        "file_convert":   "#파일 변환 — 파일명 변경 또는 확장자(jpg/png/webp 등) 변환",
        "prompt_convert": "#프롬프트 변환 — ChromaDB 가이드 기반 프롬프트 자동 변환",
        "folder_classify": "#폴더 분류 — 날짜/확장자별로 파일을 하위 폴더로 자동 정리",
        "local_search":   "#파일 검색 — 폴더 내 파일명·내용 키워드 검색 (서브폴더 포함)",
        "web_search":     "#웹 검색 — DuckDuckGo 인터넷 검색 (클릭 가능한 하이퍼링크 제공)",
        "help":           "#? — 각 기능에 대한 간략한 설명을 표시합니다",
    }

    @Slot(str, result=str)
    def getHelpText(self, key: str) -> str:
        """기능 키에 해당하는 한 줄 도움말을 반환한다."""
        return self._HELP_TEXT.get(key, "")

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

    def _on_response(self, response: str) -> None:
        self.messageAdded.emit("assistant", response)
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

    def _on_error(self, msg: str) -> None:
        self.messageAdded.emit("system", f"[오류] {msg}")

    def _on_done(self) -> None:
        self._worker = None
        self.statusChanged.emit("ready")
