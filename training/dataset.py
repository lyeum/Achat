"""
dataset.py — data/lora/ JSONL → HuggingFace Dataset (ChatML 포맷)

사용법 (직접 실행 시 데이터 검증):
  python training/dataset.py --data_dir data/lora --model Qwen/Qwen2.5-3B-Instruct

주요 기능:
  - data/lora/**/*.jsonl 재귀 로드
  - tokenizer.apply_chat_template으로 ChatML 포맷 변환
  - max_length 초과 샘플 필터링 (경고 출력)
  - conversation / function 혼합 로드
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional

from datasets import Dataset
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_MAX_LENGTH = 512


def load_jsonl_files(
    data_dir: Path,
    max_samples: int = -1,
    seed: int = 42,
    category_weights: dict[str, float] | None = None,
) -> list[dict]:
    """data_dir 하위 모든 .jsonl 파일을 재귀적으로 읽어 리스트 반환.

    max_samples > 0 이면 파일별 비율을 유지하는 stratified sampling 적용.
    category_weights 지정 시 카테고리별 과샘플/부샘플 적용 (max_samples 이후).
    """
    per_file: list[tuple[Path, list[dict]]] = []
    files = sorted(
        p for p in data_dir.rglob("*.jsonl")
        if "_excluded" not in p.parts
    )
    if not files:
        logger.warning(f"JSONL 파일 없음: {data_dir}")
        return []

    total = 0
    for path in files:
        file_records = []
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                try:
                    file_records.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(f"{path.name}:{lineno} JSON 파싱 실패: {e}")
        per_file.append((path, file_records))
        total += len(file_records)

    if max_samples > 0 and max_samples < total:
        rng = random.Random(seed)
        records = []
        for path, file_records in per_file:
            quota = max(1, round(max_samples * len(file_records) / total))
            sampled = rng.sample(file_records, min(quota, len(file_records)))
            try:
                display_path = path.relative_to(ROOT)
            except ValueError:
                display_path = path
            logger.debug(f"  로드: {display_path} ({len(file_records)}건 → {len(sampled)}건 샘플링)")
            records.extend(sampled)
        logger.info(f"총 {len(records)}건 로드 — stratified sampling {max_samples}건 기준 ({len(files)}개 파일)")
    else:
        records = []
        for path, file_records in per_file:
            try:
                display_path = path.relative_to(ROOT)
            except ValueError:
                display_path = path
            logger.debug(f"  로드: {display_path} ({len(file_records)}건)")
            records.extend(file_records)
        logger.info(f"총 {len(records)}건 로드 ({len(files)}개 파일)")

    # ── 카테고리 가중치 샘플링 ────────────────────────────────────────────────
    if category_weights:
        rng2 = random.Random(seed)
        # 카테고리 기준 그룹화
        groups: dict[str, list[dict]] = {}
        for rec in records:
            cat = rec.get("category", "__none__")
            groups.setdefault(cat, []).append(rec)

        resampled: list[dict] = []
        for cat, cat_records in groups.items():
            w = category_weights.get(cat, 1.0)
            if w == 1.0:
                resampled.extend(cat_records)
            elif w > 1.0:
                n_target    = round(len(cat_records) * w)
                full_copies = n_target // len(cat_records)
                remainder   = n_target % len(cat_records)
                result = cat_records * full_copies + rng2.sample(cat_records, remainder)
                logger.debug(f"  카테고리 '{cat}': {len(cat_records)}건 × {w} → {len(result)}건 (오버샘플)")
                resampled.extend(result)
            else:  # w < 1.0
                n_target = max(1, round(len(cat_records) * w))
                result   = rng2.sample(cat_records, n_target)
                logger.debug(f"  카테고리 '{cat}': {len(cat_records)}건 × {w} → {len(result)}건 (언더샘플)")
                resampled.extend(result)

        rng2.shuffle(resampled)
        logger.info(f"카테고리 가중치 적용 후: {len(resampled)}건 (원본 {len(records)}건)")
        records = resampled

    return records


def apply_chat_template(records: list[dict], tokenizer, max_length: int) -> tuple[list[str], int]:
    """
    각 레코드의 messages 필드에 tokenizer.apply_chat_template 적용.
    max_length 초과 샘플은 제외하고 경고 출력.
    (text 리스트, 필터된 수) 반환.
    """
    texts = []
    filtered = 0

    for i, record in enumerate(records):
        messages = record.get("messages", [])
        if not messages:
            filtered += 1
            continue
        try:
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )
        except Exception as e:
            logger.warning(f"레코드 {i} apply_chat_template 실패: {e} — 스킵")
            filtered += 1
            continue

        token_ids = tokenizer.encode(text, add_special_tokens=False)
        if len(token_ids) > max_length:
            logger.warning(
                f"레코드 {i} 토큰 수 {len(token_ids)} > {max_length} "
                f"(category={record.get('category', '?')}) — 필터"
            )
            filtered += 1
            continue

        texts.append(text)

    return texts, filtered


def load_training_data(
    data_dir: str,
    tokenizer,
    max_length: int = DEFAULT_MAX_LENGTH,
    subset: Optional[str] = None,
    max_samples: int = -1,
    category_weights: dict[str, float] | None = None,
) -> Dataset:
    """
    data_dir 하위 JSONL → HuggingFace Dataset 반환.

    Args:
        data_dir: 데이터 루트 디렉토리 (예: "data/lora" 또는 "data/lora/conversation")
        tokenizer: HuggingFace tokenizer (apply_chat_template 지원)
        max_length: 최대 토큰 수. 초과 샘플 필터링.
        subset: "conversation" | "function" | None(전체)
        max_samples: 파일별 비율 유지 stratified sampling (-1=전체)
        category_weights: 카테고리별 가중치 (예: {"emotion": 2.0, "long_dialogue": 1.5})
    """
    base = ROOT / data_dir
    if subset:
        base = base / subset

    records = load_jsonl_files(base, max_samples=max_samples, category_weights=category_weights)
    if not records:
        raise ValueError(f"로드된 데이터 없음: {base}")

    texts, filtered = apply_chat_template(records, tokenizer, max_length)
    logger.info(f"최종 샘플 수: {len(texts)} (필터: {filtered}건)")

    return Dataset.from_dict({"text": texts})


# ─── 직접 실행 시 데이터 검증 ────────────────────────────────────────────────

def _validate_without_tokenizer(data_dir: Path):
    """토크나이저 없이 JSONL 구조 검증만 수행."""
    records = load_jsonl_files(data_dir)
    if not records:
        return

    issues = 0
    for i, r in enumerate(records):
        messages = r.get("messages", [])
        if not messages:
            logger.warning(f"레코드 {i}: messages 없음")
            issues += 1
            continue
        roles = [m.get("role") for m in messages]
        non_sys = [ro for ro in roles if ro != "system"]
        if len(non_sys) < 2:
            logger.warning(f"레코드 {i}: user/assistant 턴 부족 ({non_sys})")
            issues += 1
    logger.info(f"구조 검증 완료 — {len(records)}건 중 {issues}건 이슈")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="데이터셋 검증 / 미리보기")
    parser.add_argument("--data_dir", default="data/lora", help="데이터 루트 디렉토리")
    parser.add_argument("--model",    default=None,        help="HF 모델명 (토크나이저 적용 검증용)")
    parser.add_argument("--max_length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--subset",   default=None,        help="conversation | function")
    args = parser.parse_args()

    data_path = ROOT / args.data_dir
    if args.subset:
        data_path = data_path / args.subset

    if args.model:
        from transformers import AutoTokenizer
        logger.info(f"토크나이저 로드: {args.model}")
        tok = AutoTokenizer.from_pretrained(args.model)
        ds = load_training_data(args.data_dir, tok, args.max_length, args.subset)
        logger.info(f"Dataset: {ds}")
        if len(ds) > 0:
            logger.info(f"샘플 미리보기:\n{ds[0]['text'][:300]}...")
    else:
        _validate_without_tokenizer(data_path)
