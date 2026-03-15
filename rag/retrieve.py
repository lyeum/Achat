from __future__ import annotations

from loguru import logger


class WorldRetriever:
    """세계관 문서 시맨틱 검색.

    phases.md 3-2:
    - 매 턴 실행 (키워드 트리거 방식 사용 안 함)
    - 유사도 < threshold → 빈 리스트 반환
    - top-n_results 반환
    """

    def __init__(self, config: dict):
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        self.threshold: float = config.get("vdb_threshold", 0.7)
        self.n_results: int   = config.get("vdb_top_k", 2)

        embed_model = config.get("embedding_model", "BAAI/bge-m3")
        self._ef = SentenceTransformerEmbeddingFunction(model_name=embed_model)

        chroma_path = config.get("chroma_path", "./chroma_dev")
        self._client = chromadb.PersistentClient(path=chroma_path)
        self._col_name = "world_knowledge"

    def query(self, text: str) -> list[str]:
        """text와 유사한 세계관 청크를 반환한다.

        threshold 미만이면 빈 리스트를 반환한다.
        컬렉션이 없으면 (인덱싱 전) 빈 리스트를 반환한다.
        """
        existing = [c.name for c in self._client.list_collections()]
        if self._col_name not in existing:
            logger.debug("[rag/retrieve] world_knowledge 컬렉션 없음 — 인덱싱 필요")
            return []

        col = self._client.get_collection(
            name=self._col_name, embedding_function=self._ef
        )
        if col.count() == 0:
            return []

        n = min(self.n_results, col.count())
        results = col.query(
            query_texts=[text],
            n_results=n,
            include=["documents", "distances"],
        )

        docs  = results["documents"][0]
        dists = results["distances"][0]

        cutoff = 1.0 - self.threshold
        filtered = [doc for doc, dist in zip(docs, dists) if dist <= cutoff]

        logger.debug(
            f"[rag/retrieve] '{text[:20]}...' → {len(docs)}개 후보, "
            f"{len(filtered)}개 threshold({self.threshold}) 통과"
        )
        return filtered
