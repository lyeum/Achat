"""rag/world_nav.py — 장소 이동 의도 감지 + 세계관 동적 생성/저장.

흐름
----
1. 유저 발화에 이동 지시어 포함 → LLM으로 장소명 추출
2. 추출된 장소명을 기존 YAML acts에서 매칭
3. YAML에 없으면 RAG 검색
4. RAG에도 없으면 LLM으로 장소 묘사 생성 → RAG에 저장
"""

from __future__ import annotations

from loguru import logger

# 이동 의도 지시어 (이 중 하나라도 포함되면 LLM 추출 시도)
_MOVE_TRIGGERS = [
    "가자", "가볼까", "가고 싶어", "거기 가", "이동하자", "갈까",
    "가면 어때", "가요", "가보자", "데려가", "안내해", "가고 싶다",
    "가보고 싶어", "가볼게", "가보자", "이동해",
]

_EXTRACT_PROMPT = (
    "다음 문장에서 이동하려는 장소명만 한 단어나 짧은 구로 추출해. "
    "이동 의도가 없으면 '없음'이라고만 답해. 다른 말은 쓰지 마.\n\n"
    "문장: {input}\n장소명:"
)

_CREATE_PROMPT = (
    "세계관 배경: {world_desc}\n\n"
    "위 세계관 안에 '{location}'이라는 장소를 150자 내외로 묘사해. "
    "분위기, 특징, 느낌을 자연스럽게 산문으로 써. 목록 형식은 쓰지 마."
)


def detect_move_intent(user_input: str, llm) -> str | None:
    """이동 의도가 있으면 장소명을 반환, 없으면 None.

    빠른 키워드 필터 → LLM 추출 2단계 구조.
    """
    if not any(kw in user_input for kw in _MOVE_TRIGGERS):
        return None

    raw = llm.generate(
        [{"role": "user", "content": _EXTRACT_PROMPT.format(input=user_input)}],
        stream=False,
        max_tokens=15,
    ).strip()

    # 응답 검증
    if not raw or raw == "없음" or len(raw) > 30:
        return None

    logger.debug(f"[world_nav] 이동 의도 감지 → '{raw}'")
    return raw


def create_location_desc(location_name: str, world_desc: str, llm) -> str:
    """LLM으로 장소 묘사를 생성한다."""
    desc = llm.generate(
        [{"role": "user", "content": _CREATE_PROMPT.format(
            world_desc=world_desc, location=location_name,
        )}],
        stream=False,
        max_tokens=200,
    ).strip()
    logger.info(f"[world_nav] 장소 생성 완료: '{location_name}' ({len(desc)}자)")
    return desc


def find_or_create_location(
    location_name: str,
    world_desc: str,
    retriever,
    llm,
) -> str:
    """RAG에서 장소 검색 → 없으면 LLM 생성 후 RAG에 저장.

    Parameters
    ----------
    location_name : 유저 발화에서 추출된 장소명
    world_desc    : 현재 세계관 설명 (생성 시 컨텍스트로 사용)
    retriever     : WorldRetriever 인스턴스
    llm           : LLMClient 인스턴스

    Returns
    -------
    장소 묘사 문자열
    """
    # 1. RAG 검색
    results = retriever.query(location_name)
    if results:
        logger.debug(f"[world_nav] RAG 히트: '{location_name}'")
        return results[0]

    # 2. LLM 생성
    desc = create_location_desc(location_name, world_desc, llm)

    # 3. RAG 저장 (다음 세션에도 재사용)
    doc_id = f"loc_{location_name.replace(' ', '_')}"
    retriever.add_document(
        doc_id=doc_id,
        text=f"[{location_name}] {desc}",
        metadata={"source": "generated", "location": location_name},
    )

    return desc
