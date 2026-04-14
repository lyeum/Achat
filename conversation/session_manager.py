from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class SessionState:
    """디스크에 영속화되는 세션 메타데이터.

    ConversationSession의 런타임 상태 중 재기동 후 복원이 필요한 항목을 담는다.
    dialogue_log는 런타임 전용이라 포함하지 않는다.
    """

    session_id: str
    char_id: str
    world_id: Optional[str] = None
    scenario_id: Optional[str] = None
    act_id: Optional[str] = None
    location: str = ""
    turn_count: int = 0
    mood: str = "neutral"
    affection: int = 30
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    last_active: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    # 세계관 트리거 상태 (세션 변경 시 초기화)
    fired_stories: list = field(default_factory=list)        # 발동된 story item_title 목록
    visited_places: list = field(default_factory=list)       # 방문한 장소 목록
    explained_cultures: list = field(default_factory=list)   # 세션 내 설명된 culture 항목


@dataclass
class SessionMeta:
    """세션 인덱스 항목 (sessions.json 한 줄)."""

    session_id: str
    char_id: str
    created_at: str
    last_active: str
    world_id: Optional[str] = None


class SessionManager:
    """캐릭터별 세션의 생성·활성화·저장·초기화를 담당한다.

    디렉토리 구조:
        {state_dir}/
        ├── active.json                   ← 현재 활성 세션 포인터
        └── {char_id}/
            ├── sessions.json             ← 세션 목록 인덱스
            └── {session_id}/
                └── state.json            ← 세션 상태 스냅샷
    """

    MAX_SESSIONS = 3  # 캐릭터당 유지할 최대 세션 수

    def __init__(self, state_dir: Path):
        self._root = Path(state_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    # ── 경로 헬퍼 ──────────────────────────────────────────────────────────────

    def _active_path(self) -> Path:
        return self._root / "active.json"

    def _char_dir(self, char_id: str) -> Path:
        d = self._root / char_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _sessions_index_path(self, char_id: str) -> Path:
        return self._char_dir(char_id) / "sessions.json"

    def _session_state_path(self, char_id: str, session_id: str) -> Path:
        d = self._char_dir(char_id) / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d / "state.json"

    # ── 인덱스 관리 ────────────────────────────────────────────────────────────

    def _load_index(self, char_id: str) -> list[dict]:
        p = self._sessions_index_path(char_id)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_index(self, char_id: str, index: list[dict]) -> None:
        self._sessions_index_path(char_id).write_text(
            json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _upsert_index(self, state: SessionState) -> None:
        index = self._load_index(state.char_id)
        meta = {
            "session_id":  state.session_id,
            "char_id":     state.char_id,
            "created_at":  state.created_at,
            "last_active": state.last_active,
            "world_id":    state.world_id,
        }
        for i, item in enumerate(index):
            if item["session_id"] == state.session_id:
                index[i] = meta
                break
        else:
            index.append(meta)
        self._save_index(state.char_id, index)

    # ── SessionState 직렬화 ────────────────────────────────────────────────────

    def _load_state(self, char_id: str, session_id: str) -> SessionState | None:
        p = self._session_state_path(char_id, session_id)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return SessionState(**data)
        except Exception:
            return None

    def _save_state(self, state: SessionState) -> None:
        state.last_active = datetime.now(timezone.utc).isoformat()
        self._session_state_path(state.char_id, state.session_id).write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self._upsert_index(state)

    # ── 활성 포인터 ────────────────────────────────────────────────────────────

    def _load_active(self) -> dict | None:
        p = self._active_path()
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _save_active(self, char_id: str, session_id: str) -> None:
        self._active_path().write_text(
            json.dumps(
                {"char_id": char_id, "session_id": session_id},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    # ── 공개 API ──────────────────────────────────────────────────────────────

    def get_active(self) -> SessionState | None:
        """현재 활성 세션 상태를 반환한다. 없으면 None."""
        ptr = self._load_active()
        if ptr is None:
            return None
        return self._load_state(ptr["char_id"], ptr["session_id"])

    def activate(self, char_id: str, session_id: str | None = None) -> SessionState:
        """캐릭터를 활성화한다.

        session_id를 지정하면 해당 세션을 재개한다.
        None이면 가장 최근 세션을 재개하고, 세션이 없으면 새로 생성한다.
        """
        if session_id is not None:
            state = self._load_state(char_id, session_id)
            if state:
                self._save_active(char_id, session_id)
                return state

        # 최신 세션 탐색
        index = self._load_index(char_id)
        if index:
            latest = max(index, key=lambda x: x.get("last_active", ""))
            state = self._load_state(char_id, latest["session_id"])
            if state:
                self._save_active(char_id, state.session_id)
                return state

        # 세션 없음 → 신규 생성
        return self._create_session(char_id)

    def new_session(
        self, char_id: str, keep_memory: bool = False
    ) -> tuple[SessionState, str | None]:
        """새 세션을 시작한다.

        Returns
        -------
        (새 SessionState, 삭제해야 할 이전 session_id or None)

        keep_memory=True이면 이전 session_id를 None으로 반환해
        VDB 에피소딕 기억 삭제를 생략한다.
        """
        old = self.get_active()
        old_session_id: str | None = None
        if old and old.char_id == char_id and not keep_memory:
            old_session_id = old.session_id

        return self._create_session(char_id), old_session_id

    def save_state(self, state: SessionState) -> None:
        """런타임 세션 상태를 디스크에 기록한다 (턴 종료 시 호출)."""
        self._save_state(state)

    def list_sessions(self, char_id: str) -> list[SessionMeta]:
        """해당 캐릭터의 세션 목록을 반환한다."""
        result = []
        for item in self._load_index(char_id):
            # 구버전 인덱스(world_id 없음) 하위호환
            item.setdefault("world_id", None)
            result.append(SessionMeta(**item))
        return result

    def activate_for_world(self, char_id: str, world_id: str) -> SessionState:
        """(char_id, world_id) 쌍에 해당하는 세션을 찾아 활성화한다.

        일치하는 세션이 없으면 새로 생성한다.
        """
        index = self._load_index(char_id)
        # world_id가 일치하는 세션 중 가장 최근 것
        candidates = [
            i for i in index if i.get("world_id") == world_id
        ]
        if candidates:
            latest = max(candidates, key=lambda x: x.get("last_active", ""))
            state = self._load_state(char_id, latest["session_id"])
            if state:
                self._save_active(char_id, state.session_id)
                return state
        # 없으면 신규 생성 (world_id 포함)
        return self._create_session(char_id, world_id=world_id)

    # ── 내부 ──────────────────────────────────────────────────────────────────

    def _evict_session(self, char_id: str, session_id: str) -> None:
        """세션 디렉토리와 인덱스 항목을 제거한다."""
        import shutil
        session_dir = self._char_dir(char_id) / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
        index = self._load_index(char_id)
        index = [i for i in index if i["session_id"] != session_id]
        self._save_index(char_id, index)

    def _create_session(self, char_id: str, world_id: str | None = None) -> SessionState:
        # 최대 세션 수 초과 시 가장 오래된 세션 제거
        index = self._load_index(char_id)
        if len(index) >= self.MAX_SESSIONS:
            oldest = min(index, key=lambda x: x.get("last_active", ""))
            self._evict_session(char_id, oldest["session_id"])

        now = datetime.now(timezone.utc).isoformat()
        session_id = (
            "s_"
            + datetime.now(timezone.utc).strftime("%Y%m%d_")
            + uuid.uuid4().hex[:6]
        )
        state = SessionState(
            session_id=session_id,
            char_id=char_id,
            world_id=world_id,
            created_at=now,
            last_active=now,
        )
        self._save_state(state)
        self._save_active(char_id, session_id)
        return state
