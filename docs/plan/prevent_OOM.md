# prevent_OOM.md — RAM 사용량 절감 계획

> 작성일: 2026-04-06  
> 대상 버전: dev 브랜치 (현재 진행 중)  
> 연관 문서: `docs/BUG/BUG_02.md`

---

## 1. 피드백 및 실현 방안

### 1-1. 웹 검색 기능 삭제

**요청 의도**: `duckduckgo-search` 라이브러리와 네트워크 I/O를 제거해 RAM 점유를 줄임.

**실현 가능 여부**: ✅ 가능. 단, 삭제 범위가 코드 + 테스트 + 문서까지 걸쳐 있어 주의가 필요함.

**예상 절감 효과**:
- `duckduckgo-search` 라이브러리 import 해제 → Python 모듈 캐시 메모리 소폭 감소
- 웹 검색 실행 시 발생하는 네트워크 I/O 버퍼 + HTML 파싱 peak 메모리 완전 제거
- 절대적인 숫자는 수십 MB 수준이지만, 현재 VRAM 여유(~977 MB)가 빡빡한 환경에서는 의미 있는 안전 마진

**삭제 범위**:

| 파일 | 삭제 내용 |
|---|---|
| `agent/core.py` | `WebSearchTool` import, `_KEYWORDS` 항목, `_tools` 등록, `_OP_LABELS` 항목 |
| `ui_ux/bridge.py` | `_HELP_TEXT["web_search"]` |
| `ui_ux/qml/main.qml` | 태그 pill, helpKeys 배열, placeholder 딕셔너리 |
| `tests/test_function_tools.py` | `TestWebSearchTool`, `TestWebSearchHyperlink` 클래스 전체 |
| `tests/test_integration_flows.py` | 웹 검색 관련 테스트 클래스 전체 |
| `tests/test_bridge_slots.py` | `getHelpText("web_search")` 단언 제거 |

**`tools/search/web_search.py` 파일 자체**: 참조 코드를 전부 제거하면 사실상 고아 파일이 됨.  
삭제 여부는 아래 두 가지 방향이 가능함:

- **A안 (권장)**: 파일 삭제. 필요 시 git 히스토리에서 복원 가능.
- **B안**: 파일 유지. 향후 SearXNG 셀프호스팅 전환을 고려하는 경우.

> 현 시점에서 A안을 권장. 코드베이스 경량화가 목적이므로 참조 없는 파일을 남기는 것은 노이즈.

---

### 1-2. DB 관리 UI를 접힌 메뉴바로 이동

**요청 의도**: 기존 타이틀바의 "DB" 버튼을 없애고, ≡ 버튼을 통해 열리는 사이드 메뉴 안에 "DB 조회 및 관리" 항목을 만듦.

**실현 가능 여부**: ✅ 가능. 현재 ≡ 버튼은 `SettingsPanel`을 직접 열고 있어 단순히 중간 레이어(사이드 메뉴)를 삽입하면 됨.

**설계 방향**:

```
≡ 버튼 클릭
  └─ SideMenuPanel 슬라이드인 (오른쪽, 220px)
       ├─ [DB] ▸ 펼침
       │      └─ DB 조회 및 관리 → MemoryDBPanel 열기
       ├─ [설정] → 기존 SettingsPanel
       └─ [관리] → 기존 AdminPanel
```

**기존 ≡ 버튼**: 설정 패널을 즉시 열었음 → SideMenuPanel을 먼저 열고, 설정은 SideMenuPanel 내부 항목으로 이동.  
**DB 버튼**: 타이틀바에서 제거. 동일한 기능이 사이드 메뉴에서 제공됨.

---

### 1-3. ChromaDB CRUD (조회·추가·수정·삭제)

**요청 의도**: DB 뷰어가 현재 읽기 전용(get_all + query_preview)이므로, 사용자가 항목을 직접 추가·수정·삭제할 수 있게 함.

**실현 가능 여부**: ✅ 가능. ChromaDB API 자체는 `upsert` / `delete` 지원. `long_term.py`에 세 메서드를 추가하면 됨.

**각 작업별 구현 방향**:

