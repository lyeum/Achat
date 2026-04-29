# 나레이션 시스템 개선 계획

> 작성일: 2026-04-01
> 상태: **방향 전환** (2026-04-06)
> 원래 목표: LLM 기반 나레이션 자동 삽입 + 사용자 행동 묘사 입력 지원
>
> **변경 사항**: LLM Narrator(`conversation/narrator.py`) 제거 완료.
> VRAM/RAM 절감 및 응답 지연 제거 목적. 대신 `narration_hardcoded.py` + `NarrationMonitor`를 사용.
> - `narration_hardcoded.find_trigger()`: 키워드 → 미리 작성된 묘사 텍스트, LLM 호출 없음
> - `NarrationMonitor.check_keyword()`: 세션 내 키워드당 1회 제한
> - `bridge.py`의 `_ACTION_RE`: `*...*` 패턴 → `(행동: ...)` 변환
> - 테스트 27개 `tests/test_narration.py`에서 검증 완료

---

## 구현 상태

| # | 항목 | 상태 | 대상 파일 |
|---|---|---|---|
| 1 | narrator.py — describe_action / describe_emotion 추가 + few-shot | ✅ 구현 | `conversation/narrator.py` |
| 2 | narration_monitor.py — 트리거 판단 로직 (rule-based) | ✅ 구현 | `conversation/narration_monitor.py` (신규) |
| 3 | bridge.py — 행동 패턴 감지 + NarrationWorker 비동기 연결 | ✅ 구현 | `ui_ux/bridge.py` |
| 4 | main.qml — narrator role 버블 스타일 추가 | ✅ 구현 | `ui_ux/qml/ChatBubble.qml` |
| 5 | agent/core.py + router.py — narrator 연결 및 주석 정리 | ✅ 구현 | `agent/core.py`, `conversation/core/router.py` |
| 6 | 테스트 추가 | ✅ 구현 | `tests/test_narration.py` (신규, 27개 통과) |

---

## 목표 동작

### 나레이션 자동 삽입

대화 로그와 세션 상태를 백그라운드에서 실시간 모니터링해, 의미 있는 순간에 나레이션을
자동으로 삽입한다. 사용자가 별도로 명령하지 않아도 흐름 안에서 자연스럽게 등장한다.

```
[대화 흐름 예시]
user:      "오늘 진짜 힘들었어."
narrator:  "하루는 잠시 말이 없었다. 시선이 창밖으로 갔다."        ← 자동 삽입
assistant: "...그랬구나."

user:      "*카페 창가에 앉았다*"
narrator:  "카페 창가에 자리를 잡았다. 바깥 빛이 테이블 위로 떨어졌다."  ← 행동 반응
assistant: "...창가네."
```

### 사용자 행동 묘사 입력

`*...*` 패턴으로 행동 묘사를 입력하면 일반 대화와 별도로 처리된다.

```
입력: *카페 창가에 앉았다*
→ 1. dialogue_log에 "(행동: 카페 창가에 앉았다)" 형태로 기록 (캐릭터 상황 인지)
→ 2. NarrationMonitor에 ACTION_INPUT 트리거 발동 → 행동 반응 나레이션 생성
```

---

## 1. narrator.py 확장

### 현재 상태

`describe_arrival()` / `describe_session_start()` 두 메서드만 존재.
few-shot 예시 없음.

### 추가할 메서드

```python
def describe_action(self, action_text: str, mood: str) -> str:
    """사용자 행동(*...*) 입력에 대한 캐릭터 반응 및 장면 묘사."""

def describe_emotion(self, mood: str, affection_tier: str, recent_exchange: list[dict]) -> str:
    """mood 변화 또는 감정 클라이맥스 순간의 캐릭터 내면/행동 묘사."""
```

### few-shot 프롬프트 구조

각 메서드 프롬프트에 카테고리별 예시를 정적으로 포함.
예시는 모델에게 "이런 길이, 이런 문체"를 직접 보여주는 역할.

