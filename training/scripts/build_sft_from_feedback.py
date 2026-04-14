"""
build_sft_from_feedback.py — feedback_pos 로그 → SFT 학습 데이터 변환

사용법:
  uv run python training/scripts/build_sft_from_feedback.py
  uv run python training/scripts/build_sft_from_feedback.py --reviewed_only

동작:
  1. training/log/feedback_pos/*.jsonl 전체 로드
  2. character_id + affection 기준으로 시스템 프롬프트 자동 삽입
  3. ChatML messages 형태로 변환
  4. data/lora/conversation/feedback_sft.jsonl 에 저장

출력 형식:
  {
    "messages": [
      {"role": "system",    "content": "<Layer A 시스템 프롬프트>"},
      {"role": "user",      "content": "..."},
      {"role": "assistant", "content": "..."}
    ]
  }

옵션:
  --reviewed_only   reviewed=true 인 항목만 포함 (기본: false 포함)
  --out PATH        출력 경로 지정 (기본: data/lora/conversation/feedback_sft.jsonl)
  --dry_run         변환 결과를 stdout으로 출력하고 파일에 저장하지 않음
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger

_FEEDBACK_POS_DIR = ROOT / "training" / "log" / "feedback_pos"
_DEFAULT_OUT      = ROOT / "data" / "lora" / "conversation" / "feedback_sft.jsonl"
_CHAR_DIR         = ROOT / "conversation" / "character"


# ── 시스템 프롬프트 조립 (character_id + affection 기준) ─────────────────────

# log 데이터 affection 3단계 → YAML 6단계 tier 매핑
_AFF_TIER_MAP = {"low": "stranger", "mid": "familiar", "high": "close"}

def _build_system_prompt(character_id: str, affection: str) -> str:
    """캐릭터 YAML + affection 구간으로 시스템 프롬프트를 조립한다.

    prompt_build.py PromptBuilder._layer_a() 와 동일한 순서로 조립.
    YAML 로드 실패 시 최소 폴백 프롬프트를 반환한다.
    """
    import yaml
    from conversation.core.prompt_build import (
        _STYLE_PRESETS, _PERSONA_PRESETS, _PERSONALITY_PRESETS,
        _AFFECTION_FALLBACK,
    )

    yaml_path = _CHAR_DIR / f"CH_{character_id}.yaml"
    if not yaml_path.exists():
        return f"너는 {character_id}이다. 캐릭터에 맞게 대화해."

    with open(yaml_path, encoding="utf-8") as f:
        char: dict = yaml.safe_load(f)

    tier = _AFF_TIER_MAP.get(affection, "familiar")

    parts: list[str] = []

    # 1. 이름
    name = char.get("name", character_id)
    parts.append(f"너는 {name}이다.")

    # 2. 캐릭터 설명
    if desc := char.get("description", "").strip():
        parts.append(desc)

    # 3. 말투 — prompt_build.py 동일 로직
    speech: dict = char.get("speech", {})
    formality = speech.get("formality", "").strip()
    if formality == "존댓말":
        parts.append("반드시 존댓말(경어체)로만 말한다. 반말을 절대 사용하지 않는다.")
    elif formality == "반말":
        parts.append("반드시 반말로만 말한다. 존댓말을 사용하지 않는다.")
    elif formality:
        parts.append(f"{formality}을 사용한다.")

    style_val = speech.get("style", "").strip()
    if style_val:
        parts.append(_STYLE_PRESETS.get(style_val, style_val))

    persona_val = speech.get("persona", "").strip()
    if persona_val:
        parts.append(_PERSONA_PRESETS.get(persona_val, persona_val))

    # 4. 성격
    personality_val = char.get("personality", "").strip()
    if personality_val:
        parts.append(_PERSONALITY_PRESETS.get(personality_val, personality_val))

    # 5. 친밀도 tier 행동
    aff_text = char.get("affection", {}).get(tier) or _AFFECTION_FALLBACK.get(tier, "")
    if aff_text:
        parts.append(aff_text)

    # 6. 규칙
    rules: list = char.get("rules", [])
    if rules and all(isinstance(r, str) for r in rules):
        parts.append(" ".join(rules))

    return " ".join(parts)


# ── 변환 ─────────────────────────────────────────────────────────────────────

def convert(reviewed_only: bool = False) -> list[dict]:
    """feedback_pos JSONL을 SFT ChatML 형태로 변환해 반환한다."""
    records: list[dict] = []

    pos_files = sorted(_FEEDBACK_POS_DIR.glob("*.jsonl"))
    if not pos_files:
        logger.warning(f"[build_sft] feedback_pos 파일 없음: {_FEEDBACK_POS_DIR}")
        return records

    loaded = skipped = 0
    for path in pos_files:
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("//"):
                    continue
                try:
                    entry: dict = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(f"[build_sft] JSON 파싱 실패 {path.name}:{lineno} — {e}")
                    continue

                if reviewed_only and not entry.get("reviewed", False):
                    skipped += 1
                    continue

                messages: list[dict] = entry.get("messages", [])
                if not messages:
                    skipped += 1
                    continue

                character_id = entry.get("character_id", "Haru")
                affection    = entry.get("affection", "mid")
                system_prompt = _build_system_prompt(character_id, affection)

                sft_entry = {
                    "messages": [{"role": "system", "content": system_prompt}] + messages
                }
                records.append(sft_entry)
                loaded += 1

    logger.info(f"[build_sft] 변환 완료 — {loaded}건 로드, {skipped}건 건너뜀")
    return records


# ── 저장 ─────────────────────────────────────────────────────────────────────

def save(records: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info(f"[build_sft] 저장 완료: {out_path} ({len(records)}건)")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="feedback_pos → SFT 변환")
    parser.add_argument("--reviewed_only", action="store_true",
                        help="reviewed=true 항목만 포함")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT,
                        help=f"출력 경로 (기본: {_DEFAULT_OUT})")
    parser.add_argument("--dry_run", action="store_true",
                        help="stdout 출력만 하고 파일 저장 안 함")
    args = parser.parse_args()

    records = convert(reviewed_only=args.reviewed_only)
    if not records:
        logger.warning("[build_sft] 변환할 데이터가 없습니다.")
        return

    if args.dry_run:
        for rec in records[:3]:
            print(json.dumps(rec, ensure_ascii=False, indent=2))
        print(f"\n... 총 {len(records)}건 (dry_run — 저장 안 함)")
    else:
        save(records, args.out)


if __name__ == "__main__":
    main()
