"""
web_search.py — 인터넷 검색 도구 (duckduckgo-search 라이브러리)

LLM 파라미터:
  {
    "query": "<검색어>",
    "max_results": 5    # 반환할 최대 결과 수 (선택, 기본 5)
  }

동작:
  1. DDGS.text() 로 실제 DuckDuckGo 검색 결과 수집
  2. title / href / body 포맷으로 최대 max_results 개 반환

주의:
  - 외부 네트워크 접근 필요 (오프라인 환경에서는 오류 반환)
  - 의존: ddgs (uv add ddgs)
"""

from __future__ import annotations

from loguru import logger

from tools.base import BaseTool

# ── 설정 ──────────────────────────────────────────────────────────────

_MAX_RESULTS_DEFAULT = 5
_MAX_RESULTS_CAP     = 10


def _ddg_search(query: str, max_results: int) -> list[dict]:
    """duckduckgo-search 라이브러리로 실제 검색 결과를 반환한다.

    반환 형식: [{"title": str, "url": str, "snippet": str}, ...]
    """
    from ddgs import DDGS
    from ddgs.exceptions import DDGSException

    try:
        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results)
    except DDGSException as e:
        logger.warning(f"[web_search] DDG 오류: {e}")
        raise
    except Exception as e:
        logger.warning(f"[web_search] 검색 실패: {e}")
        raise

    return [
        {
            "title":   r.get("title", ""),
            "url":     r.get("href",  ""),
            "snippet": r.get("body",  ""),
        }
        for r in (raw or [])
    ]


# ── Tool ─────────────────────────────────────────────────────────────

class WebSearchTool(BaseTool):
    name = "web_search"
    system_prompt = (
        "너는 인터넷 검색 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        '{"query": "<검색어>", "max_results": 5}\n'
        "max_results가 명시되지 않으면 5로 설정해라. 최대 10을 넘지 않도록 해라."
    )

    def execute(self, params: dict) -> str:
        query = params.get("query", "").strip()
        max_results = int(params.get("max_results", _MAX_RESULTS_DEFAULT))
        max_results = max(1, min(max_results, _MAX_RESULTS_CAP))

        if not query:
            return "오류: 검색어가 없습니다."

        logger.info(f"[web_search] 검색: {query!r} (최대 {max_results}건)")

        try:
            results = _ddg_search(query, max_results)
        except Exception as e:
            return f"오류: 검색 중 예외 발생 — {e}"

        if not results:
            return f"'{query}'에 대한 검색 결과를 찾지 못했습니다."

        lines = [f"검색 결과 — '{query}' ({len(results)}건)"]
        for i, r in enumerate(results, start=1):
            lines.append(f"\n[{i}] {r['title']}")
            if r["url"]:
                lines.append(f"    {r['url']}")
            lines.append(f"    {r['snippet']}")
        return "\n".join(lines)
