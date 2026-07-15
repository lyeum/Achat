# Achat — 워크스페이스 브리핑

> Claude가 이 프로젝트에서 즉시 컨텍스트를 파악할 수 있도록 작성된 요약 문서.
> 상세 내용은 `docs/introduce.md` / `docs/참조/구현현황.md` / `docs/참조/ERD.md` 참조.

---

## 프로젝트 정체성

**Achat** — Windows 용 플로팅 PIP형 캐릭터 챗봇 + 기능 도우미.
- 완전 로컬 동작 (인터넷 불필요), 오프라인-퍼스트
- Qwen2.5-3B-Instruct 기반 LoRA 파인튜닝 → GGUF Q4_K_M CPU 배포
- PySide6 + QML 프레임리스 플로팅 UI (Always-on-top, PIP 버블 모드)
- 두 가지 상위 모드: **대화 모드** (캐릭터 챗봇) / **기능 모드** (파일 정리·변환·검색·프롬프트 변환)

---

## 핵심 기술 스택

| 구분 | 내용 |
|---|---|
| 베이스 모델 | Qwen2.5-3B-Instruct (HuggingFace) |
| **현재 채택 어댑터** | **LoRA v11** (`output/LoRA_v11/adapter/`) — eval best 1.5387 @ step 700, r=32/alpha=64, 3,170건 학습 |
| v12 기각 이유 | RAG 주입 시 중국어 전환 치명 결함 (Qwen 베이스 중국어 bias 폭발) → v11 복귀 |
| 학습 방식 | bfloat16 풀 파라미터 + LoRA (BitsAndBytes 미사용 — Blackwell SM 10.x 미지원) |
| 양자화 | GGUF Q4_K_M (~2GB) |
| 추론 | llama-cpp-python CPU (Windows 배포), 8~15 tok/s |
| UI | PySide6 6.9.x + QML |
| 벡터 DB | ChromaDB PersistentClient + BAAI/bge-m3 (cosine) |
| 임베딩 | bge-m3, 384차원, 한국어 최적화 |
| 패키지 관리 | uv (`pyproject.toml` Linux+GPU / `pyproject-deploy.toml` Windows+CPU) |
| 배포 패키징 | PyInstaller + Inno Setup 6 → `AchatSetup.exe` |

---

## 개발 환경 제약

| 항목 | 값 |
|---|---|
| GPU | RTX 5060 Ti (Blackwell GB206) |
| VRAM | 8GB (학습 시 ~96% 점유) |
| 시스템 RAM | 8GB (LoRA 병합 시 ~6GB — 타이트) |
| OS | Linux (WSL2 Ubuntu 24.04) |
| CUDA | 12.8+ (Blackwell 필수) |
| BitsAndBytes | **미사용** (Blackwell SM 10.x 미지원) |
| 한국어 토큰 비용 | 영어 대비 2~3배 (컨텍스트 패킹 시 반드시 반영) |

---

## 핵심 임계값 (config.py 실제 값)

```python
adapter_path = "./output/LoRA_v11/adapter"  # v12 비교 후 v11 복귀 (2026-04-27)
vdb_threshold = 0.60     # LongTermMemory — cosine 유사도 ≥ 0.60
rag_threshold = 0.55     # WorldRetriever — cosine 유사도 ≥ 0.55
```

| 항목 | 값 | 위치 |
|---|---|---|
| vdb_threshold | 0.60 | `memory/long_term.py` |
| rag_threshold | 0.55 | `rag/retrieve.py` |
| 요약 저장 threshold | 0.65 | `memory/summarizer.py` |
| cosine dedup | 0.85 | `memory/long_term.py` |
| VDB quota | 200개/캐릭터 | `memory/long_term.py` |
| TTL | 30일 (importance < 0.90 항목) | `memory/long_term.py` |
| short_term 윈도우 | 5턴 | `memory/short_term.py` |
| session_context 최대 | 600자 | `memory/short_term.py` |
| mood_decay_turns | 3 (기본) | Character YAML |
| 즉시 flush 조건 | aff_delta ≥ 5 또는 world_trigger 발동 | `conversation/core/router.py` |

---

## 시스템 아키텍처

### 대화 흐름 (한 턴)

