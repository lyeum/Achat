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
│   └─ plan1/                         ⚠️ 빈 디렉토리 — 삭제 필요
│
├─ conversation/                       # 대화 엔진 (핵심)
│   ├─ __init__.py                    ✅ 패키지 초기화 (import 경로 확보)
│   ├─ core/
│   │   ├─ llm_client.py             ✅ llama_cpp + transformers 듀얼 백엔드 (스트리밍, 토큰 카운트)
│   │   ├─ prompt_build.py           ✅ Layer A~D Context Assembly, assemble(rag_results=) — Layer B에 RAG 병합
│   │   ├─ router.py                 ✅ `handle_turn()` — VDB + RAG 검색 → PromptBuilder → LLM → mood/affection → 요약 트리거
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
│   ├─ __init__.py                    ✅ 패키지 초기화
│   ├─ index.py                       ✅ `index_world()` — .md 청킹(400자/overlap 50) + ChromaDB 인덱싱 (cosine space)
│   ├─ retrieve.py                    ✅ `WorldRetriever.query()` — 매 턴 실행, threshold 0.7, 컬렉션 미존재 안전 처리
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
│   ├─ log/                           # MVP 대화 로그 수집 (카테고리별 JSONL)
│   │   ├─ _schema.json               ✅ 로그 포맷 명세 (messages/character_id/category/affection/mood/emotion_trigger)
│   │   ├─ daily.jsonl                📄 일상 대화 로그 (수집 예정)
│   │   ├─ emotion.jsonl              📄 감정 공감 로그
│   │   ├─ advice.jsonl               📄 고민 상담 로그
│   │   ├─ memory.jsonl               📄 기억 관련 로그
│   │   └─ persona.jsonl              📄 페르소나 이탈 교정 로그
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
├─ main.py                             ✅ QApplication + UIEngine + AppTrayIcon 조립 진입점
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
| `ui_ux/mode_switcher.py` | 신규 추가 | 미존재 → 삭제됨 | QML `Repeater` 기반 모드 버튼으로 대체 (Phase 4 완료) |
| `ui_ux/qml/` | 없음 | 신규 생성 | QML + PySide6 아키텍처 채택, main.qml + ChatBubble.qml |
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
| ✅ 완료 | 38 | docs 문서 6개, CH_haru.yaml, M_schema.json, rag/sources/ 3개 + Phase 1 8개 + Phase 2 9개 + Phase 3 3개 + Phase 4 8개 (ui_ux/__init__, bridge, chat_panel, widget, tray, qml/main.qml, qml/ChatBubble.qml, main.py) + training/log/_schema.json |
| 📄 데이터/설정 | 20+ | .yaml/.json 스키마, training/data/ 하위 .jsonl 학습 데이터, training/log/ 카테고리별 .jsonl |
| 🔲 구현 예정 | 8 | Phase 5~7 .py 파일 + data/lora/ 데이터 + agent/router.py |
| ⚠️ 정리 필요 | 6 | 오타 파일, 경로 불일치, 역할 미정 파일, 빈 디렉토리 |
