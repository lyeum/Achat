from __future__ import annotations

from conversation.core.session import ConversationSession

SHORT_TERM_N = 5  # 단기 버퍼 최대 턴 수 — 초과 시 session_context로 evict


def get_recent(session: ConversationSession, n: int | None = None) -> list[dict]:
    """dialogue_log에서 최근 n턴(user+assistant 쌍)을 반환한다.

    n이 None이면 session이 속한 config의 short_term_n을 사용하지 않고
    호출자(router)가 PromptBuilder에서 Layer D 예산으로 직접 관리하므로
    전체 로그를 그대로 반환한다. n을 명시하면 최대 n턴으로 자름.
    """
    log = session.dialogue_log
    if n is None:
        return log
    return log[-(n * 2):]


def evict_to_context(session: ConversationSession) -> bool:
    """dialogue_log가 SHORT_TERM_N을 초과하면 가장 오래된 턴을 session_context에 누적한다.

    한 번 호출에 가장 오래된 1턴(user+assistant 쌍)을 evict한다.
    evict가 발생하면 True, 조건 미충족이면 False를 반환한다.

    session_context 최대 길이는 600자로 제한해 Layer E 예산을 보호한다.
    """
    if len(session.dialogue_log) <= SHORT_TERM_N * 2:
        return False

    # 가장 오래된 턴(index 0, 1) 추출
    user_msg = session.dialogue_log.pop(0)
    asst_msg = session.dialogue_log.pop(0)

    u = user_msg.get("content", "").strip()
    a = asst_msg.get("content", "").strip()
    snippet = f"사용자: {u}\n캐릭터: {a}"

    if session.session_context:
        merged = session.session_context + "\n" + snippet
    else:
        merged = snippet

    # 600자 초과 시 앞부분을 잘라냄
    if len(merged) > 600:
        merged = merged[-600:]

    session.session_context = merged
    return True
