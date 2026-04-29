"""대화 로그(dialogue.json)에서 VDB 장기 기억을 추출해 저장한다.

사용법:
    uv run python tools/extract_memories.py [--char CHAR_ID] [--dry-run]

옵션:
    --char      특정 캐릭터만 처리 (기본: 전체)
    --dry-run   VDB 저장 없이 요약 결과만 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config as cfg_mod
from conversation.core.llm_client import LLMClient
from memory.long_term import LongTermMemory
from memory import summarizer


def _fake_session(char_id: str, session_id: str, turn_count: int):
    """write_to_vdb() 호출용 최소 session 대리 객체."""
    class _S:
        character_id = char_id
        session_id   = session_id
        act_id       = ""
    s = _S()
    s.turn_count = turn_count
    return s


def process_dialogue(
    dialogue: list[dict],
    char_id: str,
    session_id: str,
    llm: LLMClient,
    long_term: LongTermMemory,
    trigger_n: int,
    dry_run: bool,
) -> int:
    """dialogue를 trigger_n 턴 단위로 청크 분할해 요약 → VDB 저장.

    Returns 저장된 항목 수.
    """
    stored = 0
    total_turns = len(dialogue) // 2  # user+assistant 쌍

    for chunk_start in range(0, total_turns, trigger_n):
        chunk_end = min(chunk_start + trigger_n, total_turns)
        chunk = dialogue[chunk_start * 2 : chunk_end * 2]

        summary = summarizer.summarize(chunk, llm, trigger_n)
        score   = summarizer.score_importance(summary)

        print(f"  [{char_id}/{session_id}] 턴 {chunk_start}-{chunk_end}  score={score:.2f}")
        print(f"  {summary[:120].replace(chr(10), ' ')}")
        print()

        if dry_run or score < 0.65:
            if score < 0.65:
                print(f"  → 중요도 미달({score:.2f}), 건너뜀\n")
            continue

        fake = _fake_session(char_id, session_id, chunk_end)
        fake.turn_count = chunk_end
        ok = summarizer.write_to_vdb(summary, score, fake, long_term,
                                     character={"model_version": "manual_extract"}, trigger_n=trigger_n)
        if ok:
            stored += 1

    return stored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--char", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-adapter", action="store_true", help="LoRA 어댑터 없이 베이스 모델로 실행")
    args = parser.parse_args()

    config = cfg_mod.get_config()
    trigger_n: int = config.get("memory_trigger_n", 5)

    if args.no_adapter:
        config = dict(config)
        config["adapter_path"] = None
        print("LLM 로딩 중... (베이스 모델, 어댑터 없음)")
    else:
        print(f"LLM 로딩 중... (어댑터: {config.get('adapter_path', '없음')})")
    llm = LLMClient(config)

    long_term = LongTermMemory(config)

    session_root = Path(config.get("session_dir", "./data/sessions"))
    total_stored = 0

    for char_dir in sorted(session_root.iterdir()):
        if not char_dir.is_dir():
            continue
        char_id = char_dir.name
        if args.char and char_id != args.char:
            continue

        for sess_dir in sorted(char_dir.iterdir()):
            if not sess_dir.is_dir():
                continue
            dialogue_path = sess_dir / "dialogue.json"
            if not dialogue_path.exists():
                continue

            dialogue = json.loads(dialogue_path.read_text(encoding="utf-8"))
            if len(dialogue) < trigger_n * 2:
                print(f"[{char_id}/{sess_dir.name}] 대화 {len(dialogue)//2}턴 — 트리거 미달, 건너뜀\n")
                continue

            print(f"=== {char_id} / {sess_dir.name}  ({len(dialogue)//2}턴) ===")
            n = process_dialogue(
                dialogue, char_id, sess_dir.name,
                llm, long_term, trigger_n, args.dry_run
            )
            total_stored += n

    if not args.dry_run:
        print(f"\n완료: 총 {total_stored}개 항목 VDB 저장")
    else:
        print("\n[dry-run] VDB 저장 없이 완료")


if __name__ == "__main__":
    main()
