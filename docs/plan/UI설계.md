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

- act별로 이미지가 있는 경우에만 표시, 없으면 기존 다크 배경 유지
- 이미지 경로: `ui_ux/assets/backgrounds/{world_id}/{act_id}.png`
- act 변경 시 `backgroundChanged(path)` 시그널로 QML에 전달

### 설정 패널 (≡ 버튼 → 슬라이드인)

- **캐릭터 변경**: `conversation/character/` 내 YAML 목록 표시 → 선택 시 핫스왑
- **세계관 / 시나리오 선택**: `conversation/world/` 내 YAML 목록 표시 → act 선택 포함
- **커스터마이징**: 캐릭터 외형 및 감정 효과 설정 (섹션 4 참조)

---

## 3. PIP 마스코트 모드

> 50×50 플로팅 아이콘. 화면 위에 항상 표시.

### 평상시

```
┌────┐
│ 🎭 │  ← 50×50, 커스터마이징된 캐릭터 아이콘
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

- 말풍선 위치: 아이콘 기준 위쪽 또는 왼쪽 (화면 경계 감지 후 자동 조정)
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

### 레이어 합성 구조

아래 순서대로 위에 쌓임 (숫자 높을수록 앞에 표시).

| 순서 | 레이어 | 경로 | 제공 방식 |
|---|---|---|---|
| 9 | 감정 효과 오버레이 | `effects/{mood}/overlay.png` | **개발자 제공** (기본) / 🧑 사용자 교체 가능 |
| 8 | 악세서리 | `parts/accessory/*.png` | **개발자 제공** / 🧑 사용자 선택 |
| 7 | 앞머리 | `parts/hair_front/*.png` | **개발자 제공** / 🧑 사용자 선택 |
| 6 | 옷 | `parts/outfit/*.png` | **개발자 제공** / 🧑 사용자 선택 |
| 5 | 입 | `parts/mouth/*.png` | **개발자 제공** / 🧑 사용자 선택 |
| 4 | 눈썹 | `parts/eyebrow/*.png` | **개발자 제공** / 🧑 사용자 선택 |
| 3 | 눈 | `parts/eye/*.png` | **개발자 제공** / 🧑 사용자 선택 |
| 2 | 뒷머리 | `parts/hair_back/*.png` | **개발자 제공** / 🧑 사용자 선택 |
| 1 | 얼굴형 + 몸통 베이스 | `parts/body/*.png` | **개발자 제공** / 🧑 사용자 선택 |

> 🧑 표시 항목은 커스터마이징 UI에서 사용자가 선택/교체 가능.
> 선택하지 않으면 개발자 제공 default 적용.

---

### 베이스 캐릭터 — 입력 방식 (선택)

| 방식 | 설명 | 비고 |
|---|---|---|
| 파츠 조합 | 위 레이어 목록에서 파츠별 선택 | 개발자 제공 파츠 풀 사용 |
| 🧑 PNG 직접 업로드 | 사용자가 `128 × 160 px` 이미지를 업로드 | 파츠 레이어 1~8을 단일 이미지로 대체. 감정 효과(레이어 9)는 그대로 얹힘 |

- 저장 경로: `ui_ux/assets/characters/custom/base.png`
- 파츠 선택 저장: `ui_ux/assets/characters/custom/parts.json`

```json
{
  "body":       "body_01.png",
  "hair_back":  "hair_back_02.png",
  "eye":        "eye_03.png",
  "eyebrow":    "eyebrow_01.png",
  "mouth":      "mouth_02.png",
  "outfit":     "outfit_01.png",
  "hair_front": "hair_front_02.png",
  "accessory":  null
}
```
> `null`이면 해당 파츠 생략.

---

### 감정 효과 — 입력 방식

- mood 상태: `neutral` / `happy` / `annoyed` / `sad`
- 기존 `agent/state.py`의 mood 값과 연동
- 캔버스 규격: 동일 `128 × 160 px` 투명 PNG
- 주로 머리 영역(`128 × 80 px`) 안에 표정/이펙트 배치

| 항목 | 기본값 | 사용자 입력 |
|---|---|---|
| neutral 효과 | 개발자 제공 | 🧑 `128×160 px` PNG 업로드로 교체 가능 |
| happy 효과 | 개발자 제공 | 🧑 동일 |
| annoyed 효과 | 개발자 제공 | 🧑 동일 |
| sad 효과 | 개발자 제공 | 🧑 동일 |

- 커스텀 설정 저장: `ui_ux/assets/characters/custom/effects.json`

```json
{
  "neutral": null,
  "happy":   "custom_happy.png",
  "annoyed": null,
  "sad":     null
}
```
> `null`이면 개발자 제공 default 사용.

---

## 5. Bridge 변경사항

### 추가 Signal (Python → QML)

| 시그널 | 인자 | 용도 |
|---|---|---|
| `backgroundChanged` | `path: str` | act 변경 시 배경 이미지 경로 전달 |
| `moodChanged` | `mood: str` | mood 변경 시 감정 효과 레이어 교체 |

### 추가 Slot (QML → Python)

| 슬롯 | 인자 | 반환 | 용도 |
|---|---|---|---|
| `getCharacterList` | — | `list[str]` | 사용 가능한 캐릭터 ID 목록 |
| `getWorldList` | — | `list[dict]` | 세계관 및 시나리오 목록 |
| `changeWorld` | `world_id, scenario_id` | — | 세계관 / 시나리오 전환 |
| `saveCustomization` | `json_data: str` | — | 커스터마이징 설정 저장 |
| `loadCustomization` | — | `str` | 커스터마이징 설정 불러오기 |

---

## 6. 에셋 디렉토리 구조

> 🧑 = 사용자가 직접 제공하는 파일이 저장되는 경로
> 그 외 = 개발자가 사전 제작하여 제공

```
ui_ux/assets/
├─ backgrounds/
│   └─ {world_id}/
│       └─ {act_id}.png              ← 개발자 제공, act별 배경 이미지
│                                       (없으면 다크 배경 유지)
│
├─ characters/
│   ├─ parts/                        ← 개발자 제공 파츠 풀 (128×160 px PNG)
│   │   ├─ body/
│   │   │   └─ body_01.png, ...
│   │   ├─ hair_back/
│   │   ├─ eye/
│   │   ├─ eyebrow/
│   │   ├─ mouth/
│   │   ├─ outfit/
│   │   ├─ hair_front/
│   │   └─ accessory/
│   │
│   └─ custom/                       ← 🧑 사용자 커스터마이징 저장 경로
│       ├─ base.png                  ← 🧑 PNG 직접 업로드 시 저장 (128×160 px)
│       ├─ parts.json                ← 파츠 조합 선택 저장
│       └─ effects.json             ← mood별 커스텀 효과 선택 저장
│
├─ effects/                          ← 개발자 제공 기본 감정 효과 (128×160 px PNG)
│   ├─ neutral/overlay.png
│   ├─ happy/overlay.png
│   ├─ annoyed/overlay.png
│   ├─ sad/overlay.png
│   └─ custom/                       ← 🧑 사용자가 업로드한 커스텀 효과 이미지
│       └─ *.png
│
└─ icons/                            ← 앱 아이콘
```

---

## 7. 신규 QML 파일 목록

| 파일 | 역할 |
|---|---|
| `ui_ux/qml/PipWindow.qml` | PIP 마스코트 모드 (아이콘 + 말풍선) |
| `ui_ux/qml/SettingsPanel.qml` | 슬라이드인 설정 패널 |
| `ui_ux/qml/CustomizationPanel.qml` | 커스터마이징 편집 UI |
| `ui_ux/qml/CharacterDisplay.qml` | 레이어 합성 캐릭터 표시 컴포넌트 |

---

## 8. 구현 순서 (권장)

```
1단계 — 배경 이미지 연동
  - backgroundChanged 시그널 추가 (bridge.py)
  - main.qml 채팅 영역에 Image 레이어 추가
  - act 변경 감지 → 시그널 emit (router.py or agent/core.py)

2단계 — PIP 마스코트 모드
  - main.qml 주황 버튼 동작 변경 (isBubble → pip 모드)
  - PipWindow.qml 구현 (아이콘 + 말풍선 팝업)
  - moodChanged 시그널 연동

3단계 — 설정 패널
  - SettingsPanel.qml 구현
  - getCharacterList / getWorldList / changeWorld 슬롯 추가 (bridge.py)

4단계 — 커스터마이징
  - CharacterDisplay.qml 구현 (레이어 합성)
  - CustomizationPanel.qml 구현
  - saveCustomization / loadCustomization 슬롯 추가 (bridge.py)
```
