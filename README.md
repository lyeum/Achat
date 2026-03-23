# Achat — 플로팅 PIP 캐릭터 챗봇 + 기능 도우미

다양한 가상 캐릭터와 자연스러운 대화를 나눌 수 있는 플로팅 PIP형 챗봇.
한국어 주 사용 / Qwen2.5-3B 기반 / LoRA 파인튜닝 → GGUF 배포 파이프라인.

**두 가지 상위 모드:**
- **대화 모드** — 캐릭터 챗봇 (기존 설계)
- **기능 모드** — 선택한 작업에 특화된 챗봇 UI. 실행은 rule-based Python, LLM은 자연어 → 파라미터 추출만 담당.

> 대화 품질 설계 상세: [대화품질.md](대화품질.md)
> 학습 모델 후보 및 실험 설계: [학습후보.md](학습후보.md)

---

## 개발 환경 (실제 스펙)

| 항목 | 사양 |
|---|---|
| GPU | RTX 5060 Ti (Blackwell / GB206) |
| VRAM | 8GB |
| 시스템 RAM | 8GB |
| OS | Linux |
| CUDA | 12.8+ 필요 (Blackwell 대응) |

---

## 모델 선택 근거

> **목표 모델: Qwen2.5-3B-Instruct** (1.5B는 폴백)

| 모델 | VRAM 추론 | QLoRA 학습 VRAM | LoRA 병합 CPU RAM | 판정 |
|---|---|---|---|---|
| Qwen2.5-7B | FP16 ~14GB | ~7-8GB (한계) | **~14GB ❌** | **불가** |
| **Qwen2.5-3B** | FP16 ~6GB | ~4-6GB ✅ | **~6GB ⚠️** | **채택** |
| Qwen2.5-1.5B | FP16 ~3GB | ~3-4GB ✅ | **~3GB ✅** | 폴백 |

**7B 탈락 이유:**
- LoRA 병합 단계에서 FP16 전체 모델을 CPU RAM에 올려야 함 → 14GB 필요
- 현재 시스템 RAM 8GB로는 물리적으로 불가

**3B 채택 이유:**
- QLoRA 학습: 4-bit 기반 모델(~2GB) + LoRA + 옵티마이저 합산 ~5GB → 8GB VRAM 내에서 동작
- LoRA 병합: ~6GB RAM 필요 → 8GB에서 타이트하지만 가능
- 캐릭터 챗봇 용도에서 파인튜닝 특화 시 3B로 충분한 품질 확보 가능

**1.5B 폴백 조건:**
- 병합 단계에서 OOM 발생 시
- 또는 RTX 5060 Ti + BitsAndBytes 호환 이슈가 지속될 경우

---

## 전체 파이프라인

```
[개발 환경: Linux + RTX 5060 Ti (VRAM 8GB / RAM 8GB)]
        │
        ▼
  Qwen2.5-3B-Instruct (HuggingFace)
        │
        ▼
  LoRA 파인튜닝 (peft, bfloat16 풀 파라미터)
  - bfloat16 base + LoRA adapter (rank 16) ← BitsAndBytes 미사용 (Blackwell SM 10.x 미지원)
  - gradient_checkpointing=True, batch_size=1, grad_accum=8
  - max_seq_length=512 (한국어 토큰 밀도 고려)
  - assistant 토큰 마스킹 — system/user 구간은 loss 제외 (v7~)
  - 캐릭터 말투 / 감정 반응 / 한국어 일관성
  - 기능 모드용 자연어 → JSON 파라미터 추출 예시 포함
        │
        ▼
  LoRA 가중치 병합 (merge_and_unload, CPU 오프로드)
  ⚠️ RAM 약 6GB 사용 — 다른 프로세스 종료 후 실행 권장
        │
        ▼
  GGUF 변환 (llama.cpp convert_hf_to_gguf.py)
        │
        ▼
  Q4_K_M 양자화 (llama.cpp quantize)
  - 최종 파일 크기: 약 2GB
        │
  ───────────────────────────────────────
        │
[배포 환경: Windows + CPU]
        │
        ▼
  llama-cpp-python (CPU 추론)
  - 3B Q4_K_M 예상 속도: 8~15 tok/s
        │
        ▼
  PySide6 플로팅 UI (PIP 스타일)
  - Frameless / Always-on-top / 모서리 스냅
  - hover 투명도 전환 / 최소화 시 버블 축소
  - 대화 모드 ↔ 기능 모드 전환
```

