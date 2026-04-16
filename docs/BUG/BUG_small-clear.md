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

---

## BUG-07 · `config.py` / `rag/retrieve.py` — vdb_threshold 0.7 과도하게 엄격

**발견**: Phase 2/3 실환경 검증 (2026-03-16)

**문제**
`vdb_threshold=0.7`로 설정 시 bge-m3 한국어 임베딩에서 세계관 관련 질문조차 threshold를 통과하지 못해
RAG 결과가 항상 빈 리스트로 반환됨.

**원인**
bge-m3 코사인 유사도 실측값:
- 세계관 관련 질문 (등대지기 전설): ~0.559
- 무관한 질문 (날씨, 기억): ~0.380~0.483
- 0.7은 양쪽 모두 걸러냄

**수정**
`config.py` dev/deploy 모두 `vdb_threshold: 0.52` 로 변경.
0.52 기준: 관련 쿼리(~0.55+) 통과 / 무관 쿼리(~0.48-) 차단.

---

## BUG-08 · `rag/sources/world/*.md` — 세계관 문서 내용 불일치

**발견**: Phase 3 실환경 검증 (2026-03-16)

**문제**
`place.md`, `story.md`, `culture.md`에 일반 판타지 마을 내용이 작성되어 있었음.
`W_sea.yaml`이 바다 세계관을 지정하고 있으나 RAG 소스 문서가 불일치.
"등대지기 전설에 대해 들어봤어?" 질문에 관련 문서가 없어 RAG 히트 0건.

**수정**
세 파일 모두 바다 마을 세계관으로 교체:
- `place.md`: 해변/방파제/등대/항구 시장/마을 카페
- `story.md`: 마을 역사/등대지기 전설(100년 전 노인, 폭풍 속 불빛 유지)/태풍 사건
- `culture.md`: 생활방식/해맞이·등대축제·어부의날/사회규칙

---

## BUG-09 · `eval/verify_phases.py` — VDB 검증 타이밍 오류

**발견**: Phase 2 검증 스크립트 초안 작성 시 (2026-03-16)

**문제**
10번째 턴에서 "내 이름 기억해?" 질문으로 VDB Layer C 삽입을 검증하려 했으나,
같은 턴(10번째)에서 요약 저장이 실행되므로 저장 전에 VDB 쿼리가 먼저 실행됨.
→ VDB가 비어있어 항상 0건.

**수정**
시나리오를 12턴으로 확장:
- 1~10턴: 대화 진행 + 10번째 턴 종료 후 요약 저장
- 11번째 턴: 세계관 질문 (RAG 검증)
- 12번째 턴: "내 이름 기억해?" (VDB Layer C 검증 — 저장 이후)

---

## BUG-10 · `training/lora_train.py` — best loss 저장 없음

**발견**: Phase 5 학습 완료 후 (2026-03-16)

**문제**
학습 마지막 스텝 가중치를 `adapter/`에 저장하는 구조.
`save_total_limit=2`로 best checkpoint가 삭제될 수 있음.
validation set 없어 과적합 감지 불가.

**수정**
`--eval_split` 옵션 추가 (기본값 0.1):
- `train_test_split(test_size=0.1, seed=42)`로 검증셋 분리
- `eval_strategy="steps"`, `load_best_model_at_end=True`
- `metric_for_best_model="loss"`, `greater_is_better=False`
- `save_total_limit=3` (best + 최근 2개 유지)

---

## BUG-11 · `eval/` 3개 파일 — `device_map="auto"` + PeftModel 충돌

**발견**: Phase 5 실환경 평가 (2026-03-17)

**문제**
`ai_tell_checker.py`, `memory_test.py`, `speed_bench.py` 에서
`device_map="auto"` 로 베이스 모델 로드 후 `PeftModel.from_pretrained()` 호출 시
accelerate `get_balanced_memory()` 내부에서 `set`이 unhashable로 처리되어 TypeError 발생.

**원인**
accelerate 버전 이슈. `device_map="auto"` 상태에서 PEFT 어댑터 로드 시
`no_split_module_classes`가 set 타입으로 전달되어 hashability 체크 실패.

**수정**
`device_map="auto"` 제거, `.to(device)` 명시 + `PeftModel.from_pretrained(..., device_map={"": device})` 로 교체.

