# 인수인계 문서 — Ubuntu 24.04 환경

> 최초 작성: 2026-03-15 (Ubuntu 20.04 → 22.04 이전 기준)
> 최종 갱신: 2026-03-16
> 현재 환경: Ubuntu 24.04.3 LTS WSL2 (Windows 11, RTX 5060, 커널 6.6.87.2-microsoft-standard-WSL2)
> 현재 목적: 한글 입력 문제 ✅ 해결 — ibus + IBUS_USE_PORTAL=0 적용 완료. 우측 Alt(한영키) 전환은 WSLg 구조적 한계로 미지원, Ctrl+Space 사용

---

## 1. 현재 프로젝트 상태

| Phase | 내용 | 상태 |
|---|---|---|
| Phase 0 | 환경 설정, config.py, pyproject.toml, Dockerfile | ✅ 완료 |
| Phase 1 | LLM 클라이언트, 세션, 캐릭터 로더, 프롬프트 빌더 | ✅ 완료 |
| Phase 2 | Agent 코어, 메모리, 라우터, 페르소나 + 실환경 검증 | ✅ 완료 |
| Phase 3 | RAG 인덱스 / 검색 + 실환경 검증 | ✅ 완료 |
| Phase 4 | UI (PySide6/QML) — 시각적 동작 확인 완료 | ✅ 완료 |
| Phase 5 | LoRA 학습 파이프라인 — v1 완료, v2 학습 중 | 🔄 진행중 |
| Phase 6 | 모델 병합 → GGUF 변환 → 배포 | ⏳ Phase 5 완료 후 진행 |
| Phase 7 | 기능 모드 도구 (폴더정리/검색/프롬프트 변환) | ✅ 완료 |

코드는 GitHub 리포지토리가 최신 상태 기준. 새 환경에서 `git clone` 후 시작.

---

## 2. 해결된 이슈

### 한글 입력 불가 → ✅ 해결 (2026-03-16)
- **현상**: Ctrl+Space 한/영 전환 불가, 입력창에서 영문만 입력됨
- **근본 원인 3가지**:
  1. **fcitx5 ABI 불일치**: 시스템 `fcitx5-frontend-qt6`는 Ubuntu 24.04 시스템 Qt6 기준 빌드 → pip 설치 PySide6 번들 Qt6와 Private API 버전 불일치 → 플러그인 로드 실패
  2. **ibus Portal 의존**: `IBUS_USE_PORTAL` 기본값이 `1`이어서 `org.freedesktop.portal.Desktop` 서비스를 찾으려 하지만 WSL2 최소 환경엔 없음 → ibus 플러그인이 로드는 되지만 연결 실패
  3. **dbus 세션 미실행**: WSL2 기본 환경에 dbus 세션 버스 없음 → `fcitx5`/`ibus` 데몬이 앱과 통신 불가
- **해결책**:
  - `fcitx5` 대신 `ibus` + `ibus-hangul` 사용 (PySide6 번들 Qt6에 이미 ibus 플러그인 내장)
  - `IBUS_USE_PORTAL=0` 설정 → Portal 없이 ibus 직접 연결
  - `eval $(dbus-launch --sh-syntax)` → dbus 세션 수동 시작
- **한/영 전환 단축키**: `Ctrl+Space` (현재 유일하게 동작하는 방법)

