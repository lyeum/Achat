# UI 테스트 체크리스트

## 자동 테스트 실행

```bash
# 전체 자동 테스트 (76개, 모델/디스플레이 불필요)
ACHAT_ENV=ui_test uv run python -m pytest tests/ -v

# 구조 검사만
ACHAT_ENV=ui_test uv run python -m pytest tests/test_ui_structure.py -v

# bridge 슬롯만
ACHAT_ENV=ui_test uv run python -m pytest tests/test_bridge_slots.py -v
```

## 수동 UI 테스트 (시각적 확인)

```bash
ACHAT_ENV=ui_test uv run python main.py
```

> stub 모드(모델 미로드). 브리지 신호는 수동 트리거 또는 입력 전송으로 확인.

---

## 수정된 버그 (검토 완료)

| # | 버그 | 파일 | 수정 내용 |
|---|---|---|---|
| B1 | PIP 모드 user 메시지 중복 | main.qml | onMessageSent에서 messageModel.append 제거 |
| B2 | SettingsPanel `parent._wId/_scId` 잘못된 scope | SettingsPanel.qml | flat 모델로 재구성, modelData.world_id 직접 사용 |
| B3 | CustomizationPanel ListView delegate `parent._selected` | CustomizationPanel.qml | `ListView.view.outerSelected` attached property로 대체 |
| B4 | CharacterDisplay 빈 `Behavior on source {}` | CharacterDisplay.qml | 제거 |
| B5 | CustomizationPanel 패널 내 빈 클릭 시 패널 닫힘 | CustomizationPanel.qml | panelRect에 click-consumer MouseArea 추가 |
| B6 | `_loadCustomization()`에서 bridge null 체크 없음 | main.qml | `if (!bridge) return` 추가 |

---

---

## 1단계 — 배경 이미지 연동

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 1-1 | 배경 이미지 없을 때 기본 다크 배경 유지 | 에셋 없이 실행 | `bgImage` 숨겨지고 `#1E1E1E` 배경만 표시 |
| 1-2 | 배경 이미지 있을 때 표시 | `ui_ux/assets/backgrounds/{world_id}/{act_id}.png` 배치 후 실행 | 채팅 영역에 opacity 0.35로 이미지 오버레이 |
| 1-3 | 배경 이미지 전환 시 크로스페이드 | act 변경(메시지 전송) | opacity Behavior로 400ms 페이드 전환 |
| 1-4 | `backgroundImageUrl` 빈 문자열일 때 Image 숨김 | 에셋 없는 상태 | `bgImage.visible === false` |
| 1-5 | mood 변경 시 `currentMood` 업데이트 | 응답 수신 후 mood 변화 | `root.currentMood` 갱신 (PIP 아이콘 이모지 연동) |

---

## 2단계 — PIP 마스코트 모드

### 2-A. 모드 전환

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 2-A-1 | 풀창 → PIP 전환 | 타이틀바 주황(●) 버튼 클릭 | 창이 50×50으로 축소, 배경 투명, 아이콘 표시 |
| 2-A-2 | PIP → 풀창 복귀 (말풍선 버튼) | 말풍선 내 주황(⤢) 버튼 클릭 | 창이 360×520으로 복원 |
| 2-A-3 | 전환 시 위치 유지 | PIP 전환 후 복귀 | 화면 우하단 위치 유지 (드래그 후도 동일) |
| 2-A-4 | `isBubble` 전환 시 `pipBubbleOpen` 초기화 | 풀창→PIP | 말풍선 닫힌 상태로 시작 |

### 2-B. 아이콘 영역

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 2-B-1 | mood별 이모지 플레이스홀더 | `currentMood` 변경 | neutral=😐, happy=😊, annoyed=😤, sad=😢 |
| 2-B-2 | 아이콘 hover 시 테두리 주황 전환 | 마우스 오버 | `border.color` #3A3A3A → #F0A500 (150ms) |
| 2-B-3 | 아이콘 클릭 시 말풍선 열림 | 클릭 | 말풍선 표시, 자동 닫힘 타이머(5초) 시작 |
| 2-B-4 | 아이콘 재클릭 시 말풍선 닫힘 | 말풍선 열린 상태에서 클릭 | 말풍선 닫힘, 타이머 정지 |

### 2-C. 말풍선 크기/위치 애니메이션

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 2-C-1 | 말풍선 열릴 때 창 240×190으로 확장 | 아이콘 클릭 | yAnim + heightAnim 200ms 동시 실행 |
| 2-C-2 | 말풍선 닫힐 때 창 50×50으로 축소 | 닫기 또는 타이머 | 동일 애니메이션으로 축소 |
| 2-C-3 | 아이콘 위치 고정 (위로 확장) | 말풍선 열기/닫기 반복 | 아이콘 하단 Y 좌표 유지, 말풍선이 위로 펼쳐짐 |
| 2-C-4 | 드래그 후 말풍선 여닫기 위치 정확성 | 드래그 이동 → PIP → 말풍선 | `pipAnchorY` 갱신되어 위치 정확 |

