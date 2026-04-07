from __future__ import annotations

from loguru import logger

from agent import state as state_mod
from conversation.core.llm_client import LLMClient
from conversation.core.prompt_build import PromptBuilder
from conversation.core.session import ConversationSession
from memory import short_term, summarizer
from memory.long_term import LongTermMemory
from rag.retrieve import WorldRetriever


class ConversationRouter:
    """한 턴의 대화를 처리하는 Post-processing 라우터.

    phases.md 2-6 / 3-3 handle_turn() 구현:
    1. short_buf 수집
    2. 장기 메모리 VDB 검색
    3. 세계관 RAG 검색
    4. Context Assembly (PromptBuilder)
    5. LLM 생성
    6. mood / affection 상태 업데이트
    7. 세션에 턴 기록
    8. 요약 트리거 체크 → VDB 저장
    """

    def __init__(
        self,
        character: dict,
        world: dict,
        session: ConversationSession,
        llm: LLMClient,
        long_term: LongTermMemory,
        config: dict,
    ):
        self.character = character
        self.world = world
        self.session = session
        self.llm = llm
        self.long_term = long_term
        self.cfg = config

        self.builder = PromptBuilder(
            character, world, session, count_tokens_fn=llm.count_tokens
        )
        self.rag     = WorldRetriever(config)
        self._trigger_n: int    = config.get("memory_trigger_n", 10)
        self._aff_gate: float   = config.get("aff_gate_threshold", 0.6)

    def handle_turn(
        self,
        user_input: str,
        stream: bool = True,
        recent_ops: list[str] | None = None,
    ) -> str:
        """user_input을 받아 캐릭터 응답 문자열을 반환한다.

        Parameters
        ----------
        recent_ops:
            최근 기능 모드에서 수행한 작업 요약 목록.
            제공되면 시스템 프롬프트에 주입되어 캐릭터가 수행 내용을 인지한다.
        """
        # 0. 장소 이동 감지 → session.location_context / act_id 업데이트
        self._handle_location(user_input)

        # 1. 단기 버퍼
        short_buf = short_term.get_recent(self.session)

        # 2. 장기 메모리 VDB 검색 (우선순위 높음 → Layer C)
        vdb_results = self.long_term.query(user_input, self.session.character_id)

        # 3. 세계관 RAG 검색 (우선순위 낮음 → Layer B 병합)
        rag_results = self.rag.query(user_input)

        # 4. Context Assembly
        messages = self.builder.assemble(
            short_buf=short_buf,
            vdb_results=vdb_results,
            rag_results=rag_results,
            recent_ops=recent_ops,
            user_input=user_input,
        )
        messages.append({"role": "user", "content": user_input})

        # 5. LLM 생성
        response = self.llm.generate(messages, stream=stream)

        # 6. mood / affection 업데이트 (사용자 입력 기준)
        new_mood = state_mod.update_mood(self.session, user_input, self.character)
        # semantic 중요도 게이팅: 잡담(0.5) 발화는 affection 변화 억제
        importance = summarizer.score_importance(user_input)
        if importance >= self._aff_gate:
            state_mod.update_affection(self.session, new_mood, self.character)
        else:
            logger.debug(
                f"[router] aff 게이팅 — importance={importance:.2f} < {self._aff_gate} → 변화 억제"
            )

        # 7. 세션 기록
        self.session.add_turn(user_input, response)
        logger.debug(
            f"[router] turn={self.session.turn_count} "
            f"mood={self.session.mood} aff={self.session.affection}"
        )

        # 8. 요약 트리거
        if summarizer.check_trigger(self.session, self._trigger_n):
            self._run_summarizer()

        # 9. play_log 기록은 호출자(bridge.py or conversation/main.py)가 담당
        #    training/log/conversation_logger.py ConversationLogger.on_turn() 참조

        return response

    # ── 내부 헬퍼 ──────────────────────────────────────────────────────────────

    def _handle_location(self, user_input: str) -> None:
        """이동 의도 감지 → YAML act 매칭 or 동적 장소 생성.

        session.act_id / session.location_context를 업데이트한다.
        장소 이동 시 캐릭터 응답의 *묘사* 포맷으로 자연스럽게 반영된다.
        """
        from rag.world_nav import detect_move_intent, find_or_create_location

        location_name = detect_move_intent(user_input, self.llm)
        if not location_name:
            return

        # YAML 기존 acts 매칭 (location 필드 부분 일치)
        for scenario in self.world.get("scenarios", []):
            for act in scenario.get("acts", []):
                if location_name in act.get("location", ""):
                    self.session.scenario_id      = scenario["scenario_id"]
                    self.session.act_id           = act["act_id"]
                    self.session.location         = act["location"]
                    self.session.location_context = None
                    logger.info(f"[router] 장소 이동 (YAML): {act['location']}")
                    return

        # RAG 검색 or LLM 생성
        world_desc = self.world.get("description", "")
        desc = find_or_create_location(location_name, world_desc, self.rag, self.llm)
        self.session.location         = location_name
        self.session.location_context = f"{location_name}\n{desc}"
        logger.info(f"[router] 동적 장소 설정: '{location_name}'")

    def _run_summarizer(self) -> None:
        logger.info(
            f"[router] 요약 트리거 (turn={self.session.turn_count}) — VDB 저장 시도"
        )
        summary = summarizer.summarize(
            self.session.dialogue_log, self.llm, self._trigger_n
        )
        score = summarizer.score_importance(summary)
        summarizer.write_to_vdb(
            summary, score, self.session, self.long_term, self.character,
            trigger_n=self._trigger_n,
        )
