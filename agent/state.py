from __future__ import annotations

from loguru import logger

from conversation.core.session import ConversationSession

# trigger_events 쿨다운 세션 속성 키
_FIRED_EVENTS_ATTR = "_fired_events"

# mood가 발동된 후 키워드 없는 턴이 N번 연속되면 neutral로 복귀 (기본값)
_MOOD_DECAY_DEFAULT = 3

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

    mood_decay_turns (YAML state 필드, 기본 3):
        키워드 매칭 없는 턴이 N번 연속되면 neutral로 자연 복귀.
        매 턴 즉시 neutral 리셋이 아니므로 감정이 짧게 유지된다.
    """
    state_cfg: dict = character.get("state", {})
    triggers: dict  = state_cfg.get("mood_triggers", {})
    decay_turns: int = int(state_cfg.get("mood_decay_turns", _MOOD_DECAY_DEFAULT))

    # 키워드 매칭
    matched_mood: str | None = None
    for mood_name, keywords in triggers.items():
        if any(kw in user_input for kw in keywords):
            matched_mood = mood_name
            break

    if matched_mood:
        # 새 mood 발동 → hold 카운터 리셋
        if session.mood != matched_mood:
            logger.debug(f"[state] mood 변경: {session.mood} → {matched_mood}")
        session.mood = matched_mood
        session.mood_hold = decay_turns
    elif session.mood != "neutral":
        # hold 카운터 감소 → 0이 되면 neutral 복귀
        hold = max(0, getattr(session, "mood_hold", 0) - 1)
        session.mood_hold = hold
        if hold == 0:
            logger.debug(f"[state] mood decay: {session.mood} → neutral")
            session.mood = "neutral"
    # neutral 상태에서 키워드 없음 → 그대로 유지

    return session.mood


def check_trigger_events(
    session: ConversationSession,
    user_input: str,
    character: dict,
) -> bool:
    """trigger_events 키워드 감지 → aff 점프 + mood 강제 전환.

    발동하면 True 반환 → router에서 일반 update_mood/update_affection 건너뜀.
    cooldown_turns 동안 동일 이벤트 재발동 방지.
    """
    events: dict = character.get("state", {}).get("trigger_events", {})
    if not events:
        return False

    # 쿨다운 관리 (세션 내 임시 속성)
    fired: dict[str, int] = getattr(session, _FIRED_EVENTS_ATTR, {})
    # 매 턴 쿨다운 감소
    fired = {k: v - 1 for k, v in fired.items() if v - 1 > 0}

    triggered = False
    for event_name, cfg in events.items():
        if event_name in fired:
            continue
        keywords: list[str] = cfg.get("keywords", [])
        if not any(kw in user_input for kw in keywords):
            continue

        # aff 변경 (aff_set 우선, 없으면 aff_delta)
        if "aff_set" in cfg:
            old = session.affection
            session.affection = max(0, min(100, int(cfg["aff_set"])))
            logger.info(f"[trigger] {event_name}: aff {old} → {session.affection} (set)")
        elif "aff_delta" in cfg:
            old = session.affection
            session.affection = max(0, min(100, session.affection + int(cfg["aff_delta"])))
            logger.info(f"[trigger] {event_name}: aff {old} → {session.affection} (delta={cfg['aff_delta']:+d})")

        # mood 강제 전환
        if "mood" in cfg:
            old_mood = session.mood
            session.mood = cfg["mood"]
            logger.info(f"[trigger] {event_name}: mood {old_mood} → {session.mood}")

        # 쿨다운 등록
        cooldown = int(cfg.get("cooldown_turns", 0))
        if cooldown > 0:
            fired[event_name] = cooldown

        triggered = True
        break  # 턴당 하나의 이벤트만 발동

    setattr(session, _FIRED_EVENTS_ATTR, fired)
    return triggered


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
