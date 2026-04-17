from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger

from conversation.core.session import ConversationSession
from memory.long_term import LongTermMemory

# 중요도 판정 키워드 (M_schema.json importance_rules 기준)
# 이름 키워드는 1.0으로 강제 — VDB 검색 실패(4/5) 원인이 낮은 importance로 인한 누락
# 구조화 포맷에서 이름 항목이 채워진 경우 ("이름: -" 는 제외)
_NAME_KEYWORDS = ["이름: ", "이름은", "이름이", "이름"]
_HIGH_KEYWORDS = [
    "부탁", "약속", "싫어", "좋아해", "화해", "미안", "고마워",
    "기억해줘", "잊지마", "중요해", "말해줄게", "비밀", "처음으로",
]
_MID_KEYWORDS  = [
    "좋아", "싫어", "취미", "매일", "항상", "자주", "기억",
    "날짜", "내일", "세션", "욕", "화났", "슬퍼", "기분", "감정",
    "말했잖", "저번에", "그때", "아까", "다음에", "또 올게",
    "피드백", "고쳐", "이상해", "말투", "캐릭터",
]


_SUMMARIZE_SYSTEM = """\
아래 대화에서 사용자에 대한 정보를 추출해. 반드시 아래 형식으로만 답해.
정보가 없는 항목은 '-'로 표시해. 형식 외 다른 말은 쓰지 마.

이름: [대화에서 언급된 경우만, 없으면 -]
사건: [중요한 사건, 감정적 순간, 약속 — 없으면 -]
감정: [사용자가 드러낸 감정 상태 — 없으면 -]
기타: [취미, 선호도, 반복 화제 — 없으면 -]"""


def check_trigger(session: ConversationSession, trigger_n: int) -> bool:
    """N턴마다 요약 트리거 여부를 반환한다."""
    return session.turn_count > 0 and session.turn_count % trigger_n == 0


def should_summarize(dialogue_log: list[dict], trigger_n: int) -> bool:
    """최근 trigger_n턴에 중요 키워드가 하나라도 있을 때만 True.

    잡담만 오간 구간은 요약을 생략해 LLM 호출 낭비와 저품질 VDB 누적을 방지한다.
    """
    recent = dialogue_log[-(trigger_n * 2):]
    text   = " ".join(m["content"] for m in recent)
    important_kw = _NAME_KEYWORDS + _HIGH_KEYWORDS + _MID_KEYWORDS
    return any(kw in text for kw in important_kw)


def summarize(dialogue_log: list[dict], llm, trigger_n: int) -> str:
    """최근 trigger_n턴 대화를 LLM으로 요약한다.

    Parameters
    ----------
    dialogue_log : 전체 대화 로그 (user/assistant 교대)
    llm          : LLMClient 인스턴스
    trigger_n    : 요약 대상 턴 수

    Returns
    -------
    구조화된 요약 문자열 (이름 / 사건 / 감정 / 기타 형식)
    """
    recent = dialogue_log[-(trigger_n * 2):]
    history_text = "\n".join(
        f"{'사용자' if m['role'] == 'user' else '캐릭터'}: {m['content']}"
        for m in recent
    )
    messages = [
        {"role": "system", "content": _SUMMARIZE_SYSTEM},
        {"role": "user",   "content": history_text},
    ]
    summary = llm.generate(messages, stream=False, max_tokens=150)
    logger.debug(f"[summarizer] 요약 생성: {summary[:60]}...")
    return summary


def score_importance(summary: str) -> float:
    """요약 텍스트를 키워드 기반으로 중요도 점수로 변환한다.

    M_schema.json importance_rules 기준:
    - high(0.8~1.0): 이름/고유정보, 약속/선언, 갈등/화해
    - mid (0.5~0.8): 감정적 사건, 취향/선호도, 반복 화제
    - low (<0.5)   : 일상 잡담 → 저장 안 함
    """
    score = 0.5  # 기본값 — 키워드 없어도 일단 저장
    for kw in _NAME_KEYWORDS:
        if kw in summary and "이름: -" not in summary:
            return 1.0  # 이름 정보는 최고 중요도 — 누락 방지
    for kw in _HIGH_KEYWORDS:
        if kw in summary:
            score = max(score, 0.85)
            break
    if score == 0.5:  # high 키워드 미매칭 시에만 mid 키워드 검사
        for kw in _MID_KEYWORDS:
            if kw in summary:
                score = max(score, 0.6)
                break
    return round(score, 2)


def write_to_vdb(
    summary: str,
    score: float,
    session: ConversationSession,
    long_term: LongTermMemory,
    character: dict,
    trigger_n: int = 10,
) -> bool:
    """score >= 0.5인 경우에만 ChromaDB에 저장한다.

    Returns
    -------
    저장 여부 (True: 저장됨, False: 중요도 미달로 생략)
    """
    if score < 0.5:
        logger.debug(f"[summarizer] 중요도 미달({score:.2f}), 저장 생략")
        return False

    mem_id = f"mem_{session.character_id.lower()}_{uuid.uuid4().hex[:8]}"
    turn_start = max(0, session.turn_count - trigger_n)
    entry = {
        "id": mem_id,
        "content": summary,
        "metadata": {
            "character_id":  session.character_id,
            "session_id":    session.session_id or str(id(session)),
            "turn_range":    f"{turn_start}-{session.turn_count}",
            "importance":    score,
            "tags":          [],
            "location":      session.act_id or "",
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "model_version": character.get("model_version", "unknown"),
        },
    }
    long_term.store(entry)
    logger.info(f"[summarizer] VDB 저장 완료: {mem_id} (importance={score:.2f})")
    return True
