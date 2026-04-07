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

        self._cfg = config
        self.threshold: float = config.get("vdb_threshold", 0.7)
        self.n_results: int   = config.get("vdb_top_k", 2)
        self._ef = None  # lazy: 첫 query/add_document 호출 시 로드

        chroma_path = config.get("chroma_path", "./chroma_dev")
        self._client = chromadb.PersistentClient(path=chroma_path)
        self._col_name = "world_knowledge"

    def _load_ef(self):
        if self._ef is None:
            from memory.embedding import get_embedding_function
            self._ef = get_embedding_function(
                self._cfg.get("embedding_model", "BAAI/bge-m3"),
                self._cfg.get("embedding_device", "cpu"),
            )
        return self._ef

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
            name=self._col_name, embedding_function=self._load_ef()
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

    def add_document(self, doc_id: str, text: str, metadata: dict) -> None:
        """ChromaDB에 문서를 동적으로 추가(upsert)한다.

        컬렉션이 없으면 자동 생성 후 저장한다.
        동일 doc_id가 이미 존재하면 덮어쓴다.
        """
        existing = [c.name for c in self._client.list_collections()]
        if self._col_name not in existing:
            col = self._client.create_collection(
                name=self._col_name,
                embedding_function=self._load_ef(),
                metadata={"hnsw:space": "cosine"},
            )
        else:
            col = self._client.get_collection(
                name=self._col_name, embedding_function=self._load_ef()
            )

        col.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])
        logger.debug(f"[rag/retrieve] 문서 저장: {doc_id}")