```python
_EMOTION_PROMPT = """\
아래 예시처럼 캐릭터의 감정 변화를 행동과 짧은 서술로 묘사해.
대화체 없이 3인칭 서술체. 2~3문장 이내.

[예시 — mood: touched]
잠깐 말이 끊겼다. 하루는 시선을 내렸다가 다시 들었다.

[예시 — mood: annoyed]
대답이 짧아졌다. 손가락이 테이블 위를 한 번 두드렸다.

[예시 — mood: affectionate]
말이 느려졌다. 먼 곳을 보는 것처럼 눈빛이 잠깐 흐려졌다.

---
캐릭터: {char_name}
현재 감정: {mood}
친밀도 상태: {affection_tier}
직전 대화:
{recent_exchange}
"""

_ACTION_PROMPT = """\
아래 예시처럼 사용자의 행동에 반응하는 장면을 3인칭 서술체로 묘사해.
캐릭터의 반응(시선, 움직임, 표정)을 짧게 포함. 2~3문장 이내.

[예시 — 자리 이동]
창가에 빛이 들어왔다. 하루의 시선이 잠깐 따라갔다.

[예시 — 물건 건네기]
손이 내밀어졌다. 하루는 잠시 그것을 바라보다 받았다.

---
캐릭터: {char_name}
행동 내용: {action_text}
현재 감정: {mood}
"""
```

---

## 2. narration_monitor.py (신규)

### 역할

매 턴 완료 후 세션 상태 변화를 분석해 나레이션 트리거 여부를 rule-based로 판단.
LLM 추가 호출 없이 결정 — 나레이션 생성만 LLM에 위임.

### 트리거 규칙

| 트리거 ID | 조건 | 나레이션 유형 | 우선순위 |
|---|---|---|---|
| `ACTION_INPUT` | 사용자 입력이 `*...*` 패턴 | 행동 반응 묘사 | 1 (즉시) |
| `MOOD_SHIFT` | `prev_mood != curr_mood` and `curr_mood != neutral` | 감정/행동 묘사 | 2 |
| `EMOTIONAL_PEAK` | `mood in (affectionate, touched, angry)` | 감정 클라이맥스 묘사 | 2 |
| `TIER_CROSS` | affection이 tier 경계를 넘음 | 관계 변화 묘사 | 3 |
| `LOCATION_CHANGE` | `session.act_id` 또는 `location_context` 변경 | 장소 도착 묘사 | 3 |
| `COOLDOWN` 억제 | 마지막 나레이션으로부터 3턴 이내 | 발동 억제 | — |

### 클래스 구조

```python
class NarrationMonitor:
    """매 턴 세션 상태를 분석해 나레이션 트리거를 판단한다."""

    COOLDOWN_TURNS = 3   # 나레이션 최소 간격

    def __init__(self, narrator: Narrator):
        self._narrator = narrator
        self._last_narration_turn: int = -COOLDOWN_TURNS

    def observe(
        self,
        session: ConversationSession,
        prev_mood: str,
        prev_affection: int,
        prev_act_id: str | None,
        user_input: str,
    ) -> str | None:
        """트리거 판단 → 해당 시 나레이션 문자열 반환, 없으면 None."""
```

### 쿨다운 설계 이유

연속 트리거가 발생하면 나레이션이 매 턴 등장해 몰입을 오히려 깨뜨림.
`COOLDOWN_TURNS = 3`으로 최소 3턴 간격을 강제.
단, `ACTION_INPUT`은 쿨다운 예외 — 사용자가 명시적으로 행동 입력을 한 경우.

---

## 3. bridge.py 수정

### 행동 패턴 감지

```python
import re
_ACTION_RE = re.compile(r"^\*(.+)\*$")

@Slot(str, str, str)
def sendMessage(self, text: str, mode: str, tag: str) -> None:
    action_match = _ACTION_RE.match(text.strip())
    if action_match:
        action_text = action_match.group(1)
        # dialogue_log에 "(행동: ...)" 형태로 기록해 캐릭터가 인지하게
        text = f"(행동: {action_text})"
        # ACTION_INPUT 플래그 → narration_monitor에 전달
    ...
```

### NarrationWorker (비동기)

```python
from PySide6.QtCore import QRunnable, QThreadPool, Signal, QObject

class _NarrationSignals(QObject):
    ready = Signal(str)   # 나레이션 텍스트 완성 시

class NarrationWorker(QRunnable):
    def __init__(self, monitor, session_snapshot, ...):
        ...
    def run(self):
        text = self._monitor.observe(...)
        if text:
            self.signals.ready.emit(text)
```

```python
# sendMessage() 내부 — assistant 응답 emit 후
worker = NarrationWorker(self._narration_monitor, ...)
worker.signals.ready.connect(
    lambda txt: self.messageAdded.emit("narrator", txt)
)
QThreadPool.globalInstance().start(worker)
```

### 세션 스냅샷 문제