---

## 대화 엔진 아키텍처 (개요)

> 상세 설계는 [대화품질.md](대화품질.md) 참조

```
User Input
    │
    ▼
[모드 분기]
    ├── 대화 모드 ──────────────────────────────────────────────┐
    │                                                            │
    │   [Pre-processing]  — 의도 분류, 엔티티 추출              │
    │       │                                                    │
    │       ├──────────────────────┐                            │
    │       ▼                      ▼                            │
    │   [단기 메모리]         [장기 메모리 VDB]                 │
    │    최근 3~5턴 직접 삽입   시맨틱 유사도 검색              │
    │    (검색 없이)            (bge-m3, 임계값 0.7+)           │
    │       │                      │                            │
    │       └──────────┬───────────┘                            │
    │                  ▼                                         │
    │   [Context Assembly]  — 토큰 예산 관리                    │
    │     Layer A: 캐릭터 시스템 프롬프트 (고정, ~300 tok)      │
    │     Layer B: 세계관 + 현재 Act 상황  (고정, ~200 tok)     │
    │     Layer C: VDB 검색 결과           (동적, ~150 tok)     │
    │     Layer D: 단기 버퍼 최근 N턴      (동적, ~300 tok)     │
    │     Layer E: 현재 사용자 입력                              │
    │                  │                                         │
    │                  ▼                                         │
    │            LLM (llama-cpp)                                 │
    │                  │                                         │
    │                  ▼                                         │
    │   [Post-processing]                                        │
    │     - mood / affection 상태 업데이트                      │
    │     - Act 전환 조건 체크                                   │
    │     - 메모리 쓰기 트리거 체크 (N턴 도달 시)               │
    │                  │                                         │
    │           N턴 조건 충족 시                                 │
    │                  ▼                                         │
    │   [Memory Write Pipeline]                                  │
    │     요약 → 중요도 scoring → 임베딩 → ChromaDB 저장        │
    │                                                            │
    └── 기능 모드 ──────────────────────────────────────────────┘

        [선택한 기능 전용 시스템 프롬프트로 LLM 교체]
        [대화 히스토리 / 장기 메모리 격리 — 기능 세션은 미기록]
            │
            ▼
        LLM (llama-cpp) — 자연어 → JSON 파라미터 추출
            │
            ▼
        [Rule-based 실행기] — 실제 작업 처리 (Python)
            │
            ▼
        결과 요약 → 사용자에게 응답
```

---

## 기능 모드 — 도구 목록

각 도구는 대화 엔진에만 종속된 독립 마이크로서비스 형태.
LLM은 자연어 해석 및 파라미터 추출만 담당, 실행은 rule-based Python.

### 폴더 정리
| 세부 기능 | 방식 |
|---|---|
| 파일 분류 | 확장자 / MIME 타입 기반 자동 분류, 분류 기준은 자연어로 지정 |
| 확장자 일괄 변환 | 이미지(jpg/png/webp/bmp), 문서(txt/md) — 외부 의존 없음. 영상/음성은 ffmpeg 선택 의존 |
| 이름 일괄 변환 | 패턴/규칙 자연어 지정 → LLM이 rename 규칙 파싱 → `pathlib` 실행 |

### 프롬프트 변환
- 사용자가 작성한 텍스트를 LLM 프롬프트 형태로 재구성
- 기능 전용 시스템 프롬프트로 교체하여 대화 모드와 완전 분리

### 검색엔진
| 종류 | 방식 |
|---|---|
| 로컬 검색 | SQLite FTS5 또는 whoosh 기반 파일 인덱싱 |
| 인터넷 검색 | DuckDuckGo(무료 비공식) / SearXNG(셀프호스팅) / Brave Search API(선택) |

---

## 디렉토리 구조

