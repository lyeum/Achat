# Phase 구현 계획서

> README.md의 Phase 0~7 로드맵을 실행 단위로 구체화한 문서.
> 설계 세부사항은 [대화품질.md](../대화품질.md) (Phase 1~3) / [학습후보.md](../학습후보.md) (Phase 5~6) 참조.
> 파일 현황은 [DIR.md](../DIR.md) 참조.

---

## Phase 0 — 환경 구성 및 기반 설계

> 목표: 개발/배포 환경 분리, 공통 설정 파일 구조 확정
> 선행 조건: 없음 (첫 번째 Phase)

### 작업 목록

#### 0-1. `pyproject.toml` 작성 (Linux + GPU 환경, uv 기반) ✅
주요 의존성: transformers, peft, bitsandbytes>=0.44.0 (Blackwell 대응), accelerate,
sentence-transformers (bge-m3), chromadb, PyYAML, loguru, tqdm, rich, datasets
PyTorch CUDA 12.8 빌드는 `[tool.uv.sources]` 설정으로 자동 처리.

#### 0-2. `pyproject-deploy.toml` 작성 (Windows + CPU 환경, uv 기반) ✅
주요 의존성: llama-cpp-python (CPU 빌드), PySide6, chromadb,
sentence-transformers, Pillow, whoosh, PyYAML, loguru

#### 0-3. `config.py` 설계
```python
# 환경 판별 기준: 환경변수 ACHAT_ENV = "dev" | "deploy"
# 또는 llama-cpp-python 임포트 가능 여부로 자동 분기

CONFIG = {
    "dev": {
        "model_backend": "transformers",
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

#### 0-4. ⚠️ 데이터 경로 정리
- 기존 학습 데이터: `training/data/` (common/, personality/, speech_style/)
- README 신규 표기: `data/lora/conversation/` + `data/lora/function/`
- **방침**: Phase 5 전 `data/lora/` 디렉토리 생성 후 기존 데이터 분류·이전

### 완료 기준
- [x] `pyproject.toml` / `pyproject-deploy.toml` 구성 완료 (uv 기반, Linux+GPU / Windows+CPU)
- [x] `config.py` — `get_config()` 함수로 환경별 dict 반환

---

## Phase 1 — LLM 인터페이스 구현

> 목표: llama-cpp-python 기반 로컬 추론 + Context Assembly + CLI 루프 동작 확인
> 선행 조건: Phase 0 완료 (config.py 존재)
> 상세 설계: [대화품질.md — 구현 계획 2~4단계](../대화품질.md#구현-의존-순서)

### 구현 순서

#### 1-1. `conversation/loader/character_load.py`
- `load_character(yaml_path: str) -> dict`
- 필수 필드 검증: `id`, `speech_style`, `rules`, `memory_voice`, `state`
- 누락 필드 시 경고 로그 출력

#### 1-2. `conversation/loader/world_load.py`
- `load_world(yaml_path: str) -> dict`
- `scenarios`, `acts` 구조 파싱

#### 1-3. `conversation/loader/memory_load.py`
- `load_memory_defaults(json_path: str) -> list`
- `M_default.json` → ChromaDB 초기 삽입용 리스트 반환

#### 1-4. `conversation/core/session.py`
```python
@dataclass
class ConversationSession:
    character_id: str
    world_id:     str | None = None
    scenario_id:  str | None = None   # PromptBuilder._current_act() 조회에 필요 (spec 추가)
    act_id:       str | None = None
    mood:         str = "neutral"     # CH_*.yaml state.mood_default에서 초기화
    affection:    int = 30            # CH_*.yaml state.affection_default에서 초기화
    turn_count:   int = 0
    dialogue_log: list = field(default_factory=list)