`observe()`는 백그라운드 스레드에서 실행되므로, 호출 시점의 mood/affection/act_id를
**LLM 응답 직전에 캡처**해두어야 함. 응답 후 session이 이미 갱신된 상태이므로
"이전 상태"를 별도 변수로 보관.

---

## 4. QML — narrator 버블 스타일

`messageAdded("narrator", text)` emit 시 기존 `onMessageAdded` 핸들러에서
role="narrator"를 받아 별도 스타일로 렌더링.

```qml
// ChatBubble.qml 또는 main.qml messageModel delegate
// role === "narrator" → 이탤릭체, 중앙 정렬, 연한 색
color: role === "narrator" ? "#6A8A9A" : defaultColor
font.italic: role === "narrator"
horizontalAlignment: role === "narrator" ? Text.AlignHCenter : Text.AlignLeft
```

나레이션은 대화 버블과 시각적으로 구분되어야 흐름이 읽힘.

---

## 5. router.py — narrator 재활성화

```python
# 현재 (비활성화)
def _handle_location(self, user_input: str) -> None:
    ...
    # 나레이터는 비활성화 상태 — 대화 안정화 후 conversation/narrator.py 재연결.

# 변경 후
def _handle_location(self, user_input: str) -> None:
    ...
    if location_name and self._narrator:
        narration = self._narrator.describe_arrival(
            location_name, self.session.location_context or "", self.session.mood
        )
        # narration을 bridge로 전달하는 경로 필요 (콜백 또는 반환값 확장)
```

router → bridge 나레이션 전달 경로는 `handle_turn()`의 반환값을 `(response, narration)` 튜플로
확장하거나, 별도 콜백을 주입하는 방식 중 선택 필요.

**권고**: `handle_turn()` 반환값을 `str` → `dict` 로 확장.

```python
return {
    "response":  response,
    "narration": narration or None,   # None이면 QML에서 무시
}
```

---

## 구현 순서 및 의존성

```
[1단계] narrator.py 확장
        describe_action(), describe_emotion() 추가
        few-shot 프롬프트 템플릿 작성
            ↓
[2단계] narration_monitor.py 신규 작성
        NarrationMonitor.observe() + 트리거 규칙 구현
            ↓
[3단계] bridge.py 수정
        행동 패턴 감지 (_ACTION_RE)
        NarrationWorker 비동기 연결
        sendMessage() 내 세션 스냅샷 캡처
            ↓
[4단계] router.py narrator 재활성화
        handle_turn() 반환값 확장 or 콜백 방식 결정
            ↓
[5단계] main.qml / ChatBubble.qml
        narrator role 버블 스타일 추가
            ↓
[6단계] 테스트
        test_narration.py — 트리거 판단 / 쿨다운 / 행동 패턴 감지
```

---

## 고려사항

### CPU 배포 성능

나레이션 생성은 LLM 호출 1회 추가. Q4_K_M 기준 max_tokens=150으로 제한하면
CPU에서 15~25초 소요. 비동기(QThreadPool)로 실행하므로 대화 응답을 블로킹하지 않음.
단, 나레이션이 응답보다 늦게 표시될 수 있음 — 의도된 동작으로 허용.

### 쿨다운 튜닝

초기값 `COOLDOWN_TURNS = 3` 은 실환경 테스트 후 조정 필요.
너무 자주 나오면 늘리고, 너무 드물면 줄임.
`ACTION_INPUT`은 항상 쿨다운 예외로 유지.

### few-shot 예시 품질

예시 텍스트가 나레이션 전체 품질을 결정. 초기 3~5개로 시작하고
실환경에서 이상한 출력이 관찰되면 예시를 교체/추가.
LoRA 학습은 프롬프트 방식으로 품질이 명확히 부족할 때 검토.

---

## 관련 파일

| 파일 | 역할 |
|---|---|
| `conversation/narrator.py` | 나레이션 LLM 호출 + few-shot 프롬프트 |
| `conversation/narration_monitor.py` | 트리거 판단 (신규) |
| `conversation/core/router.py` | narrator 재연결 + handle_turn 반환값 확장 |
| `ui_ux/bridge.py` | 행동 패턴 감지 + NarrationWorker |
| `ui_ux/qml/main.qml` | narrator role 렌더링 |
| `ui_ux/qml/ChatBubble.qml` | narrator 버블 스타일 |
| `docs/BUG/BUG_03.md` | 배포 환경 LoRA on/off 한계 — narrator LoRA 관련 |
| `docs/대화품질.md` | 기능 모드 LLM 사용 원칙 — 나레이션 품질 전략 |