### 2-D. 말풍선 내용 및 입력

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 2-D-1 | assistant 응답 시 말풍선 자동 표시 | 메시지 전송 후 응답 수신 | `showBubble(content)` 호출, 말풍선 자동 열림 |
| 2-D-2 | 최신 메시지 4줄 표시 후 말줄임 | 긴 응답 전송 | `maximumLineCount: 4`, `elide: Text.ElideRight` |
| 2-D-3 | 입력창에서 Enter 전송 | 텍스트 입력 후 Return | `messageSent` signal emit, 입력창 초기화 |
| 2-D-4 | ▶ 버튼 클릭 전송 | ▶ 버튼 클릭 | 동일 |
| 2-D-5 | 전송 후 자동 닫힘 타이머 재시작 | 입력 전송 | 5초 후 말풍선 자동 닫힘 |
| 2-D-6 | 빈 입력 전송 무시 | 빈 상태에서 Enter/▶ | 아무 동작 없음 |
| 2-D-7 | `inputEnabled: false` 시 입력 비활성화 | thinking 상태 진입 | TextInput 비활성, ▶ 회색, 커서 ArrowCursor |

### 2-E. 자동 닫힘 타이머

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 2-E-1 | 5초 후 말풍선 자동 닫힘 | 말풍선 열고 대기 | 5초 후 `bubbleOpen = false` |
| 2-E-2 | 입력 전송 시 타이머 재시작 | 4초 후 입력 전송 | 5초 타이머 재시작 (닫히지 않음) |
| 2-E-3 | 아이콘 클릭으로 닫을 때 타이머 정지 | 클릭으로 닫기 | `autoClose.stop()` 호출 |

### 2-F. 풀창 모드 영향 없음 확인

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 2-F-1 | PIP 비활성 시 풀창 레이아웃 정상 | 풀창 모드 사용 | PipWindow `visible: false`, ColumnLayout 정상 |
| 2-F-2 | `inputReady` 풀창/PIP 공유 | thinking 상태에서 PIP 전환 | 두 모드 모두 입력 비활성화 |
| 2-F-3 | 풀창 채팅 기록 유지 | PIP 전환 후 복귀 | `messageModel` 내용 보존 |

---

## 3단계 — 설정 패널

### 3-A. 열기 / 닫기

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 3-A-1 | ≡ 버튼 표시 | 풀창 타이틀바 | charNameLabel 오른쪽에 ≡ 버튼 표시 |
| 3-A-2 | ≡ 클릭 시 패널 열림 | ≡ 버튼 클릭 | SettingsPanel z:10 오버레이 표시 |
| 3-A-3 | 딤 배경 클릭 시 닫힘 | 패널 왼쪽 딤 영역 클릭 | `settingsOpen = false`, 패널 숨김 |
| 3-A-4 | 패널 내 ✕ 버튼 클릭 시 닫힘 | 패널 헤더 ✕ 클릭 | 동일 |
| 3-A-5 | PIP 모드에서 패널 숨김 | PIP 전환 후 확인 | `visible: !root.isBubble` → 패널 없음 |

### 3-B. 캐릭터 변경

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 3-B-1 | 캐릭터 목록 표시 | ≡ 열기 후 캐릭터 섹션 | CH_*.yaml 파일 수만큼 버튼 표시 |
| 3-B-2 | 캐릭터 버튼 클릭 시 전환 | 버튼 클릭 (stub 모드 외) | `bridge.changeCharacter(id)` 호출, 타이틀 이름 변경 |
| 3-B-3 | 전환 후 패널 자동 닫힘 | 캐릭터 클릭 | `closeRequested` → `settingsOpen = false` |
| 3-B-4 | hover 시 버튼 배경 밝아짐 | 버튼 위 마우스 오버 | `#2E2E2E` 배경색 전환 (100ms) |

### 3-C. 시나리오 / Act 변경

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 3-C-1 | 세계관 이름 표시 | ≡ 열기 후 시나리오 섹션 | world_id 텍스트 (회색 소형) |
| 3-C-2 | Act 버튼 표시 | 시나리오 섹션 확인 | `act_id (location)` 형태 버튼 |
| 3-C-3 | Act 버튼 클릭 시 전환 | 버튼 클릭 (stub 모드 외) | `bridge.changeWorld(world_id, scenario_id, act_id)` 호출 |
| 3-C-4 | 배경 이미지 갱신 | act 변경 후 에셋 있을 때 | `backgroundChanged` → `bgImage` 갱신 |
| 3-C-5 | 전환 후 패널 자동 닫힘 | act 클릭 | `settingsOpen = false` |

---

## 4단계 — 커스터마이징