```python
device = "cuda" if torch.cuda.is_available() else "cpu"
model = AutoModelForCausalLM.from_pretrained(...).to(device)
model = PeftModel.from_pretrained(model, adapter_path, device_map={"": device})
```

---

## BUG-12 · `eval/` 3개 파일 — `torch_dtype` deprecated 경고

**발견**: Phase 5 실환경 평가 (2026-03-17)

**문제**
`AutoModelForCausalLM.from_pretrained(torch_dtype=...)` 파라미터명이 신버전 transformers에서 deprecated.
매 실행마다 `torch_dtype is deprecated! Use dtype instead!` 경고 출력.

**수정**
`torch_dtype=torch.bfloat16` → `dtype=torch.bfloat16` 으로 교체 (3개 파일 동일 적용).

---

## BUG-13 · `training/lora_train.py` — eval 중 CUDA error: unknown error

**발견**: lora_haru_v4 학습 (2026-03-17)

**문제**
`eval_split=0.1` 설정 시 step 100 eval 구간에서 `torch.AcceleratorError: CUDA error: unknown error` 발생.
학습 자체는 정상이었으나 eval forward pass 시점에 크래시.

**원인**
VRAM 8GB 환경에서 학습 중 gradient_checkpointing으로 activation을 해제하지만,
eval 시점에는 gradient_checkpointing 비활성 → 전체 activation이 VRAM에 올라오며 초과.

**대응**
- 단기: `--eval_split 0` 으로 eval 비활성화 후 학습 진행 (best checkpoint 수동 선택)
- 학습 완료 후 v3 실측 기준 epoch 3~4 근처 checkpoint 사용

---

## BUG-14 · `training/train_monitor.py` — 최종 보고 eval 기록 오탐

**발견**: LoRA_v9 (λ=150) 학습 완료 후 (2026-03-23)

**문제**
학습 정상 완료 후 모니터 최종 보고에서 "eval 기록 없음 (학습이 매우 짧게 진행됐거나 eval_split=0)"이 출력됨.
실제로는 eval_loss가 step 700~900 구간에서 8회 기록됐으나 최종 보고에만 반영되지 않음.

**원인**
`train_monitor.py`의 최종 보고는 `state_path = output_dir / "trainer_state.json"`을 직접 읽는다.
`lora_train.py`는 학습 종료 후 `checkpoint-*` 디렉토리를 전부 `shutil.rmtree`로 삭제하는데,
HuggingFace Trainer가 `trainer_state.json`을 `output_dir/` 루트가 아닌 `checkpoint-N/` 내부에만 기록하므로
모든 체크포인트 삭제 시 `trainer_state.json`도 함께 사라짐.
최종 보고 시점(`trainer.train()` 반환 직후)에는 파일이 이미 없어 `load_log_history()`가 빈 리스트를 반환.

**영향**
- 실시간 모니터링(polling 구간) 동작은 정상 — eval_loss 추적 및 조기 종료 판단에는 무영향.
- 최종 보고 섹션 ①만 eval 데이터 없이 출력됨 (오보, 기능 저하 없음).

**수정 완료 ✅ (2026-03-28)**
`lora_train.py` 체크포인트 삭제 루프 직전에 `trainer.save_state()` 호출 추가.
`output_dir/trainer_state.json` 이 보존되어 `train_monitor` 최종 보고가 정상 동작.

---

## BUG-15 · `ui_ux/qml/main.qml` — thinking indicator `...` 잔류

**발견**: MVP 대화 테스트 (2026-03-23)

**문제**
캐릭터 응답 전에 `...` 플레이스홀더가 표시된 뒤, 응답 수신 후에도 `...`가 목록에 남아 있었음.
사용자 입력 내용에도 `...`가 덧붙어 저장되는 현상 동반.

**원인**
`_on_response(role, content)` → `_on_done()` 순서로 신호가 발생.
`onStatusChanged("ready")` 핸들러에서 `messageModel.last.content === "..."` 확인 후 제거하려 했으나,
`_on_response` 시점에 이미 실제 응답으로 교체되어 제거 조건이 항상 false.

**수정** ✅ (2026-03-23)
`onMessageAdded` 핸들러에서 `role === "assistant"` 직전 마지막 항목이 `"..."`이면 제거하도록 변경.

