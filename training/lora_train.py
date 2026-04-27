"""
lora_train.py — PeFT LoRA 파인튜닝 스크립트

사용법:
  # GPU 전체 학습
  python training/lora_train.py \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --data_dir training/data \\
    --output_dir output/LoRA_v7 \\
    --epochs 6

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
import signal
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

# ── SIGTERM 핸들러 ─────────────────────────────────────────────────────────────
# train_monitor가 과적합 감지 시 SIGTERM을 전송한다.
# 기본 핸들러는 finally 블록 없이 즉시 종료하므로 어댑터 저장이 누락된다.
# SystemExit을 발생시켜 finally 블록이 실행되도록 한다.

_sigterm_received = False


def _handle_sigterm(signum, frame):
    global _sigterm_received
    _sigterm_received = True
    raise SystemExit(0)


signal.signal(signal.SIGTERM, _handle_sigterm)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from training.dataset import load_training_data


def parse_args():
    parser = argparse.ArgumentParser(description="LoRA 파인튜닝")
    parser.add_argument("--model",       default="Qwen/Qwen2.5-3B-Instruct", help="HuggingFace 모델명")
    parser.add_argument("--data_dir",    default="training/data",             help="학습 데이터 루트")
    parser.add_argument("--output_dir",  default="output/LoRA_v7",              help="어댑터 저장 디렉토리 (output/ 하위 경로)")
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
    parser.add_argument("--save_steps",  type=int,   default=50)
    parser.add_argument("--logging_steps", type=int, default=10)
    parser.add_argument("--eval_split",  type=float, default=0.1,             help="validation 비율 (0이면 eval 비활성)")
    parser.add_argument("--max_samples", type=int,   default=-1,              help="학습에 사용할 최대 샘플 수 (-1=전체)")
    # 저장 및 테스트 옵션
    parser.add_argument("--no_save",     action="store_true", help="학습 후 어댑터 저장 건너뜀 (테스트용)")
    parser.add_argument("--max_steps",   type=int,   default=-1, help="최대 학습 스텝 수 (-1=에폭 기준)")
    parser.add_argument("--skip_eval",   action="store_true", help="학습 후 자동 평가 건너뜀")
    # EWC
    parser.add_argument("--ewc_fisher",     default=None,  help="fisher.pt 경로 (EWC 활성화 시 필수)")
    parser.add_argument("--ewc_ref_params", default=None,  help="ref_params.pt 경로 (EWC 활성화 시 필수)")
    parser.add_argument("--ewc_lambda",     type=float, default=0.0, help="EWC 강도 (0이면 비활성)")
    # 카테고리 가중치
    parser.add_argument("--category_weights", default=None,
                        help='카테고리별 가중치 JSON 문자열 (예: \'{"emotion": 2.0, "long_dialogue": 1.5}\')')
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


class EWCTrainer(Trainer):
    """EWC 패널티를 compute_loss에 추가하는 Trainer 서브클래스."""

    def __init__(self, ewc_penalty=None, **kwargs):
        super().__init__(**kwargs)
        self.ewc_penalty = ewc_penalty

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        result = super().compute_loss(model, inputs, return_outputs=True, **kwargs)
        loss, outputs = result
        if self.ewc_penalty is not None:
            loss = loss + self.ewc_penalty.penalty(model)
        return (loss, outputs) if return_outputs else loss


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
    # assistant 응답 구간만 loss 계산 — 시스템·유저 토큰은 -100 마스킹
    # Qwen2.5 ChatML: <|im_start|>assistant\n ... <|im_end|>
    _asst_start = tokenizer.encode("<|im_start|>assistant\n", add_special_tokens=False)
    _im_end_id  = tokenizer.encode("<|im_end|>", add_special_tokens=False)[0]
    _s = len(_asst_start)

    def _mask_labels(ids: list[int]) -> list[int]:
        """assistant 응답 구간(im_end 포함)만 labels 활성화, 나머지는 -100."""
        labels = [-100] * len(ids)
        i = 0
        while i < len(ids):
            if ids[i : i + _s] == _asst_start:
                i += _s  # <|im_start|>assistant\n 건너뜀
                while i < len(ids):
                    labels[i] = ids[i]
                    if ids[i] == _im_end_id:
                        i += 1
                        break
                    i += 1
            else:
                i += 1
        return labels

    def tokenize(examples):
        result = tokenizer(
            examples["text"],
            truncation=True,
            max_length=max_length,
            padding=False,
        )
        result["labels"] = [_mask_labels(ids) for ids in result["input_ids"]]
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

    # ── EWC 패널티 ────────────────────────────────────────────────────────────
    ewc_penalty = None
    if args.ewc_lambda > 0:
        assert args.ewc_fisher and args.ewc_ref_params, \
            "--ewc_lambda > 0 이면 --ewc_fisher, --ewc_ref_params 필수"
        from training.ewc import EWCPenalty
        ewc_penalty = EWCPenalty(
            fisher_path=ROOT / args.ewc_fisher,
            ref_params_path=ROOT / args.ewc_ref_params,
            lambda_=args.ewc_lambda,
            device="cuda" if use_gpu else "cpu",
        )
        logger.info(f"EWC 활성화: lambda={args.ewc_lambda}")

    # ── 카테고리 가중치 ────────────────────────────────────────────────────────
    import json as _json
    category_weights = _json.loads(args.category_weights) if args.category_weights else None
    if category_weights:
        logger.info(f"카테고리 가중치: {category_weights}")

    # ── 데이터셋 ───────────────────────────────────────────────────────────────
    logger.info(f"데이터 로드: {args.data_dir} (subset={args.subset})")
    raw_ds = load_training_data(
        args.data_dir, tokenizer, args.max_length, args.subset,
        args.max_samples, category_weights=category_weights,
    )
    tokenized_ds = tokenize_dataset(raw_ds, tokenizer, args.max_length)
    logger.info(f"최종 학습 샘플 수: {len(tokenized_ds)}")

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
    trainer = EWCTrainer(
        ewc_penalty=ewc_penalty,
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        processing_class=tokenizer,
        callbacks=[LossPlotCallback(output_dir)],
    )

    logger.info("학습 시작")
    early_stopped = False
    try:
        trainer.train()
    except SystemExit:
        if _sigterm_received:
            logger.warning("SIGTERM 수신 — 조기 종료. 어댑터 저장 후 종료합니다.")
            early_stopped = True
        else:
            raise
    except KeyboardInterrupt:
        logger.warning("KeyboardInterrupt — 조기 종료. 어댑터 저장 후 종료합니다.")
        early_stopped = True

    # 학습 결과 요약
    log = trainer.state.log_history
    train_losses = [e["loss"] for e in log if "loss" in e]
    if train_losses:
        logger.info(f"최종 학습 loss: {train_losses[-1]:.4f}")

    # ── 어댑터 저장 (정상 완료 + 조기 종료 모두) ──────────────────────────────
    adapter_path = None
    if args.no_save:
        logger.info("--no_save: 어댑터 저장 건너뜀")
    else:
        adapter_path = output_dir / "adapter"
        try:
            # best checkpoint가 load_best_model_at_end=True로 이미 로드됐거나,
            # 조기 종료 시 현재 상태를 저장한다.
            trainer.save_state()
            model.save_pretrained(str(adapter_path))
            tokenizer.save_pretrained(str(adapter_path))
            logger.info(f"어댑터 저장 완료: {adapter_path}")
        except Exception as e:
            logger.error(f"어댑터 저장 실패: {e}")
            adapter_path = None

        # ── 체크포인트 정리 ────────────────────────────────────────────────────
        import shutil
        for ckpt in sorted(output_dir.glob("checkpoint-*")):
            shutil.rmtree(ckpt)
            logger.info(f"체크포인트 삭제: {ckpt.name}")

    # ── 조기 종료 시: 어댑터만 저장하고 즉시 종료 ────────────────────────────
    # eval은 train_monitor.py가 프로세스 종료 후 실행한다.
    if early_stopped:
        logger.info("조기 종료 완료. train_monitor가 eval을 실행합니다.")
        sys.exit(0)

    # ── 정상 완료 시: eval 실행 (train_monitor 없이 단독 실행한 경우) ──────────
    if args.skip_eval or adapter_path is None:
        if args.skip_eval:
            logger.info("--skip_eval: 자동 평가 건너뜀")
        return

    import gc
    import subprocess

    logger.info("VRAM 해제 중 — 학습 모델 언로드")
    trainer.model = None
    del trainer
    del model
    del tokenizer
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        free_gb = torch.cuda.mem_get_info()[0] / 1024**3
        logger.info(f"VRAM 해제 완료 — 여유 VRAM: {free_gb:.1f} GB")

    eval_dir = ROOT / "training" / "eval"
    eval_scripts = [
        (eval_dir / "ai_tell_checker.py", ["--adapter", str(adapter_path)]),
        (eval_dir / "memory_test.py",     ["--adapter", str(adapter_path)]),
        (eval_dir / "scenario_eval.py",   ["--adapter", str(adapter_path)]),
    ]
    for script, extra_args in eval_scripts:
        if not script.exists():
            logger.warning(f"평가 스크립트 없음 — 건너뜀: {script}")
            continue
        logger.info(f"자동 평가 실행: {script.name}")
        result = subprocess.run([sys.executable, str(script)] + extra_args)
        if result.returncode != 0:
            logger.warning(f"평가 종료 코드 {result.returncode}: {script.name}")


if __name__ == "__main__":
    main()