```
Achat/
│
├─ docs/                           # 프로젝트 문서
│   ├─ README.md                  # 총괄 문서 (이 파일)
│   ├─ DIR.md                     # 파일시스템 현황 참조
│   ├─ 대화품질.md                # Phase 1~3 상세 설계
│   ├─ 학습후보.md                # Phase 5~6 학습 실험 설계
│   └─ plan/
│       ├─ phases.md              # Phase 0~7 실행 계획서
│       └─ training_개선.md       # EWC / 카테고리 가중치 / assistant 마스킹 구현 계획
│
├─ conversation/                   # 대화 엔진 (핵심)
│   ├─ core/
│   │   ├─ llm_client.py          # llama-cpp-python 인터페이스
│   │   ├─ prompt_build.py        # Context Assembly + 토큰 예산
│   │   ├─ router.py              # 턴 처리 + Post-processing
│   │   └─ session.py             # 세션 상태 (mood, affection, turn_count)
│   ├─ loader/
│   │   ├─ character_load.py      # 캐릭터 YAML 로더
│   │   ├─ memory_load.py         # 메모리 로더
│   │   └─ world_load.py          # 세계관 로더
│   ├─ memory_act/                # 메모리 스키마 및 초기 데이터
│   │   ├─ M_schema.json          # VDB 저장 단위 스키마
│   │   ├─ M_default.json
│   │   └─ M_instance.json
│   ├─ character/                  # 캐릭터 설정 파일
│   │   ├─ CH_schema.json
│   │   ├─ CH_Haru.yaml
│   │   ├─ CH_Seonjae.yaml
│   │   └─ CH_default.yaml
│   ├─ world/                      # 세계관 설정 파일
│   │   ├─ W_schema.json
│   │   └─ W_sea.yaml
│   └─ main.py
│
├─ memory/                         # 메모리 관리 레이어
│   ├─ short_term.py              # 슬라이딩 윈도우 (최근 N턴)
│   ├─ long_term.py               # ChromaDB VDB 저장 / 검색
│   └─ summarizer.py              # 요약 + 중요도 scoring + 쓰기 트리거
│
├─ rag/                            # RAG 파이프라인
│   ├─ index.py                   # 세계관 문서 청킹 + ChromaDB 인덱싱
│   ├─ retrieve.py                # 시맨틱 유사도 검색 (bge-m3)
│   └─ sources/                   # 세계관 원본 문서
│       └─ world/
│           ├─ culture.md
│           ├─ place.md
│           └─ story.md
│
├─ agent/                          # Agent 오케스트레이터
│   ├─ core.py                    # 전체 흐름 조율 + 모드 분기
│   ├─ persona.py                 # 캐릭터 YAML 로딩 + 핫스왑
│   ├─ state.py                   # mood / affection 상태 정의
│   └─ router.py                  # 시동어 / 명령어 분기
│
├─ ui_ux/                          # QML + PySide6 플로팅 UI/UX (배포 환경)
│   ├─ bridge.py                  # ChatBridge(QObject) — QML↔Python 시그널/슬롯
│   ├─ chat_panel.py              # LLMWorker(QThread) — 백그라운드 LLM 추론
│   ├─ widget.py                  # UIEngine — QML 엔진 래퍼
│   ├─ tray.py                    # 시스템 트레이
│   ├─ qml/
│   │   ├─ Style.qml              # 디자인 토큰 singleton (색상/폰트/애니메이션)
│   │   ├─ main.qml               # 플로팅 윈도우 (버블 축소/확장, 드래그, 스냅)
│   │   └─ ChatBubble.qml         # 재사용 말풍선 컴포넌트
│   └─ assets/
│       ├─ icons/                 # 앱 아이콘 PNG
│       └─ characters/            # 캐릭터 PNG/GIF
│
├─ tools/                          # 기능 모드 — 도구 마이크로서비스
│   ├─ base.py                    # Tool 인터페이스 (파라미터 수신 → 실행 → 결과 반환)
│   ├─ folder/
│   │   ├─ classifier.py          # 파일 분류 (확장자 / MIME)
│   │   ├─ converter.py           # 확장자 일괄 변환
│   │   └─ renamer.py             # 이름 일괄 변환
│   ├─ prompt_converter.py        # 프롬프트 변환
│   └─ search/
│       ├─ local_search.py        # 로컬 파일 인덱싱 + FTS 검색
│       └─ web_search.py          # 인터넷 검색 (DuckDuckGo / SearXNG)
│
├─ training/                       # LoRA 파인튜닝
│   ├─ lora_train.py              # 학습 스크립트 (bfloat16, assistant 마스킹, EWCTrainer, GPU/CPU 자동 전환)
│   ├─ ewc.py                     # EWC Fisher 계산 CLI + EWCPenalty 클래스
│   ├─ train_monitor.py           # 학습 모니터링 래퍼 — 과적합 감지 시 조기 종료 + VRAM 해제
│   ├─ dataset.py                 # 데이터셋 로더 (ChatML, stratified sampling, category_weights)
│   ├─ 학습.md                    # 학습 가이드 (구조 분석, 실행법, 개선안)
│   ├─ eval/                      # 학습 결과 검증 스크립트
│   │   ├─ ai_tell_checker.py     # AI투 표현 패턴 측정 (학습 후 자동 실행)
│   │   ├─ memory_test.py         # 기억 유지 정확도 (5케이스, 자동 실행)
│   │   ├─ speed_bench.py         # 추론 속도 벤치마크 (수동)
│   │   └─ verify_phases.py       # Phase 2/3 실환경 검증 12턴 (수동)
│   ├─ data/                      # 학습 데이터 (2,401건, 38파일)
│   │   ├─ affection/             # 친밀도 단계별 (6단계: stranger~intimate)
│   │   ├─ common/                # memory_ref / ai_tell_removal / persona_follow
│   │   ├─ emotion/               # 감정 상태별 (9종: neutral/happy/affectionate/touched/curious/sad/embarrassed/annoyed/angry)
│   │   ├─ long_dialogue/         # 장대화 (8-15턴: daily_chat / emotional_support / casual_deep)
│   │   ├─ personality/           # 5종 성격별
│   │   └─ speech_style/          # 말투 조합
│   └─ log/                       # MVP 대화 로그 수집 (카테고리별 JSONL)
│
├─ output/                        # LoRA 어댑터 출력 (.gitignore 처리)
│   ├─ LoRA_v8/                   # v8 (eval best 1.353, 5 epoch 과적합)
│   └─ LoRA_v9/adapter/           # 현재 어댑터 (eval best 1.511, 3 epoch, EWC λ=500)
│
├─ data/
│   └─ lora/
│       ├─ conversation/           # training/log 빌드 후 생성 (scripts/build_dataset.py)
│       └─ function/               # 기능 모드용 자연어 → JSON 파라미터 추출 예시
│
├─ scripts/                        # 변환 스크립트
│   ├─ merge_lora.py              # LoRA 병합
│   └─ convert_to_gguf.sh         # GGUF 변환 + 양자화
│
│
├─ main.py                         # 진입점
├─ config.py                       # 환경 설정 (dev / deploy 분기)
├─ pyproject.toml                  # 개발 환경 의존성 (uv, Linux + GPU)
├─ pyproject-deploy.toml           # 배포 환경 의존성 (uv, Windows + CPU)
└─ uv.lock                         # uv lock 파일 (dev 기준)
```

