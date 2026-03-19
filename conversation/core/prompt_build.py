from __future__ import annotations

from typing import Callable, Optional

from conversation.core.session import ConversationSession

# 토큰 예산 (대화품질.md Layer 설계 기준)
BUDGET = {
    "layer_a": 300,    # 캐릭터 시스템 프롬프트 (고정)
    "layer_b": 200,    # 세계관 + Act (고정)
    "layer_c": 150,    # VDB 검색 결과 (동적, 없으면 0)
    "layer_d": 300,    # 단기 히스토리 (동적)
    "generation": 512,
}

# affection tier → Layer A 기본 톤 지시문 (캐릭터 YAML에 tone_guide 없을 때 폴백)
_TONE_DEFAULT: dict[str, str] = {
    "stranger":     "처음 만난 사이. 대화를 짧게 끊으려 하고 개인적인 반응을 거의 하지 않는다.",
    "acquaintance": "기본 대화는 가능하지만 경계가 있다. 개인적인 이야기는 아직 조심스럽다.",
    "familiar":     "조금 편해진 상태. 가끔 관심이 묻어나오지만 여전히 담담하다.",
    "friendly":     "자연스럽게 대화한다. 배려가 짧은 말 속에 드러나기 시작한다.",
    "close":        "배려가 자연스럽게 드러난다. 솔직한 반응을 자주 보인다.",
    "intimate":     "깊은 신뢰 상태. 감정을 짧게라도 솔직하게 표현한다.",
    # 구버전 호환
    "low":  "상대에게 아직 경계심을 갖고 있다. 단답형으로 짧게 말하고 가드를 높게 유지한다.",
    "mid":  "보통 상태다. 가끔 솔직한 반응을 보이기도 한다.",
    "high": "마음이 조금 열렸다. 응답이 조금 길어지고 부드러워진다.",
}

# mood → 추가 행동 힌트
_MOOD_HINT: dict[str, str] = {
    "happy":        "기분이 좋은 상태다. 반응이 약간 빨라지고 말이 조금 더 나온다.",
    "affectionate": "상대에게 마음이 기울어 있다. 배려가 말 속에 묻어난다.",
    "touched":      "뭔가 마음에 닿은 상태다. 말이 잠시 느려지거나 짧아질 수 있다.",
    "curious":      "궁금한 것이 생겼다. 짧게 되묻거나 관심을 드러낸다.",
    "sad":          "마음이 조금 가라앉아 있다. 말수가 줄고 반응이 느려진다.",
    "embarrassed":  "당황하거나 어색한 상태다. 말이 짧아지거나 화제를 돌리기도 한다.",
    "annoyed":      "짜증이 난 상태다. 반응이 더 퉁명스럽고 짧아진다.",
    "angry":        "화가 난 상태다. 말이 차갑고 날카로워진다.",
    "neutral":      "",
}


