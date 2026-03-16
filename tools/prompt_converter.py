"""
prompt_converter.py — 프롬프트 변환 도구

사용자의 자연어 요청을 LLM에 최적화된 프롬프트로 변환한다.
대화 히스토리 / 장기 메모리를 격리하여 기능 세션에 기록하지 않는다.

LLM 파라미터:
  {
    "text": "<변환할 원본 텍스트>",
    "style": "명확하게" | "간결하게" | "상세하게" | "질문형" | "지시형",
    "language": "ko" | "en"    (선택, 기본 ko)
  }

지원 스타일:
  - "명확하게"   : 모호한 표현 제거, 핵심 의도를 명확히 재서술
  - "간결하게"   : 핵심만 남겨 짧게 압축
  - "상세하게"   : 배경, 목적, 제약 조건을 포함해 풍부하게 확장
  - "질문형"     : 지시문을 질문 형태로 전환
  - "지시형"     : 질문/서술을 명령형 지시문으로 전환
"""

from __future__ import annotations

import re

from tools.base import BaseTool

SUPPORTED_STYLES = {"명확하게", "간결하게", "상세하게", "질문형", "지시형"}


class PromptConverterTool(BaseTool):
    name = "prompt_convert"
    system_prompt = (
        "너는 프롬프트 변환 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        '{"text": "<변환할 원본 텍스트>", "style": "<변환 스타일>", "language": "ko" 또는 "en"}\n'
        "style 값: 명확하게 / 간결하게 / 상세하게 / 질문형 / 지시형\n"
        "language가 명시되지 않으면 ko로 설정해라."
    )

    # ── rule-based 변환 함수들 ──────────────────────────────────────────

    def _to_clear(self, text: str) -> str:
        """모호한 표현 제거 — 접속사/부사 정리, 주어 명시"""
        # 불필요한 중복 어미 압축
        text = re.sub(r"(것 같아요|것 같습니다|것 같아)", "입니다", text)
        text = re.sub(r"(좀|약간|어쩌면|혹시|아마)\s*", "", text)
        # 두 문장 이상이면 첫 문장만 핵심 서술로 정리
        sentences = [s.strip() for s in re.split(r"[.。!?！？]+", text) if s.strip()]
        if len(sentences) > 1:
            return sentences[0] + "."
        return text.strip()

    def _to_concise(self, text: str) -> str:
        """간결하게 — 조사/어미 외 불필요한 수식어 제거"""
        text = re.sub(r"(그리고|그래서|하지만|그런데|또한|또,?)\s*", "", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()

    def _to_detailed(self, text: str) -> str:
        """상세하게 — 배경·목적·제약 안내 문구 추가"""
        prefix = "[목적] "
        suffix = "\n[추가 맥락] 위 내용과 관련된 배경, 제약 조건, 기대 결과를 함께 설명해주세요."
        return prefix + text.strip() + suffix

    def _to_question(self, text: str) -> str:
        """지시문 → 질문형"""
        text = text.rstrip(".。!！")
        # 동사 어미 '해줘 / 해주세요 / 하라 / 해라' → '어떻게 하나요?'
        text = re.sub(r"(해줘|해주세요|하라|해라|해봐|하십시오)\s*$", "", text)
        if not text.endswith("?"):
            text = text.strip() + "는 어떻게 하나요?"
        return text

    def _to_imperative(self, text: str) -> str:
        """질문/서술 → 지시형"""
        text = text.rstrip("?？")
        # '~인가요 / ~나요 / ~까요' 어미 제거
        text = re.sub(r"(인가요|나요|까요|인지요|는지요)\s*$", "", text)
        if not text.endswith(("세요", "하라", "해라", "해줘", "하십시오")):
            text = text.strip() + "해주세요."
        return text

    # ──────────────────────────────────────────────────────────────────

    def execute(self, params: dict) -> str:
        text = params.get("text", "").strip()
        style = params.get("style", "명확하게")
        language = params.get("language", "ko")

        if not text:
            return "오류: 변환할 텍스트가 없습니다."
        if style not in SUPPORTED_STYLES:
            return (
                f"오류: 지원하지 않는 스타일 — '{style}'\n"
                f"지원 스타일: {', '.join(sorted(SUPPORTED_STYLES))}"
            )
        if language not in ("ko", "en"):
            return "오류: language는 'ko' 또는 'en'만 지원합니다."

        dispatch = {
            "명확하게": self._to_clear,
            "간결하게": self._to_concise,
            "상세하게": self._to_detailed,
            "질문형":   self._to_question,
            "지시형":   self._to_imperative,
        }
        converted = dispatch[style](text)

        return f"[{style}] {converted}"
