from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConversationSession:
    """대화 세션 상태를 보관한다.

    mood / affection 초기값은 CH_*.yaml의 state 필드에서 가져온다.
    dialogue_log는 단기 버퍼로 사용되며 memory/short_term.py가 이를 참조한다.
    session_id는 SessionManager가 부여하는 영속 식별자다 (None이면 비관리 세션).
    """

    character_id: str
    world_id: Optional[str] = None
    scenario_id: Optional[str] = None
    act_id: Optional[str] = None

    location: str = ""                      # 현재 장소명 (YAML act.location 값)
    location_context: Optional[str] = None  # 동적 장소 묘사 (YAML act 덮어쓰기)

    mood: str = "neutral"   # neutral / happy / affectionate / touched / curious / sad / embarrassed / annoyed / angry
    affection: int = 30     # 0~100

    turn_count: int = 0
    dialogue_log: list[dict] = field(default_factory=list)

    # SessionManager가 부여하는 영속 세션 ID (None = 비관리 세션, 하위 호환 유지)
    session_id: Optional[str] = None

    @classmethod
    def from_character(
        cls,
        character: dict,
        world_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        act_id: Optional[str] = None,
    ) -> "ConversationSession":
        """캐릭터 YAML의 state 필드로 초기값을 설정해 세션을 생성한다."""
        state = character.get("state", {})
        return cls(
            character_id=character["id"],
            world_id=world_id,
            scenario_id=scenario_id,
            act_id=act_id,
            mood=state.get("mood_default", "neutral"),
            affection=state.get("affection_default", 30),
        )

    def add_turn(self, user: str, assistant: str) -> None:
        """한 턴(사용자 + 어시스턴트 쌍)을 dialogue_log에 추가하고 turn_count를 올린다."""
        self.dialogue_log.append({"role": "user", "content": user})
        self.dialogue_log.append({"role": "assistant", "content": assistant})
        self.turn_count += 1
