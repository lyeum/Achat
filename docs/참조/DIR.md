# DIR — 파일시스템 현황 참조 문서

> 이 문서는 실제 파일시스템 기준으로 작성됩니다. 최종 업데이트: 2026-04-20 (개선6~8 + MagicMock 픽스처 수정 + auto-reindex 완성)
> 코드·설계와 불일치하는 항목은 ⚠️로 표시합니다.
>
> 범례: ✅ 완료 | 🔲 비어있음(구현 예정) | 📄 데이터/설정 파일 | ⚠️ 불일치/정리 필요

---

## 전체 디렉토리 트리 (실제 기준)

```
Achat/
│
├─ README.md                          ✅ 총괄 문서 (루트 위치)
├─ main.py                            ✅ 루트 진입점 — torch 먼저 로드 후 Qt 초기화
│                                        WAYLAND_DISPLAY 언셋, dbus 세션 자동 확보
│                                        ibus-daemon 기동 + Ctrl+Space 토글키 등록
│                                        PID 파일 기반 이전 프로세스 정리
│                                        CUDA 여유 메모리 확인 및 경고
├─ run.bat                            ✅ Windows 배포 실행 스크립트 (모델 파일 존재 확인 + uv run)
├─ config.py                          ✅ dev / deploy / ui_test 환경 분기 설정
│                                        dev: adapter_path="./output/LoRA_v11/adapter" ✅ LoRA_v11 기준 (2026-04-14)
│                                        deploy: model_path="./models/model_q4km.gguf" ⚠️ 실제 없음
│                                        모든 환경: default_world_id="seaside_world" (2026-04-09)
│                                        모든 환경: memory_trigger_n=5 (2026-04-09, 이전 10)
├─ pyproject.toml                     ✅ 개발 환경 의존성 (uv, Linux + GPU) + ruff 설정
├─ pyproject-deploy.toml              ✅ 배포 환경 의존성 (uv, Windows + CPU)
├─ uv.lock                            ✅ uv lock 파일 (dev 기준)
├─ Dockerfile                         ✅ CUDA 12.8 + Ubuntu 24.04 + uv 기반
│                                        ibus-hangul, libgl1, IBUS_USE_PORTAL=0
├─ .gitignore                         ✅ output/ 제외 (학습 체크포인트/어댑터)
│                                        MagicMock/ 추가 (테스트 픽스처 부작용 방지, 2026-04-20)
│
├─ .github/
│   └─ workflows/
│       └─ ci.yml                     ✅ CI — ruff 린트 + 데이터 파이프라인 검증 (push/PR)
│
├─ docs/
│   ├─ DIR.md                         ✅ 이 파일 — 파일시스템 현황
│   ├─ 구현현황.md                    ✅ 모듈별 구현 상태·연결 여부·개선 가능성 평가
│   ├─ MVP대화.md                     ✅ MVP 실행 명령어 + 대화 로그 수집/검토 매뉴얼
│   ├─ 대화품질.md                    ✅ 대화 품질 설계 (Phase 1~3 구현 참조)
│   ├─ 학습후보.md                    ✅ 학습 실험 설계 (Phase 5~6 참조)
│   ├─ data_gen_prompt.md             📄 학습 데이터 생성용 프롬프트 문서
│   ├─ 포폴.md                        📄 포트폴리오 문서
│   ├─ plan/
│   │   ├─ phases.md                  ✅ Phase 0~7 실행 계획서
│   │   ├─ training_개선.md           ✅ EWC 다단계 학습 / 카테고리 가중치 / assistant 마스킹 구현 계획
│   │   ├─ UI설계-clear.md             ✅ QML + PySide6 UI 설계 상세 (1~6단계 구현 완료)
│   │   ├─ UI_테스트.md               ✅ UI 전체 수동 테스트 체크리스트 + 자동 테스트 실행 가이드
│   │   ├─ 개선5.md                   ✅ 개선5 구현 계획 (항목1~10 모두 완료, 2026-04-09)
│   │   ├─ 개선6.md                   📄 개선6 계획 (작성 중)
│   │   └─ 학습데이터_개선.md         ✅ v11 학습 데이터 카테고리 재설계 완료 (2026-04-14)
│   └─ BUG/
│       ├─ BUG_1-clear.md              ✅ 인수인계 문서 (환경 셋업, 해결된 이슈 기록)
│       └─ BUG_small-clear.md          ✅ 소규모 버그 수정 기록
│
├─ agent/
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ core.py                        ✅ Agent 클래스 — 컴포넌트 초기화 + chat() / handle_input(mode) 모드 분기
│                                        _inject_prompt_guide(tool_name) — prompt_convert 제외 기능모드 도구에 ChromaDB prompt_guides 주입 (2026-04-09)
│                                        character_overrides.rules — 세계관 YAML rules를 캐릭터 rules에 merge (2026-04-09)
│   ├─ memory.py                      ✅ memory/ 패키지 re-export (LongTermMemory, get_recent, summarizer)
│   ├─ persona.py                     ✅ load_persona() / swap_persona() 핫스왑
│   ├─ router.py                      ✅ CommandRouter — 슬래시 명령어 감지/파싱 (/캐릭터변경, /초기화, /상태 등)
│   └─ state.py                       ✅ update_mood() — mood_triggers 키워드 매칭 (8종: neutral/happy/affectionate/
│                                        touched/curious/sad/embarrassed/annoyed/angry)
│                                        update_affection() — mood별 affection 증감 (캐릭터 YAML affection_delta 우선)
│
├─ api/
│   └─ server.py                      📄 FastAPI 서버 스텁 — 미구현, Phase 8 이후 확장 예정
│
├─ chroma_dev/                        📄 런타임 생성 ChromaDB 데이터 (gitignore 권장)
│   ├─ {uuid}/                        ← HNSW 인덱스 바이너리 (data_level0.bin 등)
│   └─ chroma.sqlite3                 ← 메타데이터 SQLite DB
│
├─ conversation/
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ main.py                        ✅ CLI 루프 진입점 — 세계관 RAG 자동 인덱싱
│   │                                    monitor 서브프로세스 자동 실행
│   │                                    세션 상태 .session_state.json 기록
│   │                                    ConversationLogger 연동
│   ├─ narration_hardcoded.py         ✅ 하드코딩 키워드 트리거 나레이션 — find_trigger()
│   │                                    키워드(카페/공원/비/커피 등) → 미리 작성된 묘사 텍스트 반환
│   ├─ narration_monitor.py           ✅ NarrationMonitor — check_keyword()
│   │                                    세션 내 키워드당 1회 제한, _fired_keywords 추적
│   │
│   │
│   ├─ character/
│   │   ├─ character_schema.yaml     ✅ 캐릭터 YAML 계약 (슬롯 = 학습 카테고리 어휘, 2026-04-02 신규)
│   │   ├─ CH_Haru.yaml              ✅ 예시 캐릭터 (speech/affection/emotion/personality 슬롯 기반, 2026-04-02 재작성)
│   │   ├─ CH_MookHyeon.yaml         📄 신규 캐릭터 (작성 중)
│   │   └─ CH_default.yaml           📄 기본 캐릭터
│   │
│   ├─ core/
│   │   ├─ __init__.py               ✅ 패키지 초기화
│   │   ├─ llm_client.py             ✅ llama_cpp + transformers 듀얼 백엔드
│   │   │                               LoRA 어댑터 로드, repetition_penalty=1.1, 토큰 카운트
│   │   ├─ prompt_build.py           ✅ Layer A~D Context Assembly
│   │   │                               session.location_context 우선, 없으면 YAML act 사용
│   │   ├─ router.py                 ✅ handle_turn(mode=) — mode 파라미터 추가 (2026-04-09)
│   │   │                               mode="function"이면 요약 트리거 건너뜀
│   │   │                               _check_world_triggers() 신규 — story/place/culture 트리거 체크
│   │   │                               → VDB+RAG → PromptBuilder → LLM → mood/affection → 요약
│   │   └─ session.py                ✅ 세션 상태 (mood 8종, affection, turn_count, dialogue_log,
│   │                                   world_id, scenario_id, act_id, location_context)
│   │                                   fired_stories: list[str] — 발동된 story item_title 목록 (2026-04-09)
│   │                                   visited_places: list[str] — 방문한 장소 목록 (2026-04-09)
│   │                                   explained_cultures: list[str] — 설명된 문화 항목 목록 (2026-04-09)
│   │                                   mood_hold: int — 감정 지속 턴 카운터 (개선8, 2026-04-20)
│   │
│   ├─ loader/
│   │   ├─ __init__.py               ✅ 패키지 초기화
│   │   ├─ character_load.py         ✅ 캐릭터 YAML → dict (필수 필드 검증 포함)
│   │   ├─ chracter_load.py          ⚠️ 오타 파일 — 0 bytes 빈 파일. 삭제 필요
│   │   ├─ memory_load.py            ✅ M_default.json → ChromaDB 초기 삽입용 리스트
│   │   └─ world_load.py             ✅ 세계관 YAML → dict (get_act 헬퍼 포함)
│   │
│   ├─ memory_act/
│   │   ├─ M_schema.json             ✅ VDB 저장 단위 스키마 (중요도 규칙, 검색 설정 포함)
│   │   ├─ M_default.json            📄 캐릭터별 기본 기억 초기값
│   │   └─ M_instance.json           📄 세션 인스턴스 기억 템플릿
│   │
│   ├─ utils/
│   │   ├─ __init__.py               ✅ 패키지 초기화 (setup_logger, load_yaml 등 re-export)
│   │   ├─ file_io.py                ✅ YAML/JSON/JSONL 파일 입출력 헬퍼
│   │   └─ logger.py                 ✅ loguru 설정 — 콘솔+파일 핸들러, 로테이션
│   │
│   └─ world/
│       ├─ W_schema.json             📄 세계관 YAML 스키마
│       └─ W_sea.yaml                📄 예시 세계관 (seaside_world / morning_walk 시나리오)
│                                       act_1: location=beach / act_2: location=breakwater
│                                       character_overrides.rules 필드 추가 (2026-04-09) — 세계관별 추가 행동 규칙
│
├─ narration/                         ✅ 세계관 트리거 패키지 (루트 레벨, 2026-04-09)
│   ├─ __init__.py                   ✅ 패키지 초기화
│   └─ world_trigger.py              ✅ 세계관 트리거 판단 + 나레이션 생성
│                                       check_story_trigger(session, user_input, rag) — 절대 점수 ≥ 0.9 + 토큰 부분 매칭(0.5 가중치) 이중 판정
│                                       check_place_trigger(session, place_id) — visited_places 기반 1회
│                                       check_culture_trigger(session, rag) — explained_cultures 소거법
│
├─ data/
│   └─ lora/
│       ├─ conversation/
│       │   └─ .gitkeep              🔲 build_dataset.py 실행 후 생성 (현재 비어있음)
│       │                               (haru_stranger.jsonl, haru_action_input.jsonl 삭제됨 — training/data/로 이동)
│       └─ function/
│           ├─ folder_organize.jsonl  📄 폴더 정리 기능 학습 데이터
│           ├─ prompt_convert.jsonl   📄 프롬프트 변환 기능 학습 데이터
│           └─ search.jsonl           📄 검색 기능 학습 데이터
│
│
├─ memory/
│   ├─ __init__.py                   ✅ 패키지 초기화
│   ├─ long_term.py                  ✅ ChromaDB store/query (bge-m3, threshold 0.52, importance≥0.5)
│   │                                   CRUD 메서드 추가: delete_entry / add_entry / update_entry
│   ├─ short_term.py                 ✅ get_recent() — 슬라이딩 윈도우
│   ├─ summarizer.py                 ✅ N턴 트리거 + LLM 요약 + 키워드 중요도 scoring + VDB 저장
│   └─ embedding.py                  ✅ 임베딩 모델 lazy-load + CPU 분리 헬퍼 (VRAM 절감)
│
├─ output/
│   ├─ LoRA_v7/                      📄 LoRA_v7 학습 결과 (.gitignore 처리)
│   │   └─ adapter/                  ✅
│   ├─ LoRA_v8/                      📄 LoRA_v8 학습 결과 (.gitignore 처리)
│   │   ├─ adapter/                  ✅ (eval best 1.353, 5 epoch 과적합 — v9로 대체)
│   │   ├─ loss_curve_epoch01~05.png
│   │   ├─ loss_curve_final.png
│   │   ├─ fisher.pt                 ✅ ewc.py 실행 완료 (LoRA_v9 학습에 사용)
│   │   ├─ ref_params.pt             ✅ ewc.py 실행 완료
│   │   └─ train.log
│   ├─ LoRA_v9/                      📄 LoRA_v9 학습 결과 (.gitignore 처리)
│   │   ├─ adapter/                  ✅ (eval best 1.511, 3 epoch EWC λ=500 — v11로 대체)
│   │   ├─ loss_curve_epoch01~03.png
│   │   ├─ loss_curve_final.png
│   │   └─ train.log
│   └─ LoRA_v11/                     📄 LoRA_v11 학습 결과 (.gitignore 처리) ← 현재 최신
│       ├─ adapter/                  ✅ 현재 최신 어댑터 (config.py 참조)
│       │                               checkpoint-700 복사 (eval best 1.5387, epoch 1.97)
│       │   ├─ adapter_config.json   ← r=32, alpha=64
│       │   └─ adapter_model.safetensors
│       ├─ checkpoint-700/           ✅ best checkpoint (eval_loss 1.5387, epoch 1.97)
│       ├─ loss_curve_epoch01.png    ← epoch 1 완료 시
│       ├─ loss_curve_epoch02.png    ← epoch 2 완료 시 (학습 중단 전 마지막)
│       └─ train.log
│
├─ rag/
│   ├─ __init__.py                   ✅ 패키지 초기화
│   ├─ index.py                      ✅ index_world() — 섹션 기반 청킹 + ChromaDB 인덱싱 (2026-04-09)
│   │                                   _parse_world_md() 신규: # WorldName / ## section / ### item_title 파싱
│   │                                   story 섹션 전용 트리거 키워드: [...] 파싱
│   │                                   ChromaDB 메타: {world_id, section, item_title, trigger_keywords}
│   │                                   ~~⚠️ 고정 크기 청킹~~ → ✅ 섹션 기반 청킹으로 전환 완료 (2026-04-09)
│   ├─ retrieve.py                   ✅ WorldRetriever.query() — 매 턴 실행, threshold 0.52
│   │                                   컬렉션 미존재 안전 처리 / add_document() 동적 upsert
│   │                                   query_by_meta(world_id, section) 신규 — 섹션 전체 반환 (2026-04-09)
│   ├─ world_nav.py                  ✅ detect_move_intent() — 키워드 필터 + LLM 추출(max_tokens=15)
│   │                                   find_or_create_location() — RAG 검색 → LLM 생성 → add_document 저장
│   └─ sources/
│       └─ world/
│           └─ Seaside.md            ✅ 통합 세계관 소스 — ## culture / ## place / ## story
│                                       (culture.md / place.md / story.md 삭제됨 — 중복 인덱싱 방지)
│
├─ scripts/
│   ├─ build_dataset.py              ✅ training/log/*.jsonl → data/lora/conversation/ 빌드
│   │                                   ✅ glob("**/*.jsonl") 수정 완료 (2026-03-22)
│   ├─ merge_lora.py                 ✅ LoRA 어댑터 병합 (float16, low_cpu_mem_usage=True)
│   └─ convert_to_gguf.sh            ✅ GGUF 변환 + Q4_K_M 양자화 (--llama_cpp 경로 지정 필요)
│
├─ tests/                            ← 모든 테스트 파일은 반드시 이 폴더에 저장한다
│   │                                   (eval/ 폴더의 수동 검증 스크립트와 분리)
│   │                                   전체: 474 passed (2026-04-20 기준, 이전 421)
│   ├─ test_bridge_slots.py          ✅ ChatBridge 슬롯 단위 테스트
│   │                                   stub agent + QCoreApplication 헤드리스 실행
│   │                                   monkeypatch로 _ICONS_DIR / _CHAR_PARTS_DIR / 스크린 mock
│   │                                   getCharacterStatus / resetCharacter / CRUD 슬롯 테스트 포함
│   │                                   stub_agent 픽스처: agent.cfg = {} 필수 (없으면 MagicMock/ 디렉토리 생성 부작용)
│   ├─ test_ui_structure.py          ✅ QML 파일 존재·qmldir 등록·프로퍼티·시그널 검증
│   │                                   버그 회귀 방지 테스트 포함
│   │                                   (pipBubbleOpen 바인딩 루프, delegate scope, panelRect 클릭 등)
│   │                                   CharacterSelectPanel / CharacterStatusPanel / ResetConfirmPanel
│   │                                   SideMenuPanel / AdminPanel / CharacterCreatePanel / MemoryDBPanel 검증 포함
│   ├─ test_narration.py             ✅ NarrationMonitor.check_keyword() 세션 1회 제한
│   │                                   narration_hardcoded.find_trigger() 키워드 매칭
│   │                                   bridge._ACTION_RE *...* 패턴 감지 테스트
│   ├─ test_dialogue_quality.py      ✅ PromptBuilder Layer A 이름 형식, rules 포함, tier 톤
│   │                                   SFT 변환, reviewed_only 필터, training/data/affection/stranger.jsonl 구조 검증
│   ├─ test_function_tools.py        ✅ PromptGuideStore 저장/검색/삭제, regex fallback, 한국어 비율
│   │                                   (TestWebSearchTool 제거됨 — web_search.py 삭제)
│   ├─ test_integration_flows.py     ✅ LocalSearchFullFlow / FolderClassifyFullFlow / FileOptionsFullFlow
│   │                                   (TestWebSearchFullFlow 제거됨 — web_search.py 삭제)
│   │                                   bridge 픽스처: agent.cfg = {} 필수 (MagicMock/ 부작용 방지)
│   ├─ test_improvement4.py          ✅ 개선4 항목 검증 (deleteCharacter, getDefaultWorld 슬롯 등)
│   ├─ test_improvement5.py          ✅ 개선5 전체 커버 (35개 테스트, 2026-04-09)
│   └─ test_integration_improvement5.py ✅ 개선5 통합 테스트 (나레이션 버블 emit, Seaside.md world_id 등)
│                                       TestConversationSessionTriggerFields (3개) — fired_stories/visited_places/explained_cultures
│                                       TestRouterModeParameter (3개) — mode="chat"/"function" 분기
│                                       TestSessionManagerWorldId (4개) — SessionMeta.world_id / activate_for_world()
│                                       TestAgentInjectPromptGuide (4개) — _inject_prompt_guide() 주입 경로
│                                       TestBridgePromptGuideKeys (3개) — model_name / model 키 정규화
│                                       TestWorldTriggers (5개) — story/place/culture 트리거
│                                       TestRagIndexParser (3개) — _parse_world_md() 섹션 파서
│                                       TestConfigValues (3개) — default_world_id / memory_trigger_n
│                                       TestMemoryDBPanelQmlTab2 (7개) — CRUD UI 속성·시그널 검증
│
├─ tools/
│   ├─ __init__.py                   ✅ BaseTool re-export
│   ├─ base.py                       ✅ BaseTool 인터페이스 (parse_params JSON 추출 + execute 추상 메서드)
│   ├─ commands.py                   📄 미사용 — 추후 정리 예정
│   ├─ prompt_converter.py           ✅ 프롬프트 변환 (명확하게/간결하게/상세하게/질문형/지시형)
│   ├─ prompt_store.py               ✅ PromptGuideStore — ChromaDB prompt_guides 컬렉션 CRUD
│   │                                   query(model_key): model 키 exact match 조회
│   │                                   model 키 정규화: " " / "_" → "-", lowercase (2026-04-09 호환성 추가)
│   ├─ folder/
│   │   ├─ __init__.py               ✅ 패키지 초기화
│   │   ├─ classifier.py             ✅ 파일 분류 (확장자별/종류별, CATEGORY_MAP, dry_run)
│   │   ├─ converter.py              ✅ 이미지 포맷 변환 (Pillow: jpg/png/webp/bmp/tiff, RGBA→RGB)
│   │   └─ renamer.py                ✅ 이름 일괄 변환 (7가지 규칙, glob 패턴, dry_run)
│   └─ search/
│       ├─ __init__.py               ✅ 패키지 초기화
│       └─ local_search.py           ✅ SQLite FTS5 로컬 검색 (증분 인덱싱, mtime 추적, ~/.cache/achat/)
│                                       (web_search.py 삭제됨 — RAM/VRAM 절감 및 외부 의존성 제거)
│
├─ training/
│   ├─ 학습.md                       ✅ 학습 실행 가이드 (Step 0~6, GPU/CPU 옵션, 평가까지)
│   ├─ dataset.py                    ✅ ChatML 포맷 데이터셋 로더 (apply_chat_template, max_length 필터,
│   │                                   파일별 비율 유지 stratified sampling, category_weights 오버/언더샘플링)
│   ├─ ewc.py                        ✅ EWC Fisher 계산 CLI + EWCPenalty 클래스
│   │                                   compute_fisher(): base model + adapter 로드 → LoRA 파라미터만
│   │                                   n_samples forward/backward → Fisher 대각 평균 계산
│   │                                   → fisher.pt / ref_params.pt 저장
│   │                                   EWCPenalty(fisher_path, ref_params_path, lambda_, device)
│   │                                   → penalty(model): λ/2 × Σ F_i × (θ_i - θ*_i)²
│   ├─ train_monitor.py              ✅ 학습 모니터링 래퍼 — 학습 명령어를 입력받아 subprocess로 실행
│   │                                   find_latest_state(): checkpoint-*/trainer_state.json 중 최신 파일 탐색
│   │                                   (HuggingFace Trainer는 학습 중 체크포인트 서브디렉토리에 state 저장)
│   │                                   trainer_state.json 폴링(기본 15초) → 과적합 감지 시 SIGTERM
│   │                                   종료 조건: eval_loss N회 연속 상승(--n_rise) or gap 초과(--gap)
│   │                                   VRAM 해제 후 3가지 출력: 학습 상황 / 종료 조건 / 입력 명령어
│   │                                   사용: python training/train_monitor.py -- python -m training.lora_train ...
│   ├─ lora_train.py                 ✅ LoRA 학습 (bfloat16, GPU/CPU 자동 전환, --no_save, --max_steps,
│   │                                   --eval_split, best loss 저장, loss 그래프 PNG 자동 저장,
│   │                                   assistant 토큰 마스킹, --skip_eval,
│   │                                   EWCTrainer + --ewc_fisher/--ewc_ref_params/--ewc_lambda,
│   │                                   --category_weights JSON 문자열)
│   │                                   ✅ --data_dir 기본값 training/data로 수정 (2026-03-23)
│   │                                   학습 완료 순서:
│   │                                     1) 어댑터 저장 (output/{run}/adapter/)
│   │                                     2) checkpoint-* 삭제
│   │                                     3) VRAM 완전 해제
│   │                                        trainer.model=None → del trainer/model/tokenizer
│   │                                        gc.collect() → empty_cache() + synchronize()
│   │                                     4) training/eval/ subprocess 자동 실행
│   │
│   ├─ eval/                         ← 학습 완료 후 lora_train.py가 VRAM 해제 후 자동 실행
│   │   ├─ __init__.py
│   │   ├─ ai_tell_checker.py        ✅ AI투 표현 패턴 측정 + 베이스/LoRA 비교 (자동 실행)
│   │   ├─ memory_test.py            ✅ 멀티턴 기억 유지 정확도 5케이스 (자동 실행)
│   │   ├─ speed_bench.py            ✅ transformers/llama_cpp 추론 속도 벤치마크 (수동 실행)
│   │   └─ verify_phases.py          ✅ Phase 2/3 실환경 검증 (12턴 자동 대화, 5항목 PASS, 수동 실행)
│   │                                   LLM 풀 로드 필요 — 수동 실행만
│   │
│   ├─ data/                         📄 학습 데이터 총 3,170건 / 57파일 (v11 기준, 2026-04-14)
│   │   │                               시스템 프롬프트: `너는 {char_name}이다.` + 카테고리 속성 (2026-04-02)
│   │   ├─ affection/                📄 친밀도 단계별 데이터 (15파일)
│   │   │                               stranger/acquaintance/familiar/affection_low~high/close/friendly/intimate
│   │   │   └─ formal/               📄 존댓말 캐릭터 친밀도 6단계 (각 30건, 계 180건, v11 신규)
│   │   ├─ common/                   📄 공통 능력 데이터 (4파일)
│   │   │   ├─ ai_tell_removal.jsonl 📄 AI투 표현 제거 학습 데이터
│   │   │   ├─ memory_ref.jsonl      📄 기억 참조 학습 데이터
│   │   │   ├─ persona_follow.jsonl  📄 페르소나 준수 학습 데이터
│   │   │   └─ world_trigger_response.jsonl 📄 세계관 위치/배경 반응 (50건, v11 신규)
│   │   ├─ emotion/                  📄 감정 상태별 데이터 (10파일)
│   │   │                               neutral / happy / affectionate / touched / curious /
│   │   │                               sad / embarrassed / annoyed / angry (각 40건)
│   │   │                               + transition (감정 전환 멀티턴 40건, v11 신규)
│   │   ├─ long_dialogue/            📄 장대화 데이터 (9파일)
│   │   │   ├─ daily_chat.jsonl      📄 일상 장대화 (51건)
│   │   │   ├─ emotional_support.jsonl 📄 감정 지지 장대화
│   │   │   ├─ casual_deep.jsonl     📄 일상+깊은 대화
│   │   │   ├─ understanding.jsonl   📄 긴 설명 핵심 파악
│   │   │   ├─ opinion_exchange.jsonl 📄 의견/취향 교환
│   │   │   ├─ context_maintenance.jsonl 📄 장소/상황 맥락 유지
│   │   │   ├─ correction_graceful.jsonl 📄 오해/정정 자연스러운 반응
│   │   │   ├─ action_response.jsonl 📄 (행동:...) 패턴 반응
│   │   │   └─ topic_continuity.jsonl 📄 화제 전환 없는 주제 유지 (v11 신규)
│   │   ├─ personality/              📄 6종 성격별 데이터 (calm/cynical/tsundere/energetic/melancholic/warm)
│   │   │                               cynical/tsundere: 서술 개선 (v11) | energetic/melancholic/warm: 신규 (v11)
│   │   ├─ speech_style/
│   │   │   ├─ informal/             📄 informal_blunt.jsonl / informal_soft.jsonl
│   │   │   ├─ formal/               📄 formal_blunt.jsonl / formal_soft.jsonl (v11 신규, affection/formal과 분리)
│   │   │   └─ persona/              📄 cool_observant / gentle_quiet / quiet_sensitive / warm_dry
│   │   └─ _excluded/                📄 비활성 파일 (bright/dependent/mixed_blunt)
│   │                                   dataset.py load_jsonl_files에서 자동 제외
│   │
│   └─ log/
│       ├─ _schema.json              ✅ 로그 포맷 명세
│       ├─ conversation_logger.py    ✅ 카테고리 자동 분류 저장 — 키워드 트리거 즉시 flush,
│       │                               CHUNK_SIZE=8 일상 수집, Jaccard 중복 제거(0.55)
│       ├─ monitor.py                ✅ 세션 실시간 모니터링 — .session_state.json 폴링(2s)
│       ├─ review.py                 ✅ 미검토 항목 CLI — y/n/d/s/q, --cat 옵션
│       ├─ .session_state.json       📄 런타임 파일 (세션 상태 스냅샷, monitor 폴링용)
│       ├─ .monitor.log              📄 런타임 파일 (monitor 출력 기록)
│       ├─ daily/                    📄 일상 대화 로그 ({session_id}.jsonl + 구버전 날짜패턴 잔존)
│       ├─ emotion/                  📄 감정 공감 로그 (동일)
│       ├─ feedback_neg/             📄 교정·지적·반복루프 로그
│       ├─ feedback_pos/             📄 칭찬·동의 로그
│       ├─ memory/                   📄 기억 관련 로그
│       ├─ advice/                   ✅ 고민 상담 로그 폴더 생성됨 (2026-04-20)
│       └─ persona/                  🔲 페르소나 이탈 교정 로그 (폴더 없음 — 미수집)
│
└─ ui_ux/
    ├─ __init__.py                   ✅ 패키지 초기화
    ├─ bridge.py                     ✅ ChatBridge(QObject) — QML↔Python 시그널/슬롯 브리지
    │                                   Signal: messageAdded / statusChanged / characterNameChanged
    │                                           backgroundChanged / moodChanged / imageImported
    │                                           memoryChanged (CRUD 후 QML 실시간 갱신)
    │                                   Property: characterName / characterId / currentBackground / currentMood
    │                                   Slot: sendMessage(text, mode) / snapToEdge / changeCharacter / changeWorld
    │                                         getCharacterList / getWorldList
    │                                         loadCustomization / saveCustomization / getAllPartsList
    │                                         browseImage / importImageFromDrop / browseCharacterYaml
    │                                         newSession(keep_memory) / listSessions(char_id)  ← world_id 포함 (2026-04-09)
    │                                         getCharacterStatus / resetCharacter(char_id)
    │                                         getTheme / saveTheme(theme_id)
    │                                         deleteMemoryEntry(entry_id) / addMemoryEntry(content, meta_json)
    │                                         updateMemoryEntry(entry_id, new_content, meta_json)
    │                                         ── 개선5 신규 슬롯 (2026-04-09) ──
    │                                         getWorldKnowledgeDB() / addWorldKnowledge(section, title, content)
    │                                         updateWorldKnowledge(entry_id, content) / deleteWorldKnowledge(entry_id)
    │                                         reindexWorldKnowledge() — ChromaDB → Seaside.md 재인덱싱 (add/update/delete/create 시 자동 호출)
    │                                         ── 개선6 신규 슬롯 (2026-04-20) ──
    │                                         getPipBubbleDir() / savePipBubbleDir(dir) — PIP 말풍선 방향 설정
    │                                         addPromptGuide(model_name, content, char_id) — model 키 정규화 저장
    │                                         updatePromptGuide(entry_id, content) / deletePromptGuide(entry_id)
    │                                         getPromptModelList() — DB 내 model_name 목록
    │                                         getDefaultWorld() — config.default_world_id 반환
    │                                         changeWorld — 세계관 변경 감지, activate_for_world() 호출
    │                                   경로 상수:
    │                                     _ICONS_DIR      = ui_ux/assets/icons/
    │                                     _CHAR_PARTS_DIR = ui_ux/assets/characters/
    │                                     _BG_DIR         = ui_ux/assets/background/
    │                                     _PREFS_PATH     = ui_ux/assets/preferences.json
    │                                     _CHARACTER_DIR  = conversation/character/
    │                                     _WORLD_DIR      = conversation/world/
    │                                   _build_bg_url(): session.location → {location}.png 탐색
    │                                   SessionManager 연동: _init_session / _sync_session_state / _rebuild_agent
    │                                   activate_for_world(char_id, world_id) — (char_id, world_id) 쌍 기준 세션 초기화
    ├─ chat_panel.py                 ✅ LLMWorker(QThread) — 백그라운드 LLM 추론
    │                                   response_ready / error_occurred 시그널
    ├─ tray.py                       ✅ AppTrayIcon — 시스템 트레이 (열기/숨기기, 캐릭터 변경, 종료)
    ├─ widget.py                     ✅ UIEngine — QQmlApplicationEngine 래퍼, bridge context property 등록
    │
    ├─ assets/
    │   ├─ background/               ← 장소별 배경 이미지. 경로: {world_id}/{location}.png
    │   │   └─ seaside_world/
    │   │       └─ beach.png         ✅ 경로 일치 확인 (2026-03-22)
    │   │
    │   ├─ characters/               ← 파츠 합성용 레이어 이미지 (128×160 px PNG)
    │   │   ├─ .gitkeep
    │   │   ├─ base/                 🔲 비어있음 — 베이스(얼굴+몸통) 파츠 PNG 배치 예정
    │   │   ├─ cloth/                🔲 비어있음 — 의상 파츠 PNG 배치 예정
    │   │   ├─ eye/                  🔲 비어있음 — 눈 파츠 PNG 배치 예정
    │   │   ├─ hair/                 🔲 비어있음 — 헤어 파츠 PNG 배치 예정
    │   │   └─ mouth/                🔲 비어있음 — 입 파츠 PNG 배치 예정
    │   │
    │   ├─ icons/                    ← 캐릭터별 완성 아이콘 + 감정 오버레이
    │   │   ├─ .gitkeep
    │   │   └─ Haru/
    │   │       ├─ Haru.png          ✅ 하루 전신 기본 아이콘 (128×160 px)
    │   │       ├─ parts.json        🔲 커스터마이징 저장 파일 (saveCustomization() 호출 시 생성)
    │   │       └─ emotion/          🔲 비어있음 — 감정 오버레이 PNG 배치 예정
    │   │                               neutral/happy/affectionate/touched/curious/
    │   │                               sad/embarrassed/annoyed/angry .png (각 128×160 px)
    │   └─ preferences.json          📄 UI 환경설정 (getTheme/saveTheme로 읽기/쓰기, 앱 실행 시 자동 생성)
    │                                   {"theme": "ocean"}
    │
    └─ qml/
        ├─ qmldir                    ✅ AchatUI 모듈 선언
        │                               Style(singleton) / ChatBubble / PipWindow / SettingsPanel /
        │                               CharacterDisplay / CustomizationPanel /
        │                               CharacterSelectPanel / CharacterStatusPanel / ResetConfirmPanel /
        │                               MemoryDBPanel / AdminPanel / CharacterCreatePanel / SideMenuPanel
        ├─ Style.qml                 ✅ 디자인 토큰 singleton — 색상/폰트/간격/애니메이션 상수
        ├─ main.qml                  ✅ 프레임리스 플로팅 Window (432×624 ↔ 160×160 PIP 전환)
        │                               DragHandler, HoverHandler, 한글 폰트 로더
        │                               테마 시스템: currentTheme + _themes(ocean/solar/forest) + _th shortcut
        │                               타이틀바: charNameLabel + "캐릭터 변경" + "상태" + ≡(사이드메뉴) + PIP + ✕
        │                               isBubble / pipBubbleOpen / settingsOpen / sideMenuOpen /
        │                               charSelectOpen / charStatusOpen / resetConfirmOpen / memoryDBOpen /
        │                               customPartsJson / allPartsListJson / backgroundImageUrl / currentMood
        │                               Connections(bridge.memoryChanged → getMemoryDB() 재호출)
        │                               Component.onCompleted — default_world_id(seaside_world) 자동 적용 (2026-04-09)
        │                               onCharacterCreateRequested — CharacterCreatePanel 열기 핸들러 (2026-04-09)
        ├─ ChatBubble.qml            ✅ 재사용 말풍선 컴포넌트 (role로 좌/우 정렬·색상 제어)
        │                               userBubbleColor / assistBubbleColor 프로퍼티 (테마 색상 주입)
        ├─ PipWindow.qml             ✅ PIP 마스코트 모드 (아이콘 + 위로 확장 말풍선)
        │                               characterId 기반 icons/{id}/{id}.png + emotion 오버레이
        │                               mood 8종 이모지 플레이스홀더 / 5초 자동 닫힘 / expandRequested 시그널
        │                               bubbleDirection 프로퍼티 (left/right) — 말풍선 방향 전환 (2026-04-20)
        │                               resizeRequested 시그널 — 드래그 크기 조절 연동
        ├─ SettingsPanel.qml         ✅ 오른쪽 슬라이드인 설정 패널 (z:10)
        │                               캐릭터 / 세계관+act / 커스터마이징 / 초기화 / 테마 섹션
        │                               closeRequested / emotionPanelRequested / characterBuildRequested /
        │                               newSessionRequested / resetConfirmRequested / themeChangeRequested 시그널
        │                               characterCreateRequested 시그널 신규 (2026-04-09) — 캐릭터 생성 버튼 연결
        │                               세션 목록 display_name / {char_name}-{world_id} 표시 (2026-04-09)
        │                               session_id null 가드 추가 (2026-04-09)
        │                               PIP 말풍선 방향 설정 섹션 추가 (2026-04-20) — getPipBubbleDir/savePipBubbleDir 연결
        ├─ SideMenuPanel.qml         ✅ 오른쪽 슬라이드인 사이드 내비게이션 패널 (z:25, 220px)
        │                               DB / 설정 / 관리 세 섹션 아코디언 구조
        │                               closeRequested / openMemoryDB / openSettings / openAdmin 시그널
        │                               슬라이드인 애니메이션 (NumberAnimation rightMargin -220→0)
        ├─ MemoryDBPanel.qml         ✅ ChromaDB 장기 메모리 CRUD 패널 (z:20)
        │                               플랫 카드 목록 (이전: 세션 그룹 아코디언)
        │                               카드별 ✏ 인라인 수정 폼 / 🗑 삭제 버튼
        │                               추가 폼: 내용 + 중요도 Slider + 태그/위치 TextInput
        │                               deleteRequested / addRequested / updateRequested 시그널
        │                               bridge.memoryChanged → getMemoryDB() 실시간 갱신
        │                               탭2 (프롬프트 가이드) CRUD 완전 구현 (2026-04-09, 개선5 항목6):
        │                                 model_name 기준 그룹 접힘/펼침 구조
        │                                 추가 폼: 모델명(gAddModel) + 캐릭터ID(gAddCharId) + 내용(gAddContent)
        │                                 카드 삭제: bridge.deletePromptGuide(id) / 수정: bridge.updatePromptGuide(id, text)
        ├─ AdminPanel.qml            ✅ 관리자 패널 — affection 직접 조작 (z:20)
        ├─ CharacterCreatePanel.qml  ✅ 캐릭터 생성 패널 — 신규 캐릭터 YAML 등록 (z:20)
        ├─ CharacterBuildPanel.qml   ✅ 캐릭터 빌드 패널 — YAML 슬롯 편집 UI (개선7, 2026-04-20)
        ├─ EmotionPanel.qml          ✅ 감정 상태 조회 패널 — mood/affection 시각화 (개선8, 2026-04-20)
        ├─ FolderClassifyPanel.qml   ✅ 폴더 정리 도구 실행 패널 (기능 모드)
        ├─ CharacterDisplay.qml      ✅ 레이어 합성 캐릭터 표시 (128×160 px, z:2)
        │                               icons/{id}/{id}.png 우선 → 없으면 5레이어 파츠 합성
        │                               감정 오버레이: icons/{id}/emotion/{mood}.png
        │                               mood 8종 이모지 플레이스홀더 / _hasAnyPart 플레이스홀더 제어
        ├─ CustomizationPanel.qml    ✅ 커스터마이징 편집 모달 (z:20)
        │                               파츠 6종(base/hair/eyebrow/eye/mouth/cloth) 가로 스크롤 선택
        │                               ListView.view.outerKey/outerSelected (delegate scope 버그 방지)
        │                               saved(partsJson) 시그널
        ├─ CharacterSelectPanel.qml  ✅ 캐릭터 변경 모달 (z:20) — 타이틀바 "캐릭터 변경" 버튼
        │                               캐릭터 목록 Repeater + 선택 시 characterChanged(charId)
        │                               "+" 추가 버튼 → addRequested → bridge.browseCharacterYaml()
        ├─ CharacterStatusPanel.qml  ✅ 캐릭터 상태 모달 (z:20) — 타이틀바 "상태" 버튼
        │                               bridge.getCharacterStatus() JSON 파싱
        │                               이름/tier 배지(색상 맵)/친밀도 바(Behavior)/감정/대화 횟수
        └─ ResetConfirmPanel.qml     ✅ 캐릭터 초기화 확인 모달 (z:30)
                                        캐릭터 목록 라디오 선택 + 초기화 버튼
                                        bridge.resetCharacter(char_id) → 세션 + VDB 전체 삭제
```

