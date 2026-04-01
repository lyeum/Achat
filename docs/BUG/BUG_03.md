# BUG_03.md — 배포 환경 LoRA On/Off 미지원

> 발견 경위: 배포 환경(llama-cpp-python) 구조 검토 (2026-04-01)
> 재현 조건: 기능 모드 전환 시 어댑터 교체 시도
> 증상: 런타임 어댑터 교체 API 없음 → 현재 배포 환경에서 LoRA on/off 미구현 상태
> 수정 완료: 미결 (선택지 검토 중)

---

## 현재 목표

기능 모드 중 일부(나레이션 등)에서만 LoRA 가변 어댑터(Adapter B)를 on/off 적용하는 구조.
대화 모드와 기능 모드 사이 전환 시 동일 base 모델 위에서 어댑터만 교체.

```
[Base 모델]
    ↓ 항상 적용
[Adapter A — 상시]   ← 하루 말투, 캐릭터 페르소나
    ↓ 모드에 따라 on/off
[Adapter B — 가변]   ← 나레이션 문체 등 일부 기능 전용
                       대화/일반 기능 모드: OFF (base + A만)
```

---

## 현재 상태 분석

### 개발 환경 (transformers + PEFT)

PEFT의 `set_adapter()` / `disable_adapters()` API로 런타임 hot-swap 가능.
전환 비용: 수십 ms 이내. 모델 재로딩 없음.

```python
model.set_adapter("haru")           # 대화 모드: 상시 어댑터만
model.disable_adapters()            # 기능 모드: 어댑터 전부 OFF
```

→ **개발 환경에서는 현재도 가능한 구조.**

### 배포 환경 (llama-cpp-python)

`Llama()` 초기화 시 `lora_path`, `lora_scale` 파라미터 지원 (v0.2.x~0.3.x).
그러나 **초기화 이후 런타임에서 scale 변경·어댑터 교체 API가 없음.**

```python
# 현재 배포 코드 — lora_path 자체가 없고 샘플링 파라미터만 변경
self._model = Llama(model_path=model_path, n_ctx=4096)

# mode='function' 전환은 어댑터 교체가 아니라 이것뿐:
gen_kwargs = dict(do_sample=False, repetition_penalty=1.3)
```

**즉, 배포 환경에서는 현재 on/off가 구현되어 있지 않다.**

### C++ 레이어 상태

`llama.cpp` C++ 라이브러리 자체는 런타임 어댑터 교체를 완전 지원:

```c
llama_adapter_lora_init(model, path)  // 어댑터 로드
llama_set_adapter_lora(ctx, adapter, scale)  // 런타임 적용·교체
llama_clear_adapter_lora(ctx)         // 전체 제거
```

`llama-server` HTTP 서버 모드는 이미 이 C++ API를 사용해 `POST /lora-adapters`로
재시작 없이 hot-swap을 지원한다. **Python 바인딩에만 미노출 상태.**

---

## 선택지 비교

### 선택지 1: llama-cpp-python PR #1817 머지 대기

`set_lora_adapter_scale(path, scale)` 인스턴스 메서드를 추가하는 PR.
머지 시 아래처럼 사용 가능:

```python
self._model.set_lora_adapter_scale("narration.gguf-lora", 1.0)  # ON
self._model.set_lora_adapter_scale("narration.gguf-lora", 0.0)  # OFF
```

| 항목 | 평가 |
|---|---|
| 코드 변경 | 최소 (메서드 호출 추가 + config에 lora_path 키 추가) |
| 런타임 비용 | 모델 재로딩 없음, 전환 ms 수준 |
| 현재 사용 가능 여부 | **불가** — PR 오픈 상태, 미병합 |
| 리스크 | GPU 메모리 누수 버그 리포트됨, 머지 시점 미정 |

**첨언**: 코드 변경이 가장 작고 이상적인 경로이나 타임라인 통제 불가.
머지 여부를 주기적으로 확인하고, 머지 시 즉시 적용하는 방향으로 대기하는 것이 합리적.

---

### 선택지 2: llama-server HTTP 모드로 배포 백엔드 교체

`llama-server` 바이너리를 서브프로세스로 띄우고 `llm_client.py`를 HTTP 클라이언트로 교체.

