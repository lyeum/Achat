"""
prompt_converter.py — 모델 특화 프롬프트 변환 도구

동작 (3단 파이프라인):
  1. LLM 파라미터 추출 — 대상 모델명 + 변환할 내용 분리
  2. 웹 검색 + 크롤링 — 해당 모델의 프롬프트 가이드 수집
  3. LLM 변환 — 가이드를 참고해 모델에 최적화된 프롬프트 생성

LLM 파라미터:
  {
    "model":   "<대상 AI 모델명>",   # 예: "Stable Diffusion XL", "Midjourney"
    "content": "<변환할 내용>"       # 예: "해질녘 바닷가 풍경"
  }

LLM 주입:
  agent/core.py 에서 PromptConverterTool(llm=self.llm) 으로 생성.
  llm=None (stub 모드) 이면 검색/크롤링만 수행하고 변환은 건너뜀.

주의:
  - 외부 네트워크 접근 필요 (검색 + 크롤링)
  - 크롤링 실패 시 가이드 없이 LLM이 자체 지식으로 변환 (폴백)
  - 의존: ddgs (구 duckduckgo-search)
"""

from __future__ import annotations

import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import URLError

from loguru import logger

from tools.base import BaseTool

# ── 설정 ──────────────────────────────────────────────────────────────

_SEARCH_RESULTS  = 3      # 검색할 URL 수
_CRAWL_TIMEOUT   = 8      # 크롤링 타임아웃 (초)
_CONTEXT_MAX     = 3000   # LLM에 넘길 가이드 텍스트 최대 글자 수
_SEARCH_TEMPLATE = "{model} prompt guide tips keywords site:reddit.com OR site:civitai.com OR site:prompthero.com"


# ── 크롤링 헬퍼 ───────────────────────────────────────────────────────