---

## 실현 가능성 검토 (현재 환경 기준)

| 단계 | 실현 가능성 | 비고 |
|---|---|---|
| LoRA 파인튜닝 (3B) | ✅ 완료 | bfloat16 풀 파라미터 + LoRA, BitsAndBytes 미사용, LoRA_v9 완료 (EWC λ=500, 3 epoch, memory_test 4/5) |
| LoRA 병합 | ⚠️ 타이트 | RAM ~6GB 소모, 병합 시 다른 프로세스 최소화 필요 |
| GGUF 변환 | ✅ 가능 | Qwen2.5는 llama.cpp 공식 지원 |
| Q4_K_M 양자화 | ✅ 가능 | 3B 기준 최종 파일 ~2GB |
| CPU 추론 (Windows) | ✅ 가능 | 3B는 7B보다 빠름, AVX2 이상 권장 |
| PySide6 PIP 플로팅 UI | ✅ 가능 | Frameless + Always-on-top + 모서리 스냅, 외부 OS API 불필요 |
| 시맨틱 메모리 검색 | ✅ 가능 | ChromaDB + bge-m3, 로컬 동작 |
| 폴더 정리 도구 | ✅ 가능 | pathlib / shutil 기반 rule-based, 이미지 확장자 변환은 Pillow |
| 프롬프트 변환 도구 | ✅ 가능 | 기능 전용 시스템 프롬프트 교체로 구현 |
| 로컬 검색 도구 | ✅ 가능 | SQLite FTS5 또는 whoosh |
| 인터넷 검색 도구 | ⚠️ API 의존 | DuckDuckGo 비공식 or SearXNG 셀프호스팅 권장 |
| JSON 파라미터 추출 (3B) | ⚠️ 주의 | 파인튜닝 데이터에 기능 모드 예시 필수 포함 |
| RTX 5060 Ti BnB | ✅ 미사용 | Blackwell SM 10.x 호환 이슈로 BitsAndBytes 대신 bfloat16 풀 파라미터 채택 |

