"""conversation/narrator.py — 장면 서술 생성.

대화 외 시점에서 장소·상황을 소설 서술체로 출력한다.

호출 시점
---------
- 세션 시작: describe_session_start()
- 장소 이동: describe_arrival()
"""

from __future__ import annotations

from loguru import logger

_ARRIVAL_PROMPT = """\
캐릭터: {char_name}
세계관: {world_desc}
장소: {location_name}
장소 분위기: {location_context}
캐릭터의 현재 감정: {mood}

위 장소에 도착하는 장면을 소설 서술체로 3~5문장 써.
조건:
- 3인칭 시점, 대화체 없음
- 감각적 디테일 포함 (빛, 소리, 공기, 온도)
- {char_name}가 그 공간에 존재하는 방식 묘사
- 장면 전환 나레이션처럼, 담백하게
"""

_SESSION_START_PROMPT = """\
캐릭터: {char_name}
세계관: {world_desc}
시작 장소: {location}
상황: {context}

이 장면의 시작을 소설 서술체로 3~5문장 써.
조건:
- 3인칭 시점, 대화체 없음
- 감각적 디테일 포함 (빛, 소리, 공기, 시간대)
- 두 사람이 처음 같은 공간에 있게 된 순간처럼
- 담백하고 여백 있는 문체
"""


class Narrator:
    """LLM을 이용해 장면 서술을 생성한다."""

    def __init__(self, character: dict, world: dict, llm):
        self._char_name  = character.get("name", "")
        self._world_desc = world.get("description", "").strip()
        self._llm        = llm

    def describe_arrival(
        self,
        location_name: str,
        location_context: str,
        mood: str = "neutral",
    ) -> str:
        """장소 도착 서술을 생성해 반환한다."""
        prompt = _ARRIVAL_PROMPT.format(
            char_name        = self._char_name,
            world_desc       = self._world_desc,
            location_name    = location_name,
            location_context = location_context,
            mood             = mood,
        )
        result = self._llm.generate(
            [{"role": "user", "content": prompt}],
            stream=False,
            max_tokens=250,
        ).strip()
        logger.debug(f"[narrator] 도착 서술 생성: '{location_name}'")
        return result

    def describe_session_start(
        self,
        location: str,
        context: str,
    ) -> str:
        """세션 시작 장면 서술을 생성해 반환한다."""
        prompt = _SESSION_START_PROMPT.format(
            char_name  = self._char_name,
            world_desc = self._world_desc,
            location   = location,
            context    = context,
        )
        result = self._llm.generate(
            [{"role": "user", "content": prompt}],
            stream=False,
            max_tokens=250,
        ).strip()
        logger.debug("[narrator] 세션 시작 서술 생성")
        return result
