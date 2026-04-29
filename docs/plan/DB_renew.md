# DB_renew — 세션 관리 & VDB 재설계 구현 계획

> 목표: 캐릭터별 다중 세션 지원, 에피소딕 기억의 세션 단위 분리, 영구 지식 보존
> 관련 문서: `docs/VDB.md`
>
> **구현 현황 (2026-04-21)**
> - Phase 2 (`clear_session()`) ✅ 완료
> - Phase 6 (`enable_play_log` 플래그) ✅ 완료
> - Phase 1·3·4·5 미구현 — `docs/로드맵.md` 4단계 참조

---

## 1. 설계 요약

### 1-1. 세션 정의

| 개념 | 설명 |
|---|---|
| **세션(Session)** | 특정 캐릭터와 진행하는 하나의 대화 회차 |
| **활성 세션** | 현재 진행 중인 세션. 동시 활성 세션은 1개로 제한 |
| **세션 초기화** | 에피소딕 기억을 날리고 새 대화를 시작하는 동작 |
| **세션 복귀** | 다른 캐릭터로 전환 후 복귀 시 이전 세션을 자동으로 재개 |

### 1-2. 메모리 계층

```
캐릭터 (character_id)
 ├── 영구 지식    → world_knowledge (공유, 절대 삭제 안 함)
 └── 세션 목록
      ├── session_A  → {char_id}_memory (session_id = A 필터)
      ├── session_B  → {char_id}_memory (session_id = B 필터)
      └── session_C  → 현재 활성 세션
```

- `{char_id}_memory` 컬렉션은 캐릭터 단위로 유지하되, `session_id` 메타데이터로 세션을 구분한다.
- 세션 초기화 시 해당 `session_id`를 가진 기억만 선택적으로 삭제한다.
- `world_knowledge`는 세션과 무관하게 항상 보존된다.

### 1-3. play_log 정책

- `play_log/*.jsonl`은 개발 환경에서만 수집한다.
- 배포(deployment) 빌드에서는 play_log 관련 코드를 로드하지 않는다.
- 런타임 대화 경로(`router.py`)에서 play_log 쓰기는 `config.py`의 `enable_play_log` 플래그로 제어한다.

---

## 2. 구현 범위 및 단계

### Phase 1 — SessionManager 도입

#### 2-1. `conversation/session_manager.py` 신규 작성

```python
# 역할: 세션 생명주기 관리 (생성·조회·전환·초기화)
class SessionManager:
    def __init__(self, state_dir: Path): ...

    def get_active(self) -> SessionState | None:
        """현재 활성 세션 반환"""

    def activate(self, char_id: str, session_id: str | None = None) -> SessionState:
        """캐릭터 활성화. session_id=None이면 최근 세션 재개"""

    def new_session(self, char_id: str, keep_memory: bool = False) -> SessionState:
        """새 세션 시작. keep_memory=False면 이전 에피소딕 기억 삭제"""

    def list_sessions(self, char_id: str) -> list[SessionMeta]:
        """해당 캐릭터의 세션 목록 반환"""
```

#### 2-2. 상태 파일 구조 (`data/sessions/`)

```
data/sessions/
├── active.json          ← 현재 활성 세션 포인터
│   { "char_id": "haru", "session_id": "s_2026_03_22_001" }
└── {char_id}/
    ├── sessions.json    ← 세션 목록 인덱스
    │   [{ "session_id": "s_...", "created_at": "...", "last_active": "..." }]
    └── {session_id}/
        └── state.json   ← 세션 상태 (turn_count, location, 등)
```

---

### Phase 2 — LongTermMemory 세션 파라미터화

#### 2-3. `memory/long_term.py` 수정

현재 `LongTermMemory`는 `char_id`를 기준으로 컬렉션을 열고, `session_id`를 선택적 필터로만 사용한다.
세션 단위 삭제를 지원하도록 `clear_session()` 메서드를 추가한다.

```python
class LongTermMemory:
    def clear_session(self, session_id: str) -> int:
        """session_id에 해당하는 기억 전체 삭제. 삭제된 항목 수 반환"""
        col = self._get_col()
        result = col.get(where={"session_id": {"$eq": session_id}})
        if result["ids"]:
            col.delete(ids=result["ids"])
        return len(result["ids"])

    def query(self, text: str, session_id: str | None = None, n: int = 2):
        """session_id 지정 시 해당 세션 기억만 검색, None이면 전 세션 검색"""
```

> 세션 복귀 시 이전 세션 기억을 그대로 검색에 활용할지 여부는 `SessionManager.activate()` 호출 시
> `include_past_sessions` 파라미터로 제어한다.

---

### Phase 3 — Agent 세션 연동

#### 2-4. `conversation/core/agent.py` 수정

