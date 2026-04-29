# BUG_02.md — LLM OOM (Out of Memory)

> 발견 경위: 실환경 캐릭터 전환 테스트 (2026-03-30)
> 재현 조건: 대화 중 캐릭터 전환(changeCharacter) 시도
> 증상: 프로그램 강제 종료 또는 OS OOM-killer 발동
> 수정 완료: 2026-03-30

---

## BUG-02-A · `ui_ux/bridge.py` — 캐릭터 전환 시 LLM 이중 적재 OOM ✅

**파일**: `ui_ux/bridge.py` — `_rebuild_agent()`

### 증상

```
changeCharacter("다른_캐릭터") 호출
→ out of memory / 프로세스 강제 종료
```

### 발생 원인

`changeCharacter()` → `_rebuild_agent()` → `Agent.from_session()` 순서로 새 Agent를 생성할 때
기존 Agent의 LLM 모델 객체를 먼저 해제하지 않았다.

```
[기존 LLM] 메모리 점유 중 (Python 참조 유지)
     ↓
[신규 LLM] Agent.__init__() → LLMClient() → 모델 로드 시작
     ↓
두 모델이 동시에 메모리에 존재 → OOM
```

**모델별 메모리 사용량 (참고)**

| 백엔드 | 모델 | 메모리 |
|---|---|---|
| `transformers` | Qwen2.5-3B bfloat16 | ~6 GB RAM |
| `llama_cpp` | Qwen2.5-3B Q4_K_M | ~2.5 GB RAM |

캐릭터 전환 순간 `transformers` 기준 최대 **~12 GB** 동시 점유.

### 동일 위험이 있는 경로

`_rebuild_agent()`를 호출하는 슬롯이 3곳이며 모두 동일한 OOM 위험이 있었다:

| 슬롯 | 호출 경로 |
|---|---|
| `changeCharacter(char_id)` | 캐릭터 교체 |
| `newSession(keep_memory)` | 새 세션 시작 |
| `resetCharacter(char_id)` | 현재 캐릭터 초기화 후 재시작 |

### 해결 방법

`_rebuild_agent()` 내부에서 새 Agent 생성 **직전** `_unload_llm()`을 호출해
기존 LLM 모델을 명시적으로 해제한다.

**추가된 `_unload_llm()` 로직:**

```python
def _unload_llm(self) -> None:
    import gc
    llm    = getattr(self._agent, "llm", None)
    backend = getattr(llm, "backend", "")
    model  = getattr(llm, "_model", None)

    # llama_cpp: C 힙까지 해제하는 close() 필수
    if backend == "llama_cpp" and model is not None:
        model.close()

    # transformers: del + GPU 캐시 해제
    if backend == "transformers" and model is not None:
        del llm._model
        llm._model = None
        torch.cuda.empty_cache()   # GPU 사용 시

    del model
    gc.collect()
```

**`_rebuild_agent()` 수정 후:**

```python
def _rebuild_agent(self, state: SessionState) -> None:
    self._unload_llm()          # ← 핵심: 기존 모델 먼저 해제
    ...
    self._agent = Agent.from_session(state, cfg)
```

### 적용 범위

`_unload_llm()`은 `_rebuild_agent()` 단일 진입점에서만 호출되므로
`changeCharacter` / `newSession` / `resetCharacter` 세 슬롯 모두 자동으로 보호된다.

### 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `ui_ux/bridge.py` | `_unload_llm()` 메서드 추가 + `_rebuild_agent()` 앞에서 호출 |

---

---

## BUG-02-B · RAM 과점유 — 임베딩 모델 이중 로드 + 즉시 로드 ✅

> 발견 경위: 앱 구동 중 OOM 재발 (2026-04-03)
> 증상: 앱 시작 시 RAM ~2,730 MB 점유 → 대화 중 OOM 발생 가능성 상승

---

### 앱 구동 시 RAM 점유 구조 (측정값 기준)

| 컴포넌트 | RAM 점유 | 작동 방식 |
|---|---|---|
| PyTorch / CUDA 런타임 | +491 MB | import torch 시점에 CUDA 드라이버 초기화, 내부 할당자 준비 |
| LLMClient (Qwen 3B + LoRA) | +599 MB | 모델 가중치를 GPU(VRAM)에 적재. CPU RAM에는 tokenizer + 모델 메타데이터만 잔류 |
| ChromaDB PersistentClient | +432 MB | SQLite + HNSW 인덱스 파일 매핑, 내부 Rust 라이브러리 초기화 |
| **bge-m3 임베딩 모델** | **+1,167 MB** | `SentenceTransformer` CPU 로드. 모델 전체가 RAM 상주 |
| **합계 (수정 전)** | **~2,730 MB** | |

