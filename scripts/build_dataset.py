"""
build_dataset.py — training/log/*.jsonl → data/lora/conversation/{category}.jsonl

사용법:
  python scripts/build_dataset.py
  python scripts/build_dataset.py --log_dir training/log --out_dir data/lora/conversation
  python scripts/build_dataset.py --char_dir conversation/character --dry_run

동작:
  1. training/log/*.jsonl 읽기 (// 로 시작하는 줄은 비활성화된 항목으로 스킵)
  2. character_id + affection 기준으로 CH_{id}.yaml에서 시스템 프롬프트 생성
  3. messages 앞에 {"role": "system", "content": "..."} 삽입
  4. ChatML 포맷 검증 (role 교대, 최소 1턴)
  5. max_length=512 토큰 초과 샘플 경고 출력
  6. data/lora/conversation/{category}.jsonl 에 저장 (카테고리별 분리)
"""

import argparse
import json
import sys
from pathlib import Path

import yaml
from loguru import logger

# 프로젝트 루트를 sys.path에 추가 (직접 실행 시)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAX_LENGTH_WARN = 512  # 이 토큰 수 초과 시 경고 (실제 토크나이저 없이 문자 수로 근사)
TOKENS_PER_CHAR = 2.5  # 한국어 근사: 글자당 약 2.5 토큰 (SentencePiece 기준 한국어 음절 ~1-3 토큰)


def load_character(char_dir: Path, character_id: str) -> dict:
    yaml_path = char_dir / f"CH_{character_id}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"캐릭터 파일 없음: {yaml_path}")
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_system_prompt(character: dict, affection: str) -> str:
    """character YAML + affection tier → 시스템 프롬프트 문자열"""
    name = character.get("name", character.get("id", "캐릭터"))
    speech = character.get("speech_style", "").strip()
    rules = character.get("rules", [])

    tier_desc = {
        "low":  "상대방과 아직 친하지 않다. 단답형으로 경계적으로 말한다.",
        "mid":  "상대방과 어느 정도 친해진 상태다. 편하게 대화하되 가끔 솔직한 반응을 보인다.",
        "high": "상대방과 많이 친해진 상태다. 조금 부드럽게 대화하며 응답이 길어지기도 한다.",
    }.get(affection, "")

    rules_text = "\n".join(f"- {r}" for r in rules) if rules else ""

    parts = [f"너는 캐릭터 '{name}'이다.", speech]
    if tier_desc:
        parts.append(tier_desc)
    if rules_text:
        parts.append(f"규칙:\n{rules_text}")

    return "\n".join(p for p in parts if p.strip())


def validate_messages(messages: list) -> str | None:
    """ChatML 포맷 검증. 문제 있으면 에러 메시지 반환, 없으면 None."""
    if not messages:
        return "messages가 비어있음"
    # system 메시지 포함된 경우 첫 번째가 system이어야 함
    roles = [m.get("role") for m in messages]
    non_sys = [r for r in roles if r != "system"]
    if len(non_sys) < 2:
        return f"user/assistant 턴이 최소 1쌍 필요 (현재 {len(non_sys)}개)"
    for i in range(0, len(non_sys) - 1, 2):
        if non_sys[i] != "user":
            return f"role 교대 위반: index {i} expected 'user' got '{non_sys[i]}'"
        if i + 1 < len(non_sys) and non_sys[i + 1] != "assistant":
            return f"role 교대 위반: index {i+1} expected 'assistant' got '{non_sys[i+1]}'"
    return None


def estimate_tokens(messages: list) -> int:
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return int(total_chars * TOKENS_PER_CHAR)


