# UI 설계 문서

> 대상 환경: Windows CPU 배포 (PySide6 + QML)
> 현재 구현 기준: `ui_ux/qml/main.qml`, `ui_ux/bridge.py`

---

## 1. 모드 구조

```
[풀 창 모드] ──(주황 버튼)──▶ [PIP 마스코트 모드]
[PIP 모드]   ──(주황 버튼)──▶ [풀 창 모드]
```

---

## 2. 풀 창 모드

> 기존 창 모드 확장. 크기: 360×520

### 레이아웃

```
┌─────────────────────────────┐
│ 하루          [≡] [●] [✕]  │  ← ≡: 설정 패널, ●: PIP 전환(주황), ✕: 종료
├─────────────────────────────┤
│ [대화]  [기능]               │
├─────────────────────────────┤
│                             │
│   (act별 배경 이미지)        │
│   말풍선들...                │
│                             │
├─────────────────────────────┤
│ [입력창______________] [▶]  │
└─────────────────────────────┘
```

### 배경 이미지

- **표시 조건**: 현재 act의 `location` 값과 일치하는 이미지 파일이 존재할 때만 표시. 파일이 없으면 다크 배경 유지.
- **이미지 경로**: `ui_ux/assets/background/{world_id}/{location}.png`
  - `{location}`: YAML act의 `location` 필드값 (예: `beach`, `breakwater`)
  - 같은 장소를 배경으로 하는 여러 act는 동일한 이미지를 공유함
- act 변경 시 `backgroundChanged(url)` 시그널로 QML에 전달 (파일 없으면 빈 문자열)

> **⚠️ 구현 주의**: `ConversationSession`은 `act_id`만 저장하고 `location`은 저장하지 않음.
> `bridge.py::_build_bg_url()`이 현재 `act_id`를 파일명으로 사용하고 있으므로,
> `location` 기준으로 동작하려면 world YAML에서 act_id → location을 역참조하는 로직이 필요함.

> **현재 에셋 상태**: `background/Robby.png` (seaside_world 바닷가 마을 배경)는
> `background/seaside_world/{location}.png` 경로로 이동/복사해야 반영됨.

### 설정 패널 (≡ 버튼 → 슬라이드인)

- **캐릭터 변경**: `conversation/character/` 내 YAML 목록 표시 → 선택 시 핫스왑
- **세계관 / 시나리오 선택**: `conversation/world/` 내 YAML 목록 표시 → act 선택 포함
- **커스터마이징**: 캐릭터 파츠 구성 설정 (섹션 4 참조)

---

## 3. PIP 마스코트 모드

> 50×50 플로팅 아이콘. 화면 위에 항상 표시.

### 평상시

```
┌────┐
│ 🎭 │  ← 50×50, 캐릭터 아이콘 (icons/{id}/{id}.png) + 감정 오버레이
└────┘
```

### 말풍선 표시 조건

1. 사용자가 아이콘을 클릭할 때
2. 캐릭터(assistant)가 응답을 보낼 때

### 말풍선 표시 상태

```
┌──────────────────────────┐
│ 그랬구나...               │  ← 최신 메시지 표시
│ ─────────────────────────│
│ [입력...]        [▶] [●] │  ← ▶: 전송, ●: 풀 창 복귀(주황)
└──────────────────────────┘
┌────┐
│ 🎭 │
└────┘
```

- 말풍선 위치: 아이콘 기준 위쪽 (위로 확장)
- 입력 후 전송 시 말풍선 유지하며 대화 지속
- 일정 시간(기본 5초) 입력 없으면 말풍선 자동 닫힘

---

## 4. 캐릭터 커스터마이징

### 풀 창에서의 캐릭터 표시 위치

SD 캐릭터가 입력창 테두리에 걸쳐서 상반신이 채팅 영역으로 삐져나오는 형태.
QML에서 `z` 값 + `clip: false`로 구현.

```
│  말풍선들...                     │
│  ┌─────┐                         │
│  │ SD  │  ← 상반신이 채팅 영역으로 삐져나옴
├──┤ 캐릭 ├────────────────────────┤
│  └─────┘  [입력창________] [▶]  │  ← 하반신은 입력창 테두리에 가려짐
└─────────────────────────────────┘
```

