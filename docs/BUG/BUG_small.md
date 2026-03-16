# BUG_small.md — 소규모 버그 수정 기록

> 발견 경위: Phase 7 구현 완료 후 전체 코드 상호 검토 (2026-03-16)
> 대형 기능 변경이 아닌 버그 수정 / 연결 누락 위주로 기록한다.

---

## BUG-01 · `agent/core.py` — `LLMClient.generate()` 시그니처 불일치

**파일**: `agent/core.py:151` (Phase 7 신규 작성)

**문제**
`_handle_function()`에서 LLM을 호출할 때 존재하지 않는 키워드 인자를 사용했다.

```python
# 잘못된 코드
llm_output = self.llm.generate(
    system=tool.system_prompt,
    user=user_input,
    stream=False,
)
```

`LLMClient.generate()`의 실제 시그니처는 `generate(messages: list[dict], stream, max_tokens)` 이므로
런타임에서 `TypeError: generate() got an unexpected keyword argument 'system'` 발생.

**원인**
Phase 7 도구 파이프라인 작성 시 `LLMClient` 시그니처를 확인하지 않고 작성.

**수정**
```python
# 수정된 코드
llm_output = self.llm.generate(
    messages=[
        {"role": "system", "content": tool.system_prompt},
        {"role": "user",   "content": user_input},
    ],
    stream=False,
)
```

---

## BUG-02 · `agent/core.py` — 기능 모드 키워드 우선순위 충돌

**파일**: `agent/core.py:32` (Phase 7 신규 작성)

**문제**
`_KEYWORDS` 목록에서 `"변환"` 키워드가 `image_convert` 항목에 포함되어 있고,
`image_convert` 항목이 `prompt_convert` / `file_rename` 보다 먼저 배치되었다.

```
"프롬프트 변환해줘" → "변환"에 먼저 걸려 image_convert 선택 (wrong)
"이름 변환해줘"    → "변환"에 먼저 걸려 image_convert 선택 (wrong)
```

**원인**
`_KEYWORDS`는 첫 번째 매칭 항목을 반환하는 순서 의존 구조인데,
범용 키워드(`"변환"`)가 구체적인 키워드(`"프롬프트"`, `"이름"`)보다 앞에 배치됨.

**수정**
- `"변환"` 키워드를 `image_convert` 항목에서 제거 (이미지 고유 키워드만 유지)
- `prompt_convert` / `file_rename`을 `image_convert`보다 앞으로 이동

```python
_KEYWORDS = [
    (("프롬프트", "prompt", "명확하게", ...), "prompt_convert"),  # 먼저
    (("이름", "rename", "renamer", "파일명"), "file_rename"),      # 먼저
    (("분류", "정리", "폴더"),                "folder_classify"),
    (("이미지", "image", "png", "jpg", ...),  "image_convert"),    # 나중
    (("검색", "search", "찾아", "파일 찾"),   "local_search"),
]
```

---

## BUG-03 · `ui_ux/bridge.py` — stub 모드에서 `changeCharacter` 크래시

**파일**: `ui_ux/bridge.py:86`

**문제**
`ui_test` 환경(stub 모드)에서 트레이 메뉴 "캐릭터 변경"을 실행하면
`agent.session = None` 상태에서 `swap_persona(session=None, ...)`이 호출되어
`persona.py` 내부에서 `session.world_id` 접근 시 `AttributeError` 발생.

**원인**
stub 모드 여부를 확인하지 않고 세션 객체에 직접 접근.

**수정**
```python
def changeCharacter(self, char_id: str) -> None:
    if self._agent.session is None:   # stub / ui_test 모드
        return
    ...
```

---

## BUG-04 · `ui_ux/bridge.py` — 캐릭터 핫스왑 후 Router/Builder 미갱신

**파일**: `ui_ux/bridge.py:94`