```
- `add_turn(user: str, assistant: str)` 메서드
- `from_character(character, world_id, scenario_id, act_id)` 클래스메서드로 초기값 설정

#### 1-5. `conversation/core/llm_client.py`
- `llama_cpp.Llama` 인스턴스 (n_ctx=4096)
- `generate(messages: list, stream=True) -> str | Generator`
- `create_chat_completion` 사용 (ChatML 포맷)
- 모델 경로: config.py `model_path`에서 읽기

#### 1-6. `conversation/core/prompt_build.py`
- `PromptBuilder(character: dict, world: dict, session: ConversationSession)`
- `assemble(short_buf, vdb_results) -> list[dict]` — messages 리스트 반환
- Layer별 메서드 분리: `_layer_a()` ~ `_layer_d()` (Layer E는 caller가 append — `{"role": "user", "content": user_input}`)
- 토큰 카운트: `llm.tokenize(text.encode())` 활용
- Layer D 축소: 5턴 → 3턴 → 2턴 (예산 초과 시)
- Layer C 재서술: `character['memory_voice']` 포맷으로 VDB 결과 감쌈

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
- [x] `python -m conversation.main` 실행 시 캐릭터 YAML 로드 후 대화 루프 진입
- [x] dry-run 모드: 모델 없어도 시스템 프롬프트 조립 확인 가능
- [x] 토큰 예산 초과 시 Layer D 자동 축소 (5→3→2턴) 구현

---

## Phase 2 — 대화 엔진 구현

> 목표: 메모리, 상태 관리, Post-processing 전 레이어 완성
> 선행 조건: Phase 1 완료 (session, llm_client, prompt_build 동작)
> 상세 설계: [대화품질.md — 구현 계획 5~7단계](../대화품질.md#구현-의존-순서)

### 구현 순서

#### 2-1. `memory/short_term.py`
```python
def get_recent(dialogue_log: list, n: int = 5) -> list:
    return dialogue_log[-n * 2:]  # user+assistant 쌍