### 4-A. CharacterDisplay (풀창 채팅 영역)

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 4-A-1 | 에셋 없을 때 이모지 플레이스홀더 | 에셋 없이 실행 | mood에 맞는 이모지 (😐/😊/😤/😢) |
| 4-A-2 | CharacterDisplay 위치 (입력창 오버랩) | 풀창 모드 확인 | 캐릭터 하단 40px가 입력 영역에 가려짐 |
| 4-A-3 | 채팅 메시지 위에 표시 | 채팅 후 확인 | charDisplay z:2 → 메시지 위에 렌더링 |
| 4-A-4 | custom/base.png 있을 때 단일 이미지 표시 | base.png 배치 후 실행 | 레이어 1~8 대체, 효과 레이어 얹힘 |
| 4-A-5 | parts.json 파츠 각 레이어 합성 | 파츠 이미지 배치 후 | 9개 레이어 순서대로 합성 |
| 4-A-6 | mood 변경 시 효과 레이어 갱신 | 응답 수신 → mood 변화 | effectLayer.source 변경 |

### 4-B. 커스터마이징 패널 열기 / 닫기

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 4-B-1 | ≡ → "캐릭터 커스터마이징..." 버튼 | 설정 패널 열기 | SettingsPanel 하단에 커스터마이징 버튼 표시 |
| 4-B-2 | 버튼 클릭 시 CustomizationPanel 열림 | 버튼 클릭 | z:20 오버레이 패널 표시 |
| 4-B-3 | 딤 배경 클릭 닫기 | 패널 외 클릭 | `customizationOpen = false` |
| 4-B-4 | 취소 버튼 닫기 | 취소 클릭 | 변경사항 미저장, 패널 닫힘 |
| 4-B-5 | PIP 모드에서 패널 숨김 | PIP 전환 | `visible: !root.isBubble` |

### 4-C. 파츠 선택

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 4-C-1 | 파츠 탭 8개 파츠 타입 표시 | 파츠 탭 클릭 | body/hair_back/eye/eyebrow/mouth/outfit/hair_front/accessory 섹션 |
| 4-C-2 | 파츠 없을 때 "파츠 없음" 표시 | 에셋 없이 실행 | 각 타입 행에 "파츠 없음" 텍스트 |
| 4-C-3 | 파츠 선택 시 파란 하이라이트 | 파츠 버튼 클릭 | 선택된 버튼 `#4A90D9` 배경 |
| 4-C-4 | 동일 파츠 재클릭 시 선택 해제 | 선택된 버튼 재클릭 | 선택 해제 (null 처리) |
| 4-C-5 | 저장 시 parts.json 생성 | 파츠 선택 후 저장 | `custom/parts.json` 파일 생성 |

### 4-D. 감정 효과

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 4-D-1 | 감정 효과 탭 4개 mood 행 표시 | 탭 전환 | neutral/happy/annoyed/sad 행 |
| 4-D-2 | 커스텀 효과 없을 때 "기본값 사용" 표시 | effects.json 없이 실행 | 회색 "기본값 사용" 텍스트 |
| 4-D-3 | 커스텀 효과 있을 때 파일명 + 초기화 버튼 | effects.json 있을 때 | 파일명 파란 텍스트, 초기화 버튼 표시 |
| 4-D-4 | 초기화 버튼 클릭 시 기본값 복귀 | 초기화 클릭 | effects.json에서 해당 mood 키 제거 |
| 4-D-5 | 저장 시 effects.json 생성 | 효과 변경 후 저장 | `custom/effects.json` 파일 생성 |

### 4-E. 저장 흐름

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| 4-E-1 | 저장 후 CharacterDisplay 즉시 갱신 | 파츠 선택 → 저장 | `customPartsJson` 업데이트 → charDisplay 재렌더 |
| 4-E-2 | 시작 시 기존 설정 자동 로드 | parts.json 있는 상태에서 재실행 | `_loadCustomization()` → charDisplay 반영 |
| 4-E-3 | stub 모드에서 저장 동작 | ACHAT_ENV=ui_test에서 저장 | `_CUSTOM_DIR` 경로에 JSON 파일 생성 |

---

## 공통

| # | 항목 | 확인 방법 | 예상 결과 |
|---|---|---|---|
| C-1 | 창 드래그 이동 | 타이틀바/아이콘 외 영역 드래그 | 창 이동 (DragHandler) |
| C-2 | 닫기(✕) 버튼 | 클릭 | `Qt.quit()` 앱 종료 |
| C-3 | hover 시 opacity 1.0, 비hover 시 0.85 | 마우스 이동 | 풀창 모드에서만 적용 (PIP는 항상 1.0) |
| C-4 | 한글 입력 | 풀창/PIP 입력창에서 한글 입력 | 정상 입력 (ibus-hangul 연동) |
| C-5 | 모드 탭 전환 (대화/기능) | 모드 바 클릭 | `currentMode` 변경, 탭 하이라이트 |
