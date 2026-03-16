"""
base.py — 기능 모드 도구 공통 인터페이스

모든 도구는 BaseTool을 상속하여 구현:
  - name: 도구 식별자
  - system_prompt: LLM에 전달할 기능 전용 시스템 프롬프트
  - parse_params(llm_response): LLM 출력 → dict 파싱
  - execute(params): rule-based 실행 → 결과 문자열 반환
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod


class BaseTool(ABC):
    name: str = ""
    system_prompt: str = ""

    def parse_params(self, llm_response: str) -> dict:
        """LLM 텍스트 출력에서 JSON 파라미터를 추출한다.

        ```json ... ``` 코드블록 → 일반 JSON 객체 순서로 시도.
        파싱 실패 시 빈 dict 반환.
        """
        # 코드블록 안의 JSON 우선 추출
        block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", llm_response, re.DOTALL)
        if block:
            text = block.group(1)
        else:
            # 중괄호로 감싸진 첫 번째 JSON 객체
            inline = re.search(r"\{.*\}", llm_response, re.DOTALL)
            text = inline.group(0) if inline else ""

        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    @abstractmethod
    def execute(self, params: dict) -> str:
        """파라미터를 받아 실제 작업을 수행하고 결과 문자열을 반환한다."""
        raise NotImplementedError