---

## 로드맵

### Phase 0 — 환경 구성 및 기반 설계
> 목표: 개발/배포 환경 분리, 설정 파일 구조 확정

- [x] `pyproject.toml` / `pyproject-deploy.toml` 구성 (uv 기반, Linux+GPU / Windows+CPU 분리)
- [x] `config.py` — dev / deploy 환경 분기 설정
- [x] 캐릭터 YAML 스키마 확정 (`speech_style`, `memory_voice`, `state` 필드 추가) — `CH_haru.yaml` 반영 완료
- [x] 메모리 VDB 스키마 확정 (`M_schema.json` 확장) — 중요도 규칙, 검색 설정 반영 완료

---

### Phase 1 — LLM 인터페이스 구현
> 목표: llama-cpp-python 기반 로컬 추론 인터페이스 구현
> 상세 구현: [대화품질.md](대화품질.md) — Context Assembly, 토큰 예산 설계

- [x] `conversation/core/llm_client.py` — llama_cpp + transformers 듀얼 백엔드 (스트리밍 포함)
- [x] `conversation/core/prompt_build.py` — Context Assembly + 토큰 예산 관리
  - 레이어별 예산: system(300) + world(200) + VDB(150) + history(300) + input(가변)
  - 한국어 토큰 밀도 반영 (영어 대비 2~3배)
- [x] `conversation/core/session.py` — mood, affection, turn_count, dialogue_log
- [x] `conversation/loader/` — character_load, world_load, memory_load
- [x] `conversation/main.py` — CLI 루프 (dry-run 모드 포함)

---

### Phase 2 — 대화 엔진 구현
> 목표: 페르소나, 상태, 메모리, Post-processing 전 레이어 완성
> 상세 구현: [대화품질.md](대화품질.md) — 7계층 아키텍처, session/state/memory 구현 계획

- [x] `agent/persona.py` — 캐릭터 YAML 로딩 및 핫스왑 (`load_persona`, `swap_persona`)
- [x] `agent/state.py` — mood_triggers 키워드 매칭 (8종), affection 증감 (캐릭터 YAML affection_delta 우선)
- [x] `agent/core.py` — 전체 컴포넌트 초기화 + 대화 모드 진입점 `chat()`
- [x] `memory/short_term.py` — `get_recent()` 슬라이딩 윈도우
- [x] `memory/long_term.py` — ChromaDB store/query (bge-m3, threshold 0.7, importance ≥ 0.5 필터)
- [x] `memory/summarizer.py` — N턴 트리거 + LLM 요약 + 키워드 중요도 scoring + VDB 저장
- [x] `conversation/core/router.py` — `handle_turn()` 전체 턴 파이프라인
  - VDB 검색 → PromptBuilder → LLM → mood/affection 업데이트 → 세션 기록 → 요약 트리거
- [x] `conversation/main.py` — Router 연동으로 업데이트

---

### Phase 3 — RAG 구현
> 목표: 세계관 문서 시맨틱 검색 연동
> 상세 구현: [대화품질.md](대화품질.md) — 시맨틱 검색 전략, 캐릭터 관점 재서술

- [x] `rag/index.py` — 세계관 문서 청킹(400자/overlap 50) + ChromaDB 인덱싱 (bge-m3, cosine space)
- [x] `rag/retrieve.py` — `WorldRetriever.query()` 매 턴 실행, threshold 0.7 미만 빈 리스트 반환
- [x] `conversation/core/prompt_build.py` — `assemble(rag_results=)` 추가, Layer B에 RAG 결과 병합
- [x] `conversation/core/router.py` — RAG 검색 연동 (장기 메모리 > 세계관 RAG 우선순위)

---

### Phase 4 — 플로팅 UI 구현
> 목표: QML + PySide6 PIP 스타일 플로팅 UI (Windows 배포 대상)

- [x] `ui_ux/bridge.py` — `ChatBridge(QObject)` Python↔QML 브리지 (Signal/Slot)
- [x] `ui_ux/chat_panel.py` — `LLMWorker(QThread)` 비동기 LLM 호출
- [x] `ui_ux/widget.py` — `UIEngine` QML 엔진 초기화 + bridge 등록
- [x] `ui_ux/tray.py` — `AppTrayIcon` 열기/숨기기, 캐릭터 변경, 종료
- [x] `ui_ux/qml/main.qml` — 플로팅 윈도우 (전체 창 드래그, 모서리 스냅, hover 투명도, 버블 축소/확장, 모드 전환, 한글 폰트 로드)
- [x] `ui_ux/qml/ChatBubble.qml` — 재사용 가능한 말풍선 컴포넌트
- [x] `ui_ux/qml/Style.qml` — 디자인 토큰 singleton
- [x] `main.py` — torch 선로드 → Qt 초기화 순서 보장, PID 파일 기반 이전 프로세스 정리, VRAM 체크

