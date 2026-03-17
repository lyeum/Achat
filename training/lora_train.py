"""
lora_train.py — PeFT LoRA 파인튜닝 스크립트

사용법:
  # GPU 전체 학습
  python training/lora_train.py \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --data_dir data/lora \\
    --output_dir output/lora_haru_v1 \\
    --epochs 3

  # CPU 파이프라인 테스트 (저장 없이 5스텝만)
  python training/lora_train.py \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --data_dir training/data \\
    --no_save --max_steps 5 --max_length 128

디바이스 자동 선택:
  - CUDA 사용 가능: bfloat16 + device_map="auto" + gradient_checkpointing
  - CPU 전용:       float32 + device_map="cpu"  + gradient_checkpointing 비활성

주의 (RTX 5060 / Blackwell SM 10.x):
  - bitsandbytes 4-bit 양자화 미지원 → BitsAndBytesConfig 미사용
  - bfloat16 풀 파라미터 + LoRA 방식 사용 (VRAM ~10GB)
  - OOM 시: --max_length 256 또는 --grad_accum 16
"""

import argparse
import sys
from pathlib import Path

import torch
from loguru import logger
from peft import LoraConfig, TaskType, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training.dataset import load_training_data


def parse_args():
    parser = argparse.ArgumentParser(description="LoRA 파인튜닝")
    parser.add_argument("--model",       default="Qwen/Qwen2.5-3B-Instruct", help="HuggingFace 모델명")
    parser.add_argument("--data_dir",    default="data/lora",                 help="학습 데이터 루트")
    parser.add_argument("--output_dir",  default="output/lora_v1",            help="어댑터 저장 디렉토리")
    parser.add_argument("--subset",      default=None,                        help="conversation | function | None(전체)")
    parser.add_argument("--epochs",      type=int,   default=3)
    parser.add_argument("--batch_size",  type=int,   default=1)
    parser.add_argument("--grad_accum",  type=int,   default=8)
    parser.add_argument("--lr",          type=float, default=2e-4)
    parser.add_argument("--max_length",  type=int,   default=512)
    parser.add_argument("--lora_r",      type=int,   default=16)
    parser.add_argument("--lora_alpha",  type=int,   default=32)
    parser.add_argument("--lora_dropout", type=float, default=0.05)
    parser.add_argument("--weight_decay", type=float, default=0.0,            help="L2 정규화 (0.01 권장)")
    parser.add_argument("--save_steps",  type=int,   default=100)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--eval_split",  type=float, default=0.1,             help="validation 비율 (0이면 eval 비활성)")
    parser.add_argument("--max_samples", type=int,   default=-1,              help="학습에 사용할 최대 샘플 수 (-1=전체)")
    # 저장 및 테스트 옵션
    parser.add_argument("--no_save",     action="store_true", help="학습 후 어댑터 저장 건너뜀 (테스트용)")
    parser.add_argument("--max_steps",   type=int,   default=-1, help="최대 학습 스텝 수 (-1=에폭 기준)")
    return parser.parse_args()


def load_model_and_tokenizer(model_name: str, use_gpu: bool):
    logger.info(f"모델 로드: {model_name} ({'GPU bfloat16' if use_gpu else 'CPU float32'})")

    if not use_gpu:
        # 3B float32 ≈ 12GB RAM. 메모리 부족 시 1.5B 모델 또는 --max_length 128 권장
        logger.warning("CPU 모드: Qwen2.5-3B float32 로드에 RAM ~12GB 필요. 부족 시 OOM 발생.")

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype      = torch.bfloat16 if use_gpu else torch.float32
    device_map = "auto"         if use_gpu else "cpu"

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=dtype,
        trust_remote_code=True,
        device_map=device_map,
    )
    model.config.use_cache = False  # gradient checkpointing과 호환
    model.enable_input_require_grads()

    return model, tokenizer


