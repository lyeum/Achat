"""conversation/narrator.py — 장면 서술 생성.

대화 외 시점에서 장소·상황을 소설 서술체로 출력한다.

호출 시점
---------
- 세션 시작: describe_session_start()
- 장소 이동: describe_arrival()
- 사용자 행동(*...*): describe_action()
- 감정 변화/클라이맥스: describe_emotion()
"""

from __future__ import annotations

from loguru import logger

_ARRIVAL_PROMPT = """\
아래 예시처럼 장소 도착 장면을 3인칭 서술체로 묘사해.
감각적 디테일 포함. 3~5문장 이내.

[예시 — 카페]
카페 안은 조용했다. 창가에 빛이 들어와 먼지를 느릿하게 날렸다. 하루는 자리를 찾아 안쪽으로 걸어들어갔다.

[예시 — 옥상]
바람이 먼저였다. 옥상 난간 너머로 도시가 낮게 깔려 있었다. 하루는 거기 서서 잠깐 아무 말도 하지 않았다.

---
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
아래 예시처럼 장면의 시작을 3인칭 서술체로 묘사해.
두 사람이 처음 같은 공간에 있게 된 순간처럼. 3~5문장 이내.

[예시 — 오후 카페]
오후의 빛이 창을 비스듬하게 넘어왔다. 카페는 조용했고, 사람들의 말소리가 멀게 들렸다. 하루는 그쪽 자리에 먼저 와 있었다.

[예시 — 저녁 공원]
해가 지고 있었다. 벤치 위로 오렌지빛이 길게 드리웠다. 하루는 무릎 위에 손을 얹은 채 앉아 있었다.

---
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

_ACTION_PROMPT = """\
아래 예시처럼 사용자의 행동에 반응하는 장면을 3인칭 서술체로 묘사해.
캐릭터의 반응(시선, 움직임, 표정)을 짧게 포함. 2~3문장 이내.

[예시 — 자리 이동]
창가에 빛이 들어왔다. 하루의 시선이 잠깐 따라갔다.

[예시 — 물건 건네기]
손이 내밀어졌다. 하루는 잠시 그것을 바라보다 받았다.

[예시 — 자리에 앉기]
의자 끄는 소리가 났다. 하루는 그쪽을 잠깐 봤다가 시선을 내렸다.

---
캐릭터: {char_name}
행동 내용: {action_text}
현재 감정: {mood}
"""

_EMOTION_PROMPT = """\
아래 예시처럼 캐릭터의 감정 변화를 행동과 짧은 서술로 묘사해.
대화체 없이 3인칭 서술체. 2~3문장 이내.

[예시 — mood: touched]
잠깐 말이 끊겼다. 하루는 시선을 내렸다가 다시 들었다.

[예시 — mood: annoyed]
대답이 짧아졌다. 손가락이 테이블 위를 한 번 두드렸다.

[예시 — mood: affectionate]
말이 느려졌다. 먼 곳을 보는 것처럼 눈빛이 잠깐 흐려졌다.

[예시 — mood: sad]
아무 말도 없었다. 하루는 잠시 창밖을 봤다.

---
캐릭터: {char_name}
현재 감정: {mood}
친밀도 상태: {affection_tier}
직전 대화:
{recent_exchange}
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
            max_tokens=150,
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
            max_tokens=150,
        ).strip()
        logger.debug("[narrator] 세션 시작 서술 생성")
        return result

    def describe_action(self, action_text: str, mood: str = "neutral") -> str:
        """사용자 행동(*...*) 입력에 대한 캐릭터 반응 및 장면 묘사."""
        prompt = _ACTION_PROMPT.format(
            char_name   = self._char_name,
            action_text = action_text,
            mood        = mood,
        )
        result = self._llm.generate(
            [{"role": "user", "content": prompt}],
            stream=False,
            max_tokens=150,
        ).strip()
        logger.debug(f"[narrator] 행동 반응 서술 생성: '{action_text}'")
        return result

    def describe_emotion(
        self,
        mood: str,
        affection_tier: str,
        recent_exchange: list[dict],
    ) -> str:
        """mood 변화 또는 감정 클라이맥스 순간의 캐릭터 내면/행동 묘사."""
        exchange_text = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in recent_exchange[-4:]
        )
        prompt = _EMOTION_PROMPT.format(
            char_name       = self._char_name,
            mood            = mood,
            affection_tier  = affection_tier,
            recent_exchange = exchange_text,
        )
        result = self._llm.generate(
            [{"role": "user", "content": prompt}],
            stream=False,
            max_tokens=150,
        ).strip()
        logger.debug(f"[narrator] 감정 묘사 생성: mood={mood}, tier={affection_tier}")
        return result
