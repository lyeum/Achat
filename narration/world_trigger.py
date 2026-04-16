"""세계관 트리거 시스템.

세계관 콘텐츠를 사용자 발화 조건에 따라 나레이션으로 자동 출력한다.
모든 트리거는 같은 세션 내 최초 1회만 발동한다.

지원 트리거:
- story  : 키워드 코사인 유사도 기반, 세션 내 최초 1회
- place  : 장소 변경(act_id 변경) 시 처음 진입할 때
- culture: 사용자 발화가 문화/풍습 관련 질문일 때, 미설명 항목 소거 방식
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from conversation.session_manager import SessionState
    from rag.retrieve import WorldRetriever


# ── Story 트리거 ─────────────────────────────────────────────────────────────

def check_story_trigger(
    user_input: str,
    session: "SessionState",
    retriever: "WorldRetriever",
    threshold: float = 0.55,
) -> tuple[str, str] | None:
    """user_input이 story 트리거 키워드와 유사하면 해당 스토리 내용을 반환한다.

    같은 session 내 이미 발동된 story는 제외한다.
    임계값(threshold) 이상의 유사도를 가진 story 항목이 없으면 None 반환.
    """
    world_id = getattr(session, "world_id", None)
    if not world_id:
        return None

    try:
        # story 섹션에서 trigger_keywords를 포함한 항목 조회
        items = retriever.query_by_meta(world_id=world_id, section="story")
    except Exception:  # noqa: BLE001
        return None

    if not items:
        return None

    # 이미 발동된 항목 제외
    fired = set(getattr(session, "fired_stories", []))
    candidates = [it for it in items if it["metadata"].get("item_title") not in fired]
    if not candidates:
        return None

    # 키워드 기반 간단 매칭 (임베딩 없이 텍스트 포함 여부로 근사)
    user_lower = user_input.lower()
    best: dict | None = None
    best_score = 0

    for item in candidates:
        kw_str = item["metadata"].get("trigger_keywords", "")
        if not kw_str:
            continue
        keywords = [k.strip() for k in kw_str.split(",") if k.strip()]
        # 매칭 개수 / 총 키워드 수 = 근사 유사도
        matched = sum(1 for kw in keywords if kw in user_lower or kw in user_input)
        if matched == 0:
            continue
        score = matched / max(len(keywords), 1)
        if score > best_score:
            best_score = score
            best = item

    if best is None or best_score < threshold:
        return None

    item_title = best["metadata"].get("item_title", "")
    # 발동 기록
    if not hasattr(session, "fired_stories") or session.fired_stories is None:
        session.fired_stories = []
    session.fired_stories.append(item_title)

    logger.info(f"[world_trigger] story 트리거 발동: '{item_title}' (score={best_score:.2f})")
    return item_title, best["document"]


# ── Place 트리거 ─────────────────────────────────────────────────────────────

def check_place_trigger(
    new_place: str,
    session: "SessionState",
    retriever: "WorldRetriever",
) -> tuple[str, str] | None:
    """새 장소에 처음 진입할 때 해당 place 항목의 설명 텍스트를 반환한다.

    이미 방문한 장소면 None 반환.
    """
    world_id = getattr(session, "world_id", None)
    if not world_id or not new_place:
        return None

    visited = set(getattr(session, "visited_places", []))
    if new_place in visited:
        return None

    try:
        items = retriever.query_by_meta(world_id=world_id, section="place")
    except Exception:  # noqa: BLE001
        return None

    # 장소 이름(item_title 또는 document 안에 place 이름)으로 매칭
    matched = None
    for item in items:
        title = item["metadata"].get("item_title", "")
        if new_place.lower() in title.lower() or new_place.lower() in item["document"].lower():
            matched = item
            break

    if matched is None:
        return None

    # 방문 기록
    if not hasattr(session, "visited_places") or session.visited_places is None:
        session.visited_places = []
    session.visited_places.append(new_place)

    item_title = matched["metadata"].get("item_title", new_place)
    logger.info(f"[world_trigger] place 트리거 발동: '{new_place}'")
    return item_title, matched["document"]


# ── Culture 트리거 ───────────────────────────────────────────────────────────

def check_culture_trigger(
    user_input: str,
    session: "SessionState",
    retriever: "WorldRetriever",
    threshold: float = 0.2,
) -> tuple[str, str] | None:
    """사용자 발화가 culture 항목의 trigger_keywords와 일치하면 해당 항목을 반환한다.

    story 트리거와 동일한 키워드 매칭 방식을 사용한다 (### 레벨 항목별 매칭).
    이미 설명된 항목은 제외한다.

    threshold : 매칭된 키워드 수 / 전체 키워드 수 최소 비율 (기본 0.2 — 5개 중 1개 이상).
    """
    world_id = getattr(session, "world_id", None)
    if not world_id:
        return None

    try:
        items = retriever.query_by_meta(world_id=world_id, section="culture")
    except Exception:  # noqa: BLE001
        return None

    if not items:
        return None

    explained = set(getattr(session, "explained_cultures", []))
    candidates = [it for it in items if it["metadata"].get("item_title") not in explained]
    if not candidates:
        return None

    # 항목별 trigger_keywords 키워드 매칭 (story 트리거와 동일 방식)
    user_lower = user_input.lower()
    best: dict | None = None
    best_score = 0.0

    for item in candidates:
        kw_str = item["metadata"].get("trigger_keywords", "")
        if not kw_str:
            continue
        keywords = [k.strip() for k in kw_str.split(",") if k.strip()]
        matched = sum(1 for kw in keywords if kw in user_lower or kw in user_input)
        if matched == 0:
            continue
        score = matched / max(len(keywords), 1)
        if score > best_score:
            best_score = score
            best = item

    if best is None or best_score < threshold:
        return None

    item_title = best["metadata"].get("item_title", "")
    if not hasattr(session, "explained_cultures") or session.explained_cultures is None:
        session.explained_cultures = []
    session.explained_cultures.append(item_title)

    logger.info(f"[world_trigger] culture 트리거 발동: '{item_title}' (score={best_score:.2f})")
    return item_title, best["document"]