def plot_loss(log_history: list, output_dir: Path, tag: str = "") -> None:
    """train loss / eval loss 그래프를 PNG로 저장."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib 미설치 — 그래프 생략 (pip install matplotlib)")
        return

    train_steps = [log["step"] for log in log_history if "loss" in log and "eval_loss" not in log]
    train_loss  = [log["loss"] for log in log_history if "loss" in log and "eval_loss" not in log]
    eval_steps  = [log["step"] for log in log_history if "eval_loss" in log]
    eval_loss   = [log["eval_loss"] for log in log_history if "eval_loss" in log]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(train_steps, train_loss, label="train loss", color="steelblue", linewidth=1.5)
    if eval_loss:
        ax.plot(eval_steps, eval_loss, label="eval loss", color="tomato",
                linewidth=1.5, marker="o", markersize=4)
        best_idx = eval_loss.index(min(eval_loss))
        ax.axvline(eval_steps[best_idx], color="tomato", linestyle="--", alpha=0.5,
                   label=f"best eval {min(eval_loss):.4f} (step {eval_steps[best_idx]})")

    ax.set_xlabel("step")
    ax.set_ylabel("loss")
    ax.set_title(f"LoRA Training Loss{' — ' + tag if tag else ''}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    fname = output_dir / f"loss_curve{'_' + tag if tag else ''}.png"
    fig.savefig(fname, dpi=120, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"그래프 저장: {fname}")


class LossPlotCallback(TrainerCallback):
    """epoch 종료 및 학습 전체 종료 시 loss 그래프 저장."""

    def __init__(self, output_dir: Path):
        self._output_dir = output_dir
        self._last_epoch = 0

    def on_epoch_end(self, args, state, control, **kwargs):
        epoch = int(state.epoch)
        if epoch == self._last_epoch:
            return
        self._last_epoch = epoch
        plot_loss(state.log_history, self._output_dir, tag=f"epoch{epoch:02d}")

    def on_train_end(self, args, state, control, **kwargs):
        plot_loss(state.log_history, self._output_dir, tag="final")


def apply_lora(model, args) -> object:
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        inference_mode=False,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


def tokenize_dataset(dataset, tokenizer, max_length: int):
    def tokenize(examples):
        result = tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )
        result["labels"] = result["input_ids"].copy()
        return result

    return dataset.map(
        tokenize,
        batched=True,
        remove_columns=["text"],
        desc="토크나이징",
    )


def main():
    args = parse_args()
    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 디바이스 감지 ──────────────────────────────────────────────────────────
    use_gpu = torch.cuda.is_available()
    logger.info(f"디바이스: {'GPU (' + torch.cuda.get_device_name(0) + ')' if use_gpu else 'CPU'}")

    # ── 모델 & 토크나이저 ──────────────────────────────────────────────────────
    model, tokenizer = load_model_and_tokenizer(args.model, use_gpu)
    model = apply_lora(model, args)

    # ── 데이터셋 ───────────────────────────────────────────────────────────────
    logger.info(f"데이터 로드: {args.data_dir} (subset={args.subset})")
    raw_ds = load_training_data(args.data_dir, tokenizer, args.max_length, args.subset)
    tokenized_ds = tokenize_dataset(raw_ds, tokenizer, args.max_length)
    if args.max_samples > 0 and args.max_samples < len(tokenized_ds):
        tokenized_ds = tokenized_ds.shuffle(seed=42).select(range(args.max_samples))
        logger.info(f"샘플링 적용: {len(tokenized_ds)}건 사용 (--max_samples {args.max_samples})")
    else:
        logger.info(f"전체 샘플 수: {len(tokenized_ds)}")

    # ── Train / Eval 분리 ─────────────────────────────────────────────────────
    use_eval = args.eval_split > 0 and not args.no_save
    if use_eval:
        split = tokenized_ds.train_test_split(test_size=args.eval_split, seed=42)
        train_ds = split["train"]
        eval_ds  = split["test"]
        logger.info(f"학습: {len(train_ds)}건 / 검증: {len(eval_ds)}건 (eval_split={args.eval_split})")
    else:
        train_ds = tokenized_ds
        eval_ds  = None
        logger.info(f"학습 샘플 수: {len(train_ds)} (eval 비활성)")

    # ── TrainingArguments ──────────────────────────────────────────────────────
    use_bf16 = use_gpu and torch.cuda.is_bf16_supported()
    use_gc   = use_gpu

    effective_total = args.max_steps if args.max_steps > 0 else (
        (len(train_ds) // (args.batch_size * args.grad_accum) + 1) * args.epochs
    )
    warmup_steps = max(1, int(effective_total * 0.05))

    logger.info(
        f"학습 설정: bf16={use_bf16}, gradient_checkpointing={use_gc}, "
        f"max_steps={args.max_steps if args.max_steps > 0 else '(에폭 기준)'}, "
        f"no_save={args.no_save}, best_model={use_eval}"
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        bf16=use_bf16,
        fp16=False,
        gradient_checkpointing=use_gc,
        gradient_checkpointing_kwargs={"use_reentrant": False} if use_gc else {},
        logging_steps=args.logging_steps,
        save_steps=args.save_steps if not args.no_save else 999999,
        save_total_limit=3 if not args.no_save else 0,
        optim="adamw_torch",
        weight_decay=args.weight_decay,
        warmup_steps=warmup_steps,
        lr_scheduler_type="cosine",
        report_to="none",
        dataloader_num_workers=0,
        dataloader_pin_memory=use_gpu,
        remove_unused_columns=False,
        # ── Best model 저장 (eval_split > 0 일 때만) ─────────────────────────
        eval_strategy="steps" if use_eval else "no",
        eval_steps=args.save_steps if use_eval else None,
        load_best_model_at_end=use_eval,
        metric_for_best_model="loss" if use_eval else None,
        greater_is_better=False if use_eval else None,
    )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model,
        padding=True,
        pad_to_multiple_of=8,
        label_pad_token_id=-100,
    )

    # ── Trainer ────────────────────────────────────────────────────────────────
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        processing_class=tokenizer,
        callbacks=[LossPlotCallback(output_dir)],
    )

    logger.info("학습 시작")
    trainer.train()

    # 학습 결과 요약
    log = trainer.state.log_history
    train_losses = [e["loss"] for e in log if "loss" in e]
    if train_losses:
        logger.info(f"최종 학습 loss: {train_losses[-1]:.4f}")

    # ── 어댑터 저장 ────────────────────────────────────────────────────────────
    if args.no_save:
        logger.info("--no_save: 어댑터 저장 건너뜀")
    else:
        adapter_path = output_dir / "adapter"
        model.save_pretrained(str(adapter_path))
        tokenizer.save_pretrained(str(adapter_path))
        logger.info(f"어댑터 저장 완료: {adapter_path}")


if __name__ == "__main__":
    main()
