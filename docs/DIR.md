# DIR — 파일시스템 현황 참조 문서

> 이 문서는 실제 파일시스템 기준으로 작성됩니다.
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
│                                        dev: adapter_path="./output/LoRA_v7/adapter" ⚠️ 실제 없음
│                                        deploy: model_path="./models/model_q4km.gguf" ⚠️ 실제 없음
├─ pyproject.toml                     ✅ 개발 환경 의존성 (uv, Linux + GPU) + ruff 설정
├─ pyproject-deploy.toml              ✅ 배포 환경 의존성 (uv, Windows + CPU)
├─ uv.lock                            ✅ uv lock 파일 (dev 기준)
├─ Dockerfile                         ✅ CUDA 12.8 + Ubuntu 24.04 + uv 기반
│                                        ibus-hangul, libgl1, IBUS_USE_PORTAL=0
├─ .gitignore                         ✅ output/ 제외 (학습 체크포인트/어댑터)
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
│   │   ├─ UI설계.md                  ✅ QML + PySide6 UI 설계 상세 (1~6단계 구현 완료)
│   │   └─ UI_테스트.md               ✅ UI 전체 수동 테스트 체크리스트 + 자동 테스트 실행 가이드
│   └─ BUG/
│       ├─ BUG_1.md                   ✅ 인수인계 문서 (환경 셋업, 해결된 이슈 기록)
│       └─ BUG_small.md               ✅ 소규모 버그 수정 기록
│
├─ agent/
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ core.py                        ✅ Agent 클래스 — 컴포넌트 초기화 + chat() / handle_input(mode) 모드 분기
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
│   ├─ narrator.py                    ✅ Narrator 클래스 (비활성화) — describe_arrival / describe_session_start
│   │                                    LLM 3~5문장 장면 묘사 (대화 품질 안정화 후 재활성화 예정)
│   │
│   ├─ character/
│   │   ├─ CH_schema.json            📄 캐릭터 YAML 필드 스키마
│   │   ├─ CH_Haru.yaml              ✅ 예시 캐릭터 (speech_style, memory_voice, state, mood_triggers 8종)
│   │   ├─ CH_Seonjae.yaml           ✅ 예시 캐릭터 (6단계 affection_thresholds, affection_delta, mood_triggers 8종)
│   │   └─ CH_default.yaml           📄 기본 캐릭터
│   │
│   ├─ core/
│   │   ├─ __init__.py               ✅ 패키지 초기화
│   │   ├─ llm_client.py             ✅ llama_cpp + transformers 듀얼 백엔드
│   │   │                               LoRA 어댑터 로드, repetition_penalty=1.1, 토큰 카운트
│   │   ├─ prompt_build.py           ✅ Layer A~D Context Assembly
│   │   │                               session.location_context 우선, 없으면 YAML act 사용
│   │   ├─ router.py                 ✅ handle_turn() — 장소 이동 감지(_handle_location)
│   │   │                               → VDB+RAG → PromptBuilder → LLM → mood/affection → 요약
│   │   └─ session.py                ✅ 세션 상태 (mood 8종, affection, turn_count, dialogue_log,
│   │                                   world_id, scenario_id, act_id, location_context)
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
│
├─ data/
│   └─ lora/
│       ├─ conversation/
│       │   └─ .gitkeep              🔲 build_dataset.py 실행 후 생성 (현재 비어있음)
│       └─ function/
│           ├─ folder_organize.jsonl  📄 폴더 정리 기능 학습 데이터
│           ├─ prompt_convert.jsonl   📄 프롬프트 변환 기능 학습 데이터
│           └─ search.jsonl           📄 검색 기능 학습 데이터
│
│
├─ memory/
│   ├─ __init__.py                   ✅ 패키지 초기화
│   ├─ long_term.py                  ✅ ChromaDB store/query (bge-m3, threshold 0.52, importance≥0.5)
│   ├─ short_term.py                 ✅ get_recent() — 슬라이딩 윈도우
│   └─ summarizer.py                 ✅ N턴 트리거 + LLM 요약 + 키워드 중요도 scoring + VDB 저장
│
├─ output/
│   └─ lora_v1/                      📄 LoRA 학습 결과 (실제 폴더명)
│       └─ checkpoint-1/             ← /adapter 구조 아님, checkpoint 구조
│           ├─ adapter_config.json
│           ├─ adapter_model.safetensors
│           ├─ tokenizer.json / tokenizer_config.json
│           ├─ trainer_state.json / training_args.bin
│           └─ optimizer.pt / scheduler.pt / rng_state.pth
│   ⚠️ config.py는 ./output/LoRA_v7/adapter 를 참조하나 실제 폴더 없음
│      → dev 환경 실행 시 어댑터 로드 실패, 베이스 모델로 폴백됨
│
├─ rag/
│   ├─ __init__.py                   ✅ 패키지 초기화
│   ├─ al.txt                        📄 세계관 분위기 텍스트 메모 (바닷가/영화관/새벽 묘사)
│   ├─ index.py                      ✅ index_world() — .md 청킹(400자/overlap 50) + ChromaDB 인덱싱
│   │                                   ⚠️ 고정 크기 청킹 — ## 헤더 경계와 불일치 가능
│   │                                   → semantic chunking 전환 권장 (현재 보류: world 문서 1개뿐)
│   ├─ retrieve.py                   ✅ WorldRetriever.query() — 매 턴 실행, threshold 0.52
│   │                                   컬렉션 미존재 안전 처리 / add_document() 동적 upsert
│   ├─ world_nav.py                  ✅ detect_move_intent() — 키워드 필터 + LLM 추출(max_tokens=15)
│   │                                   find_or_create_location() — RAG 검색 → LLM 생성 → add_document 저장
│   └─ sources/
│       └─ world/
│           ├─ culture.md            📄 마을 문화 및 풍습
│           ├─ place.md              📄 주요 장소 정보 (beach/breakwater/lighthouse/항구시장/카페)
│           └─ story.md              📄 배경 스토리 (마을 역사, 등대지기 전설, 주요 사건)
│
├─ scripts/
│   ├─ build_dataset.py              ✅ training/log/*.jsonl → data/lora/conversation/ 빌드
│   │                                   ⚠️ glob("*.jsonl")이 루트만 탐색 — 실제 로그는 서브폴더
│   │                                   (daily/emotion/feedback_neg 등)에 있어 파일을 읽지 못함
│   │                                   → glob("**/*.jsonl", recursive=True) 로 수정 필요
│   ├─ merge_lora.py                 ✅ LoRA 어댑터 병합 (float16, low_cpu_mem_usage=True)
│   └─ convert_to_gguf.sh            ✅ GGUF 변환 + Q4_K_M 양자화 (--llama_cpp 경로 지정 필요)
│
├─ tests/                            ← 모든 테스트 파일은 반드시 이 폴더에 저장한다
│   │                                   (eval/ 폴더의 수동 검증 스크립트와 분리)
│   ├─ test_bridge_slots.py          ✅ ChatBridge 슬롯 단위 테스트 (26건)
│   │                                   stub agent + QCoreApplication 헤드리스 실행
│   │                                   monkeypatch로 _ICONS_DIR / _CHAR_PARTS_DIR / 스크린 mock
│   └─ test_ui_structure.py          ✅ QML 파일 존재·qmldir 등록·프로퍼티·시그널 검증 (53건)
│                                       버그 회귀 방지 테스트 포함
│                                       (pipBubbleOpen 바인딩 루프, delegate scope, panelRect 클릭 등)
│
├─ tools/
│   ├─ __init__.py                   ✅ BaseTool re-export
│   ├─ base.py                       ✅ BaseTool 인터페이스 (parse_params JSON 추출 + execute 추상 메서드)
│   ├─ commands.py                   📄 미사용 — 추후 정리 예정
│   ├─ prompt_converter.py           ✅ 프롬프트 변환 (명확하게/간결하게/상세하게/질문형/지시형)
│   ├─ folder/
│   │   ├─ __init__.py               ✅ 패키지 초기화
│   │   ├─ classifier.py             ✅ 파일 분류 (확장자별/종류별, CATEGORY_MAP, dry_run)
│   │   ├─ converter.py              ✅ 이미지 포맷 변환 (Pillow: jpg/png/webp/bmp/tiff, RGBA→RGB)
│   │   └─ renamer.py                ✅ 이름 일괄 변환 (7가지 규칙, glob 패턴, dry_run)
│   └─ search/
│       ├─ __init__.py               ✅ 패키지 초기화
│       ├─ local_search.py           ✅ SQLite FTS5 로컬 검색 (증분 인덱싱, mtime 추적, ~/.cache/achat/)
│       └─ web_search.py             ✅ 인터넷 검색 — DuckDuckGo Instant Answer API
│
├─ training/
│   ├─ 학습.md                       ✅ 학습 실행 가이드 (Step 0~6, GPU/CPU 옵션, 평가까지)
│   ├─ dataset.py                    ✅ ChatML 포맷 데이터셋 로더 (apply_chat_template, max_length 필터,
│   │                                   파일별 비율 유지 stratified sampling)
│   ├─ train_monitor.py              ✅ 학습 모니터링 래퍼 — 학습 명령어를 입력받아 subprocess로 실행
│   │                                   trainer_state.json 폴링(기본 15초) → 과적합 감지 시 SIGTERM
│   │                                   종료 조건: eval_loss N회 연속 상승(--n_rise) or gap 초과(--gap)
│   │                                   VRAM 해제 후 3가지 출력: 학습 상황 / 종료 조건 / 입력 명령어
│   │                                   사용: python training/train_monitor.py -- python -m training.lora_train ...
│   ├─ lora_train.py                 ✅ LoRA 학습 (bfloat16, GPU/CPU 자동 전환, --no_save, --max_steps,
│   │                                   --eval_split, best loss 저장, loss 그래프 PNG 자동 저장,
│   │                                   assistant 토큰 마스킹, --skip_eval)
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
│   ├─ data/
│   │   ├─ affection/                📄 친밀도 단계별 데이터 (9파일: stranger/acquaintance/familiar/
│   │   │                               affection_low~high/close/friendly/intimate)
│   │   ├─ common/
│   │   │   ├─ ai_tell_removal.jsonl 📄 AI투 표현 제거 학습 데이터
│   │   │   ├─ memory_ref.jsonl      📄 기억 참조 학습 데이터
│   │   │   └─ persona_follow.jsonl  📄 페르소나 준수 학습 데이터
│   │   ├─ personality/              📄 5종 성격별 데이터 (bright/calm/cynical/dependent/tsundere)
│   │   └─ speech_style/
│   │       ├─ formal/               📄 formal_blunt.jsonl / formal_soft.jsonl
│   │       ├─ informal/             📄 informal_blunt.jsonl / informal_soft.jsonl
│   │       ├─ mixed/                📄 mixed_blunt.jsonl (mixed_soft.jsonl 없음)
│   │       └─ persona/              📄 cool_observant / gentle_quiet / quiet_sensitive / warm_dry
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
│       ├─ advice/                   🔲 고민 상담 로그 (폴더 없음 — 해당 카테고리 미수집)
│       └─ persona/                  🔲 페르소나 이탈 교정 로그 (폴더 없음 — 미수집)
│
└─ ui_ux/
    ├─ __init__.py                   ✅ 패키지 초기화
    ├─ bridge.py                     ✅ ChatBridge(QObject) — QML↔Python 시그널/슬롯 브리지
    │                                   Signal: messageAdded / statusChanged / characterNameChanged
    │                                           backgroundChanged / moodChanged
    │                                   Property: characterName / characterId / currentBackground / currentMood
    │                                   Slot: sendMessage / snapToEdge / changeCharacter / changeWorld
    │                                         getCharacterList / getWorldList
    │                                         loadCustomization / saveCustomization / getAllPartsList
    │                                   경로 상수:
    │                                     _ICONS_DIR      = ui_ux/assets/icons/
    │                                     _CHAR_PARTS_DIR = ui_ux/assets/characters/
    │                                     _BG_DIR         = ui_ux/assets/background/
    │                                     _CHARACTER_DIR  = conversation/character/
    │                                     _WORLD_DIR      = conversation/world/
    │                                   _build_bg_url(): act_id → location 역참조 후 {location}.png 탐색
    ├─ chat_panel.py                 ✅ LLMWorker(QThread) — 백그라운드 LLM 추론
    │                                   response_ready / error_occurred 시그널
    ├─ tray.py                       ✅ AppTrayIcon — 시스템 트레이 (열기/숨기기, 캐릭터 변경, 종료)
    ├─ widget.py                     ✅ UIEngine — QQmlApplicationEngine 래퍼, bridge context property 등록
    │
    ├─ assets/
    │   ├─ background/               ← 장소별 배경 이미지. 경로: {world_id}/{location}.png
    │   │   └─ Robby.png             ⚠️ 실제 이미지 있으나 위치 불일치
    │   │                               → background/seaside_world/beach.png 등으로 이동 필요
    │   │
    │   ├─ characters/               ← 파츠 합성용 레이어 이미지 (128×160 px PNG)
    │   │   ├─ .gitkeep
    │   │   ├─ base/                 🔲 비어있음 — 베이스(얼굴+몸통) 파츠 PNG 배치 예정
    │   │   ├─ cloth/                🔲 비어있음 — 의상 파츠 PNG 배치 예정
    │   │   ├─ eye/                  🔲 비어있음 — 눈 파츠 PNG 배치 예정
    │   │   ├─ hair/                 🔲 비어있음 — 헤어 파츠 PNG 배치 예정
    │   │   └─ mouth/                🔲 비어있음 — 입 파츠 PNG 배치 예정
    │   │
    │   └─ icons/                    ← 캐릭터별 완성 아이콘 + 감정 오버레이
    │       ├─ .gitkeep
    │       └─ Haru/
    │           ├─ Haru.png          ✅ 하루 전신 기본 아이콘 (128×160 px)
    │           ├─ parts.json        🔲 커스터마이징 저장 파일 (saveCustomization() 호출 시 생성)
    │           └─ emotion/          🔲 비어있음 — 감정 오버레이 PNG 배치 예정
    │                                   neutral/happy/affectionate/touched/curious/
    │                                   sad/embarrassed/annoyed/angry .png (각 128×160 px)
    │
    └─ qml/
        ├─ qmldir                    ✅ AchatUI 모듈 선언
        │                               Style(singleton) / ChatBubble / PipWindow / SettingsPanel /
        │                               CharacterDisplay / CustomizationPanel
        ├─ Style.qml                 ✅ 디자인 토큰 singleton — 색상/폰트/간격/애니메이션 상수
        ├─ main.qml                  ✅ 프레임리스 플로팅 Window (360×520 ↔ 50×50 PIP 전환)
        │                               DragHandler, HoverHandler, 한글 폰트 로더
        │                               isBubble / pipBubbleOpen / settingsOpen / customizationOpen /
        │                               customPartsJson / allPartsListJson / backgroundImageUrl / currentMood
        ├─ ChatBubble.qml            ✅ 재사용 말풍선 컴포넌트 (role로 좌/우 정렬·색상 제어)
        ├─ PipWindow.qml             ✅ PIP 마스코트 모드 (50×50 아이콘 + 위로 확장 말풍선)
        │                               characterId 기반 icons/{id}/{id}.png + emotion 오버레이
        │                               mood 8종 이모지 플레이스홀더 / 5초 자동 닫힘 / expandRequested 시그널
        ├─ SettingsPanel.qml         ✅ 오른쪽 슬라이드인 설정 패널 (z:10)
        │                               캐릭터 변경 / 세계관+act 선택 (flat model) / 커스터마이징 열기
        │                               closeRequested / customizationRequested 시그널
        ├─ CharacterDisplay.qml      ✅ 레이어 합성 캐릭터 표시 (128×160 px, z:2)
        │                               icons/{id}/{id}.png 우선 → 없으면 5레이어 파츠 합성
        │                               감정 오버레이: icons/{id}/emotion/{mood}.png
        │                               mood 8종 이모지 플레이스홀더 / _hasAnyPart 플레이스홀더 제어
        └─ CustomizationPanel.qml    ✅ 커스터마이징 편집 모달 (z:20)
                                        파츠 5종(base/hair/eye/mouth/cloth) 가로 스크롤 선택
                                        ListView.view.outerKey/outerSelected (delegate scope 버그 방지)
                                        saved(partsJson) 시그널
