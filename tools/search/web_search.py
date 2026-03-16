"""
web_search.py — 인터넷 검색 도구 (DuckDuckGo Instant Answer API)

LLM 파라미터:
  {
    "query": "<검색어>",
    "max_results": 5    # 반환할 최대 결과 수 (선택, 기본 5)
  }

동작:
  1. DuckDuckGo Instant Answer API (api.duckduckgo.com) 에 GET 요청
  2. AbstractText (즉답) + RelatedTopics (관련 주제) 에서 결과 수집
  3. 최대 max_results 개 결과를 문자열로 반환

주의:
  - 외부 네트워크 접근 필요 (오프라인 환경에서는 오류 반환)
  - DuckDuckGo API는 rate limit이 있으므로 연속 호출 자제
  - 추가 의존성 없음 (urllib 표준 라이브러리 사용)
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from urllib.error import URLError

from loguru import logger

from tools.base import BaseTool

# ── 설정 ──────────────────────────────────────────────────────────────

_API_URL   = "https://api.duckduckgo.com/"
_TIMEOUT   = 8    # 초
_MAX_RESULTS_DEFAULT = 5
_MAX_RESULTS_CAP     = 10


def _ddg_search(query: str, max_results: int) -> list[dict]:
    """DuckDuckGo Instant Answer API를 호출해 결과 리스트를 반환한다.

    반환 형식: [{"title": str, "url": str, "snippet": str}, ...]
    """
    params = urllib.parse.urlencode({
        "q":            query,
        "format":       "json",
        "no_html":      "1",
        "skip_disambig":"1",
    })
    url = f"{_API_URL}?{params}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Achat/0.1 (local AI assistant)"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        logger.warning(f"[web_search] 네트워크 오류: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.warning(f"[web_search] JSON 파싱 오류: {e}")
        raise

    results: list[dict] = []

    # 1) Instant Answer (Abstract)
    abstract = data.get("AbstractText", "").strip()
    abstract_url = data.get("AbstractURL", "").strip()
    if abstract:
        results.append({
            "title":   data.get("Heading", query),
            "url":     abstract_url,
            "snippet": abstract,
        })

    # 2) Related Topics
    for topic in data.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        # 일부 항목은 Topics 그룹이므로 하위 항목을 펼침
        if "Topics" in topic:
            for sub in topic["Topics"]:
                if len(results) >= max_results:
                    break
                snippet = sub.get("Text", "").strip()
                url     = sub.get("FirstURL", "")
                if snippet:
                    results.append({"title": snippet[:50], "url": url, "snippet": snippet})
        else:
            snippet = topic.get("Text", "").strip()
            url     = topic.get("FirstURL", "")
            if snippet:
                results.append({"title": snippet[:50], "url": url, "snippet": snippet})

    return results[:max_results]


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
        except URLError:
            return "오류: 네트워크에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요."
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