---

### 캐릭터 캔버스 규격

- **전체 캔버스**: `128 × 160 px` (투명 PNG)
- **머리 영역**: 상단 `128 × 80 px` (전체의 상반부)
- **몸통 영역**: 하단 `128 × 80 px` (전체의 하반부)
- 입력창 위로 노출되는 영역: 머리 영역 기준 약 `80 px` (상반신)
- 모든 파츠는 동일한 `128 × 160 px` 캔버스 기준으로 제작 (투명 배경)

---

### 아이콘 구성 (캐릭터당 기본 에셋)

캐릭터 하나는 아래 이미지 세트로 구성된다. 개발자가 기본 제공하며, **사용자도 직접 등록 가능**.

| 파일 | 내용 | 규격 |
|---|---|---|
| `{CharId}.png` | 전신샷 기본 아이콘 | `128 × 160 px` |
| `emotion/neutral.png` | 감정 오버레이 — 무표정 | `128 × 160 px` (머리 영역 기준) |
| `emotion/happy.png` | 감정 오버레이 — 기쁨 | 동일 |
| `emotion/affectionate.png` | 감정 오버레이 — 애정 | 동일 |
| `emotion/touched.png` | 감정 오버레이 — 감동 | 동일 |
| `emotion/curious.png` | 감정 오버레이 — 호기심 | 동일 |
| `emotion/sad.png` | 감정 오버레이 — 슬픔 | 동일 |
| `emotion/embarrassed.png` | 감정 오버레이 — 당황 | 동일 |
| `emotion/annoyed.png` | 감정 오버레이 — 짜증 | 동일 |
| `emotion/angry.png` | 감정 오버레이 — 분노 | 동일 |

> 감정 오버레이는 전신 이미지(`{CharId}.png`) 위에 얼굴 레이어로 얹히는 구조.
> 개발자가 기본 에셋을 제공할 예정이며, 사용자가 직접 이미지를 등록해 교체하는 것도 가능.
> 파일이 없으면 오버레이 없이 기본 아이콘만 표시.

---

### 레이어 합성 구조

아래 순서대로 위에 쌓임 (숫자 높을수록 앞에 표시).

| 순서 | 레이어 | 경로 | 제공 방식 |
|---|---|---|---|
| 7 | 감정 오버레이 | `icons/{CharId}/emotion/{mood}.png` | 개발자 기본 제공 / 🧑 사용자 교체 가능 |
| 6 | 입 | `characters/mouth/*.png` | 개발자 제공 / 🧑 사용자 선택 |
| 5 | 눈 | `characters/eye/*.png` | 개발자 제공 / 🧑 사용자 선택 |
| 4 | 헤어 | `characters/hair/*.png` | 개발자 제공 / 🧑 사용자 선택 |
| 3 | 의상 | `characters/cloth/*.png` | 개발자 제공 / 🧑 사용자 선택 |
| 2 | 베이스 (얼굴+몸통) | `characters/base/*.png` | 개발자 제공 / 🧑 사용자 선택 |
| 1 | 기본 아이콘 | `icons/{CharId}/{CharId}.png` | 개발자 기본 제공 / 🧑 사용자 등록 가능 |

> **레이어 우선순위**: 기본 아이콘(`icons/{id}/{id}.png`)이 로드되면 레이어 2~6(파츠 합성)은 건너뛰고 아이콘 위에 감정 오버레이(레이어 7)만 얹힘.
> 기본 아이콘이 없으면 파츠 레이어 2~6을 순서대로 합성하고 감정 오버레이를 얹음.
> **파츠 커스터마이징은 아이콘이 있어도 없어도 사용 가능하지만, 아이콘이 있는 경우 파츠는 무시됨.**

---

### 파츠 선택 — 커스터마이징 UI

- **CustomizationPanel**: 전체 오버레이 모달 (z:20)
- 파츠 5종(base/hair/eye/mouth/cloth) 가로 스크롤 선택 버튼 (재클릭 시 선택 해제)
- 저장 시 `saved(partsJson)` 시그널 emit
- 파츠 선택 저장 경로: `ui_ux/assets/icons/{CharId}/parts.json`