#### VRAM 점유 (별도)

| 항목 | VRAM |
|---|---|
| Qwen 3B + LoRA 어댑터 | ~7,528 MB / 8,150 MB |
| 임베딩 모델 (수정 전 GPU) | ~600 MB 추가 → OOM |
| 임베딩 모델 (수정 후 CPU) | 0 MB |

---

### 발생 원인

#### 원인 1 — 임베딩 모델 GPU 이중 로드

`LongTermMemory`와 `WorldRetriever`가 각자의 `__init__`에서 독립적으로
`SentenceTransformerEmbeddingFunction`을 생성했다.
기본 device가 GPU였으므로 동일 모델이 VRAM에 두 번 올라갔다.

```
LongTermMemory.__init__()  → bge-m3 GPU 로드 (~600 MB VRAM)
WorldRetriever.__init__()  → bge-m3 GPU 로드 또 한 번 (~600 MB VRAM)
LLMClient 로드              → 7,528 MB VRAM
합계                        → 8,728 MB > 8,150 MB (RTX 5060) → OOM
```

#### 원인 2 — 앱 시작 시점 즉시 로드

두 클래스 모두 `__init__`에서 임베딩 모델을 바로 로드했다.
실제로 메모리 조회가 필요한 시점은 대화 수십 턴 이후인데,
앱이 열리는 순간부터 1.1 GB RAM이 점유되었다.

---

### 해결 방법

#### 해결 1 — 임베딩 함수 싱글턴 (`memory/embedding.py` 신규)

`(model_name, device)` 조합을 키로 캐싱해 동일 인스턴스를 공유한다.

```python
# memory/embedding.py
_cache: dict[tuple[str, str], object] = {}
_lock = Lock()

def get_embedding_function(model_name: str, device: str = "cpu"):
    key = (model_name, device)
    if key not in _cache:
        with _lock:
            if key not in _cache:
                ef = SentenceTransformerEmbeddingFunction(model_name=model_name, device=device)
                _cache[key] = ef
    return _cache[key]
```

#### 해결 2 — Lazy 로딩

`__init__`에서 로드하지 않고 첫 번째 실제 사용 시점에만 로드한다.

```python
# LongTermMemory / WorldRetriever 공통 패턴
def __init__(self, config):
    self._ef = None          # 로드 안 함
    ...

def _load_ef(self):
    if self._ef is None:
        from memory.embedding import get_embedding_function
        self._ef = get_embedding_function(
            self.cfg["embedding_model"],
            self.cfg.get("embedding_device", "cpu"),
        )
    return self._ef
```

#### 해결 3 — 임베딩 device CPU 고정 (config.py)

```python
"embedding_device": "cpu",   # dev / deploy 공통
```

LLM이 VRAM 대부분을 점유하는 환경에서 임베딩을 GPU에 올리면 OOM이 확실하다.
임베딩 추론은 배치 크기가 작고(query 1건) 지연 허용 범위가 넓으므로 CPU로 충분하다.

---

### 수정 후 RAM 점유 구조

| 시점 | RAM |
|---|---|
| 앱 초기화 완료 (임베딩 미로드) | **~1,027 MB** |
| 첫 메모리 조회 발생 (수십 턴 이후) | ~2,590 MB |
| WorldRetriever 추가 호출 | +0 MB (싱글턴 재사용) |

앱 시작 기준 RAM이 **2,730 MB → 1,027 MB** (약 1.7 GB 절감).

---

### 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `memory/embedding.py` | 신규 — 싱글턴 캐싱, 기본 device=cpu |
| `memory/long_term.py` | `__init__` 즉시 로드 제거, `_load_ef()` lazy 추가 |
| `rag/retrieve.py` | 동일 |
| `config.py` | `embedding_device: "cpu"` 추가 (dev / deploy) |

---

### 추가 개선 가능성

