# Phase 구현 계획서

> README.md의 Phase 0~6 로드맵을 실행 단위로 구체화한 문서.
> 설계 세부사항은 [대화품질.md](../대화품질.md) (Phase 1~3) / [학습후보.md](../학습후보.md) (Phase 5~6) 참조.
> 파일 현황은 [DIR.md](../DIR.md) 참조.

---

## Phase 0 — 환경 구성 및 기반 설계

> 목표: 개발/배포 환경 분리, 공통 설정 파일 구조 확정
> 선행 조건: 없음 (첫 번째 Phase)

### 작업 목록

#### 0-1. `requirements-dev.txt` 작성 (Linux + GPU 환경)
```
transformers>=4.45.0
peft>=0.11.0
bitsandbytes>=0.44.0       # Blackwell RTX 50xx 대응
accelerate>=0.30.0
sentence-transformers       # bge-m3
chromadb
PyYAML
loguru
tqdm
rich
datasets                    # 학습 데이터 로더
```

#### 0-2. `requirements-deploy.txt` 작성 (Windows + CPU 환경)
```
llama-cpp-python            # CPU 빌드
PySide6
chromadb
sentence-transformers       # bge-m3 (시맨틱 검색)
PyYAML
loguru
```

#### 0-3. `config.py` 설계
```python
# 환경 판별 기준: 환경변수 ACHAT_ENV = "dev" | "deploy"
# 또는 llama-cpp-python 임포트 가능 여부로 자동 분기

CONFIG = {
    "dev": {
        "model_backend": "transformers",  # 학습 시
        "model_path": None,               # HF 모델명으로 대체
        "chroma_path": "./chroma_dev",
        "short_term_n": 5,
        "memory_trigger_n": 10,
    },
    "deploy": {
        "model_backend": "llama_cpp",
        "model_path": "./models/model_q4km.gguf",
        "chroma_path": "./chroma_deploy",
        "short_term_n": 5,
        "memory_trigger_n": 10,
    }
}
```

#### 0-4. ⚠️ 데이터 경로 정리 (불일치 해소)
- README.md는 `data/lora/`(루트)를 표기하지만 실제 데이터는 `training/data/`에 있음
- **결정 필요**: `training/dataset.py`가 `training/data/`를 직접 참조하므로 `training/data/` 경로 유지가 자연스러움
- README.md의 디렉토리 구조 항목을 `training/data/`로 수정 권장

### 완료 기준
- [ ] `requirements-dev.txt` / `requirements-deploy.txt` 두 파일 존재
- [ ] `config.py` — `get_config()` 함수로 환경별 dict 반환
- [ ] 데이터 경로 표기 통일 완료

---

## Phase 1 — LLM 인터페이스 구현

