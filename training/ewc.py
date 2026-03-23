"""
ewc.py — Elastic Weight Consolidation (EWC) for continual LoRA fine-tuning

사용법 (Fisher 계산):
  uv run python training/ewc.py \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --adapter output/LoRA_v7/adapter \\
    --data_dir training/data \\
    --out output/LoRA_v7 \\
    --n_samples 500

출력:
  {out}/fisher.pt     — Fisher 대각 행렬 {param_name: Tensor}
  {out}/ref_params.pt — 기준 가중치      {param_name: Tensor}

EWCPenalty 사용법 (lora_train.py 등):
  from training.ewc import EWCPenalty
  ewc = EWCPenalty("output/LoRA_v7/fisher.pt", "output/LoRA_v7/ref_params.pt",
                   lambda_=0.5, device="cuda")
  loss = cross_entropy_loss + ewc.penalty(model)
"""

import argparse
import sys
from pathlib import Path

import torch
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ─── EWCPenalty ──────────────────────────────────────────────────────────────

class EWCPenalty:
    """학습 중 EWC 패널티를 계산하는 클래스.

    Args:
        fisher_path:     compute_fisher로 생성한 fisher.pt 경로
        ref_params_path: compute_fisher로 생성한 ref_params.pt 경로
        lambda_:         EWC 강도 (클수록 이전 태스크 보존 강조)
        device:          "cuda" | "cpu"
    """

    def __init__(
        self,
        fisher_path: str | Path,
        ref_params_path: str | Path,
        lambda_: float,
        device: str = "cpu",
    ):
        self.lambda_ = lambda_
        self.fisher = {
            k: v.to(device)
            for k, v in torch.load(fisher_path, map_location=device, weights_only=True).items()
        }
        self.ref_params = {
            k: v.to(device)
            for k, v in torch.load(ref_params_path, map_location=device, weights_only=True).items()
        }
        logger.info(
            f"EWCPenalty 로드: fisher {len(self.fisher)}개 파라미터, lambda={lambda_}"
        )

    def penalty(self, model) -> torch.Tensor:
        """현재 model 파라미터와 기준 가중치의 Fisher 가중 거리를 반환."""
        loss = torch.tensor(0.0, device=next(model.parameters()).device)
        for name, param in model.named_parameters():
            if not param.requires_grad:
                continue
            if name not in self.fisher:
                continue
            f   = self.fisher[name]
            ref = self.ref_params[name]
            loss = loss + (f * (param.float() - ref.float()).pow(2)).sum()
        return (self.lambda_ / 2) * loss


# ─── Fisher 계산 ─────────────────────────────────────────────────────────────

def compute_fisher(
    model_name: str,
    adapter_path: str | Path,
    data_dir: str | Path,
    out_dir: str | Path,
    n_samples: int = 500,
    max_length: int = 512,
    seed: int = 42,
) -> None:
    """LoRA 파라미터의 Fisher 대각 행렬과 기준 가중치를 계산해 저장.

    Args:
        model_name:   HuggingFace 기반 모델명
        adapter_path: 기학습된 LoRA 어댑터 경로
        data_dir:     JSONL 학습 데이터 루트
        out_dir:      fisher.pt / ref_params.pt 저장 디렉토리
        n_samples:    Fisher 추정에 사용할 샘플 수
        max_length:   최대 토큰 길이
        seed:         랜덤 시드
    """
    import random

    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from training.dataset import load_jsonl_files

    adapter_path = Path(adapter_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    use_gpu = torch.cuda.is_available()
    device  = "cuda" if use_gpu else "cpu"
    dtype   = torch.bfloat16 if use_gpu else torch.float32

    # ── 모델 로드 ─────────────────────────────────────────────────────────────
    logger.info(f"베이스 모델 로드: {model_name} ({dtype})")
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=dtype,
        trust_remote_code=True,
        device_map=device,
    )
    base_model.config.use_cache = False

    logger.info(f"어댑터 로드: {adapter_path}")
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    model.eval()

    # ── 파라미터 설정 ─────────────────────────────────────────────────────────
    # LoRA 파라미터만 Fisher 계산 대상
    for name, param in model.named_parameters():
        param.requires_grad = "lora_" in name

    lora_params = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    logger.info(f"LoRA 파라미터 수: {len(lora_params)}")

    # 기준 가중치 저장
    ref_params = {n: p.data.clone().cpu() for n, p in lora_params}

    # ── 데이터 샘플링 ─────────────────────────────────────────────────────────
    records = load_jsonl_files(Path(data_dir), max_samples=-1, seed=seed)
    if not records:
        raise ValueError(f"데이터 없음: {data_dir}")

    rng = random.Random(seed)
    if len(records) > n_samples:
        records = rng.sample(records, n_samples)
    logger.info(f"Fisher 계산용 샘플: {len(records)}건")

    # ── Fisher 누적 ───────────────────────────────────────────────────────────
    fisher_accum = {n: torch.zeros_like(p.data, device=device) for n, p in lora_params}
    n_processed = 0

    for i, record in enumerate(records):
        messages = record.get("messages", [])
        if not messages:
            continue
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
            inputs = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length,
            ).to(device)
        except Exception as e:
            logger.warning(f"샘플 {i} 토크나이징 실패: {e} — 스킵")
            continue

        try:
            model.zero_grad()
            outputs = model(**inputs, labels=inputs["input_ids"])
            loss = outputs.loss
            loss.backward()
        except Exception as e:
            logger.warning(f"샘플 {i} forward/backward 실패: {e} — 스킵")
            model.zero_grad()
            continue

        for name, param in lora_params:
            if param.grad is not None:
                fisher_accum[name] += param.grad.detach().pow(2)

        n_processed += 1
        if (i + 1) % 50 == 0:
            logger.info(f"  진행: {i + 1}/{len(records)} (처리됨: {n_processed})")

    if n_processed == 0:
        raise RuntimeError("처리된 샘플이 없습니다. 데이터/모델을 확인하세요.")

    # 평균 Fisher
    fisher = {n: (v / n_processed).cpu() for n, v in fisher_accum.items()}
    logger.info(f"Fisher 계산 완료 — {n_processed}건 처리")

    # ── 저장 ─────────────────────────────────────────────────────────────────
    fisher_path     = out_dir / "fisher.pt"
    ref_params_path = out_dir / "ref_params.pt"
    torch.save(fisher, fisher_path)
    torch.save(ref_params, ref_params_path)
    logger.info(f"저장: {fisher_path}")
    logger.info(f"저장: {ref_params_path}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EWC Fisher 대각 계산")
    parser.add_argument("--model",      default="Qwen/Qwen2.5-3B-Instruct", help="HF 기반 모델명")
    parser.add_argument("--adapter",    required=True,                       help="LoRA 어댑터 경로")
    parser.add_argument("--data_dir",   default="training/data",             help="JSONL 데이터 루트")
    parser.add_argument("--out",        required=True,                       help="fisher.pt / ref_params.pt 저장 디렉토리")
    parser.add_argument("--n_samples",  type=int, default=500,               help="Fisher 추정 샘플 수")
    parser.add_argument("--max_length", type=int, default=512)
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    compute_fisher(
        model_name=args.model,
        adapter_path=ROOT / args.adapter,
        data_dir=ROOT / args.data_dir,
        out_dir=ROOT / args.out,
        n_samples=args.n_samples,
        max_length=args.max_length,
        seed=args.seed,
    )
