"""training/log/conversation_logger.py — 대화 중 학습 데이터 자동 수집.

저장 경로: training/log/{category}/YYYY-MM-DD.jsonl
저장 시점:
  - 유저 발화에 카테고리 키워드 포함 → 즉시 flush
  - assistant 응답 3회 이상 동일 (반복 루프) → 즉시 flush
  - CHUNK_SIZE 턴 도달 → flush (일상 잡담 수집용)
  - 세션 종료 → 잔여 버퍼 flush
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent

_NEGATIVE = [
    "아니야", "아니지", "그게 아니라", "반복하지마", "반복 하지마",
    "같은 말", "틀렸", "이해 못", "왜 그런 말", "그 말 말고",
    "이상하", "말투", "왜그래", "왜 그래", "캐릭터", "붕괴",
    "어색하", "안 맞아", "맞지 않아", "뭔 말이야", "무슨 말이야",
    "한국어로", "다시 말해", "제대로", "왜 이러", "그게 무슨",
]
_POSITIVE = [
    "맞아", "맞네", "잘했", "역시", "그렇지", "고마워",
    "기억하네", "기억했", "잘 기억", "대단하", "좋았어", "좋네",
]
_MEMORY   = [
    "기억해", "기억나", "이름", "좋아하", "싫어하",
    "말했잖", "했잖아", "취미", "말한 거", "저번에", "전에 말",
]
_EMOTION  = [
    "슬프", "화나", "기쁘", "우울", "행복",
    "외롭", "힘들", "무섭", "기분", "속상", "답답",
]
_ADVICE   = [
    "어떻게 해", "조언", "고민이야", "해야 할까", "어떻게 생각",
    "어떡해", "뭐가 나아", "어떻게 하면", "뭐가 좋",
]
_PERSONA  = ["AI야", "로봇이야", "프로그램이야", "가짜야", "진짜 사람"]


def _affection_level(aff: int) -> str:
    if aff >= 67:
        return "high"
    if aff >= 34:
        return "mid"
    return "low"


def _has_repetition(turns: list[dict]) -> bool:
    """최근 assistant 응답 3개 이상 동일하면 True."""
    asst = [t["content"].strip() for t in turns if t["role"] == "assistant"]
    return len(asst) >= 3 and len(set(asst[-3:])) == 1


def _is_trigger(user_text: str) -> bool:
    """단일 유저 발화에 즉시 저장 키워드가 있으면 True."""
    all_kw = _NEGATIVE + _POSITIVE + _MEMORY + _EMOTION + _ADVICE + _PERSONA
    return any(kw in user_text for kw in all_kw)


def _importance_score(
    buffer: list[dict],
    aff_delta: int,
    mood_changed: bool,
) -> float:
    """버퍼 내 대화 중요도를 0.0~1.0으로 산출.

    점수 구성:
      - affection 변화량 (±1당 0.08, 최대 0.30)
      - mood 변화 여부 (0.15)
      - 유저 입력 평균 길이 — 긴 입력 = 깊은 대화 (최대 0.20)
      - 감정·상담 키워드 밀도 (최대 0.20)
      - 행동 묘사(*) 등장 빈도 (최대 0.15)
    """
    score = 0.0

    # affection 변화
    score += min(abs(aff_delta) * 0.08, 0.30)

    # mood 변화
    if mood_changed:
        score += 0.15

    # 유저 입력 평균 길이
    user_texts = [t["content"] for t in buffer if t["role"] == "user"]
    if user_texts:
        avg_len = sum(len(t) for t in user_texts) / len(user_texts)
        if avg_len >= 60:
            score += 0.20
        elif avg_len >= 35:
            score += 0.10

    # 감정·상담 키워드 밀도
    all_text = " ".join(t["content"] for t in buffer)
    emo_hits = sum(1 for kw in (_EMOTION + _ADVICE) if kw in all_text)
    score += min(emo_hits * 0.05, 0.20)

    # 행동 묘사 (* 포함 발화 수)
    action_turns = sum(1 for t in buffer if "*" in t["content"])
    score += min(action_turns * 0.05, 0.15)

    return min(score, 1.0)


def _dynamic_chunk_size(score: float) -> int:
    """중요도 점수 → 최대 수집 턴 수.

      score < 0.25  →  8턴 (기본)
      0.25 ~ 0.50   → 12턴
      0.50 ~ 0.70   → 18턴
      0.70 이상     → 24턴
    """
    if score >= 0.70:
        return 24
    if score >= 0.50:
        return 18
    if score >= 0.25:
        return 12
    return 8


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _is_duplicate(messages: list[dict], cat_dir: Path, threshold: float = 0.55) -> bool:
    """같은 카테고리의 최근 3개 항목과 Jaccard 유사도 비교.

    threshold 이상이면 새 내용 없다고 판단 → True 반환.
    """
    # cat_dir가 아직 없거나 파일 없으면 중복 아님
    files = sorted(cat_dir.glob("*.jsonl")) if cat_dir.exists() else []
    if not files:
        return False

    new_words = set(
        w for m in messages if m["role"] == "user"
        for w in m["content"].split()
        if len(w) > 1
    )

    checked = 0
    for jl in reversed(files):          # 최신 파일부터
        lines = [ln for ln in jl.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for line in reversed(lines):    # 최신 항목부터
            if checked >= 3:
                break
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            ex_words = set(
                w for m in existing.get("messages", []) if m["role"] == "user"
                for w in m["content"].split()
                if len(w) > 1
            )
            if _jaccard(new_words, ex_words) >= threshold:
                return True
            checked += 1
        if checked >= 3:
            break

    return False


def _classify(turns: list[dict]) -> tuple[str, str]:
    """(category, emotion_trigger) 반환."""
    if _has_repetition(turns):
        return "feedback_neg", "반복_루프"

    user_text = " ".join(t["content"] for t in turns if t["role"] == "user")

    if any(kw in user_text for kw in _NEGATIVE):
        return "feedback_neg", "교정_지적"
    if any(kw in user_text for kw in _POSITIVE):
        return "feedback_pos", "칭찬_동의"
    if any(kw in user_text for kw in _MEMORY):
        return "memory", "기억_참조"
    if any(kw in user_text for kw in _EMOTION):
        return "emotion", "감정_표현"
    if any(kw in user_text for kw in _ADVICE):
        return "advice", "고민_상담"
    if any(kw in user_text for kw in _PERSONA):
        return "persona", "페르소나_테스트"
    return "daily", "일상_잡담"


class ConversationLogger:
    """대화 턴을 버퍼링해 training/log/{category}/{session_id}.jsonl에 저장."""

    _CHUNK_MIN = 8   # 최소 수집 턴
    _CHUNK_MAX = 24  # 최대 수집 턴 (안전 상한)

    def __init__(self, character_id: str, log_dir: Path = LOG_DIR):
        self._char_id    = character_id
        self._log_dir    = log_dir
        self._session_id = uuid.uuid4().hex[:8]
        self._buffer: list[dict] = []
        self._last_aff   = 0
        self._last_mood  = "neutral"
        self._prev_aff   = 0    # 직전 flush 시점의 affection (delta 계산용)
        self._prev_mood  = "neutral"  # 직전 flush 시점의 mood
        self._turn_start = 0
        self._turn_total = 0
        self._written_files: list[Path] = []

    def on_turn(
        self,
        user_input: str,
        assistant_response: str,
        mood: str,
        affection: int,
    ) -> None:
        self._buffer.append({"role": "user",      "content": user_input})
        self._buffer.append({"role": "assistant", "content": assistant_response})
        self._last_aff  = affection
        self._last_mood = mood
        self._turn_total += 1

        # 중요도 기반 동적 청크 크기 결정
        aff_delta    = affection - self._prev_aff
        mood_changed = (mood != self._prev_mood)
        score        = _importance_score(self._buffer, aff_delta, mood_changed)
        chunk_size   = min(_dynamic_chunk_size(score), self._CHUNK_MAX)

        if (
            _is_trigger(user_input)
            or _has_repetition(self._buffer)
            or len(self._buffer) >= chunk_size * 2
        ):
            self._flush(score)

    def flush_remaining(self) -> None:
        """세션 종료 시 잔여 버퍼 저장 (최소 2턴 이상일 때)."""
        if len(self._buffer) >= 4:
            aff_delta    = self._last_aff - self._prev_aff
            mood_changed = (self._last_mood != self._prev_mood)
            score        = _importance_score(self._buffer, aff_delta, mood_changed)
            self._flush(score)

    def edit_turn(self, old_content: str, new_content: str) -> None:
        """이미 기록된 assistant 응답을 수정된 텍스트로 교체한다.

        1. 아직 버퍼에 있으면 버퍼에서 직접 수정.
        2. 이미 flush된 경우 기록된 JSONL 파일을 재작성한다.
        """
        # 1. 버퍼 먼저 탐색
        for msg in self._buffer:
            if msg.get("role") == "assistant" and msg.get("content") == old_content:
                msg["content"] = new_content
                return

        # 2. 기록된 파일 역순 탐색 (최근 파일부터)
        for file_path in reversed(self._written_files):
            if not file_path.exists():
                continue
            raw = file_path.read_text(encoding="utf-8")
            lines = raw.splitlines()
            changed = False
            new_lines = []
            for line in lines:
                if not line.strip():
                    new_lines.append(line)
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    new_lines.append(line)
                    continue
                for msg in entry.get("messages", []):
                    if msg.get("role") == "assistant" and msg.get("content") == old_content:
                        msg["content"] = new_content
                        changed = True
                new_lines.append(json.dumps(entry, ensure_ascii=False))
            if changed:
                file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                return

    def _flush(self, score: float = 0.0) -> None:
        if not self._buffer:
            return

        category, trigger = _classify(self._buffer)
        turn_end   = self._turn_total
        turn_range = f"{self._turn_start}-{turn_end}"
        n_turns    = len(self._buffer) // 2

        entry = {
            "messages":        list(self._buffer),
            "character_id":    self._char_id,
            "category":        category,
            "affection":       _affection_level(self._last_aff),
            "mood":            self._last_mood,
            "emotion_trigger": trigger,
            "turn_range":      turn_range,
            "importance":      round(score, 2),
            "logged_at":       datetime.now().isoformat(timespec="seconds"),
            "reviewed":        False,
        }

        # 카테고리별 폴더 생성
        cat_dir  = self._log_dir / category
        cat_dir.mkdir(exist_ok=True)
        out_file = cat_dir / f"{self._session_id}.jsonl"

        # 중복 체크 — 새 내용 없으면 저장 생략
        if _is_duplicate(self._buffer, cat_dir):
            print(
                f"\033[90m[LOG –] {category} | {trigger} | "
                f"turn {turn_range} — 유사 항목 존재, 생략\033[0m"
            )
            self._turn_start = turn_end
            self._prev_aff   = self._last_aff
            self._prev_mood  = self._last_mood
            self._buffer.clear()
            return

        with out_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if out_file not in self._written_files:
            self._written_files.append(out_file)

        # 콘솔 표시 (중요도 ≥ 0.5이면 강조)
        color = "\033[93m" if score >= 0.5 else "\033[90m"
        print(
            f"{color}[LOG ✓] {category} | {trigger} | "
            f"turn {turn_range} ({n_turns}턴, imp={score:.2f}) "
            f"→ {out_file.relative_to(self._log_dir.parent.parent)}\033[0m"
        )

        self._turn_start = turn_end
        self._prev_aff   = self._last_aff
        self._prev_mood  = self._last_mood
        self._buffer.clear()