```
사용자 입력 → bridge.py::sendMessage()
    → LLMWorker(QThread)
    → Agent.handle_input(mode="chat")
    → ConversationRouter.handle_turn()
        ① RAG: world_nav.detect_move_intent() + WorldRetriever.query()
        ① NarrationMonitor.check_keyword() (세션 1회)
        ① WorldTrigger: story/place/culture 트리거 (세션 1회)
        ② short_term.get_recent() → Layer D
        ③ LongTermMemory.query() → Layer C
        ④ WorldRetriever.query() → Layer B
        ⑤ PromptBuilder.assemble() → messages 리스트
        ⑥ LLMClient.generate() → 캐릭터 응답
        ⑦ update_mood() / update_affection()
        ⑦-b short_term.evict_to_context() (5턴 초과 시)
        ⑦-c _PROMISE_RE → character_notes 추가
        ⑧ summarizer.check_trigger() → ChromaDB 저장
        ⑨ ConversationLogger.log_turn() (dev 환경만, 배포 비활성)
    → bridge.py::_sync_state() → QML 시그널
```

### 6계층 컨텍스트 어셈블리

| 레이어 | 내용 | 토큰 예산 |
|---|---|---|
| A | 캐릭터 시스템 프롬프트 (name/speech/personality/affection tier/emotion/rules) | ~300 |
| B | 세계관 + 현재 Act 상황 + RAG 결과 | ~200 |
| C | VDB 장기 기억 검색 결과 | ~150 |
| D | 단기 히스토리 최근 5턴 | ~450 |
| E | session_context([이전 대화 요약]) + character_notes([이번 세션 약속]) | 동적 |
| F | 최근 기능 작업 요약 (있을 때만) | ~50 |

### 메모리 3계층 구조

| 계층 | 구현 | 범위 | 한계 |
|---|---|---|---|
| 단기 (short_term) | `session.dialogue_log` 슬라이딩 윈도우 | 최근 5턴 | ~450 tok |
| 중기 (session_context) | `evict_to_context()` 누적 텍스트 | 세션 내 전체 | 600자 |
| 장기 (long_term) | ChromaDB VDB (dedup/quota/TTL) | 세션 간 영속 | 캐릭터당 200개 |

---

## 데이터 엔티티 요약 (ERD)

| 엔티티 | 저장 위치 | 핵심 필드 |
|---|---|---|
| Character | `conversation/character/CH_*.yaml` | id, speech(formality/style/persona), personality, affection(6단계), emotion(8종), rules, mood_triggers |
| World | `conversation/world/W_*.yaml` | world_id, scenarios[], character_overrides |
| Scenario/Act | World YAML 내 중첩 | act: location, display_name, context |
| SessionState | `data/sessions/{char_id}/{session_id}/state.json` | mood(9종), affection(0~100), turn_count, fired_stories, visited_places, session_context |
| SessionMeta | `data/sessions/{char_id}/sessions.json` | 캐릭터당 최대 3개 세션 |
| ActiveSession | `data/sessions/active.json` | 현재 활성 세션 포인터 |
| MemoryEntry | ChromaDB `{char_id}_memory` | content, importance(0~1), tags, TTL 30일 |
| RAGChunk | ChromaDB `world_knowledge` | content, section(culture/place/story), world_id |
| Preferences | `ui_ux/assets/preferences.json` | theme, pip_bubble_dir, shown_tag_intro |

**현재 활성 캐릭터**: CH_Haru.yaml (반말), CH_MookHyeon.yaml (존댓말)  
**현재 활성 세계관**: seaside_world (`conversation/world/W_sea.yaml`, `rag/sources/world/Seaside.md`)

---

## 구현 완료 현황 (Phase 0~8 전부 완료)

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | 환경 구성·설정 파일 구조 | ✅ |
| 1 | LLM 인터페이스 (llama-cpp-python) | ✅ |
| 2 | 대화 엔진 (메모리 3계층, mood/affection, prompting) | ✅ |
| 3 | RAG 파이프라인 (섹션 기반 청킹 + WorldRetriever) | ✅ |
| 4 | PySide6+QML 플로팅 UI | ✅ |
| 5 | LoRA 파인튜닝 파이프라인 (v7~v11, EWC, 평가 스크립트) | ✅ |
| 6 | GGUF 변환·배포 패키징 (PyInstaller+Inno) | ✅ (실환경 검증 2개 미완) |
| 7 | 기능 모드 도구 4종 | ✅ |
| 8 | 대화 품질 개선 (8개 개선 항목) | ✅ |