> 목표: llama-cpp-python 기반 로컬 추론 + Context Assembly + CLI 루프 동작 확인
> 선행 조건: Phase 0 완료 (config.py 존재)
> 상세 설계: [대화품질.md — 구현 계획 2~4단계](../대화품질.md#구현-의존-순서)

### 구현 순서

#### 1-1. `conversation/loader/character_load.py`
- `load_character(yaml_path: str) -> dict` 함수
- `CH_*.yaml` → dict 변환
- 필수 필드 검증: `id`, `speech_style`, `rules`, `memory_voice`, `state`
- 누락 필드 시 경고 로그 출력

#### 1-2. `conversation/loader/world_load.py`
- `load_world(yaml_path: str) -> dict` 함수
- `W_*.yaml` → dict 변환
- `scenarios`, `acts` 구조 파싱

#### 1-3. `conversation/loader/memory_load.py`
- `load_memory_defaults(json_path: str) -> list` 함수
- `M_default.json` → ChromaDB 초기 삽입용 리스트 반환

#### 1-4. `conversation/core/session.py`
```python
@dataclass
class ConversationSession:
    character_id: str
    world_id:     str | None = None
    act_id:       str | None = None
    mood:         str = "neutral"   # CH_*.yaml state.mood_default에서 초기화
    affection:    int = 30          # CH_*.yaml state.affection_default에서 초기화
    turn_count:   int = 0
    dialogue_log: list = field(default_factory=list)
```
- `add_turn(user: str, assistant: str)` 메서드
- `character_data` 로드 후 `mood`/`affection` 초기값 설정

#### 1-5. `conversation/core/llm_client.py`
- `llama_cpp.Llama` 인스턴스 (n_ctx=4096)
- `generate(messages: list, stream=True) -> str | Generator` 메서드
- `create_chat_completion` 사용 (ChatML 포맷)
- 모델 경로: `config.py`의 `model_path`에서 읽기

#### 1-6. `conversation/core/prompt_build.py`
- `PromptBuilder(character: dict, world: dict, session: ConversationSession)`
- `assemble(short_buf, vdb_results) -> list[dict]` — messages 리스트 반환
- Layer별 메서드 분리: `_layer_a()` ~ `_layer_e()`
- 토큰 카운트: `llm.tokenize(text.encode())` 활용
- Layer D 축소 로직: 5턴 → 3턴 → 2턴 (예산 초과 시)
- Layer C 재서술: `character['memory_voice']`를 포맷 참조해 VDB 결과 감쌈

#### 1-7. CLI 루프 동작 확인 (`conversation/main.py`)
```python
# 최소 구성: 로더 → 세션 → prompt_build → llm_client 연결 확인
while True:
    user_input = input("You: ")
    messages = builder.assemble(short_buf=[], vdb_results=[])
    response = llm.generate(messages)
    print(f"Assistant: {response}")
```

### 완료 기준
- [ ] `python conversation/main.py` 실행 시 캐릭터 YAML 로드 후 대화 루프 진입
- [ ] 응답에 캐릭터 말투 반영 확인 (speech_style 적용)
- [ ] 토큰 예산 초과 시 Layer D 자동 축소 확인

---

## Phase 2 — 대화 엔진 구현

> 목표: 메모리, 상태 관리, Post-processing 전 레이어 완성
> 선행 조건: Phase 1 완료 (session, llm_client, prompt_build 동작)
> 상세 설계: [대화품질.md — 구현 계획 5~7단계](../대화품질.md#구현-의존-순서)

### 구현 순서

#### 2-1. `memory/short_term.py`
```python
def get_recent(dialogue_log: list, n: int = 5) -> list:
    # 마지막 n턴 슬라이스, role/content 형식 반환
    return dialogue_log[-n * 2:]  # user+assistant 쌍
```
- N은 `config.py`에서 읽기 (기본값 5)

#### 2-2. `memory/long_term.py`
- ChromaDB collection: `{character_id}_memory`
- 임베딩: `SentenceTransformer("BAAI/bge-m3")`
- `store(entry: dict)` — M_schema.json 구조 준수
- `query(text: str, character_id: str) -> list`
  - 유사도 < 0.7 → 빈 리스트 반환
  - `where={"importance": {"$gte": 0.5}}` 필터 적용
  - top-2 반환

#### 2-3. `memory/summarizer.py`
- `check_trigger(session) -> bool` — `turn_count % N == 0`
- `summarize(dialogue_log: list, llm) -> str` — LLM으로 N턴 요약 (`max_tokens=150`)
- `score_importance(summary: str) -> float` — M_schema.json `importance_rules` 기준 규칙 판정
- `write_to_vdb(summary, score, session, long_term)` — score ≥ 0.5만 저장

#### 2-4. `agent/state.py`
```python
AFFECTION_TIERS = {"low": (0,30), "mid": (31,70), "high": (71,100)}

def update_mood(session, response_text: str, character: dict) -> str:
    # character['state']['mood_triggers'] 패턴 매칭
    ...

def update_affection(session, delta: int):
    session.affection = max(0, min(100, session.affection + delta))
```

#### 2-5. `agent/persona.py`
- `load_persona(character_id: str) -> dict` — `conversation/character/CH_{id}.yaml` 로드
- `swap_persona(session, new_character_id: str)` — 핫스왑 (session 초기화 포함)

#### 2-6. `conversation/core/router.py` — `handle_turn()` 구현
```
1. pre_process(user_input)           # 명령어 감지 (/캐릭터변경 등)
2. short_buf = short_term.get(session)
3. vdb_result = long_term.query(user_input, character_id)
4. context = prompt_build.assemble(short_buf, vdb_result)
5. response = llm.generate(context)
6. state.update_mood(session, response)
7. state.update_affection(session, delta)
8. session.add_turn(user_input, response)
9. summarizer.check_trigger(session) → 조건 충족 시 VDB 저장
return response
```

#### 2-7. `agent/core.py`
- `Agent(character_id, world_id)` — 전체 컴포넌트 초기화 + 조율
- `chat(user_input: str) -> str` — `router.handle_turn()` 호출

### 완료 기준
- [ ] 10턴 대화 후 ChromaDB에 요약 저장 확인
- [ ] 11턴에서 이전 대화 내용 참조 질문 시 VDB 검색 결과가 Layer C에 삽입됨을 확인
- [ ] mood/affection 상태가 대화에 따라 변하는 것 확인

---

## Phase 3 — RAG 구현

> 목표: 세계관 문서 시맨틱 검색 → Layer B/C 연동
> 선행 조건: Phase 2 완료 (long_term.py ChromaDB 연동)
> 상세 설계: [대화품질.md — 시맨틱 검색 전략](../대화품질.md#4-시맨틱-검색-rag-및-장기-메모리)

### 구현 순서

#### 3-1. `rag/index.py`
- `index_world(world_dir: str)` — `rag/sources/world/*.md` 파일 청킹
  - 청크 크기: 300~500자 (한국어 기준)
  - 청크 overlap: 50자
- ChromaDB collection: `world_knowledge`
- bge-m3 임베딩 후 저장
- 이미 인덱싱된 경우 스킵 (collection 존재 여부 체크)

#### 3-2. `rag/retrieve.py`
- `query_world(text: str, n_results=2, threshold=0.7) -> list`
  - bge-m3 임베딩 → ChromaDB 검색
  - 유사도 < 0.7 → 빈 리스트 반환
  - **키워드 트리거 방식 사용 안 함** — 매 턴 실행

#### 3-3. `conversation/core/prompt_build.py` — Layer B/C 연동 업데이트
- Layer B: World YAML의 현재 Act 설명 + RAG 결과 병합
- Layer C: 장기 메모리 VDB 결과 (캐릭터 관점 재서술)
- 두 소스 합산 ~350tok 예산 내에서 우선순위: 장기 메모리 > 세계관 RAG

### 완료 기준
- [ ] `python rag/index.py` 실행 시 rag/sources/world/ 문서가 ChromaDB에 인덱싱됨
- [ ] 세계관 관련 질문 시 RAG 결과가 Layer에 삽입되는 것 확인
- [ ] 관련 없는 질문 시 RAG 결과 삽입 안 됨 (임계값 0.7 동작 확인)

---

## Phase 4 — 위젯 UI 구현

> 목표: PySide6 데스크탑 위젯 (Windows 배포 대상)
> 선행 조건: Phase 2 완료 (agent/core.py `chat()` 동작)
> 참고: Phase 1~3와 병렬 진행 가능 (agent.chat() 인터페이스만 있으면 됨)

### 구현 순서

#### 4-1. `ui/widget.py` — 메인 위젯
- `QWidget` 상속, `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`
- 드래그 이동: `mousePressEvent`, `mouseMoveEvent` 오버라이드
- 반투명 배경: `setAttribute(Qt.WA_TranslucentBackground)`
- 크기 조절 핸들 (우하단 리사이즈)

#### 4-2. `ui/chat_panel.py` — 채팅 패널
- `QScrollArea` + `QVBoxLayout` 기반 말풍선 UI
- 스트리밍 토큰 표시: `QThread` + `pyqtSignal` 패턴
  ```python
  class LLMWorker(QThread):
      token_received = pyqtSignal(str)
      finished = pyqtSignal()
  ```
- 사용자/캐릭터 말풍선 색상 구분

#### 4-3. `ui/tray.py` — 시스템 트레이
- `QSystemTrayIcon` 설정
- 메뉴: 열기 / 캐릭터 변경 / 종료
- 더블클릭 시 위젯 토글

#### 4-4. 캐릭터 전환 UI 연동
- 트레이 메뉴 "캐릭터 변경" → `agent.swap_persona()` 호출
- 전환 시 채팅 패널 클리어 여부 선택 다이얼로그

### 완료 기준
- [ ] 위젯 실행 시 항상 최상위 표시, 드래그 이동 가능
- [ ] 캐릭터 응답이 스트리밍으로 한 글자씩 표시됨
- [ ] 트레이 아이콘으로 위젯 숨기기/보이기 전환

---

## Phase 5 — LoRA 파인튜닝 파이프라인

> 목표: 캐릭터 말투 / 감정 반응 / 한국어 일관성 강화
> 선행 조건: Phase 0 완료, training/data/ 데이터 구축 완료
> 상세 설계: [학습후보.md — 구현 계획](../학습후보.md#6-구현-계획)

### 구현 순서

#### 5-1. 학습 데이터 확인 및 보완
현재 `training/data/`에 존재하는 데이터:
- `common/`: memory_ref.jsonl, ai_tell_removal.jsonl, persona_follow.jsonl ✅
- `personality/`: 5종 성격별 데이터 ✅
- `speech_style/`: 말투 조합 데이터 ✅

`학습후보.md` 기준 필요한 데이터:
- `character_speech.jsonl` — 캐릭터 말투 200~300건 (기존 데이터에서 병합 or 추가)
- `emotion_response.jsonl` — 감정 반응 100~150건
- ChatML 포맷 준수 확인

#### 5-2. `training/dataset.py`
```python
from datasets import load_dataset

def load_training_data(data_dir: str, model_name: str, tokenizer):
    dataset = load_dataset("json", data_files=f"{data_dir}/**/*.jsonl")
    # tokenizer.apply_chat_template 적용
    # max_length=512 초과 샘플 필터링
    return dataset
```
- 모델명을 인자로 받아 tokenizer 분기 처리

#### 5-3. `training/lora_train.py`
- CLI 인자: `--model` (HF 모델명), `--data_dir`, `--output_dir`
- `BitsAndBytesConfig` (4-bit nf4, fp16 compute)
- `LoraConfig` (r=16, alpha=32, target q/v/k/o proj)
- `TrainingArguments` (batch=1, grad_accum=8, checkpointing=True)
- 학습 완료 후 `output/{model_name}/` 에 adapter 저장

#### 5-4. 평가 실행 (eval/)
```bash
python eval/ai_tell_checker.py --model output/Qwen2.5-3B/adapter_model.bin
python eval/memory_test.py
python eval/speed_bench.py --backend transformers
```
- 학습후보.md 섹션 4-3 양식으로 결과 기록
- 모델 비교: EXAONE-3.5-2.4B → Qwen2.5-3B 순서

### 완료 기준
- [ ] `lora_train.py` 실행 시 OOM 없이 3 epoch 완료
- [ ] adapter 저장 후 `ai_tell_checker.py` 이질감 점수 감소 확인
- [ ] 최종 채택 모델 1개 결정

---

## Phase 6 — GGUF 변환 및 배포 패키징

> 목표: Windows CPU 배포 가능한 단일 패키지 구성
> 선행 조건: Phase 5 완료 (채택 모델 adapter 존재)
> 상세 설계: [학습후보.md — merge_lora, convert_to_gguf 구현](../학습후보.md#파일별-구현-핵심-사항)

### 구현 순서

#### 6-1. `scripts/merge_lora.py`
```python
# ⚠️ 실행 전 브라우저 등 메모리 사용 프로세스 종료 필수
model = AutoModelForCausalLM.from_pretrained(
    base_model_path,
    torch_dtype=torch.float16,
    low_cpu_mem_usage=True,   # 3B 병합에 ~6GB RAM
    device_map="cpu",
)
model = PeftModel.from_pretrained(model, adapter_path)
model = model.merge_and_unload()
model.save_pretrained(output_path)
tokenizer.save_pretrained(output_path)
```
- OOM 발생 시: swap 4GB 임시 확장 후 재시도

#### 6-2. `scripts/convert_to_gguf.sh`
```bash
#!/bin/bash
# llama.cpp 최신 빌드 필요 (Qwen2.5 지원 버전)
python llama.cpp/convert_hf_to_gguf.py \
    $MERGED_MODEL_PATH \
    --outfile output/model_fp16.gguf \
    --outtype f16

./llama.cpp/quantize \
    output/model_fp16.gguf \
    output/model_q4km.gguf \
    Q4_K_M
# 최종 파일 크기 확인: 3B Q4_K_M ≈ 2GB
```

#### 6-3. `requirements-deploy.txt` 검증
- Windows 환경에서 `pip install -r requirements-deploy.txt` 클린 설치 확인
- `llama-cpp-python` — AVX2 빌드 여부 확인

#### 6-4. 실행 스크립트 `run_widget.bat`
```batch
@echo off
python main.py --env deploy --model models/model_q4km.gguf
```

### 완료 기준
- [ ] `merge_lora.py` OOM 없이 완료, HF 포맷 병합 모델 저장
- [ ] `convert_to_gguf.sh` 실행 후 `model_q4km.gguf` 생성 (~2GB)
- [ ] Windows에서 `run_widget.bat` 실행 시 위젯 정상 구동
- [ ] CPU 추론 속도 8+ tok/s 달성 확인

---

## 전체 의존 관계

```
Phase 0 (환경/설정)
    │
    ├─► Phase 1 (LLM 인터페이스)
    │       │
    │       ├─► Phase 2 (대화 엔진)
    │       │       │
    │       │       └─► Phase 3 (RAG)
    │       │
    │       └─► Phase 4 (위젯 UI)  ← Phase 2와 병렬 가능
    │
    └─► Phase 5 (LoRA 학습)
            │
            └─► Phase 6 (GGUF 배포)
```

Phase 4는 `agent.chat()` 인터페이스만 있으면 Phase 2/3와 병렬 진행 가능.
Phase 5/6는 대화 엔진 완성과 무관하게 데이터가 준비되면 진행 가능.