| 방법 | 절감량 | 트레이드오프 |
|---|---|---|
| 임베딩 모델을 경량 모델로 교체 (`paraphrase-multilingual-MiniLM-L12-v2`) | ~456 MB | 한국어 검색 품질 소폭 저하 |
| ChromaDB를 in-process 대신 HTTP 서버 모드로 분리 | ~200 MB (메인 프로세스 기준) | 별도 프로세스 관리 필요 |
| 임베딩 모델 unload 후 재로드 (사용 후 해제) | 최대 1,167 MB | 재로드 지연 (~3초) |
| LLM tokenizer를 필요 시점에만 import | ~30 MB | 코드 변경 최소 |

현재 기준 가장 효과 대비 위험이 낮은 추가 개선은 **경량 임베딩 모델 교체**이며,
한국어 유사도 정확도를 실측한 뒤 판단하는 것이 적합하다.

---

---

## BUG-02-B2 · VRAM 과점유 — LLM int4 NF4 양자화 ✅

> 작업일: 2026-04-03

### 배경

임베딩 싱글턴 + Lazy 로딩으로 RAM은 절감했으나 VRAM은 그대로였다.

| 항목 | VRAM |
|---|---|
| Qwen2.5-3B + LoRA (bfloat16, 수정 전) | ~7,528 MB |
| VRAM 총 용량 (RTX 5060 Ti 8 GB) | 8,150 MB |
| **여유 헤드룸 (수정 전)** | **622 MB** |

헤드룸이 622 MB에 불과해 CUDA 작업 버퍼 + ChromaDB 연산 오버헤드만으로도
OOM에 도달할 수 있는 상태였다.

---

### 해결 방법 — int4 NF4 양자화 (bitsandbytes)

4-bit NormalFloat(NF4) 양자화를 적용해 모델 가중치를 fp16/bf16 → 4-bit로 압축한다.
`bnb_4bit_use_double_quant=True`로 양자화 상수 자체도 2차 양자화하여 추가 절감한다.

```python
# conversation/core/llm_client.py
from transformers import BitsAndBytesConfig

quantization = self.cfg.get("quantization", "int4")  # "int4" | "int8" | "none"
if quantization == "int4" and self._device == "cuda":
    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_cfg,
        low_cpu_mem_usage=True,
    )
```

```python
# config.py (dev)
"quantization": "int4",
```

#### GPU 호환성 — RTX 5060 Ti (Blackwell)

초기에 Blackwell 아키텍처에서 bitsandbytes NF4가 반려된 경위가 있었으나,
bitsandbytes ≥ 0.43 부터 SM 9.0 (Blackwell) 지원이 추가되어 실제 적용 가능함을 확인했다.
CUDA 12.x + bitsandbytes 최신 버전 환경이면 동작한다.

---

### 수정 후 VRAM 점유

| 항목 | VRAM |
|---|---|
| Qwen2.5-3B + LoRA (int4 NF4, 수정 후) | ~7,173 MB |
| **여유 헤드룸 (수정 후)** | **977 MB** |
| 절감량 | ~355 MB |

#### 기대치와 실측치의 차이

파라미터 수만으로 계산하면 bf16(2 byte) → nf4(0.5 byte)이므로
이론상 **~4배 절감** (~1,882 MB)이 예상된다.
그러나 실측값 절감은 355 MB에 그쳤는데, 이는 다음 오버헤드가 포함되기 때문이다.

| 오버헤드 항목 | 설명 |
|---|---|
| CUDA 캐싱 할당자 | PyTorch가 미래 할당을 위해 예약 블록 확보 |
| dequantize 버퍼 | 연산 시점에 레이어별로 bf16으로 복원 — 임시 버퍼 상주 |
| KV Cache | 생성 길이에 비례해 VRAM 점유 (n_ctx에 따라 수백 MB) |
| LoRA 어댑터 가중치 | 양자화 대상 아님 — fp32/bf16 그대로 유지 |

결론: 파라미터 압축 효과 자체는 유효하지만, CUDA 런타임 오버헤드로 인해
순수 파라미터 절감분이 전체 VRAM에 그대로 반영되지는 않는다.

---

### 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `conversation/core/llm_client.py` | `_load_transformers()` 내 양자화 분기 추가 (`int4` / `int8` / `none`) |
| `config.py` | dev config에 `"quantization": "int4"` 추가 |

---

## BUG-02-C · LLM 이중 호출 제거 — Narrator 삭제 ✅

> 작업일: 2026-04-03

### 배경

기존 설계에서 매 대화 턴에 최대 2회 LLM 호출이 발생했다.

