from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

# 구버전 고정 크기 청킹 상수 (레거시 파일용 — 신규 구조 파일에서는 미사용)
CHUNK_SIZE    = 400
CHUNK_OVERLAP = 50


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """텍스트를 overlap이 있는 고정 크기 청크로 분할한다 (레거시 폴백용)."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if c]


def _parse_world_md(text: str) -> tuple[str, list[dict]]:
    """세계관 마크다운을 파싱하여 (world_id, items) 를 반환한다.

    예상 구조::

        # WorldName

        ## culture | place | story

        ### 항목 제목
        [트리거 키워드: [kw1, kw2]]  ← story 전용, 선택
        내용...

    Returns
    -------
    world_id : str
        최상위 # 헤더 텍스트
    items : list[dict]
        각 항목 dict — keys: world_id, section, item_title, content,
        trigger_keywords (story에서만 사용, 나머지는 "")
    """
    lines = text.splitlines()
    world_id = ""
    items: list[dict] = []

    current_section = ""
    current_title   = ""
    current_lines: list[str] = []
    current_triggers = ""

    def _flush():
        nonlocal current_lines, current_triggers
        content = "\n".join(current_lines).strip()
        if current_title and content:
            items.append({
                "world_id":         world_id,
                "section":          current_section,
                "item_title":       current_title,
                "content":          content,
                "trigger_keywords": current_triggers,
            })
        current_lines = []
        current_triggers = ""

    for line in lines:
        # 최상위 세계관 이름
        if line.startswith("# ") and not line.startswith("## "):
            world_id = line[2:].strip()
            continue

        # 섹션 변경 (## culture / ## place / ## story)
        if line.startswith("## ") and not line.startswith("### "):
            _flush()
            current_section = line[3:].strip().lower()
            current_title   = ""
            continue

        # 항목 제목 (### 항목)
        if line.startswith("### "):
            _flush()
            current_title = line[4:].strip()
            continue

        # 트리거 키워드 라인 감지 (모든 섹션 — content에서 제외하고 메타데이터로만 저장)
        trigger_match = re.match(r"\s*트리거\s*키워드\s*:\s*\[([^\]]*)\]", line)
        if trigger_match:
            current_triggers = trigger_match.group(1).strip()
            continue

        current_lines.append(line)

    _flush()
    return world_id, items


def index_world(
    world_dir: str | Path,
    chroma_path: str,
    embedding_model: str = "BAAI/bge-m3",
    force: bool = False,
) -> None:
    """rag/sources/world/*.md 파일을 청킹하여 ChromaDB에 인덱싱한다.

    신규 구조(# WorldName / ## section / ### item) 파일은 섹션 단위로 청킹하며,
    구버전 파일(## 최상위 구조가 없는 경우)은 고정 크기 청킹으로 폴백한다.

    Parameters
    ----------
    world_dir       : 세계관 문서 디렉토리 (rag/sources/world/)
    chroma_path     : ChromaDB 저장 경로 (config의 chroma_path)
    embedding_model : 임베딩 모델명
    force           : True이면 기존 컬렉션을 삭제하고 재인덱싱
    """
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    world_dir = Path(world_dir)
    ef = SentenceTransformerEmbeddingFunction(model_name=embedding_model)

    client = chromadb.PersistentClient(path=chroma_path)
    col_name = "world_knowledge"

    existing = [c.name for c in client.list_collections()]
    if col_name in existing:
        if not force:
            logger.info(f"[rag/index] '{col_name}' 이미 존재 — 스킵 (재인덱싱: force=True)")
            return
        client.delete_collection(col_name)
        logger.info(f"[rag/index] '{col_name}' 기존 컬렉션 삭제 후 재인덱싱")

    col = client.create_collection(
        name=col_name,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    md_files = sorted(world_dir.glob("*.md"))
    if not md_files:
        logger.warning(f"[rag/index] .md 파일 없음: {world_dir}")
        return

    ids, docs, metas = [], [], []
    for md_path in md_files:
        text = md_path.read_text(encoding="utf-8").strip()

        # 신규 구조 감지: 최상위 # 헤더가 있으면 섹션 파서 사용
        if re.match(r"^# [^\n]+", text):
            world_id, items = _parse_world_md(text)
            if not world_id:
                world_id = md_path.stem

            for item in items:
                chunk_id = f"{world_id}_{item['section']}_{item['item_title']}"
                # 특수문자 제거 (ChromaDB id 제약)
                chunk_id = re.sub(r"[^\w가-힣-]", "_", chunk_id)
                ids.append(chunk_id)
                # 검색 대상 텍스트: 내용만 저장 (제목은 item_title 메타데이터 활용)
                docs.append(item["content"])
                metas.append({
                    "world_id":         item["world_id"],
                    "section":          item["section"],
                    "item_title":       item["item_title"],
                    "trigger_keywords": item["trigger_keywords"],
                    "source":           md_path.name,
                })
            logger.debug(f"[rag/index] {md_path.name} → 섹션 파서: {len(items)}개 항목")
        else:
            # 레거시 파일: 고정 크기 청킹
            chunks = _chunk_text(text)
            for i, chunk in enumerate(chunks):
                ids.append(f"{md_path.stem}_{i:03d}")
                docs.append(chunk)
                metas.append({
                    "world_id": "",
                    "section":  "",
                    "item_title": "",
                    "trigger_keywords": "",
                    "source": md_path.name,
                    "chunk_index": i,
                })
            logger.debug(f"[rag/index] {md_path.name} → 레거시 청킹: {len(chunks)}개 청크")

    if ids:
        col.add(ids=ids, documents=docs, metadatas=metas)
    logger.info(f"[rag/index] 인덱싱 완료: {len(docs)}개 항목 / {len(md_files)}개 파일")


if __name__ == "__main__":
    from config import get_config
    cfg = get_config()
    sources_dir = Path(__file__).resolve().parent / "sources" / "world"
    index_world(
        world_dir=sources_dir,
        chroma_path=cfg["chroma_path"],
        embedding_model=cfg.get("embedding_model", "BAAI/bge-m3"),
        force=True,
    )
