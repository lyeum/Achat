"""training/log/review.py — 미검토 로그 엔트리 이중 체크 도구.

사용법:
    uv run python training/log/review.py              # 전체 미검토 항목
    uv run python training/log/review.py --cat memory # 특정 카테고리만

조작키:
    y        승인 (reviewed=True, 현재 카테고리 유지)
    n        카테고리 재분류 후 승인 (목록에서 선택)
    d        삭제 (해당 줄 제거)
    s        건너뜀 (나중에 다시)
    q        종료
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LOG_DIR    = Path(__file__).resolve().parent
CATEGORIES = ["daily", "emotion", "advice", "memory", "persona", "feedback_pos", "feedback_neg"]

_COLORS = {
    "header":  "\033[1;36m",
    "cat":     "\033[1;33m",
    "msg_u":   "\033[0;37m",
    "msg_a":   "\033[0;32m",
    "prompt":  "\033[1;35m",
    "ok":      "\033[1;32m",
    "err":     "\033[1;31m",
    "reset":   "\033[0m",
}
C = _COLORS


def _c(key: str, text: str) -> str:
    return f"{C.get(key,'')}{text}{C['reset']}"


def _collect_unreviewed(cat_filter: str | None) -> list[tuple[Path, int, dict]]:
    """(파일경로, 줄번호, 엔트리) 목록 반환 — reviewed=False인 것만."""
    items = []
    cats = [cat_filter] if cat_filter else CATEGORIES
    for cat in cats:
        cat_dir = LOG_DIR / cat
        if not cat_dir.is_dir():
            continue
        for jl in sorted(cat_dir.glob("*.jsonl")):
            for i, line in enumerate(jl.read_text(encoding="utf-8").splitlines()):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not entry.get("reviewed", True):
                    items.append((jl, i, entry))
    return items


def _rewrite_file(path: Path, new_lines: list[str]) -> None:
    path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""),
                    encoding="utf-8")


def _update_entry(path: Path, line_idx: int, entry: dict) -> None:
    """파일의 특정 줄을 업데이트된 엔트리로 교체한다."""
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[line_idx] = json.dumps(entry, ensure_ascii=False)
    _rewrite_file(path, lines)


def _delete_entry(path: Path, line_idx: int) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    del lines[line_idx]
    _rewrite_file(path, lines)


def _move_entry(path: Path, line_idx: int, entry: dict, new_cat: str) -> None:
    """엔트리를 새 카테고리 파일로 이동한다."""
    # 원본 삭제
    _delete_entry(path, line_idx)

    # 새 위치에 추가
    entry["category"] = new_cat
    entry["reviewed"] = True
    date     = path.stem  # YYYY-MM-DD
    dest_dir = LOG_DIR / new_cat
    dest_dir.mkdir(exist_ok=True)
    dest_file = dest_dir / f"{date}.jsonl"
    with dest_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _print_entry(idx: int, total: int, path: Path, entry: dict) -> None:
    cat     = entry.get("category", "?")
    trigger = entry.get("emotion_trigger", "")
    t_range = entry.get("turn_range", "")
    logged  = entry.get("logged_at", "")
    aff     = entry.get("affection", "")
    mood    = entry.get("mood", "")

    print()
    print(_c("header", f"{'─'*54}"))
    print(_c("header", f"  [{idx+1}/{total}]  {path.parent.name}/{path.name}  줄?"))
    print(_c("cat",    f"  카테고리 : {cat}  ({trigger})"))
    print(            f"  turn     : {t_range}  |  affection: {aff}  mood: {mood}")
    print(            f"  logged   : {logged}")
    print(_c("header", f"{'─'*54}"))

    messages = entry.get("messages", [])
    for msg in messages:
        role    = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            print(_c("msg_u", f"  You : {content}"))
        else:
            print(_c("msg_a", f"  AI  : {content}"))
    print()


def _choose_category() -> str | None:
    print(_c("prompt", "  카테고리 선택:"))
    for i, cat in enumerate(CATEGORIES):
        print(f"    {i+1}. {cat}")
    raw = input(_c("prompt", "  번호 입력 (취소: Enter): ")).strip()
    if not raw:
        return None
    try:
        idx = int(raw) - 1
        if 0 <= idx < len(CATEGORIES):
            return CATEGORIES[idx]
    except ValueError:
        pass
    print(_c("err", "  잘못된 입력, 건너뜀"))
    return None


def run(cat_filter: str | None) -> None:
    items = _collect_unreviewed(cat_filter)
    if not items:
        print(_c("ok", "미검토 항목 없음."))
        return

    print(_c("header", f"\n미검토 항목 {len(items)}건 — (y)승인 (n)재분류 (d)삭제 (s)건너뜀 (q)종료\n"))

    # 파일별 줄 번호 오프셋 추적 (삭제/이동 시 인덱스 밀림 보정)
    offset: dict[Path, int] = {}

    for i, (path, raw_idx, entry) in enumerate(items):
        adj_idx = raw_idx + offset.get(path, 0)
        _print_entry(i, len(items), path, entry)

        while True:
            key = input(_c("prompt", "  > ")).strip().lower()

            if key == "y":
                entry["reviewed"] = True
                _update_entry(path, adj_idx, entry)
                print(_c("ok", "  ✓ 승인"))
                break

            elif key == "n":
                new_cat = _choose_category()
                if new_cat:
                    _move_entry(path, adj_idx, entry, new_cat)
                    offset[path] = offset.get(path, 0) - 1
                    print(_c("ok", f"  ✓ {new_cat}으로 이동"))
                break

            elif key == "d":
                _delete_entry(path, adj_idx)
                offset[path] = offset.get(path, 0) - 1
                print(_c("err", "  ✗ 삭제"))
                break

            elif key == "s":
                print("  → 건너뜀")
                break

            elif key == "q":
                print("종료합니다.")
                sys.exit(0)

            else:
                print("  y / n / d / s / q")

    remaining = sum(
        1 for p, _, e in _collect_unreviewed(cat_filter) if not e.get("reviewed", True)
    )
    print(_c("ok", f"\n검토 완료. 잔여 미검토: {remaining}건"))


def main() -> None:
    parser = argparse.ArgumentParser(description="로그 이중 체크 도구")
    parser.add_argument("--cat", default=None,
                        help="특정 카테고리만 검토 (예: memory, feedback_neg)")
    args = parser.parse_args()
    run(args.cat)


if __name__ == "__main__":
    main()
