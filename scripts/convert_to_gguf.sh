#!/bin/bash
# convert_to_gguf.sh — HuggingFace 병합 모델 → GGUF 변환 + Q4_K_M 양자화
#
# 사용법:
#   bash scripts/convert_to_gguf.sh \
#     --merged  output/merged_haru_v1 \
#     --out_dir output/gguf \
#     --llama_cpp /path/to/llama.cpp
#
# 선행 조건:
#   - llama.cpp 빌드 완료 (cmake --build build --config Release)
#   - pip install gguf (convert_hf_to_gguf.py 의존성)
#
# 출력:
#   output/gguf/model_fp16.gguf  — 변환 중간 파일 (~6GB)
#   output/gguf/model_q4km.gguf  — 최종 배포 파일  (~2GB)

set -e

# ── 기본값 ─────────────────────────────────────────────────────────────────
MERGED_MODEL="output/merged_haru_v1"
OUT_DIR="output/gguf"
LLAMA_CPP=""

# ── 인자 파싱 ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --merged)   MERGED_MODEL="$2"; shift 2 ;;
        --out_dir)  OUT_DIR="$2";      shift 2 ;;
        --llama_cpp) LLAMA_CPP="$2";  shift 2 ;;
        *) echo "알 수 없는 옵션: $1" >&2; exit 1 ;;
    esac
done

# ── 경로 검증 ─────────────────────────────────────────────────────────────
if [[ -z "$LLAMA_CPP" ]]; then
    echo "오류: --llama_cpp 경로를 지정해주세요." >&2
    echo "예시: bash scripts/convert_to_gguf.sh --llama_cpp ~/llama.cpp" >&2
    exit 1
fi

if [[ ! -d "$MERGED_MODEL" ]]; then
    echo "오류: 병합 모델 경로 없음: $MERGED_MODEL" >&2
    exit 1
fi

if [[ ! -f "$LLAMA_CPP/convert_hf_to_gguf.py" ]]; then
    echo "오류: convert_hf_to_gguf.py 없음: $LLAMA_CPP" >&2
    exit 1
fi

QUANTIZE_BIN="$LLAMA_CPP/build/bin/llama-quantize"
if [[ ! -f "$QUANTIZE_BIN" ]]; then
    # 빌드 위치 fallback
    QUANTIZE_BIN="$LLAMA_CPP/quantize"
fi
if [[ ! -f "$QUANTIZE_BIN" ]]; then
    echo "오류: quantize 바이너리 없음. llama.cpp를 먼저 빌드해주세요." >&2
    exit 1
fi

mkdir -p "$OUT_DIR"

FP16_GGUF="$OUT_DIR/model_fp16.gguf"
Q4KM_GGUF="$OUT_DIR/model_q4km.gguf"

# ── Step 1. HF → GGUF (fp16) ──────────────────────────────────────────────
echo "[1/2] HuggingFace → GGUF (fp16) 변환 중..."
python "$LLAMA_CPP/convert_hf_to_gguf.py" \
    "$MERGED_MODEL" \
    --outfile "$FP16_GGUF" \
    --outtype f16

echo "fp16 GGUF 저장 완료: $FP16_GGUF"

# ── Step 2. fp16 → Q4_K_M 양자화 ─────────────────────────────────────────
echo "[2/2] Q4_K_M 양자화 중..."
"$QUANTIZE_BIN" \
    "$FP16_GGUF" \
    "$Q4KM_GGUF" \
    Q4_K_M

echo ""
echo "완료!"
echo "  fp16: $FP16_GGUF"
echo "  Q4_K_M: $Q4KM_GGUF  (배포 대상)"
echo ""
echo "다음 단계: $Q4KM_GGUF 를 Windows 배포 패키지의 models/ 에 복사"