```json
{
  "base":  "base_01.png",
  "hair":  "hair_02.png",
  "eye":   "eye_03.png",
  "mouth": "mouth_01.png",
  "cloth": "cloth_02.png"
}
```
> 해당 파츠를 선택하지 않으면 키 자체가 없음 (null 아님).

---

### 감정 오버레이

mood 상태는 `agent/state.py::update_mood()`가 **사용자 입력 키워드**와 캐릭터 YAML의 `mood_triggers`를 매칭해 결정한다. 매 턴 LLM 응답 생성 후 자동 갱신.

| mood | 한국어 | 트리거 키워드 예시 (CH_Haru 기준) |
|---|---|---|
| `neutral` | 무표정 | (기본값 — 매칭 없을 때) |
| `happy` | 기쁨 | 좋아, 재밌어, 웃겨, 기뻐, 행복해 |
| `affectionate` | 애정 | 좋아해, 보고 싶어, 곁에 있어줘 |
| `touched` | 감동 | 고마워, 감동, 울컥, 따뜻하다 |
| `curious` | 호기심 | 궁금해, 어떻게 생각해, 왜 그래, 알려줘 |
| `sad` | 슬픔 | 슬퍼, 힘들어, 외로워, 우울해, 눈물 |
| `embarrassed` | 당황 | 당황, 어색해, 갑자기 왜, 부끄 |
| `annoyed` | 짜증 | 짜증, 싫어, 그만해, 됐어 |
| `angry` | 분노 | 화났어, 열받아, 진짜 왜, 미치겠다 |

- 캔버스 규격: `128 × 160 px` 투명 PNG (머리 영역에 표정 이미지 배치)
- 경로: `ui_ux/assets/icons/{CharId}/emotion/{mood}.png`
- 개발자가 캐릭터별 기본 에셋을 배치하며, 사용자도 직접 이미지를 등록해 교체 가능.
- 파일이 없으면 오버레이 없이 기본 아이콘/파츠만 표시 (에러 없이 생략).
- mood 변경은 affection 수치 변동도 연쇄 트리거함 (`update_affection()`).

---

## 5. Bridge 변경사항

### Signal (Python → QML)

| 시그널 | 인자 | 용도 |
|---|---|---|
| `messageAdded` | `role: str, content: str` | 새 메시지 추가 |
| `statusChanged` | `status: str` | `"thinking"` \| `"ready"` |
| `characterNameChanged` | `name: str` | 캐릭터 이름 변경 |
| `backgroundChanged` | `url: str` | act 변경 시 배경 이미지 file URL (장소 이미지 없으면 `""`) |
| `moodChanged` | `mood: str` | mood 변경 시 감정 상태 문자열 |

### Property (Python → QML)

| 프로퍼티 | 타입 | 용도 |
|---|---|---|
| `characterName` | `str` | 현재 캐릭터 이름 |
| `characterId` | `str` | 현재 캐릭터 ID (폴더명 기준) |
| `currentBackground` | `str` | 현재 배경 이미지 file URL |
| `currentMood` | `str` | 현재 mood 문자열 |

### Slot (QML → Python)

| 슬롯 | 인자 | 반환 | 용도 |
|---|---|---|---|
| `sendMessage` | `text: str` | — | 사용자 메시지 전송 |
| `snapToEdge` | `x, y, w, h: int` | `list[int]` | PIP 모서리 스냅 좌표 계산 |
| `getCharacterList` | — | `str` (JSON) | `[{id, name}, ...]` 목록 |
| `getWorldList` | — | `str` (JSON) | `[{world_id, description, scenarios}, ...]` 목록 |
| `changeCharacter` | `char_id: str` | — | 캐릭터 핫스왑 |
| `changeWorld` | `world_id, scenario_id, act_id: str` | — | 세계관 / act 전환 → `_build_bg_url()`이 location 역참조 후 배경 갱신 |
| `loadCustomization` | — | `str` (JSON) | `{parts, icon_url, char_id}` 반환 |
| `saveCustomization` | `json_data: str` | — | `{parts}` → `icons/{char_id}/parts.json` 저장 |
| `getAllPartsList` | — | `str` (JSON) | `{base, hair, eye, mouth, cloth}` 파일 목록 |

---

