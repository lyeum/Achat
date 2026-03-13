# DIR — 파일시스템 현황 참조 문서

> 이 문서는 실제 파일시스템 기준으로 작성됩니다.
> README.md의 설계 구조와 차이가 있는 항목은 ⚠️로 표시합니다.
>
> 범례: ✅ 완료 | 🔲 비어있음(구현 예정) | 📄 데이터/설정 파일 | ⚠️ README 불일치

---

## 전체 디렉토리 트리 (실제 기준)

```
Achat/
│
├─ docs/                              ✅ 완료
│   ├─ README.md                      ✅ 총괄 문서
│   ├─ DIR.md                         ✅ 이 파일 — 파일시스템 현황
│   ├─ 대화품질.md                    ✅ 대화 품질 설계 (Phase 1~3 구현 참조)
│   ├─ 학습후보.md                    ✅ 학습 실험 설계 (Phase 5~6 참조)
│   └─ plan/
│       └─ phases.md                  ✅ Phase 0~6 실행 계획서
│
├─ conversation/                       # 대화 엔진 (핵심)
│   ├─ core/
│   │   ├─ llm_client.py             🔲 llama-cpp-python 추론 래퍼
│   │   ├─ prompt_build.py           🔲 Layer A~E Context Assembly
│   │   ├─ router.py                 🔲 턴 처리 + Post-processing
│   │   └─ session.py                🔲 세션 상태 (mood, affection, turn_count)
│   │
│   ├─ loader/
│   │   ├─ character_load.py         🔲 캐릭터 YAML → dict
│   │   ├─ memory_load.py            🔲 메모리 초기 데이터 로더
│   │   └─ world_load.py             🔲 세계관 YAML → dict
│   │
│   ├─ utils/                         ⚠️ README에 없음 — 유틸리티 디렉토리
│   │   ├─ __init__.py               🔲
│   │   ├─ logger.py                 🔲 로거 설정
│   │   └─ file_io.py                🔲 파일 입출력 유틸
│   │
│   ├─ character/
│   │   ├─ CH_schema.json            📄 캐릭터 YAML 필드 스키마
│   │   ├─ CH_haru.yaml              ✅ 예시 캐릭터 (speech_style, memory_voice, state 완료)
│   │   ├─ CH_default.yaml           📄 기본 캐릭터 (내용 확인 필요)
│   │   └─ chracter_Haru.yaml        ⚠️ 파일명 오타 (charACTER → character), 정리 필요
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
│   └─ main.py                        🔲 대화 엔진 진입점
│
├─ memory/                             # 메모리 관리 레이어
│   ├─ short_term.py                  🔲 슬라이딩 윈도우 (최근 N턴)
│   ├─ long_term.py                   🔲 ChromaDB 저장 / 시맨틱 검색 (bge-m3)
│   └─ summarizer.py                  🔲 N턴 트리거 + 요약 + 중요도 scoring
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
│   ├─ core.py                        🔲 전체 흐름 조율
│   ├─ persona.py                     🔲 캐릭터 YAML 로딩 + 핫스왑
│   ├─ state.py                       🔲 mood / affection 전환 규칙
│   ├─ router.py                      🔲 시동어 / 명령어 분기
│   └─ memory.py                      ⚠️ README에 없음 — 역할 미정의 (agent 레벨 메모리?)
│
├─ ui/                                 # PySide6 위젯 (배포 환경)
│   ├─ widget.py                      🔲 Frameless / Always-on-top 메인 위젯
│   ├─ chat_panel.py                  🔲 스트리밍 토큰 표시 채팅 패널
│   └─ tray.py                        🔲 시스템 트레이
│
├─ training/                           # LoRA 파인튜닝
│   ├─ lora_train.py                  🔲 QLoRA 학습 (8GB VRAM 최적화)
│   ├─ dataset.py                     🔲 ChatML 포맷 데이터셋 로더
│   └─ data/                          ⚠️ README는 루트의 data/lora/ 로 표기 — 실제 위치 다름
│       ├─ data_gen_prompt.md         📄 학습 데이터 생성 프롬프트 가이드
│       ├─ common/
│       │   ├─ memory_ref.jsonl       📄 기억 참조 학습 데이터
│       │   ├─ ai_tell_removal.jsonl  📄 AI 투 표현 제거 학습 데이터
│       │   └─ persona_follow.jsonl   📄 페르소나 준수 학습 데이터
│       ├─ personality/
│       │   ├─ bright.jsonl           📄 밝은 성격
│       │   ├─ calm.jsonl             📄 차분한 성격
│       │   ├─ tsundere.jsonl         📄 츤데레 성격
│       │   ├─ dependent.jsonl        📄 의존적 성격
│       │   └─ cynical.jsonl          📄 냉소적 성격
│       └─ speech_style/              📄 말투 조합 데이터
│           └─ (informal/formal/mixed × blunt/soft)
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
├─ api/                                ⚠️ README에 없음
│   └─ server.py                      🔲 역할 미정의 (향후 웹 UI 확장 용도 추정)
│
├─ tools/
│   ├─ base.py                        🔲 Tool 인터페이스
│   └─ commands.py                    🔲 명령어 처리
│
├─ main.py                             🔲 프로젝트 진입점
├─ config.py                           🔲 dev / deploy 환경 분기 설정
├─ requirements.txt                    📄 (현재 단일 파일 — dev/deploy 분리 필요)
├─ Dockerfile                          📄 Docker 설정
└─ .gitignore
```

---

## README.md와의 불일치 목록

| 항목 | README.md 표기 | 실제 파일시스템 | 처리 방안 |
|---|---|---|---|
| 학습 데이터 위치 | `data/lora/` (루트) | `training/data/` | README 또는 실제 경로 통일 필요 |
| `api/server.py` | 없음 | 존재 | 역할 정의 후 README에 추가하거나 삭제 |
| `agent/memory.py` | 없음 | 존재 | 역할 정의 필요 (`memory/` 레이어와 중복 가능성) |
| `conversation/utils/` | 없음 | 존재 | README에 추가 검토 |
| `chracter_Haru.yaml` | 없음 | 존재 (오타) | 삭제 또는 `CH_haru.yaml`로 통합 |
| `CH_default.yaml` | 없음 | 존재 | 기본 캐릭터 역할이면 README에 추가 |
| `rag/sources/` 내용물 | 파일명만 기재 | place.md, culture.md, story.md 존재 | 이미 준비됨 |
| `requirements.txt` | `requirements-dev.txt` / `requirements-deploy.txt` 분리 | 단일 `requirements.txt` | Phase 0 작업 필요 |

---

## 파일 상태 요약

| 상태 | 수 | 항목 |
|---|---|---|
| ✅ 완료 | 9 | docs 문서 5개, CH_haru.yaml, M_schema.json, rag/sources/ 3개 |
| 📄 데이터/설정 | 20+ | .yaml, .json 스키마, .jsonl 학습 데이터 |
| 🔲 구현 예정 | 30 | 모든 .py 파일 (현재 비어있음) |
| ⚠️ 정리 필요 | 4 | 오타 파일, 경로 불일치, 역할 미정 파일 |
