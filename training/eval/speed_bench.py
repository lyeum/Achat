"""
speed_bench.py — GPU/CPU 추론 속도 벤치마크 (토큰/초)

사용법:
  # transformers 백엔드 (GPU)
  python training/eval/speed_bench.py --backend transformers --model Qwen/Qwen2.5-3B-Instruct

  # llama_cpp 백엔드 (CPU, GGUF 필요)
  python training/eval/speed_bench.py --backend llama_cpp --model_path models/model_q4km.gguf

  # LoRA 어댑터 포함
  python training/eval/speed_bench.py --backend transformers \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --adapter output/lora_haru_v1/adapter
"""

import argparse
import sys
import time
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

BENCH_PROMPTS = [
    "오늘 기분 어때?",
    "나 요즘 힘들어. 어떻게 하면 좋을까?",
    "주말에 뭐 하면 재밌을까? 추천해줘.",
    "저번에 내가 이직 고민한다고 했잖아. 어떻게 생각해?",
    "그냥 아무 말이나 해봐.",
]

SYSTEM_PROMPT = (
    "너는 캐릭터 '하루'다. "
    "반말을 사용한다. 단답형이 많다. "
    "AI 투 표현을 사용하지 않는다."
)

WARMUP_RUNS = 1
BENCH_RUNS = 3


# ─── transformers 백엔드 ──────────────────────────────────────────────────────

def bench_transformers(model_name: str, adapter_path: str | None, max_new_tokens: int) -> list[float]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info(f"[transformers] 모델 로드: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.bfloat16,
        trust_remote_code=True,
    ).to(device)
    if adapter_path:
        from peft import PeftModel
        logger.info(f"어댑터 로드: {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path, device_map={"": device})
    model.eval()

    tok_per_sec_list = []

    def run_one(prompt: str) -> float:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
            )
        elapsed = time.perf_counter() - t0
        n_new = output.shape[1] - inputs["input_ids"].shape[1]
        return n_new / elapsed if elapsed > 0 else 0.0

    # 워밍업
    for _ in range(WARMUP_RUNS):
        run_one(BENCH_PROMPTS[0])

    # 벤치마크
    for prompt in BENCH_PROMPTS[:BENCH_RUNS]:
        tps = run_one(prompt)
        tok_per_sec_list.append(tps)
        logger.info(f"  Q: {prompt[:30]}...  → {tps:.1f} tok/s")

    return tok_per_sec_list


# ─── llama_cpp 백엔드 ─────────────────────────────────────────────────────────

def bench_llama_cpp(model_path: str, max_new_tokens: int) -> list[float]:
    try:
        from llama_cpp import Llama
    except ImportError:
        logger.error("llama_cpp 미설치. pip install llama-cpp-python")
        return []

    logger.info(f"[llama_cpp] 모델 로드: {model_path}")
    llm = Llama(model_path=model_path, n_ctx=2048, verbose=False)

    tok_per_sec_list = []

    def run_one(prompt: str) -> float:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ]
        t0 = time.perf_counter()
        resp = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=0.0,
        )
        elapsed = time.perf_counter() - t0
        n_new = resp["usage"]["completion_tokens"]
        return n_new / elapsed if elapsed > 0 else 0.0

    for _ in range(WARMUP_RUNS):
        run_one(BENCH_PROMPTS[0])

    for prompt in BENCH_PROMPTS[:BENCH_RUNS]:
        tps = run_one(prompt)
        tok_per_sec_list.append(tps)
        logger.info(f"  Q: {prompt[:30]}...  → {tps:.1f} tok/s")

    return tok_per_sec_list


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="추론 속도 벤치마크")
    parser.add_argument("--backend",        choices=["transformers", "llama_cpp"], default="transformers")
    parser.add_argument("--model",          default="Qwen/Qwen2.5-3B-Instruct",  help="HF 모델명 (transformers)")
    parser.add_argument("--model_path",     default=None,                          help="GGUF 경로 (llama_cpp)")
    parser.add_argument("--adapter",        default=None,                          help="LoRA 어댑터 경로")
    parser.add_argument("--max_new_tokens", type=int, default=100)
    args = parser.parse_args()

    if args.backend == "transformers":
        adapter_full = None
        if args.adapter:
            p = Path(args.adapter)
            adapter_full = str(ROOT / p) if not p.is_absolute() else str(p)
        tps_list = bench_transformers(args.model, adapter_full, args.max_new_tokens)
    else:
        model_path = args.model_path or str(ROOT / "models/model_q4km.gguf")
        tps_list = bench_llama_cpp(model_path, args.max_new_tokens)

    if tps_list:
        avg = sum(tps_list) / len(tps_list)
        logger.info(f"\n{'='*40}")
        logger.info(f"벤치마크 결과 ({args.backend})")
        logger.info(f"  평균: {avg:.1f} tok/s")
        logger.info(f"  최소: {min(tps_list):.1f} tok/s")
        logger.info(f"  최대: {max(tps_list):.1f} tok/s")
        if args.backend == "llama_cpp":
            target = 8.0
            status = "✅ 목표 달성" if avg >= target else f"❌ 목표 미달 (목표: {target} tok/s)"
            logger.info(f"  배포 목표 ({target} tok/s): {status}")


if __name__ == "__main__":
    main()