```
현재: Python → llama-cpp-python (직접 바인딩)
변경: Python → HTTP localhost → llama-server (서브프로세스)
```

```python
# llm_client.py 변경 후
requests.post("http://localhost:8080/lora-adapters", json=[{"id": 0, "scale": 1.0}])
requests.post("http://localhost:8080/completion", json={...})
```

| 항목 | 평가 |
|---|---|
| 코드 변경 | 대규모 — `llm_client.py` 전면 재작성 |
| 런타임 비용 | 재시작 없이 hot-swap, 성능 패널티 미미 |
| 현재 사용 가능 여부 | **가능** (llama.cpp 빌드 필요) |
| 리스크 | 서브프로세스 생명주기 관리, 포트 충돌, 배포 복잡도 증가 |

**첨언**: C++ 레이어가 이미 안정적으로 지원하므로 기술적으로 가장 확실한 선택지.
그러나 아키텍처 변경이 크고 Windows 배포에서 llama-server 바이너리 동봉 및 실행 관리가
추가로 필요해 현재 배포 규모 대비 오버엔지니어링에 가까움.

---

### 선택지 3: lora_scale=0.0 초기 로딩 + C 바인딩 직접 호출

`lora_scale=0.0`으로 초기화 후, C 레벨 함수(`llama_set_adapter_lora`)를 ctypes로 직접 호출.

```python
import ctypes
lib = ctypes.cdll.LoadLibrary("libllama.so")
lib.llama_set_adapter_lora(ctx_ptr, adapter_ptr, ctypes.c_float(1.0))
```

| 항목 | 평가 |
|---|---|
| 코드 변경 | 중간 — ctypes 래퍼 작성 필요 |
| 런타임 비용 | 재로딩 없음 |
| 현재 사용 가능 여부 | 이론상 가능, 검증 필요 |
| 리스크 | llama-cpp-python 내부 포인터 구조 의존, 버전마다 깨질 수 있음. 유지보수 부담 큼 |

**첨언**: 핵이 맞고 버전 호환성이 매우 취약함. 선택지 1 머지 전 임시 방편으로도
권장하지 않음. 프로덕션 코드에 ctypes 직접 호출은 디버깅 비용이 과도함.

---

### 선택지 4: 세션 단위 reload (현재 구조 유지)

나레이션 모드 진입을 "턴마다"가 아니라 "세션 시작 시 1회"로 제한.
`_unload_llm()` → `Llama(lora_path=...)` 패턴으로 세션 경계에서만 교체.

```python
# 나레이션 세션 시작 시
self._unload_llm()
self._model = Llama(model_path="base.gguf", lora_path="narration.gguf-lora")

# 대화 세션 복귀 시
self._unload_llm()
self._model = Llama(model_path="merged_chat.gguf")  # 상시 어댑터 병합본
```

| 항목 | 평가 |
|---|---|
| 코드 변경 | 최소 — `_rebuild_agent()` 분기 추가 수준 |
| 런타임 비용 | 전환 시 5~10초 딜레이, RAM 피크 없음 (`_unload_llm()` 선행) |
| 현재 사용 가능 여부 | **즉시 가능** |
| 리스크 | 나레이션과 대화를 수시로 오가는 구조에서는 사용성 저하 |

**첨언**: 나레이션이 "대화 도중 매 턴 전환"이 아닌 "씬(세션) 단위 고정" 구조라면
실용적으로 가장 현실적인 선택지. OOM 방지는 이미 구현되어 있어 추가 리스크 없음.

---

### 선택지 5: 프롬프트 엔지니어링 (LoRA 미사용)

어댑터 교체 문제를 구조적으로 우회하는 접근. 역할 전환을 가중치가 아니라
시스템 프롬프트 교체로 처리하며, 기능 모드의 자연어 출력 품질도 프롬프트로 제어한다.

**적용 범위별 평가:**

