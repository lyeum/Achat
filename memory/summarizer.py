from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger

from conversation.core.session import ConversationSession
from memory.long_term import LongTermMemory

# 중요도 판정 키워드 (M_schema.json importance_rules 기준)
# 이름 키워드는 1.0으로 강제 — prose 요약에서 자연어로 언급된 경우만 해당
_NAME_KEYWORDS = ["이름은", "이름이", "이름을", "이름"]
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
아래 대화에서 '사용자'에 대해 기억할 중요한 정보를 자연스러운 문장으로 요약해.
추출 대상: 사용자의 이름·직업, 사용자가 겪은 사건, 사용자가 드러낸 감정·취향·선호도, 캐릭터가 사용자에게 한 약속.
주의: 사용자가 캐릭터를 배려해서 물어본 정보나 캐릭터 본인의 특성·취향은 포함하지 마.
실제로 드러난 것만 포함하고, 없는 정보는 꾸며내지 마. 2~4문장으로 작성해."""


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

    Returns
    -------
    자연어 산문 요약 문자열 (VDB에 그대로 저장)
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
    summary = llm.generate(messages, stream=False, max_tokens=250)
    logger.debug(f"[summarizer] 요약 생성: {summary[:80]}...")
    return summary


def score_importance(summary: str) -> float:
    """요약 텍스트를 키워드 기반으로 중요도 점수로 변환한다.

    M_schema.json importance_rules 기준:
    - high(0.8~1.0): 이름/고유정보, 약속/선언, 갈등/화해
    - mid (0.5~0.8): 감정적 사건, 취향/선호도, 반복 화제
    - low (<0.5)   : 일상 잡담 → 저장 안 함
    """
    score = 0.0  # 기본값 — 키워드 매칭 시에만 점수 부여
    for kw in _NAME_KEYWORDS:
        if kw in summary:
            return 1.0  # 이름 정보는 최고 중요도 — 누락 방지
    for kw in _HIGH_KEYWORDS:
        if kw in summary:
            score = max(score, 0.85)
            break
    if score == 0.0:  # high 키워드 미매칭 시에만 mid 키워드 검사
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
    if score < 0.65:
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