---

### Phase 5 — LoRA 파인튜닝 파이프라인
> 목표: 캐릭터 말투 / 감정 반응 / 한국어 일관성 강화 + 기능 모드 파라미터 추출 능력 확보

- [x] `data/lora/conversation/` — 빌드 대상 디렉토리 생성
- [x] `data/lora/function/` — folder_organize / prompt_convert / search 예시 데이터
- [x] `scripts/build_dataset.py` — training/log → data/lora/conversation 빌드 (시스템 프롬프트 자동 삽입)
- [x] `training/dataset.py` — 데이터셋 로더 (apply_chat_template, stratified sampling)
- [x] `training/lora_train.py` — GPU/CPU 자동 전환, --no_save/--max_steps, BitsAndBytes 미사용 (Blackwell 호환), v7~: assistant 토큰 마스킹, EWCTrainer / --ewc_* / --category_weights 추가
- [x] `training/ewc.py` — Fisher 대각 계산 CLI + `EWCPenalty` 클래스 (7-2 EWC 구현 완료)
- [x] `training/dataset.py` — `category_weights` 파라미터 추가 — 카테고리별 오버/언더샘플링 (7-3 구현 완료)
- [x] `training/학습.md` — 학습 구조 리뷰, 실행 가이드, 개선안 (EWC/카테고리 가중치 구현 완료)
- [x] `training/eval/ai_tell_checker.py` / `training/eval/memory_test.py` / `training/eval/speed_bench.py` / `training/eval/verify_phases.py` 구현 (구 `eval/` 폴더에서 `training/eval/`로 이동)
- [x] `training/train_monitor.py` — 과적합 모니터링 + 조기 종료 + VRAM 해제 래퍼 구현
- [x] 학습 데이터 확장: `emotion/` (9종 × 20건 = 180건) + `long_dialogue/` (54건) 추가 → 총 2,401건 (38파일)
- [x] CPU smoke test 완료 (`--max_steps 1 --no_save`, loss=3.798)
- [x] (실행 검증) LoRA_v7 GPU 학습 완료 (4 epoch, 2,167건, assistant masking, eval best 1.687)
- [x] (실행 검증) LoRA_v8 GPU 학습 완료 (5 epoch, 2,401건, category_weights, eval best 1.353 / 과적합 발생)
- [x] 훈련 데이터 system prompt 정제 — emotion/long_dialogue 234건에서 "너는 하루다." 제거
- [x] `training/lora_train.py` `--data_dir` 기본값 `data/lora` → `training/data` 수정
- [ ] (실행 검증) LoRA_v9 GPU 학습 완료 (3 epoch, EWC λ=500, 데이터 정제 후)

---

### Phase 6 — GGUF 변환 및 배포 패키징
> 목표: Windows CPU 배포 가능한 단일 패키지 구성
> 상세 구현: [학습후보.md](학습후보.md) — merge_lora, convert_to_gguf 스크립트 계획

- [x] `scripts/merge_lora.py` — LoRA 병합 (`low_cpu_mem_usage=True`)
- [x] `scripts/convert_to_gguf.sh` — GGUF 변환 + Q4_K_M 양자화
- [x] `run.bat` — Windows 배포 실행 스크립트
- [ ] GPU 파인튜닝 실행 — RTX 5060 Ti 3 epoch 완료 및 평가 결과 기록
- [ ] (실행 검증) merge → GGUF 변환 → Windows `run.bat` 전체 배포 파이프라인 작동 확인
- [ ] (실행 검증) `pyproject-deploy.toml` Windows 클린 설치 확인
- [ ] (실행 검증) CPU 추론 속도 8+ tok/s 달성 확인

---

### Phase 7 — 기능 모드 도구 구현
> 목표: 폴더 정리 / 프롬프트 변환 / 검색엔진 마이크로서비스 구현

