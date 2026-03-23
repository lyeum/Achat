from __future__ import annotations

from pathlib import Path

from loguru import logger

from agent.persona import load_persona
from config import get_config
from conversation.core.llm_client import LLMClient
from conversation.core.router import ConversationRouter
from conversation.core.session import ConversationSession
from conversation.loader.world_load import load_world
from memory.long_term import LongTermMemory
from tools.base import BaseTool
from tools.folder.classifier import ClassifierTool
from tools.folder.converter import ConverterTool
from tools.folder.renamer import RenamerTool
from tools.prompt_converter import PromptConverterTool
from tools.search.local_search import LocalSearchTool
from tools.search.web_search import WebSearchTool

# 등록된 도구 목록 (name → instance)
_TOOLS: dict[str, BaseTool] = {
    t.name: t
    for t in [
        ClassifierTool(),
        ConverterTool(),
        RenamerTool(),
        PromptConverterTool(),
        LocalSearchTool(),
        WebSearchTool(),
    ]
}

# 도구 선택용 키워드 매핑 (자연어 힌트 → tool name)
# 순서 중요: 더 구체적인 키워드가 위에 있어야 "변환" 같은 공통 단어에 먼저 걸리지 않음
_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("프롬프트", "prompt", "명확하게", "간결하게", "상세하게", "질문형", "지시형"), "prompt_convert"),
    (("이름", "rename", "renamer", "파일명"), "file_rename"),
    (("분류", "정리", "폴더"), "folder_classify"),
    (("이미지", "image", "png", "jpg", "jpeg", "webp", "bmp", "tiff"), "image_convert"),
    (("인터넷", "웹 검색", "web", "구글", "검색해줘", "찾아봐"), "web_search"),
    (("검색", "search", "찾아", "파일 찾"), "local_search"),
]


_WORLD_DIR = Path(__file__).resolve().parent.parent / "conversation" / "world"


def _find_world_path(world_id: str | None) -> Path:
    """world_id에 해당하는 W_*.yaml 경로를 반환한다.

    world_id가 None이거나 일치하는 파일이 없으면 첫 번째 YAML을 반환한다.
    """
    if world_id:
        for p in sorted(_WORLD_DIR.glob("W_*.yaml")):
            try:
                w = load_world(p)
                if w.get("world_id") == world_id:
                    return p
            except Exception:
                continue

    worlds = sorted(_WORLD_DIR.glob("W_*.yaml"))
    if worlds:
        return worlds[0]
    raise FileNotFoundError(f"world YAML 없음: {_WORLD_DIR}")


def _select_tool(user_input: str) -> BaseTool | None:
    """user_input 에서 키워드를 감지해 도구를 선택한다."""
    lower = user_input.lower()
    for keywords, name in _KEYWORDS:
        if any(kw in lower for kw in keywords):
            return _TOOLS.get(name)
    return None


class Agent:
    """전체 대화 엔진을 조율하는 상위 오케스트레이터.

    phases.md 2-7:
    - 컴포넌트 초기화 (LLM, LongTermMemory, Session, Router)
    - chat(user_input) → 대화 모드 진입점
    - handle_input(user_input, mode) → 모드별 분기 (Phase 7)
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
        self._stub = self.cfg.get("model_backend") == "stub"

        # 캐릭터 / 세계관 로드
        self.character = load_persona(character_id)
        self.world = load_world(world_path)

        if self._stub:
            logger.info("[agent] stub 모드 — LLM/메모리 로딩 건너뜀")
            self.llm = None
            self.long_term = None
            self.session = None
            self.router = None
            return

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

    @classmethod
    def from_session(
        cls,
        state: "SessionState",  # type: ignore[name-defined]  # noqa: F821
        config: dict | None = None,
    ) -> "Agent":
        """SessionState로부터 Agent 인스턴스를 복원한다.

        세션 상태(mood / affection / turn_count / location)를 YAML 초기값 대신
        저장된 값으로 복원한다. dialogue_log는 런타임 전용이므로 빈 상태로 시작한다.
        """
        from conversation.session_manager import SessionState as _SS  # local import

        cfg = config or get_config()
        world_path = _find_world_path(state.world_id)

        agent = cls(
            character_id=state.char_id,
            world_path=str(world_path),
            scenario_id=state.scenario_id,
            act_id=state.act_id,
            config=cfg,
        )

        # stub 모드에서는 session이 None이므로 복원 불필요
        if agent.session is not None:
            agent.session.session_id = state.session_id
            agent.session.mood       = state.mood
            agent.session.affection  = state.affection
            agent.session.turn_count = state.turn_count
            if state.location:
                agent.session.location = state.location

        return agent

    def chat(self, user_input: str, stream: bool = True) -> str:
        """대화 모드 진입점. user_input을 받아 캐릭터 응답을 반환한다."""
        if self._stub:
            return f"[stub] 입력 받음: {user_input}"
        return self.router.handle_turn(user_input, stream=stream)

    def handle_input(self, user_input: str, mode: str = "chat", stream: bool = True) -> str:
        """모드별 분기 진입점.

        mode == "chat"     : 대화 엔진(Router) 경유
        mode == "function" : 도구 선택 → LLM 파라미터 파싱 → rule-based 실행
        """
        if mode == "chat":
            return self.chat(user_input, stream=stream)

        if mode == "function":
            return self._handle_function(user_input)

        logger.warning(f"[agent] 알 수 없는 모드: {mode!r} — chat 으로 대체")
        return self.chat(user_input, stream=stream)

    def _handle_function(self, user_input: str) -> str:
        """기능 모드 처리: 도구 선택 → LLM 파라미터 추출 → execute"""
        tool = _select_tool(user_input)
        if tool is None:
            registered = ", ".join(_TOOLS.keys())
            return (
                f"어떤 기능을 원하시는지 파악하지 못했습니다.\n"
                f"사용 가능한 도구: {registered}"
            )

        logger.info(f"[agent:function] 도구 선택 — {tool.name}")

        if self._stub:
            # stub 모드: LLM 없이 빈 params 로 execute
            params: dict = {}
        else:
            llm_output = self.llm.generate(
                messages=[
                    {"role": "system", "content": tool.system_prompt},
                    {"role": "user", "content": user_input},
                ],
                stream=False,
            )
            params = tool.parse_params(llm_output)
            logger.debug(f"[agent:function] 파싱된 파라미터 — {params}")

        return tool.execute(params)