```

---

## 알려진 문제 / 정리 필요 항목

| # | 항목 | 위치 | 설명 | 우선순위 |
|---|---|---|---|---|
| 1 | 오타 빈 파일 잔존 | `conversation/loader/chracter_load.py` | 0 bytes 빈 파일. 삭제 필요 | 낮음 |
| 2 | config.py 어댑터 경로 불일치 | `config.py` dev.adapter_path | `./output/LoRA_v7/adapter` 참조하나 실제는 `lora_v1/checkpoint-1/` — 베이스 모델로 폴백 실행됨 | 중간 |
| 3 | build_dataset.py glob 버그 | `scripts/build_dataset.py:194` | `log_dir.glob("*.jsonl")`이 루트만 탐색 — 실제 로그는 `daily/` `emotion/` 등 서브폴더에 있어 파일을 읽지 못함. `glob("**/*.jsonl")` 으로 수정 필요 | 높음 |
| 4 | 배경 이미지 위치 불일치 | `ui_ux/assets/background/Robby.png` | `background/seaside_world/beach.png` (또는 breakwater 등) 경로로 이동해야 bridge.py가 감지함 | 중간 |
| 5 | config.py 배포 모델 없음 | `config.py` deploy.model_path | `./models/model_q4km.gguf` 참조하나 models/ 폴더 없음 — 배포 빌드 시 생성 필요 | 낮음 (배포 전 처리) |
| 6 | 구버전 날짜 패턴 로그 잔존 | `training/log/daily/`, `emotion/` | `2026-03-17.jsonl` 등 날짜 패턴 파일이 현행 session_id 패턴과 혼재 | 낮음 |

---

## 파일 상태 요약

| 상태 | 항목 수 | 설명 |
|---|---|---|
| ✅ 완료 | 90+ | 전체 대화 엔진, UI, RAG, 학습 파이프라인, 테스트 |
| 📄 데이터/설정 | 30+ | YAML/JSON 스키마, 학습 데이터, 런타임 로그 |
| 🔲 구현 예정 / 비어있음 | 8 | characters/ 파츠 PNG, emotion/ 오버레이 PNG, icons 앱 아이콘, advice·persona 로그 폴더, data/lora/conversation |
| ⚠️ 정리 필요 | 6 | 위 "알려진 문제" 표 참조 |
