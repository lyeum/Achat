"""
merge_lora.py — LoRA 어댑터 + 베이스 모델 병합 → HuggingFace 포맷 저장

사용법:
  python scripts/merge_lora.py \
    --base_model Qwen/Qwen2.5-3B-Instruct \
    --adapter output/lora_haru_v1/adapter \
    --output_dir output/merged_haru_v1

주의사항:
  - RAM ~6GB 소모 (float16 + LoRA 가중치)
  - 실행 전 브라우저 등 메모리 사용 프로세스 종료 권장
  - OOM 발생 시: WSL2 재시작 후 재시도, 또는 swap 4GB 임시 확장
    sudo fallocate -l 4G /swapfile2 && sudo chmod 600 /swapfile2
    sudo mkswap /swapfile2 && sudo swapon /swapfile2

출력:
  output/merged_haru_v1/  — HF 포맷 병합 모델 (convert_to_gguf.sh 입력)
"""

import argparse
import sys
from pathlib import Path

import torch
from loguru import logger
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def parse_args():
    parser = argparse.ArgumentParser(description="LoRA 어댑터 병합")
    parser.add_argument("--base_model", default="Qwen/Qwen2.5-3B-Instruct", help="HuggingFace 베이스 모델명")
    parser.add_argument("--adapter",    required=True,                        help="LoRA 어댑터 경로 (output/.../adapter)")
    parser.add_argument("--output_dir", default="output/merged",              help="병합 모델 저장 경로")
    return parser.parse_args()


def main():
    args = parse_args()
    adapter_path = ROOT / args.adapter
    output_path  = ROOT / args.output_dir

    if not adapter_path.exists():
        logger.error(f"어댑터 경로 없음: {adapter_path}")
        sys.exit(1)

    output_path.mkdir(parents=True, exist_ok=True)

    # ── 토크나이저 ────────────────────────────────────────────────────────────
    logger.info(f"토크나이저 로드: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)

    # ── 베이스 모델 (float16 CPU) ─────────────────────────────────────────────
    logger.info(f"베이스 모델 로드: {args.base_model} (float16, CPU)")
    logger.warning("RAM ~6GB 소모. 메모리 부족 시 OOM 발생 가능.")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        dtype=torch.float16,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        device_map="cpu",
    )

    # ── LoRA 어댑터 로드 ──────────────────────────────────────────────────────
    logger.info(f"LoRA 어댑터 로드: {adapter_path}")
    model = PeftModel.from_pretrained(model, str(adapter_path))

    # ── 병합 ──────────────────────────────────────────────────────────────────
    logger.info("어댑터 병합 중 (merge_and_unload)...")
    model = model.merge_and_unload()

    # ── 저장 ──────────────────────────────────────────────────────────────────
    logger.info(f"병합 모델 저장: {output_path}")
    model.save_pretrained(str(output_path))
    tokenizer.save_pretrained(str(output_path))
    logger.info("완료. 다음 단계: scripts/convert_to_gguf.sh 실행")


if __name__ == "__main__":
    main()