### 한/영키(우측 Alt) 커스텀 시도 → ❌ WSLg 구조적 한계
- **근본 원인**: WSLg/Weston 레이어에서 modifier 키의 state 비트가 하드코딩됨. keycode 108의 keysym을 `Hangul`로 바꿔도 modifier state는 `0x8 (Mod1/Alt)`로 고정 → ibus-hangul이 "Alt가 눌렸다"고 판단해 Hangul keysym 무시
- **시도 A** `xmodmap + dconf hangul-keys=['Hangul']`: keysym 리맵 성공 확인, dconf 설정 확인 → 앱 내 미동작
- **시도 B** `dconf hangul-keys=['Alt+Release+Alt_R']`: ibus 엔진 SetGlobalEngine 호출 자체가 `Operation was cancelled`로 실패
- **시도 C-1** Python `QApplication.notify()` + `subprocess.Popen(["ibus", "engine", ...])` 단순 버전: 우측 Alt 1회에 KeyPress/KeyRelease 다중 이벤트 발생 → ibus engine 명령 충돌(`Operation was cancelled`) → 실패
- **시도 C-2** debounce + threading + 단독 Release 감지 개선 버전 (`HangulToggler` 클래스, `nativeScanCode==108` 필터, `subprocess.run` + 300ms lock): 구조적으로는 올바르나 `ibus engine` 자체가 WSLg 환경에서 비동기 상태 전환을 못 따라옴 → 실패
- **시도 D** `dconf hangul-keys=['Shift_R']`: 동작 안 함
- **결론**: WSLg 환경에서 우측 Alt를 한/영 토글 키로 쓰는 것은 현재 불가능. 완전한 데스크탑 환경(GNOME + 네이티브 Wayland)으로 전환하기 전까지 **Ctrl+Space 고정 사용**.
- **향후 재시도 여지**: `python-ibus` 바인딩(`gi.repository.IBus`)으로 subprocess 없이 D-Bus 직접 호출하는 방식은 미시도. 단 WSLg modifier state 문제가 근본 원인이므로 효과 미지수.

### WSLg Modifier State 문제 구조 (근본 원인 분석)

X11 키 이벤트는 `keysym`(키의 의미)과 `state`(modifier 비트) 두 가지를 함께 전달한다:
```
KeyEvent { keycode: 108, keysym: Hangul, state: 0x0008 (Mod1/Alt) }
```
- `keysym`은 xmodmap으로 변경 가능
- `state`는 Weston(WSLg 컴포지터) → Wayland 프로토콜 → XWayland 경로에서 하드코딩되어 X11 레이어에서 수정 불가
- ibus-hangul은 `state` 비트에 modifier가 있으면 해당 키를 무시 → keysym을 아무리 바꿔도 전환 불가

**Ctrl+Space가 동작하는 이유**: Ctrl+Space는 ibus global trigger(`/desktop/ibus/general/hotkey/trigger` dconf 기본값)로 처리되며, **우리 코드에는 이 단축키가 정의된 곳이 없음**. ibus 데몬이 전적으로 처리.

### 미시도 해결 방향

**방향 A — non-modifier 키로 ibus trigger 변경 (권장)**
- `Scroll_Lock`, `F13` 등 modifier가 아닌 키는 state 비트 문제 없음
- 물리 우측 Alt(keycode 108)를 해당 keysym으로 리맵 + ibus trigger 변경
```bash
xmodmap -e "remove mod1 = Alt_R"          # Mod1 그룹에서 제거
xmodmap -e "keycode 108 = Scroll_Lock"    # Scroll_Lock keysym으로 리맵
dconf write /desktop/ibus/general/hotkey/trigger "['Scroll_Lock']"
```
- 불확실 요소: XWayland가 X11 modifier map 변경을 존중하는지 여부

**방향 B — ibus 없이 QML/Python 레벨 직접 구현**
- `TextInput` 키 이벤트를 Python에서 직접 처리, 한/영 상태 직접 관리
- ibus 의존성 완전 제거 가능하나 한글 조합 로직 직접 구현 필요 (난이도 높음)

---

## 3. Ubuntu 24.04 WSL2 환경 셋업 현황

### 3-0. UI 스펙 (Phase 4 완료 기준)

| 항목 | 내용 |
|---|---|
| UI 프레임워크 | PySide6 (Qt6) + QML |
| 창 형태 | 프레임리스 플로팅 윈도우 |
| 모드 | bubble (72px 아이콘) ↔ chat (360×520 채팅창) 토글 |
| 드래그 | `DragHandler { target: null; onActiveChanged: root.startSystemMove() }` |
| 한글 폰트 | `FontLoader { source: "file:///mnt/c/Windows/Fonts/malgun.ttf" }` |
| LLM↔QML 브리지 | `ChatBridge(QObject)` — `bridge.py` |
| 백그라운드 추론 | `LLMWorker(QThread)` — `chat_panel.py` |
| 트레이 아이콘 | `AppTrayIcon` — `tray.py` |
| 입력기 | ibus-hangul, Ctrl+Space 한/영 전환 (우측 Alt는 WSLg 한계로 불가) |