```
- N은 config.py에서 읽기 (기본값 5)

#### 2-2. `memory/long_term.py`
- ChromaDB collection: `{character_id}_memory`
- 임베딩: `SentenceTransformer("BAAI/bge-m3")`
- `store(entry: dict)` — M_schema.json 구조 준수
- `query(text: str, character_id: str) -> list`
  - 유사도 < 0.7 → 빈 리스트 반환
  - `where={"importance": {"$gte": 0.5}}` 필터
  - top-2 반환

#### 2-3. `memory/summarizer.py`
- `check_trigger(session) -> bool` — `turn_count % N == 0`
- `summarize(dialogue_log, llm) -> str` — LLM으로 N턴 요약 (max_tokens=150)
- `score_importance(summary) -> float` — M_schema.json `importance_rules` 기준 규칙 판정
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
- `load_persona(character_id: str) -> dict`
- `swap_persona(session, new_character_id: str)` — 핫스왑 (session 초기화 포함)

#### 2-6. `conversation/core/router.py` — `handle_turn()` 구현
```
1. pre_process(user_input)            # 명령어 감지
2. short_buf  = short_term.get(session)
3. vdb_result = long_term.query(user_input, character_id)
4. context    = prompt_build.assemble(short_buf, vdb_result)
5. response   = llm.generate(context)
6. state.update_mood(session, response)
7. state.update_affection(session, delta)
8. session.add_turn(user_input, response)
9. summarizer.check_trigger(session)  # 조건 충족 시 VDB 저장
return response
```

#### 2-7. `agent/core.py`
- `Agent(character_id, world_id)` — 전체 컴포넌트 초기화 + 조율
- `chat(user_input: str) -> str` — 대화 모드 진입점
- 모드 분기는 Phase 7에서 확장

### 완료 기준
- [x] `memory/`, `agent/` 패키지 `__init__.py` 추가 (import 경로 확보)
- [x] ChromaDB store/query 구현 (bge-m3 임베딩, threshold 0.7, importance ≥ 0.5 필터)
- [x] `memory_trigger_n`턴마다 LLM 요약 → 중요도 scoring → VDB 저장 파이프라인
- [x] `handle_turn()` — VDB 검색 → PromptBuilder → LLM → mood/affection → 세션 기록 → 요약 트리거
- [x] `Agent` 클래스 — 전체 컴포넌트 초기화 + `chat()` 대화 진입점
- [ ] (실환경 검증) 10턴 대화 후 ChromaDB에 요약 저장 확인
- [ ] (실환경 검증) 기억 참조 질문 시 VDB 결과가 Layer C에 삽입됨 확인
- [ ] (실환경 검증) mood/affection 상태 변화 확인

---

## Phase 3 — RAG 구현

> 목표: 세계관 문서 시맨틱 검색 → Layer B/C 연동
> 선행 조건: Phase 2 완료 (long_term.py ChromaDB 연동)
> 상세 설계: [대화품질.md — 시맨틱 검색 전략](../대화품질.md#4-시맨틱-검색-rag-및-장기-메모리)

### 구현 순서

#### 3-1. `rag/index.py`
- `index_world(world_dir: str)` — `rag/sources/world/*.md` 청킹
  - 청크 크기: 300~500자 (한국어 기준), overlap: 50자
- ChromaDB collection: `world_knowledge`
- 이미 인덱싱된 경우 스킵 (collection 존재 여부 체크)

#### 3-2. `rag/retrieve.py`
- `WorldRetriever(config)` 클래스 — `query(text: str) -> list[str]`
  - bge-m3 임베딩 → ChromaDB 검색
  - 유사도 < 0.7 → 빈 리스트 반환
  - 컬렉션 미존재(인덱싱 전) → 빈 리스트 반환 (안전 처리)
  - **키워드 트리거 방식 사용 안 함** — 매 턴 실행

#### 3-3. `conversation/core/prompt_build.py` — Layer B/C 연동 업데이트
- Layer B: World YAML 현재 Act 설명 + RAG 결과 병합
- Layer C: 장기 메모리 VDB 결과 (캐릭터 관점 재서술)
- 두 소스 합산 ~350tok 예산, 우선순위: 장기 메모리 > 세계관 RAG

### 완료 기준
- [x] `rag/__init__.py` 추가 (패키지 초기화)
- [x] `index_world()` — `.md` 청킹 + ChromaDB 인덱싱, cosine space 지정, 기존 컬렉션 스킵
- [x] `WorldRetriever.query()` — 매 턴 실행, threshold 미만 빈 리스트, 컬렉션 미존재 안전 처리
- [x] `PromptBuilder.assemble(rag_results=)` — Layer B에 RAG 결과 병합
- [x] `ConversationRouter` — RAG 검색 연동 (우선순위: 장기 메모리 > 세계관 RAG)
- [x] **버그 수정**: ChromaDB distance metric `l2` → `cosine` (long_term, rag/index 모두)
- [x] **버그 수정**: `summarizer.write_to_vdb(trigger_n=)` — turn_range 하드코딩 제거
- [ ] (실환경 검증) 세계관 관련 질문 시 RAG 결과 Layer B 삽입 확인
- [ ] (실환경 검증) 무관한 질문 시 RAG 결과 삽입 안 됨 확인

---

## Phase 4 — 플로팅 UI 구현

> 목표: **QML + PySide6** PIP 스타일 플로팅 UI (Windows 배포 대상)
> 선행 조건: Phase 2 완료 (agent/core.py `chat()` 동작)
> **설계 변경**: 순수 QWidget → QML + PySide6로 전환 (비정형 모양/애니메이션 구현 용이성)

### 아키텍처

```
main.py
  └─ UIEngine (ui_ux/widget.py)
       ├─ QQmlApplicationEngine
       ├─ ChatBridge (ui_ux/bridge.py) ──→ context property 'bridge'
       │     └─ LLMWorker (ui_ux/chat_panel.py) : QThread
       └─ ui_ux/qml/main.qml
             └─ ui_ux/qml/ChatBubble.qml
  └─ AppTrayIcon (ui_ux/tray.py)
```

### 구현 순서

#### 4-1. `ui_ux/bridge.py` — Python↔QML 브리지
- `ChatBridge(QObject)` — QML context property `bridge`로 등록
- Signal (Python→QML): `messageAdded(role, content)`, `statusChanged(status)`, `characterNameChanged(name)`
- Slot (QML→Python): `sendMessage(text)`, `snapToEdge(x,y,w,h) -> list`, `changeCharacter(id)`

#### 4-2. `ui_ux/chat_panel.py` — LLMWorker
- `LLMWorker(QThread)` — `agent.chat(stream=False)` 비동기 실행
- Signal: `response_ready(str)`, `error_occurred(str)`

#### 4-3. `ui_ux/widget.py` — QML 엔진
- `UIEngine` — `QQmlApplicationEngine` 래퍼
- bridge를 context property로 등록 후 `main.qml` 로드

#### 4-4. `ui_ux/qml/main.qml` — 플로팅 윈도우
- `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint` (`Qt.Tool` 제거 — WSLg 미표시 문제)
- 드래그: `DragHandler + startSystemMove()` — 전체 창 드래그, 버튼 이벤트 충돌 없음
- hover 투명도: `HoverHandler` + `Behavior on opacity`
- 버블 축소/확장: `isBubble` 프로퍼티 토글, width/height `Behavior` 애니메이션
- 모드 전환 버튼 (대화 / 기능) — Phase 7에서 기능 모드 패널 확장
- `ListView` + `messageModel(ListModel)` — `bridge.messageAdded` 시그널로 추가
- `FontLoader` — `/mnt/c/Windows/Fonts/malgun.ttf` 로드 (WSL2 한글 폰트)
- `onClosing: Qt.quit()` — X 버튼/Alt+F4 시 앱 완전 종료
- `Component.onCompleted` — 초기 위치 우하단 설정 (`Screen.width/height` 기준)

#### 4-5. `ui_ux/qml/ChatBubble.qml` — 말풍선 컴포넌트
- `role` 프로퍼티로 좌/우 정렬 및 색상 분기

#### 4-6. `ui_ux/tray.py` — 시스템 트레이
- 열기/숨기기, 캐릭터 변경(`bridge.changeCharacter()`), 종료

#### 4-7. `ui_ux/qml/Style.qml` — 디자인 토큰 (추가)
- `pragma Singleton` — 색상(bgWindow/Bubble/User/Assistant), 폰트 패밀리/크기, 간격/반지름, 애니메이션 ms, 불투명도, 기본 크기 상수
- `qmldir`에 `singleton Style 1.0 Style.qml` 등록

#### 4-8. `ui_ux/assets/` — 에셋 디렉토리 (추가)
- `icons/` — 앱 아이콘 PNG (tray.py `_make_default_icon()` fallback 교체용)
- `characters/` — 캐릭터 PNG/GIF (bubble 상태 아바타 표시용)

### 완료 기준
- [x] `ui_ux/__init__.py`, `ui_ux/bridge.py`, `ui_ux/chat_panel.py`, `ui_ux/widget.py`, `ui_ux/tray.py` 구현
- [x] `ui_ux/qml/main.qml`, `ui_ux/qml/ChatBubble.qml` 구현
- [x] `ui_ux/qml/Style.qml`, `ui_ux/qml/qmldir` 작성
- [x] `ui_ux/assets/icons/`, `ui_ux/assets/characters/` 디렉토리 생성
- [x] `main.py` — torch 선로드, PID 정리, VRAM 체크, Qt 지연 import
- [x] `mode_switcher.py` 제거 — QML 모드 전환 버튼으로 대체
- [x] (WSL2 dev 검증) 플로팅 윈도우 표시, 전체 창 드래그, 대화 동작 확인
- [x] (WSL2 dev 검증) 메시지 전송 → LLMWorker 비동기 응답 → ListView 추가
- [ ] (미해결) 한글 입력 — Ubuntu 22.04 + fcitx5-hangul 필요 (현재 20.04)
- [ ] (미검증) hover 투명도 전환, 버블 축소/확장 애니메이션 (Windows 배포 환경)

### WSL2 dev 환경 실행 이슈 및 해결
| 이슈 | 원인 | 해결 |
|---|---|---|
| Segfault | PySide6 import가 torch보다 먼저 shared lib 로드 | torch → Qt 순서로 변경 (lazy import) |
| 한글 폰트 깨짐 | Malgun Gothic이 Linux에 없음 | `FontLoader`로 Windows 폰트 직접 로드 |
| 버튼 안 먹힘 | 전체 창 MouseArea가 이벤트 가로챔 | `DragHandler + startSystemMove()`로 교체 |
| 창 안 보임 | `Qt.Tool` 플래그 + opacity 0.25 | Tool 제거, `Component.onCompleted` 위치 설정 |
| 한글 입력 불가 | Ubuntu 20.04에 fcitx5-hangul 없음 | Ubuntu 22.04 필요 |

---

## Phase 5 — LoRA 파인튜닝 파이프라인

> 목표: 캐릭터 말투 / 감정 반응 / 한국어 일관성 + 기능 모드 JSON 파라미터 추출 능력 확보
> 선행 조건: Phase 0 완료, 학습 데이터 구축 완료
> 상세 설계: [학습후보.md — 구현 계획](../학습후보.md#6-구현-계획)

### 구현 순서

#### 5-1. 학습 데이터 구축 및 정리

**대화 모드 데이터** (`data/lora/conversation/`):
- 기존 `training/data/`의 데이터를 분류·이전:
  - `common/`: memory_ref, ai_tell_removal, persona_follow
  - `personality/`: 5종 성격별
  - `speech_style/`: 말투 조합
- 추가 필요: `character_speech.jsonl` (200~300건), `emotion_response.jsonl` (100~150건)
- ChatML 포맷 준수 확인

**기능 모드 데이터** (`data/lora/function/`):
- 폴더 정리 도구: `{"task": "폴더 정리", "target": "/downloads", "rule": "확장자별 분류"}` 형태
- 프롬프트 변환: 자연어 텍스트 → 최적화된 프롬프트 변환 예시
- 검색: `{"query": "...", "scope": "local" | "web"}` 추출 예시
- 각 도구당 50~100건 목표
- ⚠️ 3B 모델은 파인튜닝 없이 JSON 출력 불안정 — 기능 모드 예시 데이터 반드시 포함

#### 5-2. `training/dataset.py`
```python
from datasets import load_dataset

def load_training_data(data_dir: str, model_name: str, tokenizer):
    dataset = load_dataset("json", data_files=f"{data_dir}/**/*.jsonl")
    # tokenizer.apply_chat_template 적용
    # max_length=512 초과 샘플 필터링
    return dataset