| 역할 | 프롬프트만으로 가능한 품질 | 한계 |
|---|---|---|
| **나레이션** | 기능적으로 동작. 3인칭 묘사·장면 전환 생성 가능 | 문체 일관성이 호출마다 흔들릴 수 있음 |
| **기능 모드 파라미터 추출** | 충분. 현재도 `greedy + repetition_penalty` 조합으로 JSON 추출 작동 중 | 추가 개선 불필요 |
| **기능 결과 요약/응답** | Layer F가 이미 최근 작업을 시스템 프롬프트에 주입해 캐릭터가 인지하도록 설계됨 | 3B 모델 한국어 요약 품질은 프롬프트 튜닝으로 상당 부분 보완 가능 |
| **prompt_convert 변환** | 크롤링+프롬프트 파이프라인으로 이미 구현됨 | 이미지 모델 특화 키워드 문법은 base 모델 사전지식 의존 |
| **대화 (하루 말투)** | 기본 동작은 되나 반말 일관성·단답형 유지가 프롬프트만으로 취약 | LoRA 없이는 캐릭터 이탈 빈도 높아짐 — 대화 영역은 LoRA 유지 필요 |

**few-shot 프롬프트 삽입 방식:**

나레이션이나 기능 요약처럼 문체가 중요한 경우, 시스템 프롬프트에 예시 2~3개를 직접 포함하는
few-shot 방식으로 LoRA 없이 스타일을 유도할 수 있다.

```python
# narrator.py — 현재 구조에 few-shot 예시 삽입 형태
_ARRIVAL_PROMPT = """\
아래 예시처럼 장면을 3인칭 서술체로 묘사해.

[예시1]
등대 위로 빛이 느리게 돌았다. 바람은 짭짤했고, 파도 소리가 낮게 깔렸다.

[예시2]
카페 안은 조용했다. 창가에 빛이 들어와 먼지를 느릿하게 날렸다.

---
캐릭터: {char_name} / 장소: {location_name}
...
"""
```

| 항목 | 평가 |
|---|---|
| 코드 변경 | 최소 — 프롬프트 문자열 수정만 필요 |
| 런타임 비용 | 0 — 모델 재로딩·어댑터 교체 없음 |
| 현재 사용 가능 여부 | **즉시 가능** |
| 리스크 | 스타일 일관성은 LoRA 대비 약함. 대화 영역은 LoRA 유지 필요 |

**첨언**: 배포 환경에서 어댑터 전환 비용을 완전히 없애는 유일한 방법.
기능 모드 자연어 출력(요약·응답)과 나레이션은 프롬프트 엔지니어링이 1차 해결책이고,
실제 품질이 부족하다고 확인된 후에 LoRA를 추가하는 순서가 투자 효율이 높음.
**대화(캐릭터 말투) 영역은 LoRA가 명확히 유효하므로 이 선택지의 대체 대상이 아님.**

---

## 현재 권고 방향

```
단기 (지금 적용):     선택지 5 (프롬프트 엔지니어링) + 선택지 4 (세션 단위 reload) 병행
                       - 나레이션·기능 요약: 프롬프트 few-shot으로 먼저 품질 검증
                       - 나레이션 모드 전환: 씬 단위로 제한해 reload 딜레이 감수
                       - 대화 LoRA는 유지

중기 (PR 머지 대기):  선택지 1 모니터링
                       https://github.com/abetlen/llama-cpp-python/pull/1817
                       머지 시 llm_client.py 소규모 수정으로 즉시 업그레이드 가능

장기 (기능 확장 시):  선택지 2 검토
                       나레이션·기능 모드가 복잡해져 프롬프트 한계 도달 확인 후
                       llama-server 전환 또는 LoRA 분리 재평가
```

---

## 관련 파일

| 파일 | 내용 |
|---|---|
| `conversation/core/llm_client.py` | LLM 백엔드 추상화, `lora_path` 파라미터 추가 위치 |
| `conversation/narrator.py` | 나레이션 프롬프트 — few-shot 삽입 대상 |
| `tools/prompt_converter.py` | 기능 모드 자연어 변환 — 프롬프트 파이프라인 |
| `conversation/core/prompt_build.py` | Layer F — 기능 결과 컨텍스트 주입 |
| `ui_ux/bridge.py` | `_unload_llm()`, `_rebuild_agent()` — 세션 단위 교체 진입점 |
| `pyproject-deploy.toml` | `llama-cpp-python>=0.3.0` 의존성 |
| `config.py` | `adapter_path` 키 (개발 환경), 배포 환경에 `lora_path` 추가 필요 |