| 작업 | 구현 방법 | 주의사항 |
|---|---|---|
| 조회 | 기존 `get_all()` 유지, 카드 레이아웃으로 표시 방식만 변경 | — |
| 추가 | `col.upsert()` + 신규 `uuid` 기반 ID 생성 | 임베딩은 내용 기반 자동 생성 |
| 수정 | `col.upsert()` (동일 ID로 덮어씀) | ID 유지 필수 — upsert가 replace 동작 |
| 삭제 | `col.delete(ids=[entry_id])` | 해당 캐릭터 컬렉션에서만 삭제 |

**실시간 반영**: `bridge.py`에 `memoryChanged = Signal()`을 추가. CRUD 슬롯이 성공하면 이 시그널을 emit → QML에서 자동으로 `getMemoryDB()` 재호출.

---

### 1-4. 프롬프트 지식을 DB에 직접 입력

**요청 의도**: 프롬프트 변환기가 사용하는 가이드 지식을 사용자가 직접 DB에 입력할 수 있게 함.

**실현 가능 여부**: ✅ 가능. DB 추가 폼에 "태그" 필드에 `"prompt_guide"` 같은 태그를 입력하면 `PromptConverterTool`의 ChromaDB 검색 쿼리에 걸림.

**현재 흐름 (변경 없음)**:

```
사용자 입력 → PromptConverterTool._collect_guide()
  → long_term.query(text, char_id)
  → ChromaDB에서 tags="prompt_guide" 포함 항목 검색
```

**필요한 작업**: `MemoryDBPanel` 추가 폼에 태그 입력 필드만 있으면 별도 구현 없이 동작함.  
단, 이 부분은 이번 작업에서 UI만 제공하고, 실제 prompt_guide 태그 연동은 추후 확인 후 진행.

---

### 1-5. 전체 RAM 절감 기대치 (누적)

| 작업 | 절감 방식 | 예상 효과 |
|---|---|---|
| BUG-02-A (캐릭터 전환 이중 LLM) | 순차 언로드 | OOM 방지 (피크 12 GB → 6 GB) |
| BUG-02-B2 (int4 NF4 양자화) | 4-bit 추론 | VRAM ~355 MB 절감 |
| BUG-02-C (나레이터 제거) | LLM 호출 1회 감소 | VRAM 연산 peak 감소 |
| **이번: 웹 검색 삭제** | 라이브러리 + I/O 제거 | RAM ~수십 MB 절감 |
| **이번: DB CRUD UI** | 추가 LLM 호출 없음 | 영향 없음 (순수 UI) |

---

## 2. 구현 계획

### Step 1 — 웹 검색 제거

**수정 파일**: `agent/core.py`, `ui_ux/bridge.py`, `ui_ux/qml/main.qml`  
**삭제 파일**: `tools/search/web_search.py`  
**테스트 수정**: `tests/test_function_tools.py`, `tests/test_integration_flows.py`, `tests/test_bridge_slots.py`

#### agent/core.py
```python
# 삭제
from tools.search.web_search import WebSearchTool

# _KEYWORDS에서 삭제
(("인터넷", "웹 검색", "web", "구글", "검색해줘", "찾아봐"), "web_search"),

# stub 모드 _tools에서 삭제
self._tools[WebSearchTool.name] = WebSearchTool()

# 정상 모드 _tools에서 삭제
self._tools[WebSearchTool.name] = WebSearchTool()

# _OP_LABELS에서 삭제
"web_search": "웹 검색",
```

#### ui_ux/bridge.py
```python
# _HELP_TEXT에서 삭제
"web_search": "#웹 검색 — DuckDuckGo 인터넷 검색 ...",
```

#### ui_ux/qml/main.qml
```qml
// 태그 pill 목록에서 삭제
{ key: "web_search", label: "#웹 검색", color: "#8A4A7A" },

// helpKeys 배열에서 삭제 (line ~781)
"web_search"

// placeholder 딕셔너리에서 삭제 (line ~934)
"web_search": "검색할 내용을 입력하세요...",
```

