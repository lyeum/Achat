"""
train_monitor.py — 학습 과적합 모니터링 및 조기 종료

사용법:
  python training/train_monitor.py -- python -m training.lora_train \\
      --output_dir output/LoRA_v8 --epochs 5 --eval_split 0.1

  (또는 --cmd 로 전달)
  python training/train_monitor.py --cmd "python -m training.lora_train --output_dir output/LoRA_v8 --epochs 5"

출력:
  1) 학습 상황 (step / loss / eval_loss 실시간)
  2) 조기 종료 조건 (어떤 조건으로 멈췄는지)
  3) 최초 입력 명령어

종료 조건:
  - eval_loss 가 N_RISE 번 연속으로 상승
  - train/eval loss gap 이 GAP_THRESHOLD 초과
  - eval_loss 가 PLATEAU_N 번 연속 best 미개선 (plateau)
  중 하나라도 충족되면 SIGTERM → 프로세스 정상 종료 대기
"""

import argparse
import gc
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

# ─── 종료 조건 설정값 ────────────────────────────────────────────────────────

# eval_loss 가 연속으로 몇 번 오르면 종료할지
N_RISE = 3

# train / eval loss gap 이 이 값을 초과하면 즉시 종료
GAP_THRESHOLD = 1.2

# eval_loss 가 연속으로 몇 번 best 를 갱신하지 못하면 plateau 로 판단해 종료
# save_steps=50 기준: PLATEAU_N=5 → best 이후 250 스텝에서 종료
PLATEAU_N = 5

# trainer_state.json 폴링 간격 (초)
POLL_INTERVAL = 15

# 프로세스 종료 대기 최대 시간 (초)
# SIGTERM 후 lora_train이 어댑터를 저장하는 데 최대 ~90s 소요될 수 있으므로 여유 있게 설정
TERMINATE_TIMEOUT = 120

# ─── 유틸 ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent


def parse_output_dir(cmd_parts: list[str]) -> Path:
    """명령어에서 --output_dir 값을 추출. 없으면 lora_train.py 기본값 사용."""
    for i, part in enumerate(cmd_parts):
        if part == "--output_dir" and i + 1 < len(cmd_parts):
            p = Path(cmd_parts[i + 1])
            return p if p.is_absolute() else ROOT / p
    return ROOT / "output" / "LoRA_v7"


def find_latest_state(output_dir: Path) -> Path:
    """학습 중 최신 checkpoint의 trainer_state.json 경로를 반환.
    checkpoint가 없으면 학습 완료 후 루트에 저장된 경로를 반환."""
    checkpoints = sorted(
        output_dir.glob("checkpoint-*"),
        key=lambda p: int(p.name.split("-")[-1]) if p.name.split("-")[-1].isdigit() else 0,
    )
    for ckpt in reversed(checkpoints):
        state = ckpt / "trainer_state.json"
        if state.exists():
            return state
    return output_dir / "trainer_state.json"


