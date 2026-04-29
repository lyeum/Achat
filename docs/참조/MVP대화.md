# MVP 대화 실행 및 학습 데이터 수집 매뉴얼

---

## 1. MVP 실행 명령어

### 환경 확인
```bash
# 현재 환경 설정 확인 (dev / deploy 분기, 모델명 등)
~/.local/bin/uv run python config.py
```

### VRAM 확인 및 정리 (dev 환경 — GPU 사용 시)

이전 실행이 비정상 종료된 경우 python 프로세스가 VRAM을 점유한 채 남아있을 수 있습니다.

```bash
# GPU 메모리 점유 확인
nvidia-smi

# Achat 이전 프로세스만 종료 (PID 파일 기준 — 다른 프로세스에 영향 없음)
kill $(cat /tmp/achat.pid) && rm /tmp/achat.pid
```

> `main.py`는 시작 시 `/tmp/achat.pid`에 자기 PID를 기록하고,
> 다음 실행 때 해당 PID만 자동으로 정리합니다.
> VRAM 여유가 3 GB 미만이면 경고 로그가 출력됩니다.

### 사전 준비 (Ubuntu 24.04 + 최초 1회)

```bash
# 시스템 패키지 (Qt6 + 한글 입력기)
sudo apt-get update && sudo apt-get install -y \
  dbus-x11 ibus ibus-hangul \
  libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xinerama0 libxcb-xkb1 libegl1 libegl-mesa0 libgl1 libglib2.0-0

# 환경변수 (~/.bashrc 하단에 추가 후 source ~/.bashrc)
export QT_IM_MODULE=ibus
export GTK_IM_MODULE=ibus
export XMODIFIERS=@im=ibus
export IBUS_USE_PORTAL=0
```

### UI 대화 시작 (메인)

```bash
# dbus 세션 + 한글 입력기 시작 (최초 1회 또는 재부팅 후)
eval $(dbus-launch --sh-syntax)
ibus-daemon -d
ibus engine hangul

# dev 환경 실행
ACHAT_ENV=dev uv run python main.py
```

> 처음 실행 시 HuggingFace에서 모델을 다운로드합니다 (약 6GB, 시간 소요).
> 이후 실행부터는 캐시에서 로드되어 빠릅니다.
> 앱 실행 중 **Ctrl+Space** 로 한/영 전환합니다.
> 우측 Alt(한영키)는 WSLg 구조적 한계로 사용 불가 — Ctrl+Space 고정 사용.

### CLI 대화 (UI 없이 터미널에서)

```bash
# dev 환경 (transformers 백엔드)
ACHAT_ENV=dev python -m conversation.main
```

### 대화 중 명령어
| 입력 | 동작 |
|---|---|
| `/quit` 또는 `/exit` 또는 `q` | 대화 종료 |

---

## 2. 학습 데이터 저장 형식

### 저장 위치
```
training/log/
├── daily.jsonl          # 일상 잡담
├── emotion.jsonl        # 감정 표현 / 반응
├── advice.jsonl         # 고민 상담
├── memory.jsonl         # 기억 참조 (이전 대화 언급)
└── persona.jsonl        # 페르소나 일관성 테스트
```

### JSONL 한 줄 형식
```json
{"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}], "character_id": "Haru", "category": "advice", "affection": "high", "mood": "neutral", "emotion_trigger": "고민_상담"}
```

> 한 줄 = 대화 하나. 여러 턴을 하나의 `messages` 배열에 담습니다.

### 필드 정의

| 필드 | 타입 | 설명 |
|---|---|---|
| `messages` | list | `role: user/assistant` 교대. system 메시지는 포함하지 않음 (빌드 시 자동 삽입) |
| `character_id` | string | 캐릭터 ID — 현재 `"Haru"` |
| `category` | string | 아래 카테고리 목록 참고 |
| `affection` | string | `"low"` / `"mid"` / `"high"` — 대화 당시 친밀도 구간 |
| `mood` | string | `"neutral"` / `"happy"` / `"annoyed"` / `"sad"` |
| `emotion_trigger` | string | 대화 유발 감정/상황 자유 기술 (예: `"고민_상담"`, `"장난"`, `"재회"`) |

### 카테고리 설명

| category | 용도 | 예시 상황 |
|---|---|---|
| `daily` | 일상 잡담, 날씨, 근황 | "오늘 뭐 했어?" |
| `emotion` | 감정 표현, 기분 반응 | "기분 안 좋아 보여" |
| `advice` | 고민 상담, 의견 요청 | "이직할까 말까" |
| `memory` | 이전 대화 언급, 기억 참조 | "저번에 말한 거 기억해?" |
| `persona` | 캐릭터 일관성 테스트 | 무례한 입력, 경계 침범 시도 |

---

## 3. 데이터 수집 및 검토 절차

### 수집 방법 (현재: 수동)

대화가 끝난 후 좋은 교환이 있으면 직접 해당 category 파일에 추가합니다.

```jsonl
# training/log/advice.jsonl 예시 (줄바꿈 없이 한 줄)
{"messages": [{"role": "user", "content": "하..이직할까 말까 고민이야."}, {"role": "assistant", "content": "왜, 거기서 또 무슨 일 있었어?"}, {"role": "user", "content": "뭔가 내가 성장을 못하는 거 같아서."}, {"role": "assistant", "content": "음.. 성장이 가능한 쪽으로 가는 게 낫지 않아?"}], "character_id": "Haru", "category": "advice", "affection": "high", "mood": "neutral", "emotion_trigger": "고민_상담"}
```

### 검토 기준

저장할 교환인지 판단할 때 체크할 것:

- [ ] assistant 응답이 반말을 유지하는가
- [ ] 불필요한 AI 투 표현이 없는가 ("물론이죠", "도움이 되셨으면" 등)
- [ ] 감정을 직접 말하지 않고 행동/짧은 언급으로 표현하는가
- [ ] 캐릭터 설정(speech_style)에서 벗어나는 발언이 없는가
- [ ] affection tier가 응답 톤과 일치하는가

### 제외 기준

아래에 해당하면 저장하지 않습니다:

- AI임을 인식하는 발언이 포함된 경우
- 한국어 외 언어가 섞인 경우
- assistant 응답이 3줄 이상으로 지나치게 길어진 경우 (low/mid tier 기준)
- 설정과 맞지 않는 과도한 감정 표현

---

## 4. 빌드 (Phase 5 예정)

수집된 로그를 학습 데이터로 변환할 때:

```
training/log/{category}.jsonl
    ↓  scripts/build_dataset.py  (Phase 5에서 구현)
data/lora/conversation/{category}.jsonl
```

빌드 시 자동으로 수행되는 작업:
- `character_id` + `affection` 기준으로 `CH_{id}.yaml`에서 시스템 프롬프트 생성
- `messages` 앞에 `{"role": "system", "content": "..."}` 삽입
- ChatML 포맷 검증 (role 교대, 최소 1턴 이상)
- `max_length=512` 초과 샘플 경고 출력