class PromptBuilder:
    """Layer A~E를 조립해 ChatML messages 리스트를 반환한다.

    Parameters
    ----------
    character:
        load_character()가 반환한 캐릭터 dict.
    world:
        load_world()가 반환한 세계관 dict.
    session:
        현재 ConversationSession.
    count_tokens_fn:
        (text: str) -> int 형태의 토큰 카운트 함수.
        미제공 시 한국어 기준 간이 추정(~2자/토큰)을 사용한다.
    """

    def __init__(
        self,
        character: dict,
        world: dict,
        session: ConversationSession,
        count_tokens_fn: Optional[Callable[[str], int]] = None,
    ):
        self.character = character
        self.world = world
        self.session = session
        self._count = count_tokens_fn or self._estimate

    # ── 공개 메서드 ───────────────────────────────────────────────────────────

    def assemble(
        self,
        short_buf: list[dict],
        vdb_results: list[str],
        rag_results: list[str] | None = None,
    ) -> list[dict]:
        """Layer A~D를 조립해 messages 리스트를 반환한다.

        Layer E(현재 사용자 입력)는 호출 측에서 마지막에 append한다.

        Parameters
        ----------
        vdb_results : 장기 메모리 VDB 검색 결과 (Layer C — 우선순위 높음)
        rag_results : 세계관 RAG 검색 결과 (Layer B에 병합 — 우선순위 낮음)
        """
        layer_b = self._layer_b(rag_results or [])
        system_parts = [self._layer_a(), layer_b]
        if vdb_results:
            system_parts.append(self._layer_c(vdb_results))

        messages: list[dict] = [
            {"role": "system", "content": "\n\n".join(system_parts)}
        ]
        messages.extend(self._layer_d(short_buf))
        return messages

    # ── Layer 생성 ────────────────────────────────────────────────────────────

    def _layer_a(self) -> str:
        """캐릭터 시스템 프롬프트: 이름·설명·말투·현재 상태·금지 규칙."""
        c = self.character
        rules = "\n".join(f"- {r}" for r in c.get("rules", []))
        tier = self._affection_tier()

        # 톤: 캐릭터 YAML tone_guide 우선, 없으면 기본값
        tone_guide: dict = c.get("state", {}).get("tone_guide", {})
        tone = tone_guide.get(tier) or _TONE_DEFAULT.get(tier, _TONE_DEFAULT["mid"])

        # mood 힌트
        mood_hint = _MOOD_HINT.get(self.session.mood, "")

        # 대화 수위 파라미터
        conv = c.get("conversation", {})
        conv_lines = []
        if "response_length" in conv:
            lvl = conv["response_length"].get(tier, conv["response_length"].get("mid", 0.5))
            if lvl <= 0.3:
                conv_lines.append("응답을 매우 짧게 유지한다 (1~2문장 이내).")
            elif lvl <= 0.6:
                conv_lines.append("응답 길이는 보통 수준으로 유지한다.")
            else:
                conv_lines.append("응답이 자연스럽게 조금 길어질 수 있다.")
        if "openness" in conv:
            lvl = conv["openness"].get(tier, conv["openness"].get("mid", 0.4))
            if lvl <= 0.2:
                conv_lines.append("자신의 감정이나 생각을 거의 드러내지 않는다.")
            elif lvl <= 0.5:
                conv_lines.append("간간이 자신의 생각을 짧게 내비친다.")
            else:
                conv_lines.append("비교적 솔직하게 자신의 생각을 표현한다.")
        if "directness" in conv:
            lvl = conv["directness"]
            if lvl <= 0.3:
                conv_lines.append("하고 싶은 말을 돌려서 표현한다.")
            elif lvl >= 0.7:
                conv_lines.append("하고 싶은 말을 직접적으로 표현한다.")

        state_parts = [f"mood: {self.session.mood}  /  affection tier: {tier}", tone]
        if mood_hint:
            state_parts.append(mood_hint)
        if conv_lines:
            state_parts.append("\n".join(conv_lines))

        return "\n".join([
            f"너의 이름은 {c['name']}이다.",
            "",
            f"[성격 / 설명]\n{c.get('description', '').strip()}",
            "",
            f"[말투 규칙]\n{c.get('speech_style', '').strip()}",
            "",
            "[현재 감정 상태]\n" + "\n".join(state_parts),
            "",
            f"[금지 규칙]\n{rules}",
        ])

    def _layer_b(self, rag_results: list[str] | None = None) -> str:
        """세계관 설명 + 현재 Act 상황 + RAG 검색 결과 (있을 때).

        우선순위: 장기 메모리(Layer C) > 세계관 RAG
        RAG 결과는 Layer B 말미에 병합하여 ~350tok 합산 예산 안에서 처리.
        """
        world_desc = self.world.get("description", "").strip()
        act = self._current_act()

        parts = [f"[세계관]\n{world_desc}"]
        if self.session.location_context:
            parts.append(f"[현재 상황]\n{self.session.location_context}")
        elif act:
            location = act.get("location", "")
            ctx = act.get("context", "").strip()
            parts.append(f"[현재 상황 — {location}]\n{ctx}")
        if rag_results:
            rag_text = "\n".join(f"- {r}" for r in rag_results)
            parts.append(f"[세계관 참고]\n{rag_text}")

        return "\n\n".join(parts)

    def _layer_c(self, vdb_results: list[str]) -> str:
        """VDB 검색 결과를 캐릭터 관점으로 재서술한다.

        memory_voice 필드를 참고용 힌트로 함께 삽입해
        모델이 캐릭터 목소리로 기억을 표현하도록 유도한다.
        """
        voice_hint = self.character.get("memory_voice", "").strip()
        parts = [f"- {r}" for r in vdb_results]
        hint = f"\n(기억 표현 방식: {voice_hint})" if voice_hint else ""
        return "[어렴풋한 기억]\n" + "\n".join(parts) + hint

    def _layer_d(self, short_buf: list[dict]) -> list[dict]:
        """단기 히스토리 — 토큰 예산 초과 시 턴 수를 점진적으로 축소한다."""
        for n_turns in (5, 3, 2):
            sliced = short_buf[-(n_turns * 2):]
            total = sum(self._count(m["content"]) for m in sliced)
            if total <= BUDGET["layer_d"]:
                return sliced
        # 최소 1턴(user+assistant 쌍) 보장
        return short_buf[-2:]

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────

    def _affection_tier(self) -> str:
        thresholds: dict = (
            self.character.get("state", {}).get("affection_thresholds", {})
        )
        aff = self.session.affection
        for tier, bounds in thresholds.items():
            if bounds[0] <= aff <= bounds[1]:
                return tier
        return "mid"

    def _current_act(self) -> Optional[dict]:
        if not (self.session.scenario_id and self.session.act_id):
            return None
        for scenario in self.world.get("scenarios", []):
            if scenario.get("scenario_id") == self.session.scenario_id:
                for act in scenario.get("acts", []):
                    if act.get("act_id") == self.session.act_id:
                        return act
        return None

    @staticmethod
    def _estimate(text: str) -> int:
        """토크나이저 없을 때 사용하는 간이 추정 (한국어 ~2자/토큰)."""
        return max(1, len(text) // 2)