```
- 모델명 인자로 tokenizer 분기 처리
- conversation/ + function/ 데이터 혼합 로드

#### 5-3. `training/lora_train.py`
- CLI 인자: `--model`, `--data_dir`, `--output_dir`, `--epochs`, `--lora_r`, `--no_save`, `--max_steps` 등
- ⚠️ **BitsAndBytesConfig 미사용** — RTX 5060 (Blackwell SM 10.x) 4-bit 양자화 미지원
  → GPU: `dtype=bfloat16` + `device_map="auto"` / CPU: `dtype=float32` + `device_map="cpu"` 자동 전환
- `LoraConfig` (r=16, alpha=32, target q/k/v/o/gate/up/down proj)
- `TrainingArguments` (batch=1, grad_accum=8, bf16=GPU only, gradient_checkpointing=GPU only)
- `--no_save`: 어댑터 저장 생략 (파이프라인 테스트용)
- `--max_steps`: 지정 스텝에서 종료 (CPU smoke test용)
- 학습 완료 후 `output/{run_name}/adapter/` 에 어댑터 저장

#### 5-4. 평가 실행 (eval/)
```bash
python eval/ai_tell_checker.py
python eval/memory_test.py
python eval/speed_bench.py --backend transformers
```
- 학습후보.md 섹션 4-3 양식으로 결과 기록

#### 5-5. `training/학습.md`
- Step 0 (사전 확인) ~ Step 6 (기존 데이터 직접 학습) 단계별 실행 가이드
- GPU/CPU 옵션, OOM 대응, 평가 스크립트 실행법 포함

### 완료 기준
- [x] `data/lora/conversation/` 디렉토리 생성 (training/log 빌드 대상)
- [x] `data/lora/function/` — folder_organize / prompt_convert / search 예시 데이터 작성
- [x] `scripts/build_dataset.py` — training/log/*.jsonl → data/lora/conversation/ 빌드 + 시스템 프롬프트 삽입 (버그 수정: TOKENS_PER_CHAR 역수 오류, relative_to 예외 처리)
- [x] `training/dataset.py` — data/lora/**/*.jsonl 로드 + apply_chat_template + max_length 필터 (버그 수정: relative_to 예외 처리)
- [x] `training/lora_train.py` — GPU/CPU 자동 전환, --no_save/--max_steps, processing_class, warmup_steps, pin_memory 버그 수정
- [x] `training/학습.md` — Step 0~6 실행 가이드 작성
- [x] `eval/ai_tell_checker.py` — AI투 표현 패턴 측정 + 베이스/LoRA 비교 (F541 버그 수정)
- [x] `eval/memory_test.py` — 멀티턴 기억 유지 정확도 측정 (5케이스)
- [x] `eval/speed_bench.py` — transformers/llama_cpp 추론 속도 벤치마크
- [x] CPU 파이프라인 smoke test 완료 (`--max_steps 1 --no_save`, loss=3.798)
- [ ] (실행 검증) GPU에서 `lora_train.py` OOM 없이 3 epoch 완료
- [ ] (실행 검증) `ai_tell_checker.py` 파인튜닝 후 AI투 감소 확인
- [ ] (실행 검증) 기능 모드 JSON 출력 정확도 확인
- [ ] 최종 채택 모델 1개 결정 (학습후보.md 평가 결과 기준)

---

## Phase 6 — GGUF 변환 및 배포 패키징

> 목표: Windows CPU 배포 가능한 단일 패키지 구성
> 선행 조건: Phase 5 완료 (채택 모델 adapter 존재)
> 상세 설계: [학습후보.md — merge_lora, convert_to_gguf 구현](../학습후보.md#파일별-구현-핵심-사항)

### 구현 순서

#### 6-1. `scripts/merge_lora.py` ✅
- `PeftModel.from_pretrained` → `merge_and_unload()` → HF 포맷 저장
- `dtype=torch.float16`, `low_cpu_mem_usage=True`, `device_map="cpu"`
- OOM 발생 시: swap 4GB 임시 확장 후 재시도
  ```bash
  sudo fallocate -l 4G /swapfile2 && sudo chmod 600 /swapfile2
  sudo mkswap /swapfile2 && sudo swapon /swapfile2
  ```

#### 6-2. `scripts/convert_to_gguf.sh` ✅
- `--merged`, `--out_dir`, `--llama_cpp` 인자로 경로 지정
- Step 1: `convert_hf_to_gguf.py` → `model_fp16.gguf`
- Step 2: `llama-quantize` → `model_q4km.gguf` (Q4_K_M, ~2GB)
- 선행 조건: llama.cpp 클론 + cmake 빌드 필요

#### 6-3. `pyproject-deploy.toml` 검증
- Windows 환경에서 `uv sync` 클린 설치 확인
- `llama-cpp-python` AVX2 빌드 여부 확인

#### 6-4. 실행 스크립트 `run.bat` ✅
- 모델 파일 존재 여부 확인 후 `uv run python main.py --env deploy` 실행

### 완료 기준
- [x] `scripts/merge_lora.py` 작성 완료
- [x] `scripts/convert_to_gguf.sh` 작성 완료
- [x] `run.bat` 작성 완료
- [ ] **GPU 파인튜닝 실행** — RTX 5060 Ti에서 3 epoch 완료, 평가 결과 기록 (ai_tell_checker / memory_test / speed_bench)
- [ ] (실행 검증) `merge_lora.py` OOM 없이 완료, HF 포맷 병합 모델 저장 ← GPU 학습 완료 후 진행
- [ ] (실행 검증) `model_q4km.gguf` 생성 (~2GB) ← llama.cpp 빌드 필요
- [ ] (실행 검증) **배포 파이프라인 전체 작동 확인** — merge → GGUF 변환 → Windows run.bat 실행 → 위젯 정상 구동
- [ ] (실행 검증) CPU 추론 속도 8+ tok/s 달성 확인

---

## Phase 7 — 기능 모드 도구 구현

> 목표: 폴더 정리 / 프롬프트 변환 / 검색엔진 마이크로서비스 구현 + agent/core 연동
> 선행 조건: Phase 2 (`agent/core.py` 기본 구조), Phase 4 (`mode_switcher.py` UI)
> 참고: Phase 5 학습 데이터의 기능 모드 JSON 예시와 연동

### 구현 순서

#### 7-1. `tools/base.py` — Tool 인터페이스 확정
```python
class BaseTool:
    name: str
    system_prompt: str   # 기능 전용 LLM 시스템 프롬프트

    def parse_params(self, llm_response: str) -> dict:
        # LLM 출력 → JSON 파라미터 파싱
        ...

    def execute(self, params: dict) -> str:
        # rule-based 실행, 결과 반환
        raise NotImplementedError