### 3-1. 현재 환경 상태

| 항목 | 상태 |
|---|---|
| OS | Ubuntu 24.04.3 LTS WSL2 |
| 커널 | 6.6.87.2-microsoft-standard-WSL2 |
| Python | 3.13.9 (conda base) |
| uv | ✅ 설치 완료 (`~/.local/bin/uv`) |
| 입력기 | ✅ ibus + ibus-hangul (fcitx5 → ibus로 교체) |
| 한글 입력 | ✅ 동작 확인 완료 |
| Dockerfile | ✅ `ubuntu24.04`, `libgl1`, `ibus`, `IBUS_USE_PORTAL=0` 반영 완료 |

### 3-2. 환경 셋업 명령어 (✅ 검증 완료)

```bash
# 1. 시스템 패키지 설치
sudo apt-get update && sudo apt-get install -y \
  dbus-x11 ibus ibus-hangul \
  libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xinerama0 libxcb-xkb1 libegl1 libegl-mesa0 libgl1 libglib2.0-0

# 2. uv 설치
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# 3. Python 패키지 설치
cd ~/projects/Achat
uv sync

# 4. 환경변수 (~/.bashrc 하단에 추가)
export QT_IM_MODULE=ibus
export GTK_IM_MODULE=ibus
export XMODIFIERS=@im=ibus
export IBUS_USE_PORTAL=0

# 5. dbus 세션 시작 + ibus 기동 + UI 실행
eval $(dbus-launch --sh-syntax)
ibus-daemon -d
ibus engine hangul
sleep 1
ACHAT_ENV=ui_test uv run python main.py
# Ctrl+Space — 한/영 전환
```

---

## 4. Ubuntu 22.04 WSL2 셋업 (구버전 참고용)

### 4-1. WSL2에 Ubuntu 22.04 설치 (Windows PowerShell)
```powershell
wsl --install -d Ubuntu-22.04
```

### 4-2. 시스템 패키지 설치
```bash
sudo apt-get update && sudo apt-get install -y \
  libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xinerama0 libxcb-xkb1 libegl1 libegl-mesa0 libglib2.0-0 \
  fcitx5 fcitx5-hangul
```

