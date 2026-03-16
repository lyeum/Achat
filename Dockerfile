FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

# 기본 환경 변수
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 필수 시스템 패키지
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    # Qt6 / PySide6 런타임 의존성
    libxkbcommon-x11-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxcb-cursor0 \
    libegl1 \
    libegl-mesa0 \
    libgl1 \
    libglib2.0-0 \
    # D-Bus (ibus 데몬 세션 연결에 필요)
    dbus-x11 \
    # 한글 입력기 — ibus 기반 (PySide6 번들 Qt6와 ABI 호환)
    # 주의: fcitx5-frontend-qt6는 시스템 Qt6 기준 빌드 → PySide6 번들 Qt6와 ABI 불일치로 로드 실패
    ibus \
    ibus-hangul \
    && rm -rf /var/lib/apt/lists/*

# uv 설치 (Python + 패키지 관리)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# 작업 디렉토리
WORKDIR /app

# 의존성 먼저 복사 (Docker 캐시 활용)
COPY pyproject.toml uv.lock ./

# Python + 패키지 설치 (pyproject.toml 기준)
RUN uv sync

# 소스 복사
COPY . .

# 한글 입력기 환경 변수 (ibus 기반)
ENV QT_IM_MODULE=ibus
ENV GTK_IM_MODULE=ibus
ENV XMODIFIERS=@im=ibus
# Portal 없는 WSL2/최소 환경에서 ibus 직접 연결 강제
ENV IBUS_USE_PORTAL=0

CMD ["/bin/bash"]
