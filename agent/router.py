"""agent/router.py — 슬래시 명령어 감지 및 pre-processing.

대화 루프에서 사용자 입력을 받아:
  1. 슬래시 명령어 여부 판별 (/캐릭터변경, /초기화, /상태, /도움말, /quit 등)
  2. 명령어면 CommandResult(type, args) 반환
  3. 일반 대화면 CommandResult(NONE) 반환

사용 예:
    from agent.router import CommandRouter, CommandType

    router = CommandRouter()
    result = router.parse("/캐릭터변경 hana")
    if result.type == CommandType.CHANGE_CHARACTER:
        agent.swap_character(result.args["character_id"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class CommandType(Enum):
    NONE             = auto()   # 일반 대화 — 라우팅 없음
    CHANGE_CHARACTER = auto()   # /캐릭터변경 <id>
    RESET            = auto()   # /초기화
    STATUS           = auto()   # /상태
    HELP             = auto()   # /도움말
    QUIT             = auto()   # /quit | /종료


@dataclass
class CommandResult:
    type: CommandType
    args: dict = field(default_factory=dict)

    @property
    def is_command(self) -> bool:
        return self.type is not CommandType.NONE


# ── 명령어 테이블 ─────────────────────────────────────────────────────────────
# (trigger_strings, CommandType, has_arg)
# has_arg=True: 명령어 뒤에 오는 첫 토큰을 args["character_id"] 등에 저장

_COMMAND_TABLE: list[tuple[tuple[str, ...], CommandType, bool]] = [
    (("/캐릭터변경", "/character", "/char"), CommandType.CHANGE_CHARACTER, True),
    (("/초기화", "/reset"),                  CommandType.RESET,             False),
    (("/상태", "/status"),                   CommandType.STATUS,            False),
    (("/도움말", "/help", "/?"),             CommandType.HELP,              False),
    (("/quit", "/종료", "/exit"),            CommandType.QUIT,              False),
]

_HELP_TEXT = """\
사용 가능한 명령어:
  /캐릭터변경 <id>   — 캐릭터 핫스왑 (예: /캐릭터변경 hana)
  /초기화            — 세션 초기화 (대화 기록 삭제)
  /상태              — 현재 mood / affection 출력
  /도움말            — 이 도움말 출력
  /quit              — 대화 종료
"""


class CommandRouter:
    """슬래시 명령어를 감지하고 CommandResult를 반환하는 pre-processor."""

    def parse(self, user_input: str) -> CommandResult:
        """user_input을 분석해 CommandResult를 반환한다.

        명령어가 아니면 CommandResult(type=NONE)을 반환한다.
        """
        text = user_input.strip()
        if not text.startswith("/"):
            return CommandResult(type=CommandType.NONE)

        tokens = text.split()
        trigger = tokens[0].lower()

        for triggers, cmd_type, has_arg in _COMMAND_TABLE:
            if trigger in triggers:
                args: dict = {}
                if has_arg and len(tokens) > 1:
                    args["character_id"] = tokens[1]
                return CommandResult(type=cmd_type, args=args)

        # 알 수 없는 슬래시 명령어 → HELP 안내
        return CommandResult(type=CommandType.HELP)

    @staticmethod
    def help_text() -> str:
        return _HELP_TEXT
