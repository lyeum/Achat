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
  QLoRA 파인튜닝 (peft + bitsandbytes)
  - 4-bit base + LoRA adapter (rank 16~32)
  - gradient_checkpointing=True, batch_size=1
  - max_seq_length=512 (한국어 토큰 밀도 고려)
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
│       └─ phases.md              # Phase 0~7 실행 계획서
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
│   │   └─ CH_haru.yaml
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
├─ ui/                             # PySide6 플로팅 UI (배포 환경)
│   ├─ widget.py                  # 메인 위젯 (Frameless / Always-on-top / 모서리 스냅)
│   ├─ chat_panel.py              # 채팅 패널 (스트리밍 토큰 표시)
│   ├─ tray.py                    # 시스템 트레이
│   └─ mode_switcher.py           # 대화 모드 ↔ 기능 모드 전환 UI
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
│   ├─ lora_train.py
│   └─ dataset.py
│
├─ data/
│   └─ lora/                      # QLoRA 파인튜닝 학습 데이터
│       ├─ conversation/           # 대화 모드용 캐릭터 대화 데이터
│       └─ function/               # 기능 모드용 자연어 → JSON 파라미터 추출 예시
│
├─ scripts/                        # 변환 스크립트
│   ├─ merge_lora.py              # LoRA 병합
│   └─ convert_to_gguf.sh         # GGUF 변환 + 양자화
│
├─ eval/                           # 평가 스크립트 (Phase 5 이후)
│   ├─ ai_tell_checker.py         # 이질감 자동 감지
│   ├─ memory_test.py             # 메모리 정확도 측정
│   └─ speed_bench.py             # 추론 속도 벤치마크
│
├─ main.py                         # 진입점
├─ config.py                       # 환경 설정 (dev / deploy 분기)
├─ requirements-dev.txt            # Linux GPU 환경
└─ requirements-deploy.txt         # Windows CPU 환경
```

---

## 실현 가능성 검토 (현재 환경 기준)

| 단계 | 실현 가능성 | 비고 |
|---|---|---|
| QLoRA 파인튜닝 (3B) | ✅ 가능 | 8GB VRAM 내 동작, gradient_checkpointing 필수 |
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
| RTX 5060 Ti BnB | ⚠️ 주의 | `bitsandbytes >= 0.44` + `CUDA 12.8+` 필수 |

---

## 로드맵

### Phase 0 — 환경 구성 및 기반 설계
> 목표: 개발/배포 환경 분리, 설정 파일 구조 확정

- [x] `requirements-dev.txt` / `requirements-deploy.txt` 분리
- [x] `config.py` — dev / deploy 환경 분기 설정
- [x] 캐릭터 YAML 스키마 확정 (`speech_style`, `memory_voice`, `state` 필드 추가) — `CH_haru.yaml` 반영 완료
- [x] 메모리 VDB 스키마 확정 (`M_schema.json` 확장) — 중요도 규칙, 검색 설정 반영 완료

---

### Phase 1 — LLM 인터페이스 구현
> 목표: llama-cpp-python 기반 로컬 추론 인터페이스 구현
> 상세 구현: [대화품질.md](대화품질.md) — Context Assembly, 토큰 예산 설계

- [ ] `conversation/core/llm_client.py` — llama-cpp-python 스트리밍 인터페이스
- [ ] `conversation/core/prompt_build.py` — Context Assembly + 토큰 예산 관리
  - 레이어별 예산: system(300) + world(200) + VDB(150) + history(300) + input(가변)
  - 한국어 토큰 밀도 반영 (영어 대비 2~3배)
- [ ] CLI 수준 기본 대화 루프 동작 확인

---

### Phase 2 — 대화 엔진 구현
> 목표: 페르소나, 상태, 메모리, Post-processing 전 레이어 완성
> 상세 구현: [대화품질.md](대화품질.md) — 7계층 아키텍처, session/state/memory 구현 계획

- [ ] `conversation/core/session.py` — `mood`, `affection`, `turn_count` 필드 추가
- [ ] `agent/persona.py` — 캐릭터 YAML 로딩 및 핫스왑
- [ ] `agent/state.py` — mood / affection 상태 정의 및 전환 규칙
- [ ] `memory/short_term.py` — 최근 N턴 슬라이딩 윈도우 버퍼
- [ ] `memory/long_term.py` — ChromaDB 저장 / 시맨틱 검색 (bge-m3)
- [ ] `memory/summarizer.py` — N턴 트리거 + 요약 + 중요도 scoring
- [ ] `conversation/core/router.py` — Post-processing 레이어
  - mood / affection 업데이트
  - 메모리 쓰기 트리거 체크
  - Act 전환 조건 체크

---

### Phase 3 — RAG 구현
> 목표: 세계관 문서 시맨틱 검색 연동
> 상세 구현: [대화품질.md](대화품질.md) — 시맨틱 검색 전략, 캐릭터 관점 재서술

- [ ] `rag/index.py` — 세계관 문서 청킹 + ChromaDB 인덱싱 (bge-m3)
- [ ] `rag/retrieve.py` — 시맨틱 유사도 검색, 임계값 0.7 이상만 반환
  - 키워드 트리거 방식 **사용 안 함** — 매 턴 유사도 검색, 결과 없으면 삽입 안 함
- [ ] 검색 결과를 캐릭터 관점으로 재서술 후 Layer C에 삽입

---

### Phase 4 — 플로팅 UI 구현
> 목표: PySide6 PIP 스타일 플로팅 UI (Windows 배포 대상)

- [ ] `ui/widget.py` — Frameless / Always-on-top / 모서리 스냅 / hover 투명도 전환
- [ ] `ui/chat_panel.py` — 스트리밍 토큰 표시 채팅 패널
- [ ] `ui/tray.py` — 시스템 트레이 아이콘 및 메뉴
- [ ] `ui/mode_switcher.py` — 대화 모드 ↔ 기능 모드 전환 UI
- [ ] 최소화 시 버블 축소 → 클릭 시 확장 동작
- [ ] 캐릭터 전환 UI 연동

---

### Phase 5 — LoRA 파인튜닝 파이프라인
> 목표: 캐릭터 말투 / 감정 반응 / 한국어 일관성 강화 + 기능 모드 파라미터 추출 능력 확보

- [ ] `data/lora/conversation/` — ChatML 포맷 캐릭터 대화 데이터 구축
- [ ] `data/lora/function/` — 자연어 → JSON 파라미터 추출 예시 데이터 구축
  - 폴더 정리 / 프롬프트 변환 / 검색 각각의 입출력 예시 포함
- [ ] `training/dataset.py` — 두 데이터셋 혼합 로더
- [ ] `training/lora_train.py` — QLoRA 학습 (8GB VRAM 최적화 설정)
- [ ] 학습 후 평가 (`docs/학습후보.md` 평가 척도 기준)

---

### Phase 6 — GGUF 변환 및 배포 패키징
> 목표: Windows CPU 배포 가능한 단일 패키지 구성
> 상세 구현: [학습후보.md](학습후보.md) — merge_lora, convert_to_gguf 스크립트 계획

- [ ] `scripts/merge_lora.py` — LoRA 병합 (`low_cpu_mem_usage=True`)
- [ ] `scripts/convert_to_gguf.sh` — GGUF 변환 + Q4_K_M 양자화
- [ ] `requirements-deploy.txt` 검증
- [ ] 실행 스크립트 작성 (`run.bat`)

---

### Phase 7 — 기능 모드 도구 구현
> 목표: 폴더 정리 / 프롬프트 변환 / 검색엔진 마이크로서비스 구현

- [ ] `tools/base.py` — Tool 인터페이스 확정 (파라미터 수신 → 실행 → 결과 반환)
- [ ] `tools/folder/classifier.py` — 확장자 / MIME 기반 파일 분류
- [ ] `tools/folder/converter.py` — 확장자 일괄 변환 (Pillow 기반, ffmpeg 선택)
- [ ] `tools/folder/renamer.py` — 이름 일괄 변환 (pathlib)
- [ ] `tools/prompt_converter.py` — 프롬프트 변환
- [ ] `tools/search/local_search.py` — SQLite FTS5 기반 로컬 파일 검색
- [ ] `tools/search/web_search.py` — DuckDuckGo / SearXNG 연동
- [ ] `agent/core.py` — 기능 모드 분기 및 도구 라우팅 연동

---

## 환경 요구사항

### 개발 환경 (학습) — 현재 구성
| 항목 | 현재 스펙 | 비고 |
|---|---|---|
| GPU | RTX 5060 Ti | Blackwell(GB206), CUDA 12.8+ 필수 |
| VRAM | 8GB | 3B QLoRA 학습 가능, gradient_checkpointing 필수 |
| 시스템 RAM | 8GB | LoRA 병합 시 타이트 (다른 프로세스 종료 권장) |
| OS | Linux | — |
| CUDA | **12.8+** | RTX 50 시리즈 BitsAndBytes 대응 버전 |
| Python | 3.10+ | 3.11 권장 |
| bitsandbytes | **>=0.44.0** | Blackwell SM 10.x 지원 버전 |

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

## 알려진 제약 및 주의사항

- **LoRA 병합 RAM**: 3B FP16 병합에 ~6GB 소모. 실행 전 브라우저/기타 프로세스 종료 필수.
  OOM 발생 시 `low_cpu_mem_usage=True`, `device_map="cpu"` 옵션 사용.
- **RTX 5060 Ti BitsAndBytes**: `bitsandbytes >= 0.44.0` + `CUDA 12.8+` 조합 필수.
  확인: `python -c "import bitsandbytes as bnb; print(bnb.__version__)"`
- **한국어 토큰 비용**: 영어 대비 2~3배 소모. 컨텍스트 패킹 시 반드시 반영.
- **CPU 추론 속도**: 3B Q4_K_M 기준 8~15 tok/s. 스트리밍 출력으로 체감 속도 보완.
- **ChromaDB 로컬 저장 경로**: 개발/배포 환경 각각 경로 분리 필요.
- **1.5B 폴백 기준**: 병합 OOM, BnB 호환 이슈, 학습 VRAM 부족 중 하나라도 발생 시 전환.
- **JSON 파라미터 추출 안정성**: 3B 기반 모델은 파인튜닝 없이 JSON 출력이 불안정할 수 있음.
  기능 모드용 자연어 → JSON 예시 데이터를 Phase 5 학습 데이터에 반드시 포함할 것.
- **확장자 변환 범위**: 이미지(jpg/png/webp/bmp), 문서(txt/md)는 외부 의존 없음.
  영상/음성 변환은 ffmpeg 바이너리 필요 — 선택적 기능으로 분리 권장.
- **인터넷 검색**: DuckDuckGo 비공식 API는 rate limit 있음. 안정성이 필요하면 SearXNG 셀프호스팅 권장.