## 6. 에셋 디렉토리 구조

> 🧑 = 사용자 커스터마이징 결과가 저장되는 경로
> 그 외 = 개발자가 사전 제작하여 제공

```
ui_ux/assets/
├─ background/                       ← 개발자 제공, 장소별 배경 이미지
│   └─ {world_id}/
│       └─ {location}.png           ← YAML act의 location 필드값이 파일명
│                                      (없으면 다크 배경 유지)
│
│   예시 (seaside_world):
│       background/seaside_world/beach.png       ← act_1 (location: beach)
│       background/seaside_world/breakwater.png  ← act_2 (location: breakwater)
│
├─ characters/                       ← 개발자 제공 파츠 풀 (128×160 px PNG)
│   ├─ base/
│   │   └─ base_01.png, ...
│   ├─ hair/
│   ├─ eye/
│   ├─ mouth/
│   └─ cloth/
│
└─ icons/                            ← 캐릭터별 완성 이미지 + 감정 오버레이
    └─ {CharId}/
        ├─ {CharId}.png             ← 완성된 캐릭터 기본 아이콘 (개발자/사용자 제공)
        ├─ parts.json               ← 🧑 사용자 파츠 선택 저장 (커스터마이징 결과)
        └─ emotion/
            ├─ neutral.png          ← 개발자 기본 제공 / 🧑 사용자 교체 가능 (현재 비어있음)
            ├─ happy.png
            ├─ affectionate.png
            ├─ touched.png
            ├─ curious.png
            ├─ sad.png
            ├─ embarrassed.png
            ├─ annoyed.png
            └─ angry.png
```

> ⚠️ 설계 초안 대비 변경사항:
> - `backgrounds/` → `background/` (단수형)
> - `characters/parts/{8타입}/` → `characters/{5타입}/` (`parts/` 중간 디렉토리 없음)
> - `characters/custom/` 경로 제거 → 사용자 커스터마이징 결과는 `icons/{CharId}/parts.json`에 저장
> - `effects/{mood}/overlay.png` 경로 제거 → 감정 오버레이는 `icons/{CharId}/emotion/{mood}.png`

---

## 7. 신규 QML 파일 목록

| 파일 | 역할 |
|---|---|
| `ui_ux/qml/PipWindow.qml` | PIP 마스코트 모드 (아이콘 + 말풍선) |
| `ui_ux/qml/SettingsPanel.qml` | 슬라이드인 설정 패널 |
| `ui_ux/qml/CustomizationPanel.qml` | 커스터마이징 편집 UI (파츠 선택) |
| `ui_ux/qml/CharacterDisplay.qml` | 레이어 합성 캐릭터 표시 컴포넌트 |

---

## 8. 구현 순서

