from __future__ import annotations

from conversation.core.session import ConversationSession


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
