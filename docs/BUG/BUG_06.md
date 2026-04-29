# BUG-08 — Windows 배포 v0.0 UI 이슈 세트

> 발생일: 2026-04-28
> 단계: Phase 6 — Windows 배포 실환경 검증 (v0.0)
> 환경: Windows 11, C:\Achat, CPU 추론 (llama-cpp Q4_K_M)

---

## 개요

`C:\Achat`에 소스 그대로 배포한 v0.0 실환경에서 발견된 UI/UX 이슈 5건.
모두 Windows + PySide6 QML 환경에서만 드러나는 문제들이었다.

---

## 이슈 1 — WindowStaysOnTopHint 풀창 모드에서도 적용돼 다른 앱 위를 가림

### 증상

`main.qml`의 `flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint` 설정이
풀창(full window) 모드에서도 항상-위로 작동, 크롬·탐색기 등 다른 앱 위에 Achat 창이 겹쳐 사용 불편.

### 원인

`Qt.WindowStaysOnTopHint`가 풀창/PIP 구분 없이 전역으로 적용됨.
PIP 마스코트 모드는 항상-위가 필요(바탕화면 위 떠있는 캐릭터)하지만,
풀창 모드는 일반 앱과 같이 다른 창 뒤로 갈 수 있어야 한다.

### 해결

```qml
// main.qml
// Before:
flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint

// After:
flags: Qt.FramelessWindowHint | (root.isBubble ? Qt.WindowStaysOnTopHint | Qt.Tool : Qt.Window)
```

`isBubble`(PIP 모드)일 때만 `WindowStaysOnTopHint | Tool` 조합 적용.
풀창은 `Qt.Window`로 일반 창 동작.

---

## 이슈 2 — 절전 모드 오버레이가 PNG 투명 영역까지 암전

### 증상

PIP 모드 절전(5분 비활동 → LLM 언로드) 시 캐릭터 이미지 위에 어두운 Rectangle을
씌워 "💤 절전 중" 안내를 표시했는데, 캐릭터 PNG의 투명 배경 부분도 검게 채워짐.

```qml
// Before — Rectangle이 charArea 전체를 덮어씀
Rectangle {
    visible: pipRoot.isSleeping
    color: "#CC000000"   // 반투명 검정이지만 투명 픽셀도 채움
    ...
}
```

### 원인

`Rectangle`은 QML 아이템의 bounding box 전체를 채운다.
PNG의 alpha=0 픽셀도 Rectangle 안에 포함되므로 투명하게 유지되지 않음.

### 해결

`charArea` 자체의 `opacity`를 낮추는 방식으로 전환.

```qml
// After — charArea opacity로 희미하게 처리 (투명 영역 유지)
Item {
    id: charArea
    opacity: pipRoot.isSleeping ? 0.35 : 1.0
    Behavior on opacity { NumberAnimation { duration: 400 } }
    ...
}

// 💤 안내 텍스트는 charArea 외부 sibling 아이템에 배치 (dimming 안 받도록)
Item {
    visible: pipRoot.isSleeping
    anchors { bottom: parent.bottom; left: parent.left }
    width: charArea.width; height: charArea.height
    z: 5
    Column { ... Text { text: "💤" } ... Text { text: "절전 중" } ... }
}
```

---

## 이슈 3 — 이전 테마(solar/forest) 저장값 로드 시 흰 화면

### 증상

기존 `preferences.json`에 `"theme": "solar"` 또는 `"forest"`로 저장된 경우,
앱 업데이트 후 테마 데이터 키를 찾지 못해 UI 색상이 `undefined`로 렌더링.

### 원인

`solar`·`forest` 테마를 `amber`·`violet`으로 교체했는데, 기존 저장값 마이그레이션
로직이 없었음.

```python
# Before — solar/forest를 유효하지 않은 값으로 처리
return saved if saved in ("ocean", "solar", "forest") else "ocean"
```

### 해결

```python
# After — 구 저장값을 신 테마로 자동 마이그레이션
_VALID   = {"ocean", "amber", "violet"}
_MIGRATE = {"solar": "amber", "forest": "violet"}
return _MIGRATE.get(saved, saved) if saved in _VALID or saved in _MIGRATE else "ocean"
```

`solar` → `amber`, `forest` → `violet`으로 런타임에 자동 변환.
사용자가 수동으로 파일을 편집할 필요 없음.

---

## 이슈 4 — 캐릭터 이미지 좌측 여백이 너무 넓음

### 증상

캐릭터 PNG 파일 내부에 좌측 투명 여백이 존재, 화면에서 캐릭터가 창 왼쪽 가장자리로부터
글자 3~4개 분량 떨어져 표시됨.

### 원인

PNG sprite에 내장된 투명 패딩 + `x: 4` 양수 offset의 합산 효과.
이미지 크기는 `width: 283`이지만 실제 캐릭터가 차지하는 픽셀은 우측으로 치우쳐 있음.

### 해결

```qml
// x 값을 음수로 설정해 PNG의 좌측 투명 여백을 상쇄
x: -40   // 4px → -40px (글자 0~1개 분량 간격)
```

---

## 이슈 5 — 대화창 글씨가 작아 가독성 부족

### 증상

Windows 실환경(FHD 모니터)에서 ChatBubble 폰트(16px), 타이틀바(13px), 입력창(13px)이
너무 작게 보임. 특히 나레이션 글씨(15px)와 일반 대화 글씨 구분이 어려움.

### 해결

| 대상 | 변경 전 | 변경 후 |
|---|---|---|
| ChatBubble assistant | 16px | 14px |
| ChatBubble narrator  | 15px | 13px |
| SettingsButton | 15px | 14px |
| 캐릭터명(타이틀바) | 13px | 15px |
| 입력 필드 | 13px | 14px |
| 타이틀바 높이 | 38px | 44px |
| 입력창 높이 | 48px | 56px |

> 참고: ChatBubble의 경우 폰트 크기는 줄였지만 `Font.Medium` 굵기를 유지해
> 가독성을 확보했다. 크기를 줄인 이유는 캐릭터 이미지 크기 조정(1.4x→1.3x)에
> 따라 말풍선 표시 영역이 넓어졌기 때문이다.

---

## 공통 수정 파일

| 파일 | 이슈 |
|---|---|
| `ui_ux/qml/main.qml` | 1, 3(테마), 4, 5 |
| `ui_ux/qml/PipWindow.qml` | 2 |
| `ui_ux/qml/ChatBubble.qml` | 5 |
| `ui_ux/qml/SettingsPanel.qml` | 5 |
| `ui_ux/bridge.py` | 3(마이그레이션) |