```

#### 7-2. `tools/folder/classifier.py` — 파일 분류
- 확장자 / MIME 타입 기반 자동 분류
- 분류 기준: LLM이 자연어 → JSON 파라미터로 파싱
  ```json
  {"target": "/downloads", "rule": "확장자별", "dry_run": true}
  ```
- `pathlib` + `shutil` 기반 이동 실행

#### 7-3. `tools/folder/converter.py` — 확장자 일괄 변환
- 이미지: `Pillow` (jpg/png/webp/bmp — 외부 의존 없음)
- 문서: txt/md 인코딩 변환
- 영상/음성: `ffmpeg` 바이너리 필요 — 존재 여부 체크 후 실행, 없으면 안내 메시지

#### 7-4. `tools/folder/renamer.py` — 이름 일괄 변환
- LLM이 `rename_rule: "날짜_원본명"` 형태로 파싱
- `pathlib.Path.rename()` 실행

#### 7-5. `tools/prompt_converter.py` — 프롬프트 변환
- 기능 전용 시스템 프롬프트로 LLM 교체
- 대화 히스토리 / 장기 메모리 격리 (기능 세션 미기록)
- 사용자 텍스트 → 최적화 프롬프트 변환 후 반환

#### 7-6. `tools/search/local_search.py` — 로컬 파일 검색
- SQLite FTS5 또는 whoosh 기반 파일 인덱싱
- LLM이 `{"query": "...", "scope": "local", "path": "/home"}` 파싱
- 검색 결과 요약 → 사용자에게 응답

#### 7-7. `tools/search/web_search.py` — 인터넷 검색
- DuckDuckGo 비공식 API (rate limit 주의) 또는 SearXNG 셀프호스팅
- LLM이 `{"query": "...", "scope": "web"}` 파싱
- 검색 결과 상위 N개 요약 → 응답

#### 7-8. `agent/core.py` — 기능 모드 분기 확장
```python
def handle_input(self, user_input: str, mode: str) -> str:
    if mode == "chat":
        return self.router.handle_turn(user_input)
    elif mode == "function":
        tool = self.select_tool(user_input)    # 도구 선택
        params = tool.parse_params(            # LLM: 자연어 → JSON
            llm.generate(tool.system_prompt + user_input)
        )
        result = tool.execute(params)          # rule-based 실행
        return result