| 호출 | 역할 | 시점 |
|---|---|---|
| **1회차** | 캐릭터 대화 응답 생성 | 사용자 입력 직후 |
| **2회차** | Narrator — 장면 묘사 생성 | 응답 완료 후 비동기 |

2회차 나레이션 호출은 `Narrator` 클래스(`conversation/narrator.py`)를 통해 동일 모델+LoRA로 다른 프롬프트를 적용해 실행됐다.

### 문제

- CPU 배포(llama_cpp) 환경에서 턴당 최대 2배 응답 지연
- VRAM `_generate_lock` 직렬화로 인해 나레이션 생성이 대화 응답 뒤에 블로킹
- 배포 환경에서 `n_threads=cpu_count()` 최대화 이후에도 나레이션 지연이 병목

### 해결 방법

**나레이션 호출 자체를 제거하고 LLM 응답 포맷으로 통합한다.**

캐릭터 응답 생성 시 시스템 프롬프트에 `*묘사* 대사` 혼합 포맷을 지시하면
별도 호출 없이 한 번의 생성으로 장면 묘사와 대사를 동시에 출력할 수 있다.

```
기존: LLM 호출 1 (대화) + LLM 호출 2 (나레이션) = 최대 2배 지연
변경: LLM 호출 1 (대화 + *묘사* 통합) = 단일 호출
```

### 수정 내용

| 파일 | 변경 내용 |
|---|---|
| `conversation/narrator.py` | 유지 (미사용 — 삭제 안 함) |
| `conversation/narration_monitor.py` | LLM 트리거 전부 제거, 키워드 트리거만 유지 |
| `conversation/narration_hardcoded.py` | 유지 — LLM 없는 키워드 트리거용 |
| `agent/core.py` | `Narrator` 초기화 제거 |
| `ui_ux/bridge.py` | `_NarrationWorker`, `_SessionStartWorker`, `_start_narrator_async`, `requestSessionNarration` 제거 |
| `ui_ux/qml/main.qml` | `requestSessionNarration()` 호출 제거 |

### 효과

- 턴당 LLM 호출: **2회 → 1회**
- CPU 배포 기준 응답 지연: 절반 수준으로 감소 예상
- RAM/VRAM 추가 사용 없음 (동일 모델 1회 사용)

---

## BUG-02-D · 응답 인라인 편집 및 로그 품질 개선 ✅

> 작업일: 2026-04-03

### 배경

`training/log/`에 자동 수집되는 대화 데이터가 LLM 원본 응답 기준이므로
품질이 낮은 응답이 그대로 학습 데이터로 저장될 수 있었다.

### 해결 방법

UI에서 생성된 응답을 사용자가 직접 수정하고, 수정된 텍스트가 로그에 반영되도록 한다.

**흐름:**
1. `ChatBubble.qml` — assistant/narrator 버블 더블클릭 → 인라인 `TextEdit` 전환
2. `✓` 버튼 또는 `Ctrl+Enter` 확인 → `messageModel` UI 즉시 반영
3. `bridge.editMessage(idx, oldText, newText)` 슬롯 호출
4. `session.dialogue_log` 내 해당 assistant 메시지 교체
5. `ConversationLogger.edit_turn()` — 버퍼 또는 이미 기록된 JSONL 파일 내 항목 교체

### 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `ui_ux/qml/ChatBubble.qml` | 더블클릭 편집, 확인/취소 버튼, 키보드 지원 |
| `ui_ux/qml/main.qml` | delegate에 `modelIndex`, `editable`, `onEditConfirmed` 연결 |
| `ui_ux/bridge.py` | `editMessage(idx, old, new)` Slot 추가 |
| `training/log/conversation_logger.py` | `_written_files` 추적, `edit_turn()` 메서드 추가 |

---

## 배포 환경(llama_cpp) 관련 메모

- `llama_cpp`의 `Llama` 객체는 Python GC만으로는 C 레벨 힙이 즉시 해제되지 않는다.
  `model.close()` 명시 호출이 반드시 필요하다.
- Q4_K_M GGUF 기준 메모리는 ~2.5 GB이므로 CPU 배포 환경(8 GB RAM)에서도
  해제 없이 교체 시 OOM이 발생할 수 있다.
- `gc.collect()` 단독으로는 C 확장 객체의 메모리를 즉시 회수하지 못하므로
  명시적 `close()` / `del` 선행이 필수다.