---

## 알려진 문제 / 정리 필요 항목

| # | 항목 | 위치 | 설명 | 우선순위 |
|---|---|---|---|---|
| ~~1~~ | ~~오타 빈 파일 잔존~~ | — | ✅ 해당 없음 — 이 작업공간에 `chracter_load.py` 없음 | 해결 |
| ~~2~~ | ~~config.py 어댑터 경로 불일치~~ | — | ✅ `./output/LoRA_v11/adapter` 경로 일치 (2026-04-14) | 해결 |
| ~~3~~ | ~~build_dataset.py glob 버그~~ | — | ✅ `glob("**/*.jsonl")` 수정 완료 (2026-03-22) | 해결 |
| ~~4~~ | ~~배경 이미지 위치 불일치~~ | — | ✅ `background/seaside_world/beach.png` 로 이동 완료 (2026-03-22) | 해결 |
| ~~5~~ | ~~런타임 로그 gitignore 미적용~~ | `.gitignore` | ✅ training/log/daily|emotion|feedback_neg|feedback_pos|memory/ + data/sessions/ 패턴 추가, git rm --cached 완료 (2026-03-28) | 해결 |
| 6 | config.py 배포 모델 없음 | `config.py` deploy.model_path | `./models/model_q4km.gguf` 참조하나 models/ 폴더 없음 — 배포 빌드 시 생성 필요 | 낮음 (배포 전 처리) |
| 7 | 구버전 날짜 패턴 로그 잔존 | `training/log/daily/`, `emotion/` | `2026-03-17.jsonl` 등 날짜 패턴 파일이 현행 session_id 패턴과 혼재 | 낮음 |
| ~~8~~ | ~~MagicMock/ 디렉토리 생성~~ | — | ✅ stub_agent 픽스처에 `agent.cfg = {}` 추가로 해결 + .gitignore 추가 (2026-04-20) | 해결 |

---

## 파일 상태 요약

| 상태 | 항목 수 | 설명 |
|---|---|---|
| ✅ 완료 | 100+ | 전체 대화 엔진, UI, RAG, 학습 파이프라인, 테스트 + 개선5 + v11 학습 완료 (2026-04-14) |
| 📄 데이터/설정 | 30+ | YAML/JSON 스키마, 학습 데이터, 런타임 로그 |
| 🔲 구현 예정 / 비어있음 | 8 | characters/ 파츠 PNG, emotion/ 오버레이 PNG, icons 앱 아이콘, advice·persona 로그 폴더, data/lora/conversation |
| ⚠️ 정리 필요 | 3 | 위 "알려진 문제" 표 참조 (이전 6개 중 3개 해결됨) |