#### 테스트 수정
- `test_function_tools.py`: `TestWebSearchTool`, `TestWebSearchHyperlink` 두 클래스 전체 삭제
- `test_integration_flows.py`: 웹 검색 관련 테스트 클래스 전체 삭제
- `test_bridge_slots.py`: `getHelpText("web_search")` 단언 삭제

---

### Step 2 — long_term.py CRUD 메서드 추가

**수정 파일**: `memory/long_term.py`

```python
def delete_entry(self, character_id: str, entry_id: str) -> bool:
    """항목 하나를 ID로 삭제한다. 성공 시 True."""

def add_entry(self, character_id: str, content: str, metadata: dict) -> str:
    """새 항목을 추가하고 생성된 ID를 반환한다.
    ID는 uuid4 기반 자동 생성.
    metadata 필수 키: importance(float), tags(list[str]), location(str)
    """

def update_entry(self, character_id: str, entry_id: str,
                 new_content: str, new_metadata: dict) -> bool:
    """기존 항목을 동일 ID로 덮어쓴다 (upsert). 성공 시 True."""
```

**ID 생성 방식** (`add_entry`):
```python
import uuid
entry_id = f"mem_{character_id.lower()}_{uuid.uuid4().hex[:8]}"
```

---

### Step 3 — bridge.py 수정

**수정 파일**: `ui_ux/bridge.py`

#### 추가할 Signal
```python
memoryChanged = Signal()   # CRUD 성공 시 emit → QML에서 자동 갱신
```

#### 추가할 Slot 3개
```python
@Slot(str, result=bool)
def deleteMemoryEntry(self, entry_id: str) -> bool:
    """항목 삭제. 성공하면 memoryChanged emit."""

@Slot(str, str, result=str)
def addMemoryEntry(self, content: str, meta_json: str) -> str:
    """항목 추가. 성공하면 memoryChanged emit. 반환: 생성된 entry_id."""

@Slot(str, str, str, result=bool)
def updateMemoryEntry(self, entry_id: str, new_content: str, meta_json: str) -> bool:
    """항목 수정. 성공하면 memoryChanged emit."""
```

**meta_json 형식** (QML → Python):
```json
{
    "importance": 0.8,
    "tags": ["이름", "취미"],
    "location": "카페",
    "session_id": "manual"
}
```

---

### Step 4 — SideMenuPanel.qml 생성

**신규 파일**: `ui_ux/qml/SideMenuPanel.qml`

**레이아웃**:
```
오른쪽 슬라이드인 패널 (너비 220px)
─────────────────────────────
  × 닫기
─────────────────────────────
  ▾ DB
      · DB 조회 및 관리
─────────────────────────────
  ▾ 설정
      · 설정 열기
─────────────────────────────
  ▾ 관리
      · 관리자 패널
─────────────────────────────
```

**Signal**:
```qml
signal openMemoryDB()
signal openSettings()
signal openAdmin()
signal closeRequested()
```

---

### Step 5 — MemoryDBPanel.qml 재설계

**수정 파일**: `ui_ux/qml/MemoryDBPanel.qml` (전면 재작성)

**변경 사항**:

| 항목 | 기존 | 변경 후 |
|---|---|---|
| 레이아웃 | 세션별 아코디언 | 플랫 카드 목록 (세션 구분 표시) |
| 상단 영역 | 검색바만 | 검색바 + "항목 추가" 폼 토글 |
| 카드 내용 | 텍스트만 | 내용·중요도·태그·위치·타임스탬프 |
| 카드 액션 | 없음 | 수정(✏) / 삭제(🗑) 버튼 |
| 수정 방식 | 없음 | 카드 인라인 편집 폼 |

**Signal**:
```qml
signal deleteRequested(string entryId)
signal addRequested(string content, string metaJson)
signal updateRequested(string entryId, string newContent, string metaJson)
```

**추가 폼 필드**:
- 내용 (TextArea, 3줄)
- 중요도 (Slider 0.0~1.0)
- 태그 (TextField, 쉼표 구분)
- 위치 (TextField)

---

### Step 6 — main.qml 수정

**수정 파일**: `ui_ux/qml/main.qml`

