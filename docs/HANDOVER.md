# 인수인계 문서 — Ubuntu 22.04 환경 이전

> 작성 기준일: 2026-03-15
> 이전 환경: Ubuntu 20.04 WSL2 (Windows 11, RTX 5060)
> 이전 목적: 한글 입력 문제 해결 (`fcitx5-hangul` 패키지가 Ubuntu 22.04+ 전용)

---

## 1. 현재 프로젝트 상태

| Phase | 내용 | 상태 |
|---|---|---|
| Phase 0 | 환경 설정, config.py, pyproject.toml, Dockerfile | ✅ 완료 |
| Phase 1 | LLM 클라이언트, 세션, 캐릭터 로더, 프롬프트 빌더 | ✅ 완료 |
| Phase 2 | Agent 코어, 메모리, 라우터, 페르소나 | ✅ 완료 |
| Phase 3 | RAG 인덱스 / 검색 | ✅ 완료 (스텁 수준) |
| Phase 4 | UI (PySide6/QML) — 시각적 동작 확인 완료 | ✅ 완료 |
| Phase 5 | LoRA 학습 파이프라인 | ⏳ 미착수 |
| Phase 6 | 모델 병합 → GGUF 변환 → 배포 | ⏳ 미착수 |

코드는 GitHub 리포지토리가 최신 상태 기준. 새 환경에서 `git clone` 후 시작.

---

## 2. 미해결 이슈 (이전 목적)

### 한글 입력 불가
- **원인**: Ubuntu 20.04에 `fcitx5-hangul` 패키지 없음
- **해결**: Ubuntu 22.04 WSL2 인스턴스로 이전 후 `fcitx5-hangul` 설치
- **확인 방법**: 앱 실행 후 메시지 입력창에서 한/영 전환(Ctrl+Space) 동작 여부

---

## 3. Ubuntu 22.04 WSL2 신규 환경 셋업

### 3-1. WSL2에 Ubuntu 22.04 설치 (Windows PowerShell)
```powershell
wsl --install -d Ubuntu-22.04
```

### 3-2. 시스템 패키지 설치
```bash
sudo apt-get update && sudo apt-get install -y \
  libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xinerama0 libxcb-xkb1 libegl1 libegl-mesa0 libglib2.0-0 \
  fcitx5 fcitx5-hangul
```

