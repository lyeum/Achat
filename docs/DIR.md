# DIR — 파일시스템 현황 참조 문서

> 이 문서는 실제 파일시스템 기준으로 작성됩니다.
> README.md의 설계 구조와 차이가 있는 항목은 ⚠️로 표시합니다.
>
> 범례: ✅ 완료 | 🔲 비어있음(구현 예정) | 📄 데이터/설정 파일 | ⚠️ 불일치/정리 필요

---

## 전체 디렉토리 트리 (실제 기준)

```
Achat/
│
├─ docs/                              ✅ 완료
│   ├─ README.md                      ✅ 총괄 문서 (실제 위치: 루트)
│   ├─ DIR.md                         ✅ 이 파일 — 파일시스템 현황
│   ├─ 대화품질.md                    ✅ 대화 품질 설계 (Phase 1~3 구현 참조)
│   ├─ 학습후보.md                    ✅ 학습 실험 설계 (Phase 5~6 참조)
│   ├─ plan/
│   │   └─ phases.md                  ✅ Phase 0~7 실행 계획서
│   └─ plan1/                         ⚠️ 빈 디렉토리 — 삭제 필요
│
├─ conversation/                       # 대화 엔진 (핵심)
│   ├─ __init__.py                    ✅ 패키지 초기화 (import 경로 확보)
│   ├─ core/
│   │   ├─ llm_client.py             ✅ llama_cpp + transformers 듀얼 백엔드 (스트리밍, 토큰 카운트)
│   │   ├─ prompt_build.py           ✅ Layer A~D Context Assembly (Layer E는 호출자 append)
│   │   ├─ router.py                 ✅ `handle_turn()` — VDB 검색 → PromptBuilder → LLM → mood/affection → 요약 트리거
│   │   └─ session.py                ✅ 세션 상태 (mood, affection, turn_count, dialogue_log)
│   │
│   ├─ loader/
│   │   ├─ character_load.py         ✅ 캐릭터 YAML → dict (필수 필드 검증 포함)
│   │   ├─ memory_load.py            ✅ M_default.json → ChromaDB 초기 삽입용 리스트
│   │   └─ world_load.py             ✅ 세계관 YAML → dict (get_act 헬퍼 포함)
│   │
│   ├─ utils/                         ⚠️ README에 없음 — 유틸리티 디렉토리
│   │   ├─ __init__.py               🔲
│   │   ├─ logger.py                 🔲 로거 설정
│   │   └─ file_io.py                🔲 파일 입출력 유틸
│   │
│   ├─ character/
│   │   ├─ CH_schema.json            📄 캐릭터 YAML 필드 스키마
│   │   ├─ CH_haru.yaml              ✅ 예시 캐릭터 (speech_style, memory_voice, state 완료)
│   │   ├─ CH_default.yaml           📄 기본 캐릭터
│   │   └─ chracter_Haru.yaml        ⚠️ 파일명 오타 (charACTER → character) — 삭제 권장
│   │
│   ├─ world/
│   │   ├─ W_schema.json             📄 세계관 YAML 스키마
│   │   └─ W_sea.yaml                📄 예시 세계관 (바다 배경)
│   │
│   ├─ memory_act/
│   │   ├─ M_schema.json             ✅ VDB 저장 단위 스키마 (중요도 규칙, 검색 설정 포함)
│   │   ├─ M_default.json            📄 캐릭터별 기본 기억 초기값
│   │   └─ M_instance.json           📄 세션 인스턴스 기억 템플릿
│   │
│   └─ main.py                        ✅ CLI 루프 진입점 (dry-run 모드 포함, ROOT sys.path 삽입)
│
├─ memory/                             # 메모리 관리 레이어
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ short_term.py                  ✅ `get_recent()` — 슬라이딩 윈도우
│   ├─ long_term.py                   ✅ ChromaDB store/query (bge-m3, threshold 0.7, importance≥0.5)
│   └─ summarizer.py                  ✅ N턴 트리거 + LLM 요약 + 키워드 중요도 scoring + VDB 저장
│
├─ rag/                                # RAG 파이프라인
│   ├─ index.py                       🔲 세계관 문서 청킹 + ChromaDB 인덱싱
│   ├─ retrieve.py                    🔲 시맨틱 유사도 검색
│   └─ sources/
│       └─ world/
│           ├─ place.md               📄 장소 정보 (이미 존재)
│           ├─ culture.md             📄 세계관 문화 (이미 존재)
│           └─ story.md               📄 배경 스토리 (이미 존재)
│
├─ agent/                              # 상위 오케스트레이터
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ core.py                        ✅ `Agent` 클래스 — 컴포넌트 초기화 + `chat()` 대화 진입점
│   ├─ persona.py                     ✅ `load_persona()` / `swap_persona()` 핫스왑
│   ├─ state.py                       ✅ mood_triggers 키워드 매칭, affection ±3 증감
│   ├─ router.py                      🔲 시동어 / 명령어 분기 (Phase 2 미구현, Phase 7에서 확장)
│   └─ memory.py                      ⚠️ README에 없음 — 역할 미정의 (정리 필요)
│
├─ ui/                                 # PySide6 플로팅 UI (배포 환경)
│   ├─ widget.py                      🔲 Frameless / Always-on-top / 모서리 스냅 / hover 투명도
│   ├─ chat_panel.py                  🔲 스트리밍 토큰 표시 채팅 패널
│   ├─ tray.py                        🔲 시스템 트레이
│   └─ mode_switcher.py               🔲 대화 모드 ↔ 기능 모드 전환 UI
│
├─ tools/                              # 기능 모드 — 도구 마이크로서비스
│   ├─ base.py                        🔲 Tool 인터페이스 (파라미터 수신 → 실행 → 결과 반환)
│   ├─ folder/
│   │   ├─ classifier.py             🔲 파일 분류 (확장자 / MIME 기반)
│   │   ├─ converter.py              🔲 확장자 일괄 변환 (Pillow, ffmpeg 선택)
│   │   └─ renamer.py                🔲 이름 일괄 변환 (pathlib)
│   ├─ prompt_converter.py            🔲 프롬프트 변환
│   └─ search/
│       ├─ local_search.py           🔲 로컬 파일 인덱싱 + FTS 검색 (SQLite FTS5 / whoosh)
│       └─ web_search.py             🔲 인터넷 검색 (DuckDuckGo / SearXNG)
│
├─ training/                           # LoRA 파인튜닝
│   ├─ lora_train.py                  🔲 QLoRA 학습 (8GB VRAM 최적화)
│   ├─ dataset.py                     🔲 ChatML 포맷 데이터셋 로더
│   └─ data/                          ⚠️ 기존 데이터 위치 (README는 루트 data/lora/ 로 변경)
│       ├─ data_gen_prompt.md         📄 학습 데이터 생성 프롬프트 가이드
│       ├─ common/
│       │   ├─ memory_ref.jsonl       📄 기억 참조 학습 데이터
│       │   ├─ ai_tell_removal.jsonl  📄 AI 투 표현 제거 학습 데이터
│       │   └─ persona_follow.jsonl   📄 페르소나 준수 학습 데이터
│       ├─ personality/               📄 5종 성격별 데이터
│       └─ speech_style/              📄 말투 조합 데이터
│
├─ data/                               ⚠️ README 신규 표기 — 실제 미생성 (Phase 5 전 생성 필요)
│   └─ lora/
│       ├─ conversation/              🔲 대화 모드용 캐릭터 대화 데이터 (ChatML)
│       └─ function/                  🔲 기능 모드용 자연어 → JSON 파라미터 추출 예시
│
├─ scripts/                            # 변환 스크립트
│   ├─ merge_lora.py                  🔲 LoRA 병합 (low_cpu_mem_usage=True)
│   └─ convert_to_gguf.sh             🔲 GGUF 변환 + Q4_K_M 양자화
│
├─ eval/                               # 평가 스크립트 (Phase 5 이후)
│   ├─ ai_tell_checker.py             🔲 이질감 자동 측정
│   ├─ memory_test.py                 🔲 기억 유지 정확도
│   └─ speed_bench.py                 🔲 GPU/CPU 추론 속도 벤치마크
│
├─ api/                                ⚠️ README에 없음 — 역할 미정의
│   └─ server.py                      🔲 (향후 웹 UI 확장 용도 추정, 필요시 정리)
│
├─ main.py                             🔲 프로젝트 진입점
├─ config.py                           ✅ dev / deploy 환경 분기 설정
├─ pyproject.toml                      ✅ 개발 환경 의존성 (uv, Linux + GPU)
├─ pyproject-deploy.toml               ✅ 배포 환경 의존성 (uv, Windows + CPU)
├─ uv.lock                             ✅ uv lock 파일 (dev 기준)
├─ Dockerfile                          📄 Docker 설정
└─ .gitignore
```