**테스트**: 474개 통과 (2026-04-20 기준)  
**학습 데이터**: 3,983건 / 71파일 (v12 데이터 포함, 채택 모델은 v11)

---

## 미완료 / 미검증 항목

1. **실환경 검증 — AchatSetup.exe 클린 설치 → 실행 → 제어판 삭제** 전 과정 (Windows 실기)
2. **CPU 추론 속도 8+ tok/s 달성 확인** (Windows 실기)
3. **감정 오버레이 에셋** (`ui_ux/assets/characters/emotion/`) — 구조 준비됨, PNG 배치 대기
4. **캐릭터 파츠 에셋** (`ui_ux/assets/characters/` 하위) — 구조 준비됨, PNG 배치 대기
5. **v13 학습 계획** — v12 결함 원인(RAG 주입 시 한국어 유지 데이터 부족)을 보강한 데이터셋 필요

---

## 핵심 파일 위치

| 목적 | 파일 |
|---|---|
| 진입점 | `main.py`, `deploy/launcher.py` |
| 설정 | `config.py` (dev/deploy 분기, adapter_path, 임계값 모두 여기) |
| 대화 엔진 핵심 | `conversation/core/router.py` (handle_turn), `conversation/core/prompt_build.py` (컨텍스트 어셈블리) |
| Agent 조율 | `agent/core.py` (모드 분기, _inject_function_feedback, mood_decay) |
| 메모리 | `memory/short_term.py`, `memory/long_term.py`, `memory/summarizer.py` |
| RAG | `rag/retrieve.py` (WorldRetriever), `rag/index.py`, `rag/world_nav.py` |
| UI 브리지 | `ui_ux/bridge.py` (QML↔Python 모든 Signal/Slot) |
| 학습 | `training/lora_train.py`, `training/ewc.py`, `training/train_monitor.py` |
| 평가 | `training/eval/scenario_eval.py` (18개 시나리오, 합격 15/18), `ai_tell_checker.py`, `memory_test.py` |
| 배포 | `deploy/achat.spec`, `deploy/achat_setup.iss`, `deploy/build_installer.bat` |
| 세계관 소스 | `rag/sources/world/Seaside.md` (culture/place/story 섹션 구조) |
| 캐릭터 YAML | `conversation/character/CH_Haru.yaml`, `CH_MookHyeon.yaml` |
| 세계관 YAML | `conversation/world/W_sea.yaml` |

---

## 장기 계획 (docs/plan/additional_plan.md)

| 항목 | 방향 | 실현 가능성 |
|---|---|---|
| 강화학습 (RL) | DPO 권장 — Claude API를 judge로 쓰는 RLAIF→DPO (VRAM 8GB 내 가능, PPO는 14~18GB 필요) | ✅ 실현 가능 |
| 클라우드 로그 수집 | AWS Serverless (Lambda+S3+Glue+Athena) + Apache Iceberg, opt-in + 비식별화 전제 | ⚠️ 인프라 구축 필요 |
| DW 구조 | OPS(/operation, /training) + Dialogue(/daily, /emotion, /advice, /feedback_neg, /feedback_pos) | 설계 완료 |
| LangChain/LangGraph | **불채택** — 100+ 의존성, 3계층 메모리 구조와 불호환, 단일 에이전트 선형 파이프라인에 과도 | ❌ |

---

## 알려진 제약

- **BitsAndBytes**: Blackwell SM 10.x 미지원 → bfloat16 + LoRA로 완전 대체
- **LoRA 병합 RAM**: 3B FP16 병합 ~6GB, 실행 전 다른 프로세스 종료 필수
- **PySide6 버전**: 6.9.x 이하 고정 (6.10.x는 WSL2 ibus 연결 실패 버그)
- **한글 입력**: ibus 기반, `Ctrl+Space` 토글. fcitx 잔재 있으면 차단됨
- **배포 환경 log 수집 비활성**: `training/log/` 는 dev 전용. `config.py`의 `log_enabled` 배포 시 False
- **LocalSearch 캐시**: `~/.cache/achat/` 고정 — 배포 환경 경로 충돌 가능성
- **v12 결함**: RAG 주입 시 중국어 전환. v13 학습 전 세계관 문서 주입 상황 한국어 유지 데이터 추가 필수