```
1단계 — 배경 이미지 연동 ✅ 완료 (2026-03-19)
  - backgroundChanged / moodChanged 시그널 + Property 추가 (bridge.py)
  - main.qml 채팅 영역을 Item으로 감싸고 배경 Image 레이어 추가
  - _sync_state()로 응답 후 act/mood 변화 감지 → 시그널 emit
  - ruff exclude에 **/*.qml 추가 (pyproject.toml)

  구현 파일:
    ui_ux/bridge.py        — backgroundChanged, moodChanged 시그널 / currentBackground, currentMood Property / _sync_state()
    ui_ux/qml/main.qml     — backgroundImageUrl, currentMood 프로퍼티 / Image 레이어 (opacity 0.35, PreserveAspectCrop)
    pyproject.toml         — ruff exclude에 **/*.qml 추가

  에셋 배치 경로 (이미지 준비되면 넣으면 바로 반영):
    ui_ux/assets/background/{world_id}/{act_id}.png

2단계 — PIP 마스코트 모드 ✅ 완료 (2026-03-20)
  - PipWindow.qml 신규 구현
      · 50×50 캐릭터 아이콘 (characterId 기반 icons/{id}/{id}.png + 감정 오버레이)
      · 에셋 없으면 mood별 이모지 플레이스홀더
      · 말풍선: 메시지 4줄 + 입력창 + 전송 버튼 + 풀창복귀(주황) 버튼 + 꼬리 삼각형
      · 5초 자동 닫힘 타이머
      · 클릭으로 말풍선 토글 / assistant 응답 시 자동 표시
  - main.qml 변경
      · isBubble 크기: 50×50 (말풍선 시 240×190으로 동적 확장)
      · y + height 동시 NumberAnimation (yAnim/heightAnim) — Behavior 단독 사용 시 아이콘 들뜨는 버그 수정
      · bubbleOpen 바인딩 루프 제거: onPipBubbleOpenChanged에서 단방향 동기화
      · inputReady 프로퍼티 도입 (풀창/PIP 공유)
      · 컨테이너 color transparent + clip false (PIP 투명 배경)
  - qmldir에 PipWindow 1.0 등록

  구현 파일:
    ui_ux/qml/PipWindow.qml   — PIP 마스코트 컴포넌트 (신규)
    ui_ux/qml/main.qml        — PIP 모드 통합, 크기/위치 로직, 바인딩 루프 수정
    ui_ux/qml/qmldir          — PipWindow 등록

  테스트 체크리스트:
    docs/plan/UI_테스트.md     — 1단계 + 2단계 항목 포함

3단계 — 설정 패널 ✅ 완료 (2026-03-20)
  - SettingsPanel.qml 신규 구현
      · 오른쪽 슬라이드인 오버레이 (z:10, 딤 배경 클릭으로 닫기)
      · 캐릭터 섹션: getCharacterList() 결과로 버튼 목록 → 클릭 시 changeCharacter
      · 시나리오 섹션: getWorldList() 결과를 flat 배열로 가공 → act 버튼 → 클릭 시 changeWorld
        (중첩 Repeater parent scope 버그 방지를 위해 flat model 사용)
      · inline component(SectionLabel, SettingsButton)로 재사용 구조
  - bridge.py 슬롯 추가
      · getCharacterList() → conversation/character/CH_*.yaml 스캔, JSON 반환
      · getWorldList()     → conversation/world/W_*.yaml 스캔, JSON 반환
      · changeWorld(world_id, scenario_id, act_id) → world/session/router 교체
  - main.qml 변경
      · settingsOpen / charListJson / worldListJson 프로퍼티 추가
      · 타이틀바에 ≡ 버튼 추가 (클릭 시 목록 갱신 후 패널 오픈)
      · SettingsPanel 인스턴스 컨테이너 안 z:10 오버레이로 배치
  - qmldir에 SettingsPanel 1.0 등록

  구현 파일:
    ui_ux/qml/SettingsPanel.qml  — 설정 패널 컴포넌트 (신규)
    ui_ux/qml/main.qml           — ≡ 버튼, SettingsPanel 연동
    ui_ux/qml/qmldir             — SettingsPanel 등록
    ui_ux/bridge.py              — getCharacterList / getWorldList / changeWorld 슬롯

4단계 — 커스터마이징 ✅ 완료 (2026-03-20)
  - CharacterDisplay.qml 신규 구현
      · characterId 기반 icons/{id}/{id}.png 로드 → 성공 시 파츠 합성 생략
      · 파츠 합성: base → cloth → hair → eye → mouth (5레이어)
      · 감정 오버레이: icons/{id}/emotion/{mood}.png (파일 없으면 생략)
      · 파츠/아이콘 모두 없을 때 mood별 이모지 플레이스홀더
  - CustomizationPanel.qml 신규 구현
      · 전체 오버레이 모달 (z:20)
      · 파츠 5종(base/hair/eye/mouth/cloth) 가로 스크롤 선택 버튼 (재클릭 시 해제)
      · 감정 효과 탭 없음 (개발자 전용 — UI에서 제외)
      · 저장 시 saved(partsJson) 시그널 emit
      · ListView delegate에서 ListView.view.outerKey / outerSelected 사용
        (delegate 내 parent scope 버그 방지)
  - bridge.py 슬롯 추가
      · loadCustomization()     → {parts, icon_url, char_id} JSON 반환
                                   저장 경로: icons/{char_id}/parts.json
      · saveCustomization(json) → {parts} → icons/{char_id}/parts.json 저장
      · getAllPartsList()        → {base, hair, eye, mouth, cloth} 파일 목록 반환
                                   스캔 경로: characters/{type}/*.png
      · characterId Property    → bridge.characterId로 QML에서 직접 접근 가능
  - main.qml 변경
      · customizationOpen / customPartsJson / allPartsListJson 프로퍼티
        (초안의 customEffectsJson / customBasePngUrl 제거)
      · Component.onCompleted에서 loadCustomization() 초기 로드 (bridge null 가드 포함)
      · CharacterDisplay: 채팅 영역 Item 안 z:2, bottomMargin:-40 (입력창 40px 오버랩)
        characterId: bridge ? bridge.characterId : "" 바인딩
      · PipWindow: characterId: bridge ? bridge.characterId : "" 바인딩
      · CustomizationPanel onSaved: saved(partsJson) 단일 인자로 변경
  - qmldir에 CharacterDisplay, CustomizationPanel 등록

  구현 파일:
    ui_ux/qml/CharacterDisplay.qml    — 레이어 합성 캐릭터 (신규)
    ui_ux/qml/CustomizationPanel.qml  — 커스터마이징 편집 UI (신규)
    ui_ux/qml/SettingsPanel.qml       — 커스터마이징 버튼 추가
    ui_ux/qml/main.qml                — CharacterDisplay/CustomizationPanel 연동
    ui_ux/qml/qmldir                  — 신규 컴포넌트 등록
    ui_ux/bridge.py                   — loadCustomization / saveCustomization / getAllPartsList / characterId 슬롯

  에셋 배치 경로:
    ui_ux/assets/characters/{base|hair|eye|mouth|cloth}/*.png   ← 개발자 파츠 풀
    ui_ux/assets/icons/{CharId}/{CharId}.png                    ← 완성 캐릭터 이미지
    ui_ux/assets/icons/{CharId}/emotion/{mood}.png              ← 감정 오버레이 (차후 추가)
    ui_ux/assets/background/{world_id}/{location}.png           ← 배경 이미지 (location 기반)

5단계 — 배경 이미지 location 기반 전환 ✅ 완료 (2026-03-20)
  현황:
    - bridge.py::_build_bg_url()이 session.act_id를 파일명으로 사용 중
      → background/{world_id}/{act_id}.png 탐색 (예: act_1.png)
    - 설계 기준은 location 값이 파일명 (예: beach.png, breakwater.png)
    - ConversationSession에 location 필드 없음 → YAML 역참조 필요

  구현 내용:
    - bridge.py::_build_bg_url() 수정
        · world YAML을 로드해 현재 act_id에 해당하는 location 필드 조회
        · world_load.py의 load_world() + get_act() 헬퍼 활용
        · 경로: background/{world_id}/{location}.png
        · location이 없는 act이거나 파일이 없으면 빈 문자열 반환

  구현 파일:
    ui_ux/bridge.py  — _build_bg_url() 수정 (act_id → location 역참조)

  에셋 준비 (코드 수정 후 이미지 배치):
    ui_ux/assets/background/seaside_world/beach.png       ← act_1 (location: beach)
    ui_ux/assets/background/seaside_world/breakwater.png  ← act_2 (location: breakwater)

6단계 — mood 8종 전체 대응 ✅ 완료 (2026-03-20)
  현황:
    - CharacterDisplay.qml, PipWindow.qml 이모지 플레이스홀더가 4종만 처리
      (neutral / happy / annoyed / sad)
    - 실제 mood는 8종 (neutral / happy / affectionate / touched / curious /
      sad / embarrassed / annoyed / angry)
    - session.py mood 주석도 4종으로 기재되어 있어 불일치

  구현 내용:
    - CharacterDisplay.qml 플레이스홀더 Text 블록 수정
        · affectionate → 🥰  touched → 🥹  curious → 🤔
        · embarrassed → 😳  angry → 😠
    - PipWindow.qml 플레이스홀더 Text 블록 동일하게 수정
    - session.py mood 주석 8종으로 업데이트
      neutral / happy / affectionate / touched / curious / sad / embarrassed / annoyed / angry

  구현 파일:
    ui_ux/qml/CharacterDisplay.qml  — 이모지 플레이스홀더 8종
    ui_ux/qml/PipWindow.qml         — 이모지 플레이스홀더 8종
    conversation/core/session.py    — mood 주석 정비
```