### 3-3. uv 설치 (Python + 패키지 관리)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # 또는 재시작
```

### 3-4. 리포지토리 클론 및 의존성 설치
```bash
git clone <repo-url> ~/projects/Achat
cd ~/projects/Achat
uv sync
```

### 3-5. fcitx5 자동 시작 설정 (~/.bashrc 하단에 추가)
```bash
# fcitx5 한글 입력기
export QT_IM_MODULE=fcitx
export GTK_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
```

### 3-6. 실행
```bash
fcitx5 &
ACHAT_ENV=dev python main.py
```
> Ctrl+Space — 한/영 전환

---

## 4. 이전 세션에서 해결한 주요 문제들 (참고)

### 4-1. Segfault — torch + Qt 공유 라이브러리 충돌
- **현상**: `python main.py` 실행 즉시 segfault
- **원인**: 파일 상단에서 PySide6 import → Qt 공유 라이브러리 먼저 로드 → torch 로드 시 충돌
- **해결**: `main.py`에서 모든 PySide6 import를 `main()` 함수 안 `Agent` 초기화 이후로 이동
- **관련 파일**: `main.py`

### 4-2. Segfault — bitsandbytes + RTX 5060 (Blackwell SM 10.x)
- **현상**: 모델 로딩 중 segfault, faulthandler 출력 없음
- **원인**: `bitsandbytes` 4-bit 양자화가 SM 10.x 아키텍처 미지원
- **해결**: BitsAndBytesConfig 제거, `dtype=torch.bfloat16` + `.to("cuda")` 직접 사용
- **관련 파일**: `conversation/core/llm_client.py`

### 4-3. 창이 보이지 않음
- **원인**: `Qt.Tool` 플래그가 WSLg 환경에서 창을 숨김
- **해결**: `Qt.Tool` 제거, `Component.onCompleted`에서 화면 우하단에 초기 위치 설정
- **관련 파일**: `ui_ux/qml/main.qml`

### 4-4. 버튼 클릭 안 됨
- **원인**: 전체 창을 덮는 MouseArea가 모든 마우스 이벤트를 가로챔
- **해결**: `HoverHandler` + `DragHandler { target: null; onActiveChanged: root.startSystemMove() }` 로 교체
- **관련 파일**: `ui_ux/qml/main.qml`

### 4-5. 한글 폰트 깨짐 (네모 표시)
- **원인**: Linux에 Malgun Gothic 폰트 없음
- **해결**: QML에서 `FontLoader { source: "file:///mnt/c/Windows/Fonts/malgun.ttf" }` 로드
- **관련 파일**: `ui_ux/qml/main.qml`, `ui_ux/qml/ChatBubble.qml`

### 4-6. QML TypeError — bridge is null
- **현상**: `TypeError: Cannot read property 'charAt' of null`
- **원인**: Connections 핸들러에서 `charNameLabel.text = name` 직접 대입이 QML 바인딩을 깨뜨림
- **해결**: 직접 대입 제거, `bridge ? bridge.characterName : ""` null guard 추가
- **관련 파일**: `ui_ux/qml/main.qml`

### 4-7. VRAM 이전 프로세스 잔류
- **현상**: 비정상 종료 후 python 프로세스가 VRAM 점유
- **해결**: `/tmp/achat.pid` PID 파일 패턴 — 시작 시 이전 PID kill, 자신의 PID 기록
- **수동 정리**: `kill $(cat /tmp/achat.pid) && rm /tmp/achat.pid`
- **관련 파일**: `main.py`

---

## 5. 디렉토리 구조 핵심 참조

```
Achat/
├── main.py                        # 진입점 (Qt import는 main() 내부에서)
├── config.py                      # ACHAT_ENV=dev/deploy 분기
├── conversation/
│   ├── core/llm_client.py         # bfloat16, .to("cuda") — BnB 없음
│   └── character/CH_Haru.yaml     # 대소문자 주의 (CHARACTER_ID = "Haru")
├── ui_ux/
│   ├── qml/main.qml               # 주 UI — DragHandler, FontLoader 포함
│   ├── qml/ChatBubble.qml         # fontFamily prop으로 한글 폰트 전달
│   ├── qml/Style.qml              # 디자인 토큰 (singleton)
│   └── qml/qmldir                 # AchatUI 모듈 등록
├── docs/
│   ├── DIR.md                     # 전체 파일 구조 + 상태
│   ├── plan/phases.md             # Phase별 구현 계획
│   └── MVP대화.md                 # 실행 방법 + 학습 데이터 수집 가이드
├── pyproject.toml                 # uv 의존성 (dev: PySide6 포함)
└── Dockerfile                     # nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04
```

---

## 6. 다음 작업 — Phase 5 (LoRA 학습 파이프라인)

`docs/plan/phases.md` Phase 5 항목 참조.

우선순위 작업:
1. `scripts/build_dataset.py` — `training/log/*.jsonl` → `data/lora/` 변환
2. `scripts/train_lora.py` — unsloth 기반 LoRA 파인튜닝 실행
3. `training/log/` 에 대화 데이터 수동 수집 (`docs/MVP대화.md` § 3 참조)

학습 전 최소 수집 목표: 카테고리별 30~50건.

---

## 7. 환경 변수 요약

| 변수 | 값 | 용도 |
|---|---|---|
| `ACHAT_ENV` | `dev` / `deploy` | 모델 백엔드 분기 |
| `QT_IM_MODULE` | `fcitx` | Qt 한글 입력기 |
| `GTK_IM_MODULE` | `fcitx` | GTK 한글 입력기 |
| `XMODIFIERS` | `@im=fcitx` | X11 입력기 |
| `DISPLAY` | `:0` (WSLg 자동) | X11 디스플레이 |