```

### 완료 기준
- [x] 폴더 정리: 자연어 → JSON 파싱 → 파일 이동 실행 (`tools/folder/classifier.py`)
- [x] 확장자 변환: 이미지 포맷 변환 동작 (Pillow) (`tools/folder/converter.py`)
- [x] 이름 변환: 패턴 규칙 적용 실행 (`tools/folder/renamer.py`)
- [x] 프롬프트 변환: rule-based 변환 구현, 기능 세션 격리 (`tools/prompt_converter.py`)
- [x] 로컬 검색: SQLite FTS5 인덱싱 + MATCH 쿼리 결과 반환 (`tools/search/local_search.py`)
- [ ] 웹 검색: DuckDuckGo 또는 SearXNG 결과 반환 ← 네트워크 의존, 보류
- [x] `agent/core.py` — `handle_input(mode)` 기능 모드 분기 구현 (도구 선택 → LLM 파싱 → execute)

---

## 전체 의존 관계

```
Phase 0 (환경/설정)
    │
    ├─► Phase 1 (LLM 인터페이스)
    │       │
    │       ├─► Phase 2 (대화 엔진)
    │       │       │
    │       │       ├─► Phase 3 (RAG)
    │       │       │
    │       │       └─► Phase 7 (기능 모드 도구) ← Phase 4 병렬 가능
    │       │
    │       └─► Phase 4 (플로팅 UI) ← Phase 2와 병렬 가능
    │
    └─► Phase 5 (LoRA 학습)
            │
            └─► Phase 6 (GGUF 배포)
```

- Phase 4는 `agent.chat()` 인터페이스만 있으면 Phase 2/3와 병렬 진행 가능
- Phase 5/6는 대화 엔진 완성과 무관하게 데이터 준비 후 진행 가능
- Phase 7은 Phase 2의 `agent/core.py` 기본 구조와 Phase 4의 `mode_switcher.py`가 있으면 진행 가능

---

## CI 구성

> `main`, `dev` 브랜치 push/PR 시 GitHub Actions 자동 실행

| Job | 내용 | 비고 |
|---|---|---|
| lint | `ruff check .` | E402(sys.path 패턴), E501, F401 ignore |
| data-validate | `build_dataset.py --dry_run` + `dataset.py` 구조 검증 | torch 없이 경량 실행 |

- `.github/workflows/ci.yml` ✅
- `pyproject.toml` — `[tool.ruff]` 설정 추가 ✅
- GPU 학습 smoke test는 모델 다운로드 비용 문제로 로컬 전용