def process_log_file(
    log_path: Path,
    char_dir: Path,
    out_dir: Path,
    dry_run: bool,
    char_cache: dict,
) -> tuple[int, int, int]:
    """파일 하나 처리. (성공, 스킵, 경고) 카운트 반환."""
    ok = skip = warn = 0

    with open(log_path, encoding="utf-8") as f:
        lines = f.readlines()

    results: dict[str, list[str]] = {}  # category → list of json strings

    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("//"):
            skip += 1
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning(f"{log_path.name}:{lineno} JSON 파싱 실패: {e}")
            skip += 1
            continue

        char_id = entry.get("character_id", "Haru")
        affection = entry.get("affection", "mid")
        category = entry.get("category", log_path.stem)
        messages = entry.get("messages", [])

        # 이미 system 메시지가 포함된 경우 그대로 사용
        if messages and messages[0].get("role") == "system":
            full_messages = messages
        else:
            # 캐릭터 YAML 로드 (캐시)
            cache_key = f"{char_id}_{affection}"
            if cache_key not in char_cache:
                try:
                    char = load_character(char_dir, char_id)
                    char_cache[cache_key] = build_system_prompt(char, affection)
                except FileNotFoundError as e:
                    logger.warning(f"{log_path.name}:{lineno} {e} — 스킵")
                    skip += 1
                    continue
            system_prompt = char_cache[cache_key]
            full_messages = [{"role": "system", "content": system_prompt}] + messages

        # ChatML 검증
        err = validate_messages(full_messages)
        if err:
            logger.warning(f"{log_path.name}:{lineno} 검증 실패: {err} — 스킵")
            skip += 1
            continue

        # 토큰 길이 경고
        tokens = estimate_tokens(full_messages)
        if tokens > MAX_LENGTH_WARN:
            logger.warning(f"{log_path.name}:{lineno} 토큰 초과 근사 {tokens}>{MAX_LENGTH_WARN} (category={category})")
            warn += 1

        out_entry = {
            "messages": full_messages,
            "character_id": char_id,
            "category": category,
            "affection": affection,
            "mood": entry.get("mood", "neutral"),
            "emotion_trigger": entry.get("emotion_trigger", ""),
        }

        results.setdefault(category, []).append(json.dumps(out_entry, ensure_ascii=False))
        ok += 1

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        for category, json_lines in results.items():
            out_path = out_dir / f"{category}.jsonl"
            mode = "a" if out_path.exists() else "w"
            with open(out_path, mode, encoding="utf-8") as f:
                f.write("\n".join(json_lines) + "\n")
            try:
                display_path = out_path.relative_to(ROOT)
            except ValueError:
                display_path = out_path
            logger.info(f"  → {display_path} ({len(json_lines)}건 {'추가' if mode == 'a' else '생성'})")

    return ok, skip, warn


def main():
    parser = argparse.ArgumentParser(description="training/log → data/lora/conversation 빌드")
    parser.add_argument("--log_dir",  default="training/log",             help="입력 JSONL 디렉토리")
    parser.add_argument("--out_dir",  default="data/lora/conversation",   help="출력 디렉토리")
    parser.add_argument("--char_dir", default="conversation/character",   help="캐릭터 YAML 디렉토리")
    parser.add_argument("--dry_run",  action="store_true",                help="출력 없이 검증만 실행")
    args = parser.parse_args()

    log_dir  = ROOT / args.log_dir
    out_dir  = ROOT / args.out_dir
    char_dir = ROOT / args.char_dir

    if not log_dir.exists():
        logger.error(f"log_dir 없음: {log_dir}")
        sys.exit(1)

    jsonl_files = sorted(log_dir.glob("**/*.jsonl"))
    if not jsonl_files:
        logger.warning(f"JSONL 파일 없음: {log_dir}")
        sys.exit(0)

    logger.info(f"빌드 시작 — {len(jsonl_files)}개 파일 처리 {'(dry-run)' if args.dry_run else ''}")

    char_cache: dict = {}
    total_ok = total_skip = total_warn = 0

    for path in jsonl_files:
        if path.name.startswith("_"):  # _schema.json 등 메타 파일 스킵
            continue
        logger.info(f"처리 중: {path.name}")
        ok, skip, warn = process_log_file(path, char_dir, out_dir, args.dry_run, char_cache)
        total_ok += ok
        total_skip += skip
        total_warn += warn

    logger.info(
        f"완료 — 성공 {total_ok}건 / 스킵 {total_skip}건 / 길이 경고 {total_warn}건"
    )
    if args.dry_run:
        logger.info("dry-run 모드: 파일 출력 없음")


if __name__ == "__main__":
    main()
