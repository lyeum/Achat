"""
klue_regression.py — KLUE 벤치마크 회귀 테스트 (lm-evaluation-harness 래퍼)

파인튜닝 후 한국어 일반 언어 능력이 저하됐는지 확인.
작업: klue_ynat (뉴스 주제 분류 7-class) + klue_sts (문장 유사도)

사용법:
  # 베이스 모델 기준점 측정
  python training/eval/klue_regression.py --model Qwen/Qwen2.5-3B-Instruct --save_baseline

  # 어댑터 적용 후 측정 (기준점과 비교)
  python training/eval/klue_regression.py \\
    --model Qwen/Qwen2.5-3B-Instruct \\
    --adapter output/LoRA_v9/adapter \\
    --baseline training/eval/klue_baseline.json

  # 빠른 테스트 (소수 샘플)
  python training/eval/klue_regression.py --model Qwen/Qwen2.5-3B-Instruct --limit 50

사전 조건:
  pip install lm_eval   (또는 uv add lm-eval)
  lm_eval 패키지가 klue_ynat, klue_sts 태스크를 지원해야 합니다.
  (lm-eval 0.4+ 기준: lm_eval.tasks 에 klue 포함)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent.parent

KLUE_TASKS = ["klue_ynat", "klue_sts"]

# lm_eval 결과에서 추출할 지표 이름
METRIC_KEYS = {
    "klue_ynat": ["acc,none", "acc"],
    "klue_sts":  ["pearsonr,none", "pearsonr", "spearmanr,none", "spearmanr"],
}


def run_lm_eval(
    model_name: str,
    adapter_path: str | None,
    tasks: list[str],
    limit: int | None,
    output_path: Path,
) -> dict:
    """lm_eval CLI 를 subprocess 로 실행하고 결과 JSON 을 파싱."""
    cmd = [
        sys.executable, "-m", "lm_eval",
        "--model", "hf",
        "--model_args", f"pretrained={model_name},trust_remote_code=True" + (
            f",peft={adapter_path}" if adapter_path else ""
        ),
        "--tasks", ",".join(tasks),
        "--output_path", str(output_path),
        "--log_samples",
    ]

    if limit is not None:
        cmd += ["--limit", str(limit)]

    logger.info(f"lm_eval 실행: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode != 0:
        logger.error(f"lm_eval 종료 코드: {result.returncode}")
        return {}

    # lm_eval 은 output_path/*.json 으로 저장
    json_files = list(output_path.glob("results_*.json")) + list(output_path.glob("*.json"))
    if not json_files:
        logger.error("결과 JSON 파일을 찾을 수 없음")
        return {}

    latest = max(json_files, key=lambda p: p.stat().st_mtime)
    with open(latest, encoding="utf-8") as f:
        return json.load(f)


def extract_metrics(raw: dict) -> dict[str, float]:
    """lm_eval 결과에서 태스크별 주요 지표를 추출."""
    metrics: dict[str, float] = {}
    results = raw.get("results", {})

    for task, keys in METRIC_KEYS.items():
        task_data = results.get(task, {})
        for key in keys:
            if key in task_data:
                metrics[task] = round(float(task_data[key]), 4)
                break

    return metrics


def compare(current: dict[str, float], baseline: dict[str, float]) -> bool:
    """현재 지표와 기준점을 비교. 5% 이상 하락 시 WARN."""
    regression = False
    for task, cur_val in current.items():
        base_val = baseline.get(task)
        if base_val is None:
            logger.info(f"  {task}: {cur_val:.4f}  (기준점 없음)")
            continue

        diff = cur_val - base_val
        pct  = diff / base_val * 100 if base_val != 0 else 0.0
        sign = "+" if diff >= 0 else ""

        if pct < -5.0:
            logger.warning(f"  {task}: {cur_val:.4f}  (기준={base_val:.4f}, {sign}{pct:.1f}%)  ← REGRESSION")
            regression = True
        else:
            logger.info(f"  {task}: {cur_val:.4f}  (기준={base_val:.4f}, {sign}{pct:.1f}%)")

    return regression


def main() -> None:
    parser = argparse.ArgumentParser(description="KLUE 벤치마크 회귀 테스트")
    parser.add_argument("--model",         default="Qwen/Qwen2.5-3B-Instruct", help="베이스 모델 ID")
    parser.add_argument("--adapter",       default=None,  help="LoRA 어댑터 경로")
    parser.add_argument("--baseline",      default=None,  help="기준점 JSON 경로 (비교 시)")
    parser.add_argument("--save_baseline", action="store_true", help="측정 결과를 기준점으로 저장")
    parser.add_argument("--limit",         type=int, default=None, help="태스크당 평가 샘플 수 제한")
    parser.add_argument("--tasks",         nargs="+", default=KLUE_TASKS, help="평가할 lm_eval 태스크")
    parser.add_argument("--out_dir",       default="training/eval/klue_results", help="lm_eval 출력 디렉토리")
    args = parser.parse_args()

    # lm_eval 설치 여부 확인
    try:
        import lm_eval  # noqa: F401
    except ImportError:
        logger.error("lm_eval 패키지가 없습니다. 'pip install lm_eval' 후 재시도하세요.")
        sys.exit(1)

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    label = "adapter" if args.adapter else "base"
    run_output = out_dir / label
    run_output.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("KLUE 회귀 테스트 시작")
    logger.info(f"  모델   : {args.model}")
    logger.info(f"  어댑터 : {args.adapter or '없음 (베이스 모델)'}")
    logger.info(f"  태스크 : {args.tasks}")
    logger.info(f"  limit  : {args.limit or '전체'}")
    logger.info("=" * 60)

    raw = run_lm_eval(args.model, args.adapter, args.tasks, args.limit, run_output)
    if not raw:
        logger.error("lm_eval 실행 실패 — 결과 없음")
        sys.exit(1)

    current_metrics = extract_metrics(raw)
    if not current_metrics:
        logger.error("결과에서 지표 추출 실패")
        sys.exit(1)

    logger.info("")
    logger.info("[ 측정 결과 ]")

    has_regression = False
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            with open(baseline_path, encoding="utf-8") as f:
                baseline_metrics = json.load(f)
            has_regression = compare(current_metrics, baseline_metrics)
        else:
            logger.warning(f"기준점 파일 없음: {baseline_path}")
            for task, val in current_metrics.items():
                logger.info(f"  {task}: {val:.4f}")
    else:
        for task, val in current_metrics.items():
            logger.info(f"  {task}: {val:.4f}")

    if args.save_baseline:
        baseline_save_path = ROOT / "training" / "eval" / "klue_baseline.json"
        with open(baseline_save_path, "w", encoding="utf-8") as f:
            json.dump(current_metrics, f, ensure_ascii=False, indent=2)
        logger.info(f"기준점 저장: {baseline_save_path}")

    logger.info("=" * 60)
    if has_regression:
        logger.warning("KLUE 회귀 감지 — 일부 지표가 5% 이상 하락했습니다.")
        sys.exit(1)
    else:
        logger.info("KLUE 회귀 없음 — 정상 범위입니다.")
        sys.exit(0)


if __name__ == "__main__":
    main()