def load_log_history(output_dir: Path) -> list[dict]:
    """최신 checkpoint의 trainer_state.json 에서 log_history 를 읽어 반환. 실패 시 빈 리스트."""
    state_path = find_latest_state(output_dir)
    try:
        with open(state_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("log_history", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def extract_metrics(log_history: list[dict]) -> tuple[list[float], list[float], list[float]]:
    """log_history 에서 (eval_steps, eval_losses, train_losses) 추출."""
    eval_steps: list[float] = []
    eval_losses: list[float] = []
    train_losses: list[float] = []

    for entry in log_history:
        if "eval_loss" in entry:
            eval_steps.append(entry.get("step", 0))
            eval_losses.append(entry["eval_loss"])
        if "loss" in entry and "eval_loss" not in entry:
            train_losses.append(entry["loss"])

    return eval_steps, eval_losses, train_losses


def check_overfitting(
    eval_losses: list[float],
    train_losses: list[float],
    n_rise: int = N_RISE,
    gap_threshold: float = GAP_THRESHOLD,
    plateau_n: int = PLATEAU_N,
) -> tuple[bool, str]:
    """
    과적합 여부 판단.
    Returns (should_stop, reason_message)
    """
    # 조건 1: eval_loss n_rise 번 연속 상승
    if len(eval_losses) >= n_rise + 1:
        recent = eval_losses[-(n_rise + 1):]
        if all(recent[i] < recent[i + 1] for i in range(n_rise)):
            best = min(eval_losses)
            current = eval_losses[-1]
            return True, (
                f"eval_loss {n_rise}회 연속 상승 "
                f"(best={best:.4f} → 현재={current:.4f})"
            )

    # 조건 2: train/eval loss gap 초과
    if train_losses and eval_losses:
        latest_train = train_losses[-1]
        latest_eval = eval_losses[-1]
        gap = latest_eval - latest_train
        if gap > gap_threshold:
            return True, (
                f"train/eval 손실 격차 초과 "
                f"(train={latest_train:.4f}, eval={latest_eval:.4f}, "
                f"gap={gap:.4f} > {gap_threshold})"
            )

    # 조건 3: plateau — plateau_n 번 연속 best 미갱신
    # train 이 eval 보다 훨씬 낮아졌는데 eval 이 더 이상 개선되지 않는 상태를 감지.
    # (조건 1·2가 걸리지 않는 "완만한 포화" 패턴 대응)
    if len(eval_losses) >= plateau_n + 1:
        best = min(eval_losses)
        recent = eval_losses[-plateau_n:]
        if all(loss > best for loss in recent):
            return True, (
                f"eval_loss plateau 감지 — {plateau_n}회 연속 best 미갱신 "
                f"(best={best:.4f}, 최근={recent[-1]:.4f})"
            )

    return False, ""


def release_vram() -> None:
    """현재 프로세스에서 torch VRAM 해제 시도 (subprocess 종료 후 잔여 정리용)."""
    try:
        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            free_gb = torch.cuda.mem_get_info()[0] / 1024**3
            logger.info(f"VRAM 정리 완료 — 여유 VRAM: {free_gb:.1f} GB")
    except ImportError:
        pass


# ─── 메인 ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="학습 모니터링 및 과적합 조기 종료",
        epilog="예) python training/train_monitor.py -- python -m training.lora_train --output_dir output/LoRA_v8 --epochs 5",
    )
    parser.add_argument(
        "--cmd",
        default=None,
        help="학습 명령어 문자열 (-- 뒤에 직접 전달해도 됨)",
    )
    parser.add_argument(
        "--n_rise",
        type=int,
        default=N_RISE,
        help=f"eval_loss 연속 상승 허용 횟수 (기본: {N_RISE})",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=GAP_THRESHOLD,
        help=f"train/eval loss gap 임계값 (기본: {GAP_THRESHOLD})",
    )
    parser.add_argument(
        "--poll",
        type=int,
        default=POLL_INTERVAL,
        help=f"폴링 간격 초 (기본: {POLL_INTERVAL})",
    )
    parser.add_argument(
        "--plateau_n",
        type=int,
        default=PLATEAU_N,
        help=f"eval_loss best 미갱신 연속 허용 횟수 (기본: {PLATEAU_N}, 0=비활성)",
    )
    parser.add_argument(
        "--skip_eval",
        action="store_true",
        help="학습 완료 후 자동 평가 건너뜀",
    )

    # '--' 이후의 인자를 학습 명령어로 취급
    argv = sys.argv[1:]
    if "--" in argv:
        sep_idx = argv.index("--")
        monitor_argv = argv[:sep_idx]
        cmd_parts = argv[sep_idx + 1:]
    else:
        monitor_argv = argv
        cmd_parts = []

    args = parser.parse_args(monitor_argv)

    # 학습 명령어 결정
    if cmd_parts:
        original_cmd = " ".join(cmd_parts)
    elif args.cmd:
        original_cmd = args.cmd
        cmd_parts = shlex.split(args.cmd)
    else:
        parser.error("학습 명령어를 -- 뒤에 전달하거나 --cmd 로 지정하세요.")

    n_rise = args.n_rise
    gap_threshold = args.gap
    plateau_n = args.plateau_n
    poll_interval = args.poll
    skip_eval = args.skip_eval

    output_dir = parse_output_dir(cmd_parts)

    logger.info("=" * 60)
    logger.info("학습 모니터 시작")
    logger.info(f"  명령어   : {original_cmd}")
    logger.info(f"  출력 경로: {output_dir}")
    logger.info(f"  종료 조건: eval_loss {n_rise}회 연속 상승  OR  gap > {gap_threshold}  OR  plateau {plateau_n}회")
    logger.info(f"  폴링 간격: {poll_interval}s")
    logger.info("=" * 60)

    # ── 학습 프로세스 시작 ────────────────────────────────────────────────────
    # train_monitor가 eval을 담당하므로 lora_train 내부 eval 실행을 억제한다.
    launch_cmd = list(cmd_parts)
    if "--skip_eval" not in launch_cmd:
        launch_cmd.append("--skip_eval")

    proc = subprocess.Popen(
        launch_cmd,
        cwd=str(ROOT),
        env={**os.environ},
    )

    stop_reason = "정상 완료"
    forced_stop = False

    # ── 폴링 루프 ─────────────────────────────────────────────────────────────
    try:
        while proc.poll() is None:
            time.sleep(poll_interval)

            log_history = load_log_history(output_dir)
            eval_steps, eval_losses, train_losses = extract_metrics(log_history)

            # 현재 상태 출력
            if eval_losses:
                best_eval = min(eval_losses)
                latest_eval = eval_losses[-1]
                latest_train = train_losses[-1] if train_losses else float("nan")
                gap = latest_eval - latest_train
                step = int(eval_steps[-1]) if eval_steps else 0
                logger.info(
                    f"[step {step:>5}] "
                    f"train={latest_train:.4f}  eval={latest_eval:.4f}  "
                    f"best_eval={best_eval:.4f}  gap={gap:+.4f}"
                )
            else:
                logger.info("trainer_state.json 대기 중 (첫 checkpoint 저장 전)...")

            # 과적합 검사
            should_stop, reason = check_overfitting(
                eval_losses,
                train_losses,
                n_rise=n_rise,
                gap_threshold=gap_threshold,
                plateau_n=plateau_n,
            )

            if should_stop:
                logger.warning(f"과적합 감지 → 학습 중단: {reason}")
                stop_reason = reason
                forced_stop = True
                proc.send_signal(signal.SIGTERM)
                try:
                    proc.wait(timeout=TERMINATE_TIMEOUT)
                    logger.info("학습 프로세스 정상 종료됨.")
                except subprocess.TimeoutExpired:
                    logger.warning("SIGTERM 후 타임아웃 — SIGKILL 전송")
                    proc.kill()
                    proc.wait()
                break

    except KeyboardInterrupt:
        logger.info("사용자 중단 (Ctrl+C) — 학습 프로세스 종료 중...")
        stop_reason = "사용자 수동 중단 (KeyboardInterrupt)"
        forced_stop = True
        proc.terminate()
        try:
            proc.wait(timeout=TERMINATE_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    # ── 정상 완료 대기 ────────────────────────────────────────────────────────
    if not forced_stop:
        exit_code = proc.wait()
        if exit_code != 0:
            stop_reason = f"학습 프로세스 비정상 종료 (exit code {exit_code})"

    # ── VRAM 정리 ─────────────────────────────────────────────────────────────
    logger.info("VRAM 정리 중...")
    release_vram()

    # ── 자동 평가 ─────────────────────────────────────────────────────────────
    # lora_train이 단독 실행(train_monitor 없이)되면 lora_train 내부에서 eval을 실행.
    # train_monitor를 통해 실행된 경우: 조기 종료/정상 완료 모두 여기서 eval을 담당.
    # lora_train에 --skip_eval을 전달해 중복 실행을 막는다.
    if not skip_eval:
        adapter_path = output_dir / "adapter"
        if adapter_path.exists():
            eval_dir = ROOT / "training" / "eval"
            eval_scripts = [
                (eval_dir / "ai_tell_checker.py", ["--adapter", str(adapter_path)]),
                (eval_dir / "memory_test.py",     ["--adapter", str(adapter_path)]),
                (eval_dir / "scenario_eval.py",   ["--adapter", str(adapter_path)]),
            ]
            logger.info("")
            logger.info("[ 자동 평가 시작 ]")
            for script, extra_args in eval_scripts:
                if not script.exists():
                    logger.warning(f"평가 스크립트 없음 — 건너뜀: {script.name}")
                    continue
                logger.info(f"  실행 중: {script.name}")
                result = subprocess.run(
                    [sys.executable, str(script)] + extra_args,
                    cwd=str(ROOT),
                )
                if result.returncode != 0:
                    logger.warning(f"  종료 코드 {result.returncode}: {script.name}")
                else:
                    logger.info(f"  완료: {script.name}")
        else:
            logger.warning(f"어댑터 없음 — 자동 평가 건너뜀: {adapter_path}")
    else:
        logger.info("--skip_eval: 자동 평가 건너뜀")

    # ── 최종 요약 ─────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=" * 60)
    logger.info("[ 모니터 최종 보고 ]")
    logger.info("")

    # (1) 학습 상황
    log_history = load_log_history(output_dir)
    eval_steps, eval_losses, train_losses = extract_metrics(log_history)
    if eval_losses:
        best_eval = min(eval_losses)
        best_step = int(eval_steps[eval_losses.index(best_eval)])
        latest_eval = eval_losses[-1]
        latest_train = train_losses[-1] if train_losses else float("nan")
        logger.info("① 학습 상황")
        logger.info(f"   eval 체크포인트 수 : {len(eval_losses)}")
        logger.info(f"   best eval_loss     : {best_eval:.4f}  (step {best_step})")
        logger.info(f"   최종 eval_loss     : {latest_eval:.4f}")
        logger.info(f"   최종 train_loss    : {latest_train:.4f}")
    else:
        logger.info("① 학습 상황: eval 기록 없음 (학습이 매우 짧게 진행됐거나 eval_split=0)")

    # (2) 종료 조건
    logger.info("")
    logger.info(f"② 종료 조건: {stop_reason}")

    # (3) 원본 명령어
    logger.info("")
    logger.info(f"③ 입력 명령어: {original_cmd}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