def _fetch_text(url: str) -> str:
    """URL을 fetch해 HTML 태그를 제거한 순수 텍스트를 반환한다.
    실패 시 빈 문자열 반환.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Achat/0.1)"},
        )
        with urllib.request.urlopen(req, timeout=_CRAWL_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except (URLError, Exception) as e:
        logger.debug(f"[prompt_convert] 크롤링 실패: {url} — {e}")
        return ""

    # 노이즈 블록 제거: script / style / svg / noscript / iframe
    html = re.sub(
        r"<(script|style|svg|noscript|iframe)[^>]*>.*?</(script|style|svg|noscript|iframe)>",
        " ", html, flags=re.DOTALL | re.IGNORECASE,
    )
    # data-uri 속성 제거 (base64 이미지 등)
    html = re.sub(r'(?:src|href|data)="data:[^"]{30,}"', "", html)
    # 200자 초과 인라인 JSON 블록 제거 (JSON-LD, 메타데이터)
    html = re.sub(r"\{[^{}]{200,}\}", " ", html)
    # 나머지 태그 제거 후 공백 정규화
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _collect_guide(model: str) -> str:
    """모델 프롬프트 가이드를 검색·크롤링해 합산 텍스트를 반환한다.
    수집 실패 시 빈 문자열 반환.
    """
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException

    query = _SEARCH_TEMPLATE.format(model=model)
    logger.info(f"[prompt_convert] 검색: {query!r}")

    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=_SEARCH_RESULTS) or []
    except DDGSException as e:
        logger.warning(f"[prompt_convert] 검색 실패: {e}")
        return ""

    urls = [r.get("href", "") for r in results if r.get("href")]
    logger.debug(f"[prompt_convert] 병렬 크롤링: {len(urls)}개 URL")

    parts: list[str] = []
    with ThreadPoolExecutor(max_workers=len(urls) or 1) as executor:
        futures = {executor.submit(_fetch_text, url): url for url in urls}
        for future in as_completed(futures, timeout=_CRAWL_TIMEOUT + 2):
            try:
                text = future.result()
                if text:
                    parts.append(text[:_CONTEXT_MAX // _SEARCH_RESULTS])
            except Exception as e:
                logger.debug(f"[prompt_convert] 크롤링 future 예외: {e}")

    guide = " ".join(parts)
    return guide[:_CONTEXT_MAX]


# ── Tool ─────────────────────────────────────────────────────────────

class PromptConverterTool(BaseTool):
    name = "prompt_convert"
    system_prompt = (
        "너는 프롬프트 변환 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        '{"model": "<대상 AI 모델명>", "content": "<변환할 내용>"}\n\n'
        "model: 사용자가 언급한 AI 모델 이름 (예: Stable Diffusion 1.5, Midjourney, DALL-E 3, FLUX)\n"
        "content: 해당 모델로 생성하고 싶은 내용 (모델명 제외)\n"
        "model이 명시되지 않으면 빈 문자열로 설정해라.\n\n"
        "예시:\n"
        "입력: stable diffusion 1.5로 고양이 그려줘\n"
        '출력: {"model": "Stable Diffusion 1.5", "content": "고양이"}\n\n'
        "입력: midjourney에서 사이버펑크 도시 밤 풍경 만들고 싶어\n"
        '출력: {"model": "Midjourney", "content": "사이버펑크 도시 밤 풍경"}\n\n'
        "입력: DALL-E 3 모델에게 귀여운 강아지 픽셀아트를 생성하라고 하고 싶은데\n"
        '출력: {"model": "DALL-E 3", "content": "귀여운 강아지 픽셀아트"}\n\n'
        "입력: stable-diffusion 1.5 모델에게 귀여운 고양이의 픽셀아트를 생성하라고 하고싶은데 뭐라고 하면 될까?\n"
        '출력: {"model": "Stable Diffusion 1.5", "content": "귀여운 고양이 픽셀아트"}'
    )

    def __init__(self, llm=None, config: dict | None = None) -> None:
        self._llm    = llm
        self._config = config or {}
        self._store: "PromptGuideStore | None" = None  # lazy init  # noqa: F821

    def _get_store(self):
        """PromptGuideStore lazy 초기화 (chroma_path가 없는 stub 환경에서는 None)."""
        if self._store is not None:
            return self._store
        chroma_path = self._config.get("chroma_path", "")
        if not chroma_path:
            return None
        from tools.prompt_store import PromptGuideStore
        embed = self._config.get("embedding_model")
        self._store = PromptGuideStore(chroma_path, embedding_model=embed)
        return self._store

    def execute(self, params: dict) -> str:
        model   = params.get("model",   "").strip()
        content = params.get("content", "").strip()

        if not content:
            return "오류: 변환할 내용이 없습니다."
        if not model:
            return "오류: 대상 모델을 입력해주세요. (예: 'Stable Diffusion XL에 대해 ~')"

        logger.info(f"[prompt_convert] 모델={model!r}, 내용={content!r}")

        # ── 2단: DB 조회 → 크롤링 fallback ─────────────────────────────
        guide = ""
        guide_source = ""
        store = self._get_store()
        if store:
            cached = store.query(model)
            if cached:
                guide = cached
                guide_source = "DB"
                logger.info(f"[prompt_convert] DB 가이드 사용 ({len(guide)}자)")

        if not guide:
            # DB 미스 → 크롤링 fallback
            guide = _collect_guide(model)
            if guide:
                guide_source = "crawl"
                logger.info(f"[prompt_convert] 크롤링 가이드 수집 ({len(guide)}자)")
                # 크롤링 성공 시 DB에 자동 저장 (이후 요청은 DB에서 바로 조회)
                if store:
                    store.save(model, guide, source="crawl")
            else:
                logger.warning("[prompt_convert] 가이드 없음 — LLM 자체 지식으로 변환")

        # ── stub 모드: LLM 없음 ─────────────────────────────────────────
        if self._llm is None:
            guide_preview = guide[:200] + "..." if len(guide) > 200 else guide
            return (
                f"[stub] model={model!r}, content={content!r}, source={guide_source or 'none'}\n"
                f"가이드 미리보기: {guide_preview or '(없음)'}"
            )

        # ── 3단: LLM 변환 ───────────────────────────────────────────────
        context_block = (
            f"=== {model} 프롬프트 가이드 ({guide_source}) ===\n{guide}\n"
            if guide else
            f"('{model}'에 대한 가이드를 찾지 못했습니다. 자체 지식을 활용해주세요.)\n"
        )

        system = (
            f"너는 '{model}' 모델 전용 프롬프트 엔지니어다.\n"
            "아래 가이드를 참고해서 사용자의 요청을 해당 모델에 최적화된 프롬프트로 변환해라.\n"
            "출력은 변환된 프롬프트만 작성하고, 설명이나 전처리 없이 바로 사용 가능한 형태로 반환해라.\n\n"
            + context_block
        )

        try:
            converted = self._llm.generate(
                messages=[
                    {"role": "system",  "content": system},
                    {"role": "user",    "content": f"변환 요청: {content}"},
                ],
                stream=False,
            )
        except Exception as e:
            return f"오류: LLM 변환 중 예외 발생 — {e}"

        return f"[{model}] {converted}"