현재 `Agent`는 초기화 시 세션 1개를 고정 생성한다. `SessionManager`에서 받은 `SessionState`를
주입받는 방식으로 전환한다.

```python
class Agent:
    def __init__(self, char_id: str, session_state: SessionState, ...): ...

    @classmethod
    def from_session(cls, session: SessionState, config: dict) -> "Agent":
        """SessionState로부터 Agent 인스턴스를 구성하는 팩토리 메서드"""
```

#### 2-5. `conversation/core/router.py` 수정

- `handle_turn()` 내 `long_term.query()` 호출 시 `session_id` 전달
- play_log 쓰기는 router가 아닌 호출자(bridge.py / main.py)에서 담당

---

### Phase 4 — bridge.py 세션 슬롯 연동

#### 2-6. `ui_ux/bridge.py` 수정

```python
class Bridge(QObject):
    # 현재: self._agent (단일)
    # 변경: SessionManager를 통해 활성 세션의 Agent를 동적으로 참조

    def changeCharacter(self, char_id: str):
        """캐릭터 전환 → SessionManager.activate(char_id) → Agent 교체"""

    def newSession(self, keep_memory: bool = False):
        """새 세션 시작 → SessionManager.new_session() → Agent 재생성"""

    def listSessions(self, char_id: str) -> str:
        """세션 목록 JSON 반환 (UI 표시용)"""
```

---

### Phase 5 — UI 세션 관리

#### 2-7. `ui_ux/qml/SettingsPanel.qml` 확장

커스터마이징 섹션 아래에 **세션 관리** 섹션을 추가한다.

```
──────────────────────────
세션 관리
  새 대화 시작 (기억 초기화)
  새 대화 시작 (기억 유지)
──────────────────────────
```

- "기억 초기화"는 확인 다이얼로그 후 `bridge.newSession(keep_memory=false)` 호출
- "기억 유지"는 `bridge.newSession(keep_memory=true)` 호출

---

### Phase 6 — play_log 배포 분리

play_log 수집 코드(`ConversationLogger`)는 이미 `training/log/conversation_logger.py`에
구현되어 있으며 CLI(`conversation/main.py`)에서 동작 중이다.

#### 2-8. `config.py` 플래그 (구현 완료)

```python
"enable_play_log": True,   # dev 환경
"enable_play_log": False,  # deploy / ui_test 환경
```

#### 2-9. `bridge.py` — UI 모드 로거 연결 (구현 완료)

`ChatBridge.__init__()`에서 `enable_play_log=True`일 때 `ConversationLogger`를 초기화하고,
`_on_response()` 콜백에서 `conv_logger.on_turn()`을 호출한다.

```
training/log/{category}/{session_id}.jsonl
  category: daily | emotion | advice | memory | persona | feedback_pos | feedback_neg
  저장 주체: ConversationLogger (CLI) / ChatBridge._on_response() (UI)
```

배포 환경에서는 `enable_play_log=False`이므로 `ConversationLogger`가 초기화되지 않아
`training/` 경로 전체가 불필요하다.

---

## 3. 마이그레이션 전략

현재 `{char_id}_memory`에는 `session_id` 메타데이터가 이미 존재한다.
기존 데이터는 마이그레이션 없이 그대로 사용 가능하다.

| 항목 | 현재 상태 | 마이그레이션 필요 여부 |
|---|---|---|
| `{char_id}_memory` session_id 필드 | 이미 존재 | 불필요 |
| `world_knowledge` | 변경 없음 | 불필요 |
| `data/sessions/` 디렉토리 | 없음 | Phase 1에서 신규 생성 |
| `active.json` | 없음 | Phase 4 연동 시 자동 생성 |

기존에 `session_id`가 없는 레거시 기억 항목은 `session_id = "legacy"`로 간주하고
새 세션 초기화 시 삭제 대상에서 제외한다.

---

## 4. 구현 우선순위

| 단계 | 항목 | 우선순위 |
|---|---|---|
| Phase 1 | SessionManager + 상태 파일 구조 | 높음 |
| Phase 2 | LongTermMemory.clear_session() | 높음 |
| Phase 4 | bridge.py 세션 슬롯 | 높음 |
| Phase 3 | Agent 세션 주입 | 중간 |
| Phase 5 | UI 세션 관리 섹션 | 중간 |
| Phase 6 | play_log 분리 | 낮음 (배포 전까지) |

Phase 1 → 2 → 4 순서로 먼저 구현하면 세션 전환·초기화의 핵심 기능이 동작하게 된다.
이후 Phase 3로 Agent 주입 방식을 정리하고, Phase 5로 UI를 노출한다.
Phase 6은 배포 준비 단계에서 처리한다.
