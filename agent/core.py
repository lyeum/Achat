from __future__ import annotations

from loguru import logger

from agent.persona import load_persona
from config import get_config
from conversation.core.llm_client import LLMClient
from conversation.core.router import ConversationRouter
from conversation.core.session import ConversationSession
from conversation.loader.world_load import load_world
from memory.long_term import LongTermMemory


class Agent:
    """전체 대화 엔진을 조율하는 상위 오케스트레이터.

    phases.md 2-7:
    - 컴포넌트 초기화 (LLM, LongTermMemory, Session, Router)
    - chat(user_input) → 대화 모드 진입점
    - 모드 분기는 Phase 7에서 확장
    """

    def __init__(
        self,
        character_id: str,
        world_path: str,
        scenario_id: str | None = None,
        act_id: str | None = None,
        config: dict | None = None,
    ):
        self.cfg = config or get_config()

        # 캐릭터 / 세계관 로드
        self.character = load_persona(character_id)
        self.world = load_world(world_path)

        world_id = self.world.get("world_id")

        # 세션 초기화
        self.session = ConversationSession.from_character(
            self.character,
            world_id=world_id,
            scenario_id=scenario_id,
            act_id=act_id,
        )

        # LLM 로드
        logger.info("[agent] LLM 로딩 중...")
        self.llm = LLMClient(self.cfg)

        # 장기 메모리 초기화
        self.long_term = LongTermMemory(self.cfg)

        # 대화 라우터
        self.router = ConversationRouter(
            character=self.character,
            world=self.world,
            session=self.session,
            llm=self.llm,
            long_term=self.long_term,
            config=self.cfg,
        )

        logger.info(
            f"[agent] 초기화 완료 — 캐릭터: {self.character['name']} "
            f"mood: {self.session.mood} / affection: {self.session.affection}"
        )

    def chat(self, user_input: str, stream: bool = True) -> str:
        """대화 모드 진입점. user_input을 받아 캐릭터 응답을 반환한다."""
        return self.router.handle_turn(user_input, stream=stream)
