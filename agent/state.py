from __future__ import annotations

from loguru import logger

from conversation.core.session import ConversationSession

# affection 변화량 기본값 (캐릭터 YAML에 affection_delta 없을 때 폴백)
_AFF_DELTA_DEFAULT = {
    "happy":       +3,
    "affectionate": +5,
    "touched":     +4,
    "curious":     +1,
    "neutral":      0,
    "sad":          0,
    "embarrassed": -1,
    "annoyed":     -3,
    "angry":       -5,
}


def update_mood(session: ConversationSession, user_input: str, character: dict) -> str:
    """user_input의 키워드를 기반으로 mood를 갱신하고 새 mood를 반환한다.

    character['state']['mood_triggers'] 구조:
        mood_name: [...keyword list...]
    YAML에 정의된 순서대로 우선순위 적용 (먼저 매칭된 mood 채택).
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


def update_affection(session: ConversationSession, mood: str, character: dict | None = None) -> int:
    """현재 mood에 따라 affection을 증감하고 새 affection 값을 반환한다.

    캐릭터 YAML의 state.affection_delta가 있으면 우선 적용, 없으면 기본값 사용.
    affection은 0~100 범위로 클램핑된다.
    session.affection_locked=True이면 lock_value로 고정하고 즉시 반환한다.
    """
    if session.affection_locked:
        lock_val = session.affection_lock_value
        if lock_val is not None:
            session.affection = max(0, min(100, lock_val))
        logger.debug(f"[state] affection 잠금 중 — 값 고정: {session.affection}")
        return session.affection

    char_delta: dict = {}
    if character:
        char_delta = character.get("state", {}).get("affection_delta", {})

    delta = char_delta.get(mood, _AFF_DELTA_DEFAULT.get(mood, 0))
    if delta == 0:
        return session.affection

    old = session.affection
    session.affection = max(0, min(100, session.affection + delta))
    logger.debug(f"[state] affection: {old} → {session.affection} (delta={delta:+d}, mood={mood})")
    return session.affection