```javascript
function onMessageAdded(role, content) {
    if (role === "assistant" && messageModel.count > 0) {
        var last = messageModel.get(messageModel.count - 1)
        if (last.content === "...") messageModel.remove(messageModel.count - 1)
    }
    messageModel.append({ "role": role, "content": content })
    ...
}
```

---

## BUG-16 · `conversation/core/prompt_build.py` — Layer A 학습/런타임 형식 불일치

**발견**: MVP 대화 테스트 (2026-03-23)

**문제**
affection 93 (intimate tier) 상태에서도 단답형 고착, tone 변화 미반영, 맥락 이해 불가.

**원인**
학습 데이터 system prompt는 전부 평문 단락 형식:
> `"조용하고 차분한 태도로 대화한다. 반말을 쓰고 단답형이 많다. ..."`

런타임 `_layer_a()`는 `[캐릭터 설명]` / `[말투]` / `[현재 감정 상태]` 섹션 구조로 조립.
모델이 런타임 형식을 학습 중 한 번도 본 적 없어 affection tier 지시문 무시,
섹션 헤더를 대화 맥락으로 오인하는 것으로 추정.

**수정** ✅ (2026-03-23)
`_layer_a()`를 섹션 구조 → 평문 단락으로 전면 재작성.
name / description / speech_style / tone / mood_hint / rules_brief를 공백으로 이어붙임.

```python
return " ".join(parts)  # 헤더 없는 단일 평문 단락
```

---

## BUG-17 · `conversation/core/prompt_build.py` — YAML rules 무시 (학습/추론 프롬프트 불일치) ✅

**발견**: 대화 품질 개선 항목 C(CH_Haru.yaml rules 강화) 적용 후 정합성 검토 (2026-03-29)

**파일**: `conversation/core/prompt_build.py:121`

**문제**
`_layer_a()` 내부에서 캐릭터 YAML의 `rules` 필드를 실제로 읽지 않고 하드코딩된 요약 문자열을 사용:

```python
# 수정 전
rules_list = c.get("rules", [])
rules_brief = "캐릭터를 벗어나는 발언, AI임을 언급하는 발언, \"물론이죠\"·\"좋은 질문\" 같은 표현은 하지 않는다." if rules_list else ""
```

→ CH_Haru.yaml과 CH_Seonjae.yaml에 추가한 언어 규칙·문법 규칙·stranger tier 제한 3개 항목이 런타임 시스템 프롬프트에 반영되지 않음.

**부수 문제**: 이름 형식이 `"너의 이름은 {name}이다."` 로 되어 있었으나, `build_sft_from_feedback.py`의 학습 데이터 생성 형식은 `"너는 {name}이다."` → 학습/추론 프롬프트 불일치.

**원인**
rules 필드가 하드코딩으로 고정된 채 방치됨. `build_sft_from_feedback.py`는 YAML rules를 직접 join해서 사용하므로 학습 데이터 형식과 차이 발생.

**수정** ✅ (2026-03-29)

```python
# 수정 후: 문자열 리스트 rules → 직접 join (build_sft_from_feedback.py와 동일 포맷)
rules_list = c.get("rules", [])
if rules_list and all(isinstance(r, str) for r in rules_list):
    rules_brief = " ".join(rules_list)
elif rules_list:
    # dict 타입 rules(CH_default.yaml 등) — 폴백 요약
    rules_brief = "캐릭터를 벗어나는 발언, AI임을 언급하는 발언, \"물론이죠\"·\"좋은 질문\" 같은 표현은 하지 않는다."
else:
    rules_brief = ""

# 이름 형식 통일
parts.append(f"너는 {name}이다.")  # "너의 이름은" → "너는"
```

CH_Haru.yaml / CH_Seonjae.yaml의 실제 rules 내용이 런타임 Layer A에 포함되도록 수정.

---

## BUG-18 · `memory/summarizer.py` — `score_importance()` mid 키워드 분기 죽은 코드 ✅

**발견**: 대화 품질 개선 항목 D(summarizer.py 이름 importance 보완) 이후 정합성 검토 (2026-03-29)

**파일**: `memory/summarizer.py:73`

**문제**
```python
# 수정 전
score = 0.5  # 기본값 — 키워드 없어도 일단 저장
for kw in _HIGH_KEYWORDS:
    if kw in summary:
        score = max(score, 0.85)
        break
if score < 0.5:     # ← 항상 False (score 기본값이 0.5이므로)
    for kw in _MID_KEYWORDS:
        if kw in summary:
            score = max(score, 0.6)
            break
```

