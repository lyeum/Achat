from __future__ import annotations

from pathlib import Path

from loguru import logger

# 청킹 설정 (phases.md 3-1 기준)
CHUNK_SIZE    = 400   # 한국어 기준 300~500자
CHUNK_OVERLAP = 50


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """텍스트를 overlap이 있는 고정 크기 청크로 분할한다."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end].strip())
        start += size - overlap
    return [c for c in chunks if c]


def index_world(
    world_dir: str | Path,
    chroma_path: str,
    embedding_model: str = "BAAI/bge-m3",
    force: bool = False,
) -> None:
    """rag/sources/world/*.md 파일을 청킹하여 ChromaDB에 인덱싱한다.

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

    # 이미 인덱싱된 경우 스킵 (force=True면 재인덱싱)
    existing = [c.name for c in client.list_collections()]
    if col_name in existing:
        if not force:
            logger.info(f"[rag/index] '{col_name}' 이미 존재 — 스킵 (재인덱싱: force=True)")
            return
        client.delete_collection(col_name)
        logger.info(f"[rag/index] '{col_name}' 기존 컬렉션 삭제 후 재인덱싱")

    # hnsw:space=cosine — retrieve.py의 cutoff = 1.0 - threshold 계산과 일치시킴
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
        chunks = _chunk_text(text)
        for i, chunk in enumerate(chunks):
            ids.append(f"{md_path.stem}_{i:03d}")
            docs.append(chunk)
            metas.append({"source": md_path.name, "chunk_index": i})
        logger.debug(f"[rag/index] {md_path.name} → {len(chunks)}개 청크")

    col.add(ids=ids, documents=docs, metadatas=metas)
    logger.info(f"[rag/index] 인덱싱 완료: {len(docs)}개 청크 / {len(md_files)}개 파일")


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