### 4-3. uv 설치 (Python + 패키지 관리)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc   # 또는 재시작
```

### 4-4. 리포지토리 클론 및 의존성 설치
```bash
git clone <repo-url> ~/projects/Achat
cd ~/projects/Achat
uv sync
```

### 4-5. fcitx5 자동 시작 설정 (~/.bashrc 하단에 추가)
```bash
# fcitx5 한글 입력기
export QT_IM_MODULE=fcitx
export GTK_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
```

### 4-6. 실행
```bash
fcitx5 &
ACHAT_ENV=dev python main.py
```
> Ctrl+Space — 한/영 전환

---

## 5. 이전 세션에서 해결한 주요 문제들 (참고)

### 5-1. Segfault — torch + Qt 공유 라이브러리 충돌
- **현상**: `python main.py` 실행 즉시 segfault
- **원인**: 파일 상단에서 PySide6 import → Qt 공유 라이브러리 먼저 로드 → torch 로드 시 충돌
- **해결**: `main.py`에서 모든 PySide6 import를 `main()` 함수 안 `Agent` 초기화 이후로 이동
- **관련 파일**: `main.py`

### 5-2. Segfault — bitsandbytes + RTX 5060 (Blackwell SM 10.x)
- **현상**: 모델 로딩 중 segfault, faulthandler 출력 없음
- **원인**: `bitsandbytes` 4-bit 양자화가 SM 10.x 아키텍처 미지원
- **해결**: BitsAndBytesConfig 제거, `dtype=torch.bfloat16` + `.to("cuda")` 직접 사용
- **관련 파일**: `conversation/core/llm_client.py`

### 5-3. 창이 보이지 않음
- **원인**: `Qt.Tool` 플래그가 WSLg 환경에서 창을 숨김
- **해결**: `Qt.Tool` 제거, `Component.onCompleted`에서 화면 우하단에 초기 위치 설정
- **관련 파일**: `ui_ux/qml/main.qml`

### 5-4. 버튼 클릭 안 됨
- **원인**: 전체 창을 덮는 MouseArea가 모든 마우스 이벤트를 가로챔
- **해결**: `HoverHandler` + `DragHandler { target: null; onActiveChanged: root.startSystemMove() }` 로 교체
- **관련 파일**: `ui_ux/qml/main.qml`

### 5-5. 한글 폰트 깨짐 (네모 표시)
- **원인**: Linux에 Malgun Gothic 폰트 없음
- **해결**: QML에서 `FontLoader { source: "file:///mnt/c/Windows/Fonts/malgun.ttf" }` 로드
- **관련 파일**: `ui_ux/qml/main.qml`, `ui_ux/qml/ChatBubble.qml`

### 5-6. QML TypeError — bridge is null
- **현상**: `TypeError: Cannot read property 'charAt' of null`
- **원인**: Connections 핸들러에서 `charNameLabel.text = name` 직접 대입이 QML 바인딩을 깨뜨림
- **해결**: 직접 대입 제거, `bridge ? bridge.characterName : ""` null guard 추가
- **관련 파일**: `ui_ux/qml/main.qml`

### 5-7. VRAM 이전 프로세스 잔류
- **현상**: 비정상 종료 후 python 프로세스가 VRAM 점유
- **해결**: `/tmp/achat.pid` PID 파일 패턴 — 시작 시 이전 PID kill, 자신의 PID 기록
- **수동 정리**: `kill $(cat /tmp/achat.pid) && rm /tmp/achat.pid`
- **관련 파일**: `main.py`

---

## 6. 디렉토리 구조 핵심 참조

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
└── Dockerfile                     # nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04 (libgl1-mesa-glx → libgl1 수정 완료)
```

---

## 7. 현재 작업 — Phase 5 v2 학습 + Phase 6 대기

### Phase 5 완료 항목 (lora_haru_v1)
- GPU 학습 3 epoch 완료 (loss 0.4425, RTX 5060, ~37분)
- AI투 표현: 0건/응답 (캐릭터 말투 개선 확인)
- 기억 정확도: 40% (목표 80% 미달 — v2 재학습 중)
- 추론 속도: 10.3 tok/s GPU

### 현재 진행 중 (lora_haru_v2)
- `training/data` 전체 1,461건 × 3 epoch
- **best eval loss 기반 저장** (eval_split=0.1, `load_best_model_at_end=True`)
- 어댑터: `output/lora_haru_v2/adapter/`

### Phase 5 → 6 전환 조건
v2 학습 완료 후:
1. `eval/memory_test.py` — 기억 정확도 80% 이상 달성 확인
2. `scripts/merge_lora.py` — LoRA 어댑터 → HF 포맷 병합
3. cmake 설치 완료 확인 후 `scripts/convert_to_gguf.sh` 실행
   - llama.cpp 클론: `~/llama.cpp` (또는 임의 경로)
   - 빌드: `cmake -B build && cmake --build build --config Release`

---

## 8. 환경 변수 요약

| 변수 | 값 | 용도 |
|---|---|---|
| `ACHAT_ENV` | `dev` / `deploy` | 모델 백엔드 분기 |
| `QT_IM_MODULE` | `ibus` | Qt 한글 입력기 |
| `GTK_IM_MODULE` | `ibus` | GTK 한글 입력기 |
| `XMODIFIERS` | `@im=ibus` | X11 입력기 |
| `DISPLAY` | `:0` (WSLg 자동) | X11 디스플레이 |
| `ACHAT_ENV` | `ui_test` | stub 모드 — LLM 로딩 없이 UI만 기동 |
| `IBUS_USE_PORTAL=0` | `0` | WSL2 최소 환경에서 Portal 없이 ibus 직접 연결 (필수) |
