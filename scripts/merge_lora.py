"""
merge_lora.py — LoRA 어댑터 + 베이스 모델 병합 → HuggingFace 포맷 저장

사용법:
  python scripts/merge_lora.py \
    --base_model Qwen/Qwen2.5-3B-Instruct \
    --adapter output/LoRA_v11/adapter \
    --output_dir output/merged_v11

메모리 요구사항:
  - float16 병합: RAM ~6GB  (기본값)
  - OOM 발생 시: 아래 swap 확장 후 재시도
    sudo fallocate -l 6G /swapfile2 && sudo chmod 600 /swapfile2
    sudo mkswap /swapfile2 && sudo swapon /swapfile2
    # 완료 후 제거: sudo swapoff /swapfile2 && sudo rm /swapfile2
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


def _check_memory() -> None:
    """가용 RAM을 확인하고 부족 시 경고 + swap 안내를 출력한다."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        available_gb = (vm.available + swap.free) / (1024 ** 3)
        logger.info(
            f"메모리 현황 — RAM 가용: {vm.available / (1024**3):.1f}GB  "
            f"Swap 가용: {swap.free / (1024**3):.1f}GB  "
            f"합산: {available_gb:.1f}GB"
        )
        if available_gb < 7.0:
            logger.warning(
                f"가용 메모리 {available_gb:.1f}GB — 병합에 ~6GB 필요. OOM 위험.\n"
                "  swap 확장 후 재시도:\n"
                "    sudo fallocate -l 6G /swapfile2 && sudo chmod 600 /swapfile2\n"
                "    sudo mkswap /swapfile2 && sudo swapon /swapfile2"
            )
    except ImportError:
        pass  # psutil 없으면 건너뜀


def parse_args():
    parser = argparse.ArgumentParser(description="LoRA 어댑터 병합")
    parser.add_argument("--base_model", default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--adapter",    required=True,                help="LoRA 어댑터 경로")
    parser.add_argument("--output_dir", default="output/merged",      help="병합 모델 저장 경로")
    return parser.parse_args()


def main():
    args = parse_args()
    adapter_path = ROOT / args.adapter
    output_path  = ROOT / args.output_dir

    if not adapter_path.exists():
        logger.error(f"어댑터 경로 없음: {adapter_path}")
        sys.exit(1)

    _check_memory()

    output_path.mkdir(parents=True, exist_ok=True)

    # ── 토크나이저 ────────────────────────────────────────────────────────────
    logger.info(f"토크나이저 로드: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)

    # ── 베이스 모델 (float16, CPU, 샤드 단위 스트리밍 로드) ──────────────────
    logger.info(f"베이스 모델 로드: {args.base_model} (float16, CPU)")
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,   # 샤드 단위 로드 — 피크 RAM 절감
        trust_remote_code=True,
        device_map="cpu",
    )

    # ── LoRA 어댑터 로드 ──────────────────────────────────────────────────────
    logger.info(f"LoRA 어댑터 로드: {adapter_path}")
    model = PeftModel.from_pretrained(model, str(adapter_path))

    # ── 병합 ──────────────────────────────────────────────────────────────────
    logger.info("어댑터 병합 중 (merge_and_unload)...")
    model = model.merge_and_unload()

    # ── 저장 (safetensors 포맷 — 분할 저장으로 피크 메모리 절감) ─────────────
    logger.info(f"병합 모델 저장: {output_path}")
    model.save_pretrained(str(output_path), safe_serialization=True, max_shard_size="2GB")
    tokenizer.save_pretrained(str(output_path))

    logger.info("병합 완료. 다음 단계: scripts/convert_to_gguf.sh 실행")
    logger.info(f"  bash scripts/convert_to_gguf.sh --merged {args.output_dir} --out_dir output/gguf --llama_cpp <경로>")


if __name__ == "__main__":
    main()