---

## README.md와의 불일치 목록

| 항목 | README.md 표기 | 실제 파일시스템 | 처리 방안 |
|---|---|---|---|
| 학습 데이터 위치 | `data/lora/conversation/` + `data/lora/function/` (루트) | `training/data/` (기존 구조) | Phase 5 전 `data/lora/` 신규 생성, 기존 데이터 병합/이전 |
| `data/lora/function/` | 신규 표기 | 미존재 | Phase 5에서 기능 모드 JSON 추출 데이터 구축 시 생성 |
| `tools/folder/`, `tools/search/` | 하위 구조화 | 이전 `tools/base.py`, `tools/commands.py`만 존재 | Phase 7에서 신규 구현 |
| `ui/mode_switcher.py` | 신규 추가 | 미존재 | Phase 4에서 구현 |
| `agent/memory.py` | 없음 | 존재 | 역할 정의 필요 (`memory/` 레이어와 중복 가능성) |
| `conversation/utils/` | 없음 | 존재 | README에 추가 또는 삭제 검토 |
| `chracter_Haru.yaml` | 없음 | 존재 (오타) | 삭제 권장 |
| `api/server.py` | 없음 | 존재 | 역할 정의 후 README에 추가하거나 삭제 |
| 패키지 관리 | `requirements-*.txt` | `pyproject.toml` / `pyproject-deploy.toml` (uv) | ✅ 완료 |
| `docs/plan1/` | 없음 | 빈 디렉토리 | 삭제 권장 |

---

## 파일 상태 요약

| 상태 | 수 | 항목 |
|---|---|---|
| ✅ 완료 | 25 | docs 문서 5개, CH_haru.yaml, M_schema.json, rag/sources/ 3개 + Phase 1 8개 + Phase 2 9개 (memory/__init__, short_term, long_term, summarizer / agent/__init__, core, persona, state / conversation/core/router) |
| 📄 데이터/설정 | 20+ | .yaml/.json 스키마, training/data/ 하위 .jsonl 학습 데이터 |
| 🔲 구현 예정 | 17 | Phase 3~7 .py 파일 + data/lora/ 데이터 + agent/router.py |
| ⚠️ 정리 필요 | 6 | 오타 파일, 경로 불일치, 역할 미정 파일, 빈 디렉토리 |
