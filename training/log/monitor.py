"""training/log/monitor.py — 대화 세션 실시간 모니터링.

main.py가 시작할 때 백그라운드로 자동 실행된다.
출력은 training/log/.monitor.log 에 기록된다.

별도 터미널에서 확인:
    tail -f training/log/.monitor.log
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

LOG_DIR    = Path(__file__).resolve().parent
STATE_FILE = LOG_DIR / ".session_state.json"
MON_FILE   = LOG_DIR / ".monitor.log"

CATEGORIES = ["daily", "emotion", "advice", "memory", "persona", "feedback_pos", "feedback_neg"]
REFRESH_SEC = 2


def _read_state() -> dict | None:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_today(category: str) -> tuple[int, int]:
    """(전체, 미검토) 건수 반환."""
    today = datetime.now().strftime("%Y-%m-%d")
    f = LOG_DIR / category / f"{today}.jsonl"
    if not f.exists():
        return 0, 0
    total, unreviewed = 0, 0
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        try:
            if not json.loads(line).get("reviewed", True):
                unreviewed += 1
        except Exception:
            pass
    return total, unreviewed


def _recent_entries(n: int = 6) -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    entries = []
    for cat in CATEGORIES:
        f = LOG_DIR / cat / f"{today}.jsonl"
        if not f.exists():
            continue
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for line in lines[-2:]:
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    entries.sort(key=lambda x: x.get("logged_at", ""))
    return entries[-n:]


def _render(state: dict | None, recent: list[dict]) -> str:
    now   = datetime.now().strftime("%H:%M:%S")
    lines = [
        f"{'─' * 52}",
        f"  Achat 모니터  {now}",
        f"{'─' * 52}",
    ]

    # 세션 상태
    if state:
        lines += [
            f"  turn    : {state.get('turn', '?')}",
            f"  mood    : {state.get('mood', '?')}   affection: {state.get('affection', '?')}",
            f"  act_id  : {state.get('act_id', '?')}",
        ]
        if state.get("location_context"):
            loc_preview = state["location_context"][:40].replace("\n", " ")
            lines.append(f"  location: {loc_preview}…")
        lines.append(f"  vdb     : {state.get('vdb_count', '?')}건")
    else:
        lines.append("  세션 대기 중...")

    # 오늘 카테고리별 누적 건수
    lines.append("")
    lines.append("  오늘 누적 로그:")
    total_unreviewed = 0
    for cat in CATEGORIES:
        cnt, unrev = _count_today(cat)
        if cnt:
            flag = f"  ★미검토 {unrev}건" if unrev else ""
            lines.append(f"    {cat:<14} {cnt}건{flag}")
            total_unreviewed += unrev
    if total_unreviewed:
        lines.append(f"  → 미검토 합계: {total_unreviewed}건  (python training/log/review.py)")

    # 최근 저장 내역
    if recent:
        lines.append("")
        lines.append("  최근 저장:")
        for e in recent:
            cat     = e.get("category", "?")
            trigger = e.get("emotion_trigger", "")
            t_range = e.get("turn_range", "")
            logged  = e.get("logged_at", "")[-8:]
            n_turns = len(e.get("messages", [])) // 2
            lines.append(f"    [{logged}] {cat:<14} {trigger}  ({n_turns}턴, {t_range})")

    lines.append(f"{'─' * 52}")
    return "\n".join(lines)


def run() -> None:
    print(f"[monitor] 시작 — {MON_FILE}", flush=True)
    while True:
        state  = _read_state()
        recent = _recent_entries()
        text   = _render(state, recent)
        MON_FILE.write_text(text + "\n", encoding="utf-8")
        time.sleep(REFRESH_SEC)


if __name__ == "__main__":
    run()
