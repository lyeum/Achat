from __future__ import annotations

from pathlib import Path

from loguru import logger

from conversation.core.session import ConversationSession
from conversation.loader.character_load import load_character

# 캐릭터 파일 탐색 기준 디렉토리
_CHARACTER_DIR = Path(__file__).resolve().parent.parent / "conversation" / "character"


def load_persona(character_id: str) -> dict:
    """character_id에 해당하는 CH_*.yaml을 로드하여 dict를 반환한다.

    탐색 순서: CH_{character_id}.yaml → 대소문자 무시 glob 탐색
    """
    # 정확한 이름 먼저 시도
    exact = _CHARACTER_DIR / f"CH_{character_id}.yaml"
    if exact.exists():
        return load_character(exact)

    # 대소문자 무시 탐색
    for path in _CHARACTER_DIR.glob("CH_*.yaml"):
        if path.stem.lower() == f"ch_{character_id.lower()}":
            logger.warning(f"[persona] 대소문자 불일치로 로드: {path.name}")
            return load_character(path)

    raise FileNotFoundError(
        f"캐릭터 파일 없음: CH_{character_id}.yaml (탐색 경로: {_CHARACTER_DIR})"
    )


def swap_persona(
    session: ConversationSession,
    new_character_id: str,
    world_id: str | None = None,
    scenario_id: str | None = None,
    act_id: str | None = None,
    reset_state: bool = True,
) -> tuple[dict, ConversationSession]:
    """캐릭터를 핫스왑하고 새 (character, session) 쌍을 반환한다.

    Parameters
    ----------
    session        : 현재 세션 (참조용 — 직접 변경하지 않음)
    new_character_id : 전환할 캐릭터 ID
    world_id / scenario_id / act_id : 새 세션 컨텍스트
    reset_state    : True면 mood/affection을 캐릭터 초기값으로 리셋

    Returns
    -------
    (새 character dict, 새 ConversationSession)
    """
    character = load_persona(new_character_id)

    if reset_state:
        new_session = ConversationSession.from_character(
            character,
            world_id=world_id or session.world_id,
            scenario_id=scenario_id or session.scenario_id,
            act_id=act_id or session.act_id,
        )
    else:
        new_session = ConversationSession(
            character_id=character["id"],
            world_id=world_id or session.world_id,
            scenario_id=scenario_id or session.scenario_id,
            act_id=act_id or session.act_id,
            mood=session.mood,
            affection=session.affection,
            turn_count=session.turn_count,
            dialogue_log=list(session.dialogue_log),
        )

    logger.info(
        f"[persona] 핫스왑: {session.character_id} → {character['id']} "
        f"(reset_state={reset_state})"
    )
    return character, new_session
