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

# ── speech.style preset 해석 ─────────────────────────────────────────────────
_STYLE_PRESETS: dict[str, str] = {
    "blunt": "말이 짧고 직접적이다. 불필요한 설명이나 완충 표현을 하지 않는다.",
    "soft":  "말투가 부드럽고 배려가 있다. 상대의 반응을 살피며 말한다.",
}

# ── speech.persona preset 해석 ───────────────────────────────────────────────
_PERSONA_PRESETS: dict[str, str] = {
    "cool_observant":  "감정을 억제하고 상황을 관찰하는 말투. 반응이 냉정하고 분석적이다.",
    "gentle_quiet":    "조용하고 온화한 말투. 상대를 배려하며 천천히 말한다.",
    "quiet_sensitive": "말수가 적지만 상대의 감정에 민감하게 반응한다.",
    "warm_dry":        "따뜻하지만 표현이 건조하다. 직접적이지 않게 감정을 전달한다.",
}

# ── personality preset 해석 ──────────────────────────────────────────────────
_PERSONALITY_PRESETS: dict[str, str] = {
    "calm":     "차분하고 안정된 태도. 쉽게 흔들리지 않는다.",
    "cynical":  "세상을 냉소적으로 본다. 기대치가 낮고 비틀린 시각으로 반응한다.",
    "tsundere": "직접적인 호감 표현을 피하지만 행동에서 드러난다. 부정하면서도 신경 쓴다.",
}

