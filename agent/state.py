from __future__ import annotations

from loguru import logger

from conversation.core.session import ConversationSession

# affection 변화량 기본값
_AFF_DELTA = {
    "happy":   +3,
    "annoyed": -3,
    "sad":      0,   # 슬픈 감정은 affection 중립
    "neutral":  0,
}


def update_mood(session: ConversationSession, user_input: str, character: dict) -> str:
    """user_input의 키워드를 기반으로 mood를 갱신하고 새 mood를 반환한다.

    character['state']['mood_triggers'] 구조:
        happy:   [...keyword list...]
        annoyed: [...keyword list...]
        sad:     [...keyword list...]
    """
    triggers: dict = character.get("state", {}).get("mood_triggers", {})
    new_mood = "neutral"

    for mood_name, keywords in triggers.items():
        if any(kw in user_input for kw in keywords):
            new_mood = mood_name
            break

    if session.mood != new_mood:
        logger.debug(f"[state] mood 변경: {session.mood} → {new_mood}")
    session.mood = new_mood
    return new_mood


def update_affection(session: ConversationSession, mood: str) -> int:
    """현재 mood에 따라 affection을 증감하고 새 affection 값을 반환한다.

    affection은 0~100 범위로 클램핑된다.
    """
    delta = _AFF_DELTA.get(mood, 0)
    if delta == 0:
        return session.affection

    old = session.affection
    session.affection = max(0, min(100, session.affection + delta))
    logger.debug(f"[state] affection: {old} → {session.affection} (delta={delta:+d}, mood={mood})")
    return session.affection
