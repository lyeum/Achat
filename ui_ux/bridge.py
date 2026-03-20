from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from PySide6.QtWidgets import QApplication

from ui_ux.chat_panel import LLMWorker

_ASSETS         = Path(__file__).resolve().parent / "assets"
_CHARACTER_DIR  = Path(__file__).resolve().parent.parent / "conversation" / "character"
_WORLD_DIR      = Path(__file__).resolve().parent.parent / "conversation" / "world"
_ICONS_DIR      = _ASSETS / "icons"         # icons/{CharId}/{CharId}.png + emotion/
_CHAR_PARTS_DIR = _ASSETS / "characters"    # characters/{type}/*.png (base/hair/eye/mouth/cloth)
_BG_DIR         = _ASSETS / "background"    # background/{world_id}/{act_id}.png


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

    def __init__(self, agent):
        super().__init__()
        self._agent = agent
        self._worker: LLMWorker | None = None
        self._character_name: str = agent.character.get("name", "")

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

    # ── 내부 헬퍼 ────────────────────────────────────────────────────────────

    def _build_bg_url(self) -> str:
        """현재 session의 act에 해당하는 location 배경 이미지 file URL을 반환한다.
        파일이 없거나 stub 모드면 빈 문자열을 반환한다.

        탐색 경로: background/{world_id}/{location}.png
        location은 world YAML의 act.location 필드에서 역참조한다.
        """
        from conversation.loader.world_load import get_act, load_world

        session = getattr(self._agent, "session", None)
        world   = getattr(self._agent, "world", {})
        world_id    = world.get("world_id", "")
        scenario_id = session.scenario_id if session else None
        act_id      = session.act_id if session else None
        if not (world_id and scenario_id and act_id):
            return ""

        # world dict가 이미 로드돼 있으면 그대로 사용, 없으면 YAML에서 로드
        if world:
            act = get_act(world, scenario_id, act_id)
        else:
            try:
                for p in _WORLD_DIR.glob("W_*.yaml"):
                    w = load_world(p)
                    if w.get("world_id") == world_id:
                        act = get_act(w, scenario_id, act_id)
                        break
                else:
                    act = None
            except Exception:  # noqa: BLE001
                act = None

        location = act.get("location", "") if act else ""
        if not location:
            return ""
        path = _BG_DIR / world_id / f"{location}.png"
        return QUrl.fromLocalFile(str(path)).toString() if path.exists() else ""

    def _read_mood(self) -> str:
        session = getattr(self._agent, "session", None)
        return session.mood if session else "neutral"

    def _sync_state(self) -> None:
        """응답 후 act/mood 변화를 감지하고 변경 시 시그널을 emit한다."""
        new_bg = self._build_bg_url()
        if new_bg != self._current_bg:
            self._current_bg = new_bg
            self.backgroundChanged.emit(new_bg)

        new_mood = self._read_mood()
        if new_mood != self._current_mood:
            self._current_mood = new_mood
            self.moodChanged.emit(new_mood)

    # ── Slots (QML → Python) ──────────────────────────────────────────────────

    @Slot(str)
    def sendMessage(self, text: str) -> None:
        """QML 입력창에서 메시지를 전송할 때 호출된다."""
        if not text.strip() or self._worker is not None:
            return

        self.messageAdded.emit("user", text)
        self.statusChanged.emit("thinking")

        self._worker = LLMWorker(self._agent, text)
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

        part_types = ["base", "hair", "eye", "mouth", "cloth"]
        result: dict[str, list[str]] = {}
        for pt in part_types:
            d = _CHAR_PARTS_DIR / pt
            result[pt] = sorted(f.name for f in d.iterdir() if f.suffix.lower() == ".png") \
                         if d.exists() else []
        return json.dumps(result, ensure_ascii=False)

    @Slot(str, str, str)
    def changeWorld(self, world_id: str, scenario_id: str, act_id: str) -> None:
        """세계관 / 시나리오 / act를 전환한다."""
        if self._agent.session is None:
            return

        import json as _json

        from agent.persona import swap_persona
        from conversation.core.prompt_build import PromptBuilder
        from conversation.loader.world_load import load_world

        for path in _WORLD_DIR.glob("W_*.yaml"):
            try:
                world = load_world(path)
            except Exception:  # noqa: BLE001
                continue
            if world.get("world_id") != world_id:
                continue

            try:
                new_char, new_session = swap_persona(
                    session=self._agent.session,
                    new_character_id=self._agent.character["id"],
                    world_id=world_id,
                    scenario_id=scenario_id,
                    act_id=act_id,
                )
                self._agent.world     = world
                self._agent.character = new_char
                self._agent.session   = new_session

                if self._agent.router is not None:
                    self._agent.router.character = new_char
                    self._agent.router.session   = new_session
                    self._agent.router.builder   = PromptBuilder(
                        new_char, world, new_session,
                        count_tokens_fn=self._agent.llm.count_tokens,
                    )

                self._sync_state()
            except Exception as e:  # noqa: BLE001
                self.messageAdded.emit("system", f"[세계관 변경 실패] {e}")
            return

        self.messageAdded.emit("system", f"[세계관 변경 실패] world_id='{world_id}' 없음")

    @Slot(str)
    def changeCharacter(self, char_id: str) -> None:
        """캐릭터를 핫스왑하고 이름 변경 시그널을 emit한다."""
        if self._agent.session is None:   # stub / ui_test 모드
            return

        from agent.persona import swap_persona
        from conversation.core.prompt_build import PromptBuilder
        try:
            new_char, new_session = swap_persona(
                session=self._agent.session,
                new_character_id=char_id.strip(),
            )
            self._agent.character = new_char
            self._agent.session   = new_session

            # router와 builder도 새 character / session 으로 교체
            if self._agent.router is not None:
                self._agent.router.character = new_char
                self._agent.router.session   = new_session
                self._agent.router.builder   = PromptBuilder(
                    new_char,
                    self._agent.world,
                    new_session,
                    count_tokens_fn=self._agent.llm.count_tokens,
                )

            self._character_name = new_char.get("name", char_id)
            self.characterNameChanged.emit(self._character_name)
        except FileNotFoundError as e:
            self.messageAdded.emit("system", f"[캐릭터 변경 실패] {e}")

    # ── 내부 콜백 ─────────────────────────────────────────────────────────────

    def _on_response(self, response: str) -> None:
        self.messageAdded.emit("assistant", response)
        self._sync_state()

    def _on_error(self, msg: str) -> None:
        self.messageAdded.emit("system", f"[오류] {msg}")

    def _on_done(self) -> None:
        self._worker = None
        self.statusChanged.emit("ready")