`score` 초기값이 `0.5`이므로 `if score < 0.5:` 조건은 항상 False → mid 키워드(취미/감정/날짜 등) 분기가 실행되지 않음.

**영향**
- high 키워드 없고 mid 키워드만 있는 요약 → 0.6이 아닌 0.5로 저장
- VDB 저장 기준(score >= 0.5)은 만족하므로 데이터 손실은 없음
- 기억 중요도가 과소평가되어 쿼리 필터(`where importance >= 0.5`)를 통과하나 순위가 낮아질 수 있음

**수정** ✅ (2026-03-29)

```python
# 수정 후
if score == 0.5:  # high 키워드 미매칭 시에만 mid 키워드 검사
    for kw in _MID_KEYWORDS:
        if kw in summary:
            score = max(score, 0.6)
            break
```

mid 키워드(취미/감정/날짜 등) → 0.6 / high 키워드(이름/약속/갈등 등) → 0.85 / 무키워드 → 0.5 로 정확하게 동작.

---

## BUG-19 · `agent/core.py` — `prompt_convert` regex fallback 한국어 탐욕적 캡처 + content 비정상 미감지 ✅

**발견**: 실행 로그 분석 (2026-03-29)

**파일**: `agent/core.py` (prompt_convert fallback 블록)

**문제 1 — regex 탐욕적 캡처**
```python
# 수정 전
r"(stable[\s\-]diffusion[\s\w\.]*|sdxl[\s\w\.]*...)"
# Python \w는 유니코드 포함 → 한국어도 매칭됨
# 입력: "stable diffusion 모델에 고양이를 그려달라고..."
# 결과: model = 'stable diffusion 모델에 고양이를 그려달라고...' (전체 문장)
```

**문제 2 — content 비정상 미감지**
```python
# 수정 전
if not params.get("content"):
    params["content"] = user_input
# content = '고양이 그리기 request for Stable Diffusion model' (영어 hallucination, 비어있지 않음)
# → 비어있지 않으므로 fallback 미트리거
```

**수정** ✅ (2026-03-29)

regex를 ASCII 전용으로 교체하고, `_is_content_valid()` / `_korean_ratio()` 모듈 레벨 함수 추가:

```python
# 수정 후 — ASCII 전용 캡처
_PROMPT_CONVERT_MODEL_RE = re.compile(
    r"(stable[\s\-]diffusion(?:\s+[a-zA-Z0-9._-]+){0,2}|...)",
    re.IGNORECASE,
)

def _korean_ratio(text: str) -> float:
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\uAC00" <= c <= "\uD7A3") / len(chars)

def _is_content_valid(content: str, src: str) -> bool:
    if not content:
        return False
    src_ko = _korean_ratio(src)
    # src 30% 이상 한국어인데 content가 src 한국어 비율의 50% 미만 → 비정상
    if src_ko >= 0.3 and _korean_ratio(content) < src_ko * 0.5:
        return False
    return True
```

**검증**: `test_function_tools.TestPromptConvertFallbackUtils` 10개 테스트 (198개 전체 통과)

---

## BUG-20 · `ui_ux/bridge.py` — 캐릭터/세계관 변경 시 채팅창 미초기화 ✅

**발견**: Phase 7-A chatReset 구현 (2026-04-16)

**파일**: `ui_ux/bridge.py` (`changeCharacter`, `changeWorld`)

**문제**
`changeCharacter()` / `changeWorld()` 호출 후 QML 채팅창이 초기화되지 않아
이전 캐릭터/세계관의 대화 버블이 그대로 남아 있었음.
동시에 새로 활성화된 세션의 이전 기록도 복원되지 않음.

**원인**
세션 교체 후 UI에 알릴 시그널이 없었음.
`chatReset` 시그널 자체가 미정의 상태였음.

**수정** ✅ (2026-04-16)

```python
# Signal 추가
chatReset = Signal("QVariantList")  # 캐릭터/세계관 변경 시 채팅창 초기화 + 이전 기록 로드

# changeCharacter() / changeWorld() 종료 시 emit
self.chatReset.emit(self.getSessionHistory())
```