- [x] `tools/base.py` — `BaseTool` 인터페이스 (JSON 파라미터 파싱 + execute 추상 메서드)
- [x] `tools/folder/classifier.py` — 확장자별 / 종류별 파일 분류 (shutil.move, dry_run)
- [x] `tools/folder/converter.py` — 이미지 포맷 변환 (Pillow: jpg/png/webp/bmp/tiff)
- [x] `tools/folder/renamer.py` — 이름 일괄 변환 (7가지 규칙, glob 패턴, dry_run)
- [x] `tools/prompt_converter.py` — 프롬프트 변환 (명확하게 / 간결하게 / 상세하게 / 질문형 / 지시형)
- [x] `tools/search/local_search.py` — SQLite FTS5 로컬 검색 (증분 인덱싱, mtime 추적)
- [x] `tools/search/web_search.py` — DuckDuckGo Instant Answer API 연동 구현
- [x] `agent/core.py` — `handle_input(mode)` 기능 모드 분기 + 키워드 기반 도구 선택

---

## 환경 요구사항

### 개발 환경 (학습) — 현재 구성
| 항목 | 현재 스펙 | 비고 |
|---|---|---|
| GPU | RTX 5060 Ti | Blackwell(GB206), CUDA 12.8+ 필수 |
| VRAM | 8GB | 3B QLoRA 학습 가능, gradient_checkpointing 필수 |
| 시스템 RAM | 8GB | LoRA 병합 시 타이트 (다른 프로세스 종료 권장) |
| OS | Linux | — |
| CUDA | **12.8+** | RTX 50 시리즈 대응 버전 |
| Python | 3.10+ | 3.11 권장 |
| bitsandbytes | 미사용 | Blackwell SM 10.x 미지원 — bfloat16 풀 파라미터로 대체 |

### 배포 환경 (추론)
| 항목 | 최소 | 권장 |
|---|---|---|
| CPU | AVX2 지원 | AVX-512 지원 |
| 시스템 RAM | 4GB | 8GB |
| OS | Windows 10+ | Windows 11 |
| 저장 공간 | 3GB | 5GB |
| Python | 3.10+ | 3.11 |

---

## 패키지 관리 (uv)

의존성은 uv로 관리합니다. 환경별로 별도 toml 파일을 사용합니다.

| 파일 | 환경 | 용도 |
|---|---|---|
| `pyproject.toml` | Linux + GPU | QLoRA 학습 / 대화 엔진 개발 |
| `pyproject-deploy.toml` | Windows + CPU | GGUF 추론 + PySide6 위젯 실행 |

### 개발 환경 설치 (Linux)
```bash
# uv 설치 (최초 1회)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치 (pyproject.toml 기준)
uv sync

# PyTorch CUDA 12.8 빌드는 [tool.uv.sources] 설정으로 자동 처리됨
```

### 배포 환경 설치 (Windows)
```bash
# pyproject-deploy.toml → pyproject.toml 로 복사 후 sync
copy pyproject-deploy.toml pyproject.toml
uv sync
```

---

## 환경 구축 매뉴얼

### 개발 환경 — Ubuntu 24.04 WSL2 (Linux + GPU)

#### 1. 시스템 패키지 설치
```bash
sudo apt-get update && sudo apt-get install -y \
  # Qt6 / PySide6 런타임
  libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xinerama0 libxcb-xkb1 libegl1 libegl-mesa0 libgl1 libglib2.0-0 \
  # D-Bus + 한글 입력기 (ibus 기반)
  dbus-x11 ibus ibus-hangul
```

> **왜 ibus?** PySide6 번들 Qt6에는 ibus 플러그인이 내장되어 있음.
> `fcitx5-frontend-qt6`는 시스템 Qt6 기준 빌드라 ABI 불일치로 로드 실패함.

#### 2. uv 설치 (최초 1회)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

#### 3. 리포지토리 클론 및 의존성 설치
```bash
git clone <repo-url> ~/projects/Achat
cd ~/projects/Achat
uv sync
```

> `pyproject.toml`에 `pyside6<6.10`이 고정되어 있음.
> PySide6 6.10.x는 WSL2 ibus 연결 실패(invalid portal bus) 버그가 있으므로 6.9.x 이하 사용.

#### 4. 실행
```bash
# UI 테스트 (LLM 없이 UI만 기동)
ACHAT_ENV=ui_test uv run python main.py

# 개발 모드 (HuggingFace 모델 로드)
ACHAT_ENV=dev uv run python main.py
```

