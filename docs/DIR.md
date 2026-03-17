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
│   ├─ MVP대화.md                     ✅ MVP 실행 명령어 + 대화 로그 수집/검토 매뉴얼
│   ├─ plan/
│   │   └─ phases.md                  ✅ Phase 0~7 실행 계획서
│   └─ BUG/
│       ├─ BUG_1.md                   ✅ 인수인계 문서 (환경 셋업, 해결된 이슈 기록)
│       └─ BUG_small.md               ✅ 소규모 버그 수정 기록 (Phase 7 이후)
│
├─ conversation/                       # 대화 엔진 (핵심)
│   ├─ __init__.py                    ✅ 패키지 초기화 (import 경로 확보)
│   ├─ core/
│   │   ├─ llm_client.py             ✅ llama_cpp + transformers 듀얼 백엔드 (LoRA 어댑터 로드, repetition_penalty=1.1, 토큰 카운트)
│   │   ├─ prompt_build.py           ✅ Layer A~D Context Assembly — session.location_context 우선, 없으면 YAML act 사용
│   │   ├─ router.py                 ✅ `handle_turn()` — 장소 이동 감지(_handle_location) → VDB+RAG → PromptBuilder → LLM → mood/affection → 요약
│   │   └─ session.py                ✅ 세션 상태 (mood, affection, turn_count, dialogue_log, location_context)
│   │
│   ├─ loader/
│   │   ├─ character_load.py         ✅ 캐릭터 YAML → dict (필수 필드 검증 포함)
│   │   ├─ memory_load.py            ✅ M_default.json → ChromaDB 초기 삽입용 리스트
│   │   └─ world_load.py             ✅ 세계관 YAML → dict (get_act 헬퍼 포함)
│   │
│   ├─ utils/                         ✅ 유틸리티 디렉토리
│   │   ├─ __init__.py               ✅ 패키지 초기화 (setup_logger, load_yaml 등 re-export)
│   │   ├─ logger.py                 ✅ loguru 설정 — 콘솔+파일 핸들러, 로테이션
│   │   └─ file_io.py                ✅ YAML/JSON/JSONL 파일 입출력 헬퍼
│   │
│   ├─ character/
│   │   ├─ CH_schema.json            📄 캐릭터 YAML 필드 스키마
│   │   ├─ CH_Haru.yaml              ✅ 예시 캐릭터 (speech_style, memory_voice, state 완료)
│   │   └─ CH_default.yaml           📄 기본 캐릭터
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
│   ├─ main.py                        ✅ CLI 루프 진입점 — 세계관 RAG 자동 인덱싱, monitor 서브프로세스 자동 실행, 세션 상태 .session_state.json 기록, ConversationLogger 연동
│   └─ narrator.py                   ✅ Narrator 클래스 (비활성화) — describe_arrival / describe_session_start LLM 3~5문장 장면 묘사 (대화 품질 안정 후 재활성화 예정)
│
├─ memory/                             # 메모리 관리 레이어
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ short_term.py                  ✅ `get_recent()` — 슬라이딩 윈도우
│   ├─ long_term.py                   ✅ ChromaDB store/query (bge-m3, threshold 0.52, importance≥0.5)
│   └─ summarizer.py                  ✅ N턴 트리거 + LLM 요약 + 키워드 중요도 scoring + VDB 저장
│
├─ rag/                                # RAG 파이프라인
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ index.py                       ✅ `index_world()` — .md 청킹(400자/overlap 50) + ChromaDB 인덱싱 (cosine space)
│   ├─ retrieve.py                    ✅ `WorldRetriever.query()` — 매 턴 실행, threshold 0.52, 컬렉션 미존재 안전 처리 / `add_document()` — 동적 위치 ChromaDB upsert
│   ├─ world_nav.py                   ✅ `detect_move_intent()` — 키워드 필터 + LLM 추출(max_tokens=15) / `find_or_create_location()` — RAG 검색 → LLM 생성 → add_document 저장
│   └─ sources/
│       └─ world/
│           ├─ place.md               📄 장소 정보 (이미 존재)
│           ├─ culture.md             📄 세계관 문화 (이미 존재)
│           └─ story.md               📄 배경 스토리 (이미 존재)
│
├─ agent/                              # 상위 오케스트레이터
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ core.py                        ✅ `Agent` 클래스 — 컴포넌트 초기화 + `chat()` / `handle_input(mode)` 모드 분기
│   ├─ persona.py                     ✅ `load_persona()` / `swap_persona()` 핫스왑
│   ├─ state.py                       ✅ mood_triggers 키워드 매칭, affection ±3 증감
│   ├─ router.py                      ✅ `CommandRouter` — 슬래시 명령어 감지/파싱 (/캐릭터변경, /초기화, /상태 등)
│   └─ memory.py                      ✅ memory/ 패키지 re-export (LongTermMemory, get_recent, summarizer 함수)
│
├─ ui_ux/                              # QML + PySide6 플로팅 UI (배포 환경)
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ bridge.py                      ✅ ChatBridge(QObject) — QML↔Python 시그널/슬롯 브리지 (sendMessage, snapToEdge, changeCharacter)
│   ├─ chat_panel.py                  ✅ LLMWorker(QThread) — 백그라운드 LLM 추론 (response_ready / error_occurred 시그널)
│   ├─ widget.py                      ✅ UIEngine — QQmlApplicationEngine 래퍼, bridge context property 등록, main.qml 로드
│   ├─ tray.py                        ✅ AppTrayIcon — 시스템 트레이 (열기/숨기기, 캐릭터 변경, 종료)
│   ├─ qml/
│   │   ├─ qmldir                    ✅ QML 모듈 선언 (AchatUI — Style singleton, ChatBubble)
│   │   ├─ Style.qml                 ✅ 디자인 토큰 singleton — 색상/폰트/간격/애니메이션 상수
│   │   ├─ main.qml                  ✅ 프레임리스 플로팅 Window — isBubble 토글(72px↔360×520), 드래그+모서리 스냅, 채팅 ListView, 모드 전환 버튼
│   │   └─ ChatBubble.qml            ✅ 재사용 말풍선 컴포넌트 (role 프로퍼티로 좌/우 정렬·색상 제어)
│   └─ assets/
│       ├─ icons/                    🔲 앱 아이콘 PNG (16/32/64/256px) — tray.py fallback 교체용
│       └─ characters/               🔲 캐릭터 PNG/GIF — bubble 상태 아바타 표시용
│
├─ tools/                              # 기능 모드 — 도구 마이크로서비스
│   ├─ __init__.py                    ✅ BaseTool re-export
│   ├─ base.py                        ✅ BaseTool 인터페이스 (parse_params JSON 추출 + execute 추상 메서드)
│   ├─ commands.py                    📄 (미사용 — 추후 정리)
│   ├─ folder/
│   │   ├─ __init__.py               ✅ 패키지 초기화
│   │   ├─ classifier.py             ✅ 파일 분류 (확장자별 / 종류별, CATEGORY_MAP, dry_run)
│   │   ├─ converter.py              ✅ 이미지 포맷 변환 (Pillow: jpg/png/webp/bmp/tiff, RGBA→RGB)
│   │   └─ renamer.py                ✅ 이름 일괄 변환 (7가지 규칙, glob 패턴, dry_run)
│   ├─ prompt_converter.py            ✅ 프롬프트 변환 (명확하게/간결하게/상세하게/질문형/지시형)
│   └─ search/
│       ├─ __init__.py               ✅ 패키지 초기화
│       ├─ local_search.py           ✅ SQLite FTS5 로컬 검색 (증분 인덱싱, mtime 추적, ~/.cache/achat/)
│       └─ web_search.py             ✅ 인터넷 검색 — DuckDuckGo Instant Answer API (urllib, 추가 의존성 없음)
│
├─ training/                           # LoRA 파인튜닝
│   ├─ 학습.md                        ✅ 학습 실행 가이드 (Step 0~6, GPU/CPU 옵션, 평가까지)
│   ├─ lora_train.py                  ✅ LoRA 학습 (bfloat16, GPU/CPU 자동 전환, --no_save, --max_steps, --eval_split, best loss 저장, epoch/전체 완료 시 loss 그래프 PNG 자동 저장)
│   ├─ dataset.py                     ✅ ChatML 포맷 데이터셋 로더 (apply_chat_template, max_length 필터)
│   ├─ log/                           # MVP 대화 로그 수집 (카테고리별 폴더 + JSONL)
│   │   ├─ _schema.json               ✅ 로그 포맷 명세 (messages/character_id/category/affection/mood/emotion_trigger/logged_at/reviewed)
│   │   ├─ conversation_logger.py     ✅ 카테고리 자동 분류 저장 — 키워드 트리거 즉시 flush, CHUNK_SIZE=8 일상 수집, Jaccard 중복 제거(0.55), reviewed:false 태그
│   │   ├─ monitor.py                 ✅ 세션 실시간 모니터링 — .session_state.json 폴링(2s), 카테고리별 누적 건수 + 미검토 표시, .monitor.log 기록
│   │   ├─ review.py                  ✅ 미검토 항목 이중 체크 CLI — y(승인)/n(재분류+이동)/d(삭제)/s(건너뜀)/q(종료), --cat 옵션
│   │   ├─ daily/YYYY-MM-DD.jsonl     📄 일상 대화 로그 (대화 중 자동 수집)
│   │   ├─ emotion/YYYY-MM-DD.jsonl   📄 감정 공감 로그
│   │   ├─ advice/YYYY-MM-DD.jsonl    📄 고민 상담 로그
│   │   ├─ memory/YYYY-MM-DD.jsonl    📄 기억 관련 로그
│   │   ├─ persona/YYYY-MM-DD.jsonl   📄 페르소나 이탈 교정 로그
│   │   ├─ feedback_pos/YYYY-MM-DD.jsonl 📄 칭찬·동의 로그
│   │   ├─ feedback_neg/YYYY-MM-DD.jsonl 📄 교정·지적·반복루프 로그
│   │   └─ .session_state.json        📄 세션 상태 스냅샷 (monitor 폴링용, 런타임 생성)
│   └─ data/                          ⚠️ 기존 데이터 위치 (README는 루트 data/lora/ 로 변경)
│       ├─ data_gen_prompt.md         📄 학습 데이터 생성 프롬프트 가이드
│       ├─ common/
│       │   ├─ memory_ref.jsonl       📄 기억 참조 학습 데이터
│       │   ├─ ai_tell_removal.jsonl  📄 AI 투 표현 제거 학습 데이터
│       │   └─ persona_follow.jsonl   📄 페르소나 준수 학습 데이터
│       ├─ personality/               📄 5종 성격별 데이터
│       └─ speech_style/              📄 말투 조합 데이터
│
├─ data/                               ✅ Phase 5에서 생성
│   └─ lora/
│       ├─ conversation/              🔲 training/log 빌드 후 생성 (scripts/build_dataset.py)
│       └─ function/                  ✅ folder_organize / prompt_convert / search 예시 JSONL
│
├─ scripts/                            # 변환 스크립트
│   ├─ build_dataset.py               ✅ training/log/*.jsonl → data/lora/conversation/ 빌드
│   ├─ merge_lora.py                  ✅ LoRA 어댑터 병합 (float16, low_cpu_mem_usage=True) — 학습 완료 후 실행
│   └─ convert_to_gguf.sh             ✅ GGUF 변환 + Q4_K_M 양자화 (--llama_cpp 경로 지정 필요)
│
├─ eval/                               # 평가 스크립트 (Phase 5)
│   ├─ ai_tell_checker.py             ✅ AI투 표현 패턴 측정 + 베이스/LoRA 비교
│   ├─ memory_test.py                 ✅ 멀티턴 기억 유지 정확도 (5케이스)
│   ├─ speed_bench.py                 ✅ transformers/llama_cpp 추론 속도 벤치마크
│   └─ verify_phases.py               ✅ Phase 2/3 실환경 검증 (12턴 자동 대화, 5항목 PASS)
│
├─ api/                                📄 향후 웹 UI / REST API 확장용 (Phase 8 예정)
│   └─ server.py                      📄 FastAPI 서버 스텁 — 현재 미구현, Phase 8 이후 확장
│
├─ .github/
│   └─ workflows/
│       └─ ci.yml                      ✅ CI — ruff 린트 + 데이터 파이프라인 검증 (push/PR 자동 실행)
│
├─ main.py                             ✅ 루트 진입점 — torch 먼저 로드 후 Qt 초기화 (shared lib 충돌 방지)
│                                          _cleanup_previous() PID 파일 기반 이전 프로세스 정리
│                                          _check_vram() CUDA 여유 메모리 확인 및 경고
├─ run.bat                             ✅ Windows 배포 실행 스크립트 (모델 파일 존재 확인 + uv run)
├─ config.py                           ✅ dev / deploy 환경 분기 설정 (dev: adapter_path 추가 — None이면 베이스 모델)
├─ pyproject.toml                      ✅ 개발 환경 의존성 (uv, Linux + GPU) + ruff 설정 (matplotlib 포함)
├─ pyproject-deploy.toml               ✅ 배포 환경 의존성 (uv, Windows + CPU)
├─ uv.lock                             ✅ uv lock 파일 (dev 기준)
├─ Dockerfile                          ✅ CUDA 12.8 + Ubuntu 24.04 + uv 기반 (ibus-hangul, libgl1, IBUS_USE_PORTAL=0)
└─ .gitignore                          ✅ output/ 추가 (학습 체크포인트/어댑터 제외)
```

---

## README.md와의 불일치 목록

| 항목 | README.md 표기 | 실제 파일시스템 | 처리 방안 |
|---|---|---|---|
| 학습 데이터 위치 | `data/lora/conversation/` + `data/lora/function/` (루트) | `training/data/` (기존 구조) | Phase 5 전 `data/lora/` 신규 생성, 기존 데이터 병합/이전 |
| `data/lora/function/` | 신규 표기 | 미존재 | Phase 5에서 기능 모드 JSON 추출 데이터 구축 시 생성 |
| `tools/folder/`, `tools/search/` | 하위 구조화 | 이전 `tools/base.py`, `tools/commands.py`만 존재 | Phase 7에서 신규 구현 |
| `ui_ux/mode_switcher.py` | 신규 추가 | 미존재 → 삭제됨 | QML `Repeater` 기반 모드 버튼으로 대체 (Phase 4 완료) |
| `ui_ux/qml/` | 없음 | 신규 생성 | QML + PySide6 아키텍처 채택, main.qml + ChatBubble.qml |
| `agent/memory.py` | 없음 | ✅ 정리 완료 | memory/ 패키지 re-export 모듈로 역할 정의 |
| `conversation/utils/` | 없음 | ✅ 정리 완료 | logger.py + file_io.py 구현, __init__.py re-export |
| `chracter_Haru.yaml` | 없음 | ✅ 삭제 완료 | 오타 파일 삭제 |
| `api/server.py` | 없음 | 📄 스텁 유지 | FastAPI 서버 스텁 — Phase 8 확장 예정 |
| 패키지 관리 | `requirements-*.txt` | `pyproject.toml` / `pyproject-deploy.toml` (uv) | ✅ 완료 |
| `docs/plan1/` | 없음 | 빈 디렉토리 | 삭제 권장 |

---

## 파일 상태 요약

| 상태 | 수 | 항목 |
|---|---|---|
| ✅ 완료 | 79 | docs/ 9개(학습.md, BUG_1.md, BUG_small.md 포함), CH_Haru.yaml, M_schema.json, rag/sources/ 3개, Phase 1~4 구현 파일, main.py, Dockerfile, Phase 5 (lora_train+eval_split, dataset, build_dataset, eval 4개, data/lora/function 3개), Phase 6 스크립트 3개, ci.yml, run.bat, .gitignore, Phase 7 tools/ 8개, agent/router.py, agent/memory.py, conversation/utils/ 3개, conversation/narrator.py(비활성), rag/world_nav.py, training/log/ 수집 파이프라인 3개(conversation_logger, monitor, review) |
| 📄 데이터/설정 | 20+ | .yaml/.json 스키마, training/data/ 하위 .jsonl 학습 데이터, training/log/ 카테고리별 .jsonl, api/server.py (스텁) |
| 🔲 구현 예정 / 보류 | 0 | 없음 |
| ⚠️ 정리 필요 | 0 | 없음 |