# ── affection tier 폴백 (character YAML에 affection 슬롯 없을 때) ────────────
_AFFECTION_FALLBACK: dict[str, str] = {
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

# ── emotion 폴백 (character YAML에 emotion 슬롯 없을 때) ────────────────────
_EMOTION_FALLBACK: dict[str, str] = {
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
        recent_ops: list[str] | None = None,
    ) -> list[dict]:
        """Layer A~D(+F)를 조립해 messages 리스트를 반환한다."""
        layer_b = self._layer_b(rag_results or [])
        system_parts = [self._layer_a(), layer_b]
        if vdb_results:
            system_parts.append(self._layer_c(vdb_results))
        if recent_ops:
            system_parts.append(self._layer_f(recent_ops))

        messages: list[dict] = [
            {"role": "system", "content": "\n\n".join(system_parts)}
        ]
        messages.extend(self._layer_d(short_buf))
        return messages

    # ── Layer 생성 ────────────────────────────────────────────────────────────

    def _layer_a(self) -> str:
        """캐릭터 시스템 프롬프트 — 스키마 슬롯 기반 조립.

        조립 순서:
          너는 {name}이다.
          {description}
          {speech.formality}을 사용한다.
          {speech.style}      ← preset 해석 또는 직접 텍스트
          {speech.persona}    ← preset 해석 또는 직접 텍스트
          {personality}       ← preset 해석 또는 직접 텍스트
          {affection[tier]}   ← 현재 tier 행동 텍스트 (YAML 우선, 폴백 사용)
          {emotion[mood]}     ← mood != neutral일 때만 삽입 (YAML 우선, 폴백 사용)
          {conv_hints}        ← response_length / openness / directness → 자연어
          {rules}             ← 각 항목을 문장으로
        """
        c = self.character
        tier = self._affection_tier()
        mood = self.session.mood

        parts: list[str] = []

        # 1. 이름
        name = c.get("name", "")
        if name:
            parts.append(f"너는 {name}이다.")

        # 2. 캐릭터 설명
        if desc := c.get("description", "").strip():
            parts.append(desc)

        # 3. 말투
        speech: dict = c.get("speech", {})
        formality = speech.get("formality", "").strip()
        if formality:
            parts.append(f"{formality}을 사용한다.")

        style_val = speech.get("style", "").strip()
        if style_val:
            parts.append(_STYLE_PRESETS.get(style_val, style_val))

        persona_val = speech.get("persona", "").strip()
        if persona_val:
            parts.append(_PERSONA_PRESETS.get(persona_val, persona_val))

        # 4. 성격
        personality_val = c.get("personality", "").strip()
        if personality_val:
            parts.append(_PERSONALITY_PRESETS.get(personality_val, personality_val))

        # 5. 친밀도 tier 행동
        aff_text = (
            c.get("affection", {}).get(tier)
            or _AFFECTION_FALLBACK.get(tier, "")
        )
        if aff_text:
            parts.append(aff_text)

        # 6. 감정 상태 (neutral이면 빈 문자열 → 삽입 안 함)
        if mood != "neutral":
            emotion_text = (
                c.get("emotion", {}).get(mood)
                or _EMOTION_FALLBACK.get(mood, "")
            )
            if emotion_text:
                parts.append(emotion_text)

        # 7. 대화 수위 파라미터
        parts.extend(self._conv_hints(c, tier))

        # 8. 규칙
        rules_list = c.get("rules", [])
        if rules_list and all(isinstance(r, str) for r in rules_list):
            parts.append(" ".join(rules_list))
        elif rules_list:
            parts.append(
                "캐릭터를 벗어나는 발언, AI임을 언급하는 발언, "
                "\"물론이죠\"·\"좋은 질문\" 같은 표현은 하지 않는다."
            )

        return " ".join(parts)

    def _layer_b(self, rag_results: list[str] | None = None) -> str:
        """세계관 설명 + 현재 Act 상황 + RAG 검색 결과."""
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
        """VDB 검색 결과를 캐릭터 관점으로 재서술한다."""
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
        return short_buf[-2:]

    def _layer_f(self, recent_ops: list[str]) -> str:
        """Layer F — 최근 기능 작업 컨텍스트."""
        ops_text = "\n".join(f"- {op}" for op in recent_ops[-5:])
        return (
            "[방금 수행한 작업]\n"
            f"{ops_text}\n"
            "위 작업에 대해 사용자가 질문하거나 대화를 시도할 수 있다. "
            "작업 내용을 인지한 상태로 자연스럽게 대응한다."
        )

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _conv_hints(character: dict, tier: str) -> list[str]:
        """conversation 파라미터를 자연어 지시문 리스트로 변환한다."""
        conv: dict = character.get("conversation", {})
        if not conv:
            return []

        hints: list[str] = []

        rl_val = conv.get("response_length", {})
        rl = rl_val.get(tier) if isinstance(rl_val, dict) else rl_val
        if rl is not None:
            if rl < 0.15:
                hints.append("한 문장 이내로 짧게 끊는다.")
            elif rl < 0.35:
                hints.append("한두 문장 정도로 답한다.")
            elif rl < 0.55:
                hints.append("두세 문장 수준으로 답한다.")
            elif rl < 0.70:
                hints.append("서너 문장 정도로 답할 수 있다.")
            else:
                hints.append("감정이나 생각을 여러 문장으로 표현할 수 있다.")

        op_val = conv.get("openness", {})
        op = op_val.get(tier) if isinstance(op_val, dict) else op_val
        if op is not None:
            if op < 0.1:
                hints.append("감정을 거의 드러내지 않는다.")
            elif op < 0.25:
                hints.append("감정을 드러내는 경우가 드물다.")
            elif op < 0.45:
                hints.append("가끔 감정이 말 속에 묻어난다.")
            elif op < 0.65:
                hints.append("감정을 자연스럽게 표현한다.")
            else:
                hints.append("감정을 솔직하게 표현한다.")

        dr = conv.get("directness")
        if dr is not None:
            if dr < 0.3:
                hints.append("말을 자주 돌려서 표현한다.")
            elif dr < 0.55:
                hints.append("말을 돌려 표현하는 경우가 많다.")
            elif dr < 0.7:
                hints.append("대체로 직접적으로 표현한다.")
            else:
                hints.append("하고 싶은 말을 직접적으로 표현한다.")

        return hints

    def _affection_tier(self) -> str:
        thresholds: dict = (
            self.character.get("state", {}).get("affection_thresholds", {})
        )
        aff = self.session.affection
        for tier, bounds in thresholds.items():
            if bounds[0] <= aff <= bounds[1]:
                return tier
        return "familiar"

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
        return max(1, len(text) // 2)