`getSessionHistory()` — `@Slot(result="QVariantList")` 신규 추가.
`session.dialogue_log` 최근 `_HISTORY_DISPLAY_TURNS * 2` (= 20) 메시지를 반환.
`**...**` / `*...*` 나레이션 분할을 포함하므로 재로드 시 bubble 타입도 올바르게 복원.

---

## BUG-21 · `ui_ux/bridge.py` — 앱 재시작 시 이전 대화 기록 미복원 ✅

**발견**: Phase 7-A 세션 영속화 구현 (2026-04-16)

**파일**: `ui_ux/bridge.py` (`_rebuild_agent`)

**문제**
앱 재시작 후 `activate()` / `activate_for_world()`로 기존 세션을 불러와도
`session.dialogue_log`가 빈 리스트로 초기화되어 이전 대화 내용이 사라짐.

**원인**
`SessionState`는 `dialogue_log`를 런타임 전용으로 취급해 저장하지 않음.
대화 기록은 `dialogue.json`에 별도 저장되지만, `_rebuild_agent()`에서 복원하지 않음.

**수정** ✅ (2026-04-16)

```python
# _rebuild_agent() 내 swap_character() 이후
if self._agent.session is not None and state.session_id:
    dialogue = self._session_manager.load_dialogue(state.char_id, state.session_id)
    if dialogue:
        self._agent.session.dialogue_log = dialogue
```

`SessionManager.save_dialogue()` / `load_dialogue()` — `dialogue.json` R/W 신규 추가.
`_on_done()` 및 `new_session()` 에서 `save_dialogue()` 호출.

---

## BUG-22 · `ui_ux/bridge.py` — `changeWorld()` 동일 세계관 전환 시 dialogue_log 손실 ✅

**발견**: Phase 7-A 구현 중 (2026-04-16)

**파일**: `ui_ux/bridge.py` (`changeWorld`)

**문제**
같은 세계관에서 act(시나리오)만 변경할 때 `swap_persona()` 내부에서
`session.dialogue_log`가 덮어써져 이전 대화 내용이 모두 사라졌음.

**원인**
`swap_persona()`가 내부적으로 새 `ConversationSession`을 생성하거나
`dialogue_log`를 초기화하는 경로가 있었고, 호출 전 dialogue를 보존하지 않음.

**수정** ✅ (2026-04-16)

```python
# swap_persona() 호출 전 dialogue 저장
old_dialogue = list(getattr(self._agent.session, "dialogue_log", []) or [])
# ...swap_persona() 호출...
new_session.dialogue_log = old_dialogue   # 복원
```

---

## BUG-23 · `tests/test_bridge_slots.py` — `_rebuild_agent` 테스트에서 `_session_manager` 누락 ✅

**발견**: `_rebuild_agent()` 수정 후 테스트 실행 시 (2026-04-16)

**파일**: `tests/test_bridge_slots.py` (`test_rebuild_calls_swap_character`)

**문제**
`AttributeError: 'ChatBridge' object has no attribute '_session_manager'`

**원인**
`ChatBridge.__new__(ChatBridge)`로 인스턴스를 생성하면 `__init__`이 실행되지 않아
`_session_manager`가 설정되지 않음.
`_rebuild_agent()`가 `load_dialogue()` 호출을 추가하면서 `_session_manager` 접근이 생겼으나
테스트 setup에서 해당 속성이 mock으로 주입되지 않았음.

**수정** ✅ (2026-04-16)

```python
fake_sm = MagicMock()
fake_sm.load_dialogue.return_value = []
bridge_inst._session_manager = fake_sm
```

---

## 미수정 항목 (계획 미완성 / 의도적 설계)

| 항목 | 이유 |
|---|---|
| 메모리 seeding 파이프라인 미연결 (`Agent.__init__`) | 어느 캐릭터의 M_default.json을 사용할지 경로 설계가 phases.md에서 미완성 |
| RAG 인덱싱 자동 실행 없음 | `WorldRetriever` 주석에 "컬렉션 없으면 빈 리스트" 명시 — 의도된 수동 초기화 설계 |
| `short_term_n` config 키 미사용 | `short_term.py` 주석에 "PromptBuilder 예산으로 대체" 명시 — 의도적 설계 변경 |
| `conversation/main.py` 병렬 초기화 | CLI가 Agent 클래스보다 먼저 작성된 구조. 리팩토링 범위 |
