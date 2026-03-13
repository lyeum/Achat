FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# 기본 환경 변수
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 필수 시스템 패키지
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# python 기본 설정
RUN ln -sf /usr/bin/python3.10 /usr/bin/python
RUN python -m pip install --upgrade pip

# 작업 디렉토리
WORKDIR /app

# requirements 먼저 복사 (Docker 캐시 활용)
COPY requirements.txt .

# PyTorch (CUDA 12.1)
RUN pip install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu121

# Python 패키지 설치
RUN pip install -r requirements.txt
RUN pip install einops

# 기본 진입
CMD ["/bin/bash"]
