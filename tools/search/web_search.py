"""
web_search.py — 인터넷 검색 도구 (duckduckgo-search 라이브러리)

LLM 파라미터:
  {
    "query": "<검색어>",
    "max_results": 5    # 반환할 최대 결과 수 (선택, 기본 5)
  }

동작:
  1. DDGS.text() 로 실제 DuckDuckGo 검색 결과 수집
  2. 사용자 쿼리와 snippet 간의 어절 겹침으로 의미적 유사도 스코어링
  3. 유사도 기준 재정렬 후 HTML hyperlink 형식으로 반환
     (QML Text.AutoText 또는 RichText로 렌더링 시 클릭 가능)

주의:
  - 외부 네트워크 접근 필요 (오프라인 환경에서는 오류 반환)
  - 의존: ddgs (uv add ddgs)
"""

from __future__ import annotations

import re

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


def _tokenize(text: str) -> set[str]:
    """텍스트에서 유니코드 단어 토큰을 추출한다 (한국어 어절 포함)."""
    return set(re.findall(r"\w+", text.lower(), re.UNICODE))


def _score_relevance(query_tokens: set[str], result: dict) -> int:
    """쿼리 토큰이 결과 텍스트(title + snippet)에 포함된 수를 반환한다.

    한국어는 조사가 붙어 "파이썬" → "파이썬은" 처럼 형태가 바뀌므로
    정확 일치 대신 쿼리 토큰이 결과 텍스트의 부분 문자열인지 검사한다.
    """
    text = (result.get("title", "") + " " + result.get("snippet", "")).lower()
    return sum(1 for qt in query_tokens if qt in text)


def _format_html(query: str, results: list[dict]) -> str:
    """검색 결과를 HTML hyperlink 형식으로 포맷한다.

    QML Text.AutoText / Text.RichText 환경에서 클릭 가능한 링크로 렌더링된다.
    """
    lines = [f"검색 결과 — '{query}' ({len(results)}건)<br>"]
    for i, r in enumerate(results, start=1):
        title = r["title"] or r["url"]
        url   = r["url"]
        snippet = r["snippet"]

        if url:
            link = f'<a href="{url}">[{i}] {title}</a>'
        else:
            link = f"[{i}] {title}"

        lines.append(link)
        if snippet:
            # snippet은 plain text — HTML 특수문자 이스케이프
            safe_snippet = (
                snippet
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            lines.append(f"<font color='#8090A0'>{safe_snippet}</font>")
        lines.append("")

    return "<br>".join(lines).rstrip("<br>")


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

        # 쿼리 토큰 추출 후 유사도 스코어링 → 재정렬
        q_tokens = _tokenize(query)
        scored = sorted(results, key=lambda r: _score_relevance(q_tokens, r), reverse=True)

        # 스코어 0인 결과(쿼리 토큰이 전혀 없음)는 DDG 랭킹 유지하되 뒤로 보냄
        # (최소 1건은 보장하기 위해 완전 제거는 하지 않음)
        logger.debug(
            f"[web_search] 스코어: "
            + ", ".join(f"{r['title'][:20]}={_score_relevance(q_tokens, r)}" for r in scored)
        )

        return _format_html(query, scored)
