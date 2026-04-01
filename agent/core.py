from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from loguru import logger

# prompt_convert fallback: ASCII 전용 모델명 패턴 (한국어 \w 포함 방지)
_PROMPT_CONVERT_MODEL_RE = re.compile(
    r"(stable[\s\-]diffusion(?:\s+[a-zA-Z0-9._-]+){0,2}"
    r"|sdxl(?:\s+[a-zA-Z0-9._-]+){0,1}"
    r"|midjourney(?:\s+[a-zA-Z0-9._-]+){0,1}"
    r"|dall[\s\-]e(?:\s+[a-zA-Z0-9._-]+){0,1}"
    r"|flux(?:\s+[a-zA-Z0-9._-]+){0,2}"
    r"|leonardo(?:\s+[a-zA-Z0-9._-]+){0,2}"
    r"|imagen(?:\s+[a-zA-Z0-9._-]+){0,1})",
    re.IGNORECASE,
)


def _korean_ratio(text: str) -> float:
    """문자열 내 한글(가-힣) 비율 반환 (공백 제외)."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0
    return sum(1 for c in chars if "\uAC00" <= c <= "\uD7A3") / len(chars)


def _is_content_valid(content: str, src: str) -> bool:
    """src(user_input)가 주로 한국어인데 content 한국어 비율이 낮으면 비정상."""
    if not content:
        return False
    src_ko = _korean_ratio(src)
    # user_input 30% 이상 한국어인데 content가 src 한국어 비율의 50% 미만 → 비정상(영어 hallucination)
    if src_ko >= 0.3 and _korean_ratio(content) < src_ko * 0.5:
        return False
    return True

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

# LLM 주입 불필요 도구 — 모듈 로드 시 즉시 생성
# WebSearchTool은 LLM + character 주입이 필요하므로 Agent.__init__에서 생성
_STATIC_TOOLS: list[BaseTool] = [
    ClassifierTool(),
    ConverterTool(),
    RenamerTool(),
    LocalSearchTool(),
]

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

        # 최근 기능 작업 기록 (대화 모드로 전환 시 캐릭터 컨텍스트에 주입)
        self._recent_ops: list[str] = []

        if self._stub:
            logger.info("[agent] stub 모드 — LLM/메모리 로딩 건너뜀")
            self.llm = None
            self.long_term = None
            self.session = None
            self.router = None
            self.narrator = None
            # stub 모드: LLM 없음 — 도구에 None 주입
            self._tools: dict[str, BaseTool] = {
                t.name: t for t in _STATIC_TOOLS
            }
            self._tools[PromptConverterTool.name] = PromptConverterTool(llm=None, config=self.cfg)
            self._tools[WebSearchTool.name] = WebSearchTool()
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

        # Narrator 초기화 (NarrationMonitor가 bridge에서 사용)
        from conversation.narrator import Narrator
        self.narrator = Narrator(self.character, self.world, self.llm)

        # 도구 목록 (LLM 로딩 후 구성 — LLM + config/character 주입)
        self._tools = {t.name: t for t in _STATIC_TOOLS}
        self._tools[PromptConverterTool.name] = PromptConverterTool(llm=self.llm, config=self.cfg)
        self._tools[WebSearchTool.name] = WebSearchTool()

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
        """대화 모드 진입점. user_input을 받아 캐릭터 응답을 반환한다.

        최근 기능 작업(_recent_ops)이 있으면 라우터에 전달해
        캐릭터가 방금 수행한 작업을 인지하고 대화할 수 있게 한다.
        """
        if self._stub:
            return f"[stub] 입력 받음: {user_input}"
        return self.router.handle_turn(
            user_input, stream=stream, recent_ops=self._recent_ops or None
        )

    def handle_input(
        self,
        user_input: str,
        mode: str = "chat",
        stream: bool = True,
        tool_name: str = "",
        selected_path: str = "",
    ) -> str:
        """모드별 분기 진입점.

        mode == "chat"     : 대화 엔진(Router) 경유
        mode == "function" : 도구 선택 → LLM 파라미터 파싱 → rule-based 실행

        Parameters
        ----------
        tool_name : str
            UI 태그 선택으로 전달된 도구 이름. 빈 문자열이면 키워드 감지로 폴백.
        selected_path : str
            파일 탐색기에서 사용자가 선택한 디렉토리 경로.
            path가 필요한 도구(folder_classify / file_rename / image_convert / local_search)에
            주입되어 LLM 추출 경로를 덮어씀.
        """
        if mode == "chat":
            return self.chat(user_input, stream=stream)

        if mode == "function":
            return self._handle_function(user_input, tool_name=tool_name, selected_path=selected_path)

        logger.warning(f"[agent] 알 수 없는 모드: {mode!r} — chat 으로 대체")
        return self.chat(user_input, stream=stream)

    def _select_tool(self, user_input: str) -> BaseTool | None:
        """user_input에서 키워드를 감지해 도구를 선택한다 (폴백용)."""
        lower = user_input.lower()
        for keywords, name in _KEYWORDS:
            if any(kw in lower for kw in keywords):
                return self._tools.get(name)
        return None

    def _handle_function(self, user_input: str, tool_name: str = "", selected_path: str = "") -> str:
        """기능 모드 처리: 도구 선택 → LLM 파라미터 추출 → execute

        tool_name이 제공되면 키워드 감지 없이 해당 도구를 직접 사용한다.
        selected_path가 제공되면 도구의 경로 파라미터를 덮어쓴다.
        """
        # 도구 선택: 명시적 이름 우선, 없으면 키워드 감지 폴백
        if tool_name:
            tool = self._tools.get(tool_name)
            if tool is None:
                return f"알 수 없는 도구: '{tool_name}'"
        else:
            tool = self._select_tool(user_input)
            if tool is None:
                registered = ", ".join(self._tools.keys())
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
                mode="function",
            )
            params = tool.parse_params(llm_output)
            logger.debug(f"[agent:function] 파싱된 파라미터 — {params}")

            # prompt_convert 전용: LLM 추출 실패 시 fallback
            if tool.name == "prompt_convert":
                # model: 비면 regex로 직접 추출
                if not params.get("model"):
                    m = _PROMPT_CONVERT_MODEL_RE.search(user_input)
                    if m:
                        params["model"] = m.group(1).strip()
                        logger.warning(
                            f"[agent:function] model 필드 LLM 추출 실패 — regex fallback: {params['model']!r}"
                        )
                # content: 비거나 한국어 입력 대비 한국어 비율이 낮으면 user_input으로 대체
                if not _is_content_valid(params.get("content", ""), user_input):
                    params["content"] = user_input
                    logger.warning("[agent:function] content 필드 LLM 추출 실패 — user_input으로 대체")

        # 사용자가 선택한 경로를 LLM 추출값보다 우선 적용
        _PATH_PARAM: dict[str, str] = {
            "folder_classify": "target",
            "file_rename":     "target",
            "image_convert":   "target",
            "local_search":    "path",
        }
        if selected_path and tool.name in _PATH_PARAM:
            params[_PATH_PARAM[tool.name]] = selected_path

        result = tool.execute(params)

        # 최근 기능 작업 기록 — 대화 모드 컨텍스트 주입용
        summary = self._summarize_op(tool.name, params, result)
        self._recent_ops.append(summary)
        if len(self._recent_ops) > 5:
            self._recent_ops.pop(0)

        return result

    _OP_LABELS: dict[str, str] = {
        "folder_classify": "폴더 분류",
        "file_rename":     "파일 이름 변경",
        "file_convert":    "파일 변환",
        "image_convert":   "이미지 변환",
        "local_search":    "파일 검색",
        "web_search":      "웹 검색",
        "prompt_convert":  "프롬프트 변환",
    }

    def _summarize_op(self, tool_name: str, params: dict, result: str) -> str:
        """기능 실행 결과를 한 줄 요약으로 변환한다."""
        label = self._OP_LABELS.get(tool_name, tool_name)
        # 결과 첫 줄(혹은 최대 60자)을 요약으로 사용
        first_line = result.split("\n")[0].split("<br>")[0].strip()
        short = first_line[:60] + ("..." if len(first_line) > 60 else "")
        # 경로/쿼리 힌트 추출
        hint = ""
        if "target" in params:
            hint = f" (대상: {params['target']})"
        elif "query" in params:
            hint = f" (검색어: {params['query']})"
        return f"[{label}]{hint} → {short}"