> **ibus 설정은 자동 처리됨**: `main.py`가 시작 시 ibus-daemon 기동, hangul 엔진 설정,
> `Ctrl+Space` 한/영 토글 키 등록을 자동으로 수행함. 별도 환경변수 설정 불필요.

> ⚠️ **Ubuntu 24.04 주의**: `eval $(dbus-launch --sh-syntax)` 사용 금지.
> systemd user session이 D-Bus를 관리하므로 dbus-launch를 실행하면 ibus 연결이 끊김.

#### 한글 입력
- 앱 실행 후 TextInput 클릭 → **Ctrl+Space** 로 한/영 전환
- 우측 Alt 키는 WSLg 구조적 한계(modifier state 하드코딩)로 사용 불가
- 한글 입력이 안 될 경우 `~/.bashrc`에 `QT_IM_MODULE=fcitx` 잔재가 있는지 확인
  (main.py가 강제 override하므로 앱 재실행으로 해결됨 — docs/BUG/BUG_1.md 참조)

---

### 배포 환경 — Windows + CPU

#### 1. 모델 파일 준비
```
Achat/
└─ models/
   └─ model_q4km.gguf     ← Phase 6 변환 결과물 배치
```

#### 2. uv 설치 (최초 1회)
```powershell
# PowerShell
winget install --id=astral-sh.uv -e
```

#### 3. 의존성 설치
```powershell
copy pyproject-deploy.toml pyproject.toml
uv sync
```

#### 4. 실행
```powershell
run.bat
# 또는
uv run python main.py
```

---

## CI

GitHub Actions로 `main`, `dev` 브랜치 push/PR 시 자동 실행.

| Job | 내용 |
|---|---|
| lint | `ruff check` — 코드 품질 검사 |
| data-validate | `build_dataset.py --dry_run` + `dataset.py` 구조 검증 (torch 없이 경량 실행) |

파이프라인 smoke test (GPU 학습)는 모델 다운로드 비용 문제로 로컬에서만 실행.

---

## 알려진 제약 및 주의사항

- **LoRA 병합 RAM**: 3B FP16 병합에 ~6GB 소모. 실행 전 브라우저/기타 프로세스 종료 필수.
  OOM 발생 시 `low_cpu_mem_usage=True`, `device_map="cpu"` 옵션 사용.
- **RTX 5060 Ti BitsAndBytes**: Blackwell SM 10.x 4-bit 양자화 미지원 → **bfloat16 풀 파라미터 + LoRA 방식** 채택.
  학습 중 VRAM ~7.7GB(≈96%) 사용. OOM 시 `--max_length 256` 또는 `--grad_accum 16`.
- **한국어 토큰 비용**: 영어 대비 2~3배 소모. 컨텍스트 패킹 시 반드시 반영.
- **CPU 추론 속도**: 3B Q4_K_M 기준 8~15 tok/s. 스트리밍 출력으로 체감 속도 보완.
- **fcitx 잔재 주의**: 이전에 fcitx를 사용했던 환경이라면 `~/.bashrc`에 `QT_IM_MODULE=fcitx`가 남아 있을 수 있음.
  fcitx가 설치되지 않은 상태에서 이 값이 남으면 한글 입력이 완전히 차단됨.
  main.py가 강제 override하므로 앱 내에서는 동작하나, 근본 원인 제거 권장:
  ```bash
  grep -n "fcitx\|IM_MODULE" ~/.bashrc ~/.profile 2>/dev/null
  ```
- **ChromaDB 로컬 저장 경로**: 개발/배포 환경 각각 경로 분리 필요.
- **1.5B 폴백 기준**: 병합 OOM, BnB 호환 이슈, 학습 VRAM 부족 중 하나라도 발생 시 전환.
- **JSON 파라미터 추출 안정성**: 3B 기반 모델은 파인튜닝 없이 JSON 출력이 불안정할 수 있음.
  기능 모드용 자연어 → JSON 예시 데이터를 Phase 5 학습 데이터에 반드시 포함할 것.
- **확장자 변환 범위**: 이미지(jpg/png/webp/bmp), 문서(txt/md)는 외부 의존 없음.
  영상/음성 변환은 ffmpeg 바이너리 필요 — 선택적 기능으로 분리 권장.
- **인터넷 검색**: DuckDuckGo 비공식 API는 rate limit 있음. 안정성이 필요하면 SearXNG 셀프호스팅 권장.