#### 추가할 property
```qml
property bool sideMenuOpen: false
```

#### 제거
- DB 버튼 블록 전체 (lines 522~541)

#### 변경: ≡ 버튼 동작
```qml
// 기존: 설정 패널 직접 열기
onClicked: {
    root.charListJson  = bridge.getCharacterList()
    root.worldListJson = bridge.getWorldList()
    root.settingsOpen  = true
}

// 변경: 사이드 메뉴 열기
onClicked: {
    root.sideMenuOpen = true
}
```

#### SideMenuPanel 인스턴스 추가
```qml
SideMenuPanel {
    anchors.fill: parent
    visible: root.sideMenuOpen && !root.isBubble
    z: 23
    fontFamily: koreanFont.font.family
    onCloseRequested: root.sideMenuOpen = false
    onOpenMemoryDB: {
        root.memoryDbJson = bridge.getMemoryDB()
        root.memoryDbOpen = true
        root.sideMenuOpen = false
    }
    onOpenSettings: {
        root.charListJson  = bridge.getCharacterList()
        root.worldListJson = bridge.getWorldList()
        root.settingsOpen  = true
        root.sideMenuOpen  = false
    }
    onOpenAdmin: {
        root.adminConvJson  = bridge.getConvParams()
        root.adminPanelOpen = true
        root.sideMenuOpen   = false
    }
}
```

#### MemoryDBPanel CRUD 신호 연결
```qml
MemoryDBPanel {
    ...
    onDeleteRequested: function(entryId) {
        bridge.deleteMemoryEntry(entryId)
    }
    onAddRequested: function(content, metaJson) {
        bridge.addMemoryEntry(content, metaJson)
    }
    onUpdateRequested: function(entryId, newContent, metaJson) {
        bridge.updateMemoryEntry(entryId, newContent, metaJson)
    }
}
```

#### bridge.memoryChanged 연결
```qml
Connections {
    target: bridge
    function onMemoryChanged() {
        if (root.memoryDbOpen) {
            root.memoryDbJson = bridge.getMemoryDB()
        }
    }
}
```

---

### Step 7 — qmldir 업데이트

**수정 파일**: `ui_ux/qml/qmldir`

```
SideMenuPanel 1.0 SideMenuPanel.qml
```

---

## 3. 검증 계획

| 항목 | 방법 |
|---|---|
| 웹 검색 제거 | `uv run pytest tests/` — web_search 관련 import 오류 없는지 확인 |
| CRUD 동작 | MemoryDBPanel에서 항목 추가 → DB 뷰어 즉시 갱신 확인 |
| 사이드 메뉴 | ≡ 클릭 → SideMenuPanel 열림, DB 클릭 → MemoryDBPanel 전환 확인 |
| RAM 절감 | `uv run python main.py` 실행 후 `htop`으로 RSS 비교 |
| 테스트 전체 | `uv run pytest tests/ -v` 모두 통과 |

---

## 4. 파일 목록 요약

| 파일 | 작업 |
|---|---|
| `agent/core.py` | 웹 검색 import/등록/레이블 제거 |
| `ui_ux/bridge.py` | `_HELP_TEXT` 항목 제거, `memoryChanged` 시그널 + CRUD 슬롯 3개 추가 |
| `ui_ux/qml/main.qml` | DB 버튼 제거, ≡ 버튼 변경, SideMenuPanel 추가, CRUD 신호 연결 |
| `ui_ux/qml/SideMenuPanel.qml` | **신규** — 사이드 내비게이션 패널 |
| `ui_ux/qml/MemoryDBPanel.qml` | 전면 재작성 — 카드 레이아웃 + CRUD |
| `ui_ux/qml/qmldir` | SideMenuPanel 등록 |
| `memory/long_term.py` | CRUD 메서드 3개 추가 |
| `tools/search/web_search.py` | **삭제** |
| `tests/test_function_tools.py` | `TestWebSearchTool`, `TestWebSearchHyperlink` 제거 |
| `tests/test_integration_flows.py` | 웹 검색 테스트 클래스 제거 |
| `tests/test_bridge_slots.py` | `web_search` 관련 단언 제거 |
