from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger


class LongTermMemory:
    """ChromaDB 기반 장기 메모리 저장 / 시맨틱 검색.

    M_schema.json 구조를 기준으로 저장/검색한다.
    embedding_model: BAAI/bge-m3 (SentenceTransformer)
    """

    def __init__(self, config: dict):
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        self.cfg = config
        self.threshold: float = config.get("vdb_threshold", 0.7)
        self.top_k: int = config.get("vdb_top_k", 2)

        embed_model = config.get("embedding_model", "BAAI/bge-m3")
        self._ef = SentenceTransformerEmbeddingFunction(model_name=embed_model)

        chroma_path = config.get("chroma_path", "./chroma_dev")
        self._client = chromadb.PersistentClient(path=chroma_path)
        logger.info(f"[long_term] ChromaDB 초기화: {chroma_path}")

    def _collection(self, character_id: str):
        """캐릭터별 컬렉션을 가져오거나 생성한다.

        hnsw:space=cosine 으로 고정 — query()의 cutoff = 1.0 - threshold 계산이
        cosine distance (0=동일, 1=직교)를 전제로 하기 때문.
        """
        return self._client.get_or_create_collection(
            name=f"{character_id.lower()}_memory",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    def store(self, entry: dict) -> None:
        """M_schema.json 구조의 entry를 ChromaDB에 저장한다.

        entry 예시:
        {
            "id": "mem_haru_012",
            "content": "...",
            "metadata": {
                "character_id": "Haru",
                "session_id": "...",
                "turn_range": "3-8",
                "importance": 0.85,
                "tags": ["이름", "취미"],
                "location": "beach",
                "timestamp": "2025-01-18T09:30:00"
            }
        }
        """
        meta = entry["metadata"]
        character_id = meta["character_id"]
        col = self._collection(character_id)

        # ChromaDB metadata는 str/int/float/bool만 허용 — tags(list)는 직렬화
        flat_meta = {
            "character_id": meta.get("character_id", ""),
            "session_id":   meta.get("session_id", ""),
            "turn_range":   meta.get("turn_range", ""),
            "importance":   float(meta.get("importance", 0.0)),
            "tags":         ",".join(meta.get("tags", [])),
            "location":     meta.get("location", ""),
            "timestamp":    meta.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }

        col.upsert(
            ids=[entry["id"]],
            documents=[entry["content"]],
            metadatas=[flat_meta],
        )
        logger.debug(f"[long_term] 저장: {entry['id']} (importance={flat_meta['importance']:.2f})")

    def query(self, text: str, character_id: str) -> list[str]:
        """시맨틱 검색. 유사도 threshold 미만이면 빈 리스트를 반환한다.

        Returns:
            조건을 만족하는 기억 content 문자열 리스트 (최대 top_k개)
        """
        col = self._collection(character_id)
        if col.count() == 0:
            return []

        results = col.query(
            query_texts=[text],
            n_results=min(self.top_k, col.count()),
            where={"importance": {"$gte": 0.5}},
            include=["documents", "distances"],
        )

        docs = results["documents"][0]
        dists = results["distances"][0]

        # ChromaDB distance는 L2 또는 cosine(1-similarity). bge-m3는 cosine space.
        # distance < (1 - threshold) 조건으로 필터
        cutoff = 1.0 - self.threshold
        filtered = [doc for doc, dist in zip(docs, dists) if dist <= cutoff]

        logger.debug(
            f"[long_term] query '{text[:20]}...' → {len(docs)}개 후보, "
            f"{len(filtered)}개 threshold 통과"
        )
        return filtered

    def seed(self, entries: list[dict]) -> None:
        """M_default.json 초기 데이터를 일괄 삽입한다 (이미 있으면 upsert로 덮어씀)."""
        for entry in entries:
            self.store(entry)
        logger.info(f"[long_term] seed 완료: {len(entries)}개 항목")