**문제**
`changeCharacter()` 실행 후 `agent.character`와 `agent.session`만 교체되고
`agent.router.character`, `agent.router.session`, `agent.router.builder`는 이전 객체를
그대로 참조함. UI에서는 새 캐릭터 이름이 표시되지만 실제 대화 응답은 이전 캐릭터
설정(말투, affection 임계값, 시스템 프롬프트)으로 생성되는 silent bug.

**원인**
`ConversationRouter.__init__`에서 `PromptBuilder`를 생성 시 캐릭터/세션을 멤버로
저장하므로, `agent.router.builder` 자체를 교체하지 않으면 변경이 반영되지 않음.

**수정**
```python
if self._agent.router is not None:
    self._agent.router.character = new_char
    self._agent.router.session   = new_session
    self._agent.router.builder   = PromptBuilder(
        new_char,
        self._agent.world,
        new_session,
        count_tokens_fn=self._agent.llm.count_tokens,
    )
```

`router.long_term`과 `router.rag`는 캐릭터와 무관(character_id를 매 호출 시 인자로
받거나 세계관 공통 컬렉션 사용)하므로 교체 불필요.

---

## BUG-05 · `conversation/memory_act/M_default.json` — 스키마 불일치

**파일**: `conversation/memory_act/M_default.json`

**문제**
`M_schema.json`이 요구하는 구조(`id`, `content`, `metadata` 래퍼)와 달리
항목이 플랫 구조(`act_id`, `location`, `summary`)로 작성되어 있었음.

`long_term.store(entry)`는 첫 줄에서 `entry["metadata"]`를 접근하므로
seeding 시도 시 즉시 `KeyError: 'metadata'` 발생.

**원인**
데이터 파일 초안 작성 시 `M_schema.json`의 최종 스키마가 확정되기 전 포맷으로
작성된 채 방치됨.

**수정**
`M_schema.json` 명세에 맞게 재작성:

```json
{
  "entries": [
    {
      "id": "mem_haru_000",
      "content": "아직 특별한 대화 기록은 없다.",
      "metadata": {
        "character_id": "Haru",
        "session_id": "default",
        "turn_range": "0-0",
        "importance": 0.5,
        "tags": [],
        "location": "unknown",
        "timestamp": "2025-01-01T00:00:00+00:00"
      }
    }
  ]
}
```

---

## BUG-06 · `conversation/core/llm_client.py` — CUDA 하드코딩

**파일**: `conversation/core/llm_client.py:59`

**문제**
`_load_transformers()`에서 모델 디바이스를 `.to("cuda")`로 고정.
CUDA가 없는 dev 환경(WSL CPU 테스트 등)에서 실행 시 `AssertionError` 발생.

**원인**
`lora_train.py`는 `torch.cuda.is_available()` 분기를 갖추고 있으나
`LLMClient`에는 동일 처리가 누락됨.

**수정**
```python
self._device = "cuda" if torch.cuda.is_available() else "cpu"
self._model = self._model.to(self._device)
logger.info(f"[llm_client] 디바이스: {self._device}")
```

`_generate_transformers()`는 이미 `inputs.to(self._model.device)`를 사용하므로
추가 수정 없이 CPU/GPU 모두 동작.

---

## 미수정 항목 (계획 미완성 / 의도적 설계)

| 항목 | 이유 |
|---|---|
| 메모리 seeding 파이프라인 미연결 (`Agent.__init__`) | 어느 캐릭터의 M_default.json을 사용할지 경로 설계가 phases.md에서 미완성 |
| RAG 인덱싱 자동 실행 없음 | `WorldRetriever` 주석에 "컬렉션 없으면 빈 리스트" 명시 — 의도된 수동 초기화 설계 |
| `short_term_n` config 키 미사용 | `short_term.py` 주석에 "PromptBuilder 예산으로 대체" 명시 — 의도적 설계 변경 |
| `conversation/main.py` 병렬 초기화 | CLI가 Agent 클래스보다 먼저 작성된 구조. 리팩토링 범위 |
