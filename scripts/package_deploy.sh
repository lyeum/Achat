#!/bin/bash
# package_deploy.sh — 배포 패키지 생성 스크립트
#
# 수행 작업:
#   1. dist/achat/ 에 배포용 파일 복사 (학습 데이터·dev 파일 제외)
#   2. pyproject-deploy.toml → dist/achat/pyproject.toml 으로 복사
#   3. models/ 빈 디렉토리 생성 (GGUF 파일 위치 안내)
#   4. dist/achat.zip 압축
#
# 사용법:
#   bash scripts/package_deploy.sh [--gguf output/gguf/model_q4km.gguf]
#
# 옵션:
#   --gguf <path>   GGUF 파일을 models/ 에 포함할 경우 지정 (생략 시 빈 디렉토리만 생성)

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist/achat"
GGUF_PATH=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --gguf) GGUF_PATH="$2"; shift 2 ;;
        *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
    esac
done

echo "[1/4] dist 초기화: $DIST"
rm -rf "$DIST"
mkdir -p "$DIST"

# ── 소스 복사 (rsync: 제외 패턴 지정) ────────────────────────────────────────
echo "[2/4] 소스 파일 복사..."
rsync -a --exclude='__pycache__' \
         --exclude='*.pyc' \
         --exclude='.venv' \
         --exclude='.git' \
         --exclude='output/' \
         --exclude='training/' \
         --exclude='tests/' \
         --exclude='docs/' \
         --exclude='chroma_dev/' \
         --exclude='chroma_verify/' \
         --exclude='chroma_deploy/' \
         --exclude='data/' \
         --exclude='dist/' \
         --exclude='*.log' \
         --exclude='*.png' \
         --exclude='pyproject.toml' \
         --exclude='pyproject-deploy.toml' \
         "$ROOT/" "$DIST/"

# ── pyproject-deploy.toml → pyproject.toml ────────────────────────────────────
echo "    pyproject-deploy.toml → pyproject.toml"
cp "$ROOT/pyproject-deploy.toml" "$DIST/pyproject.toml"

# ── models/ 디렉토리 ─────────────────────────────────────────────────────────
mkdir -p "$DIST/models"
if [[ -n "$GGUF_PATH" ]]; then
    if [[ ! -f "$GGUF_PATH" ]]; then
        echo "경고: GGUF 파일 없음: $GGUF_PATH — models/ 는 비어있습니다." >&2
    else
        echo "    GGUF 복사: $GGUF_PATH → models/"
        cp "$GGUF_PATH" "$DIST/models/model_q4km.gguf"
    fi
else
    # 안내 파일 생성
    cat > "$DIST/models/README.txt" << 'EOF'
models/ 디렉토리에 model_q4km.gguf 파일을 복사해주세요. (약 2GB)

GGUF 파일 생성 방법:
  1. LoRA 병합: python scripts/merge_lora.py --adapter output/LoRA_v11/adapter --output_dir output/merged_v11
  2. GGUF 변환: bash scripts/convert_to_gguf.sh --merged output/merged_v11 --out_dir output/gguf --llama_cpp /path/to/llama.cpp
  3. 생성된 output/gguf/model_q4km.gguf 를 이 폴더에 복사
EOF
fi

# ── chroma_deploy 초기 디렉토리 ─────────────────────────────────────────────
mkdir -p "$DIST/chroma_deploy"

# ── zip 압축 ─────────────────────────────────────────────────────────────────
echo "[3/4] zip 압축: dist/achat.zip"
cd "$ROOT/dist"
uv run python3 -c "
import zipfile, pathlib
exclude = {'achat/models/model_q4km.gguf'}
with zipfile.ZipFile('achat.zip', 'w', zipfile.ZIP_DEFLATED) as zf:
    for f in pathlib.Path('achat').rglob('*'):
        if f.is_file() and str(f).replace(chr(92), '/') not in exclude:
            zf.write(f)
"
# GGUF 파일은 용량이 크므로 zip 제외 — 별도 배포

echo "[4/4] 완료"
echo ""
echo "  배포 디렉토리 : dist/achat/"
echo "  배포 zip      : dist/achat.zip  (모델 제외)"
echo ""
echo "  배포 절차:"
echo "    1. dist/achat/ 를 Windows PC 에 복사"
echo "    2. models/model_q4km.gguf 복사"
echo "    3. uv sync 실행 (최초 1회)"
echo "    4. run.bat 실행"
