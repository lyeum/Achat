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

        self.cfg = config
        self.threshold: float = config.get("vdb_threshold", 0.7)
        self.top_k: int = config.get("vdb_top_k", 2)
        self._ef = None  # lazy: 첫 _collection() 호출 시 로드

        chroma_path = config.get("chroma_path", "./chroma_dev")
        self._client = chromadb.PersistentClient(path=chroma_path)
        logger.info(f"[long_term] ChromaDB 초기화: {chroma_path}")

    def _load_ef(self):
        """임베딩 함수를 처음 사용할 때만 로드한다 (lazy)."""
        if self._ef is None:
            from memory.embedding import get_embedding_function
            self._ef = get_embedding_function(
                self.cfg.get("embedding_model", "BAAI/bge-m3"),
                self.cfg.get("embedding_device", "cpu"),
            )
        return self._ef

    def _collection(self, character_id: str):
        """캐릭터별 컬렉션을 가져오거나 생성한다.

        hnsw:space=cosine 으로 고정 — query()의 cutoff = 1.0 - threshold 계산이
        cosine distance (0=동일, 1=직교)를 전제로 하기 때문.
        """
        return self._client.get_or_create_collection(
            name=f"{character_id.lower()}_memory",
            embedding_function=self._load_ef(),
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

    def clear_session(self, character_id: str, session_id: str) -> int:
        """해당 session_id의 에피소딕 기억을 모두 삭제한다.

        Parameters
        ----------
        character_id : 캐릭터 ID (컬렉션 특정용)
        session_id   : 삭제할 세션 ID

        Returns
        -------
        삭제된 항목 수
        """
        col = self._collection(character_id)
        if col.count() == 0:
            return 0

        result = col.get(where={"session_id": {"$eq": session_id}})
        ids = result.get("ids", [])
        if ids:
            col.delete(ids=ids)
            logger.info(
                f"[long_term] 세션 기억 삭제: {character_id}/{session_id} ({len(ids)}개)"
            )
        return len(ids)

    def clear_all(self, character_id: str) -> int:
        """해당 캐릭터의 모든 기억을 삭제한다 (캐릭터 초기화용).

        Returns
        -------
        삭제된 항목 수
        """
        col = self._collection(character_id)
        count = col.count()
        if count == 0:
            return 0
        all_ids = col.get()["ids"]
        if all_ids:
            col.delete(ids=all_ids)
            logger.info(f"[long_term] 전체 기억 삭제: {character_id} ({len(all_ids)}개)")
        return len(all_ids)

    def get_all(self, character_id: str) -> dict:
        """전체 기억을 세션별로 그룹화해 반환한다 (DB 뷰어용).

        Returns
        -------
        {
            "collection": "haru_memory",
            "total": 23,
            "sessions": {
                "session-abc": [
                    {"id": ..., "content": ..., "importance": 0.85,
                     "tags": "이름,취미", "location": "cafe",
                     "timestamp": "2025-01-18T09:30:00", "turn_range": "3-8"},
                    ...
                ],
                ...
            }
        }
        """
        col = self._collection(character_id)
        total = col.count()
        if total == 0:
            return {"collection": f"{character_id.lower()}_memory", "total": 0, "sessions": {}}

        result = col.get(include=["documents", "metadatas"])
        sessions: dict = {}
        for doc_id, doc, meta in zip(result["ids"], result["documents"], result["metadatas"]):
            sess = meta.get("session_id", "unknown")
            if sess not in sessions:
                sessions[sess] = []
            sessions[sess].append({
                "id":         doc_id,
                "content":    doc,
                "importance": meta.get("importance", 0.0),
                "tags":       meta.get("tags", ""),
                "location":   meta.get("location", ""),
                "timestamp":  meta.get("timestamp", ""),
                "turn_range": meta.get("turn_range", ""),
            })

        for sess in sessions:
            sessions[sess].sort(key=lambda x: x["timestamp"], reverse=True)

        return {"collection": f"{character_id.lower()}_memory", "total": total, "sessions": sessions}

    def query_preview(self, text: str, character_id: str, top_k: int = 5) -> list[dict]:
        """유사 기억 검색 미리보기 — threshold 무관하게 상위 top_k개를 반환한다."""
        col = self._collection(character_id)
        n = col.count()
        if n == 0:
            return []

        results = col.query(
            query_texts=[text],
            n_results=min(top_k, n),
            include=["documents", "metadatas", "distances"],
        )

        docs  = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        return [
            {
                "content":    doc,
                "importance": meta.get("importance", 0.0),
                "tags":       meta.get("tags", ""),
                "similarity": round(1.0 - dist, 3),
            }
            for doc, meta, dist in zip(docs, metas, dists)
        ]

    def delete_entry(self, character_id: str, entry_id: str) -> bool:
        """ID로 항목 하나를 삭제한다. 성공하면 True."""
        col = self._collection(character_id)
        try:
            existing = col.get(ids=[entry_id])
            if not existing["ids"]:
                logger.warning(f"[long_term] 삭제 대상 없음: {entry_id}")
                return False
            col.delete(ids=[entry_id])
            logger.info(f"[long_term] 항목 삭제: {entry_id}")
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"[long_term] 삭제 실패: {entry_id} — {e}")
            return False

    def add_entry(self, character_id: str, content: str, metadata: dict) -> str:
        """새 항목을 추가하고 생성된 entry_id를 반환한다.

        metadata 권장 키: importance(float), tags(list[str]|str),
                          location(str), session_id(str)
        """
        import uuid

        entry_id = f"mem_{character_id.lower()}_{uuid.uuid4().hex[:8]}"
        entry = {
            "id": entry_id,
            "content": content,
            "metadata": {
                "character_id": character_id,
                "session_id":   metadata.get("session_id", "manual"),
                "turn_range":   metadata.get("turn_range", ""),
                "importance":   float(metadata.get("importance", 0.5)),
                "tags":         metadata.get("tags", []),
                "location":     metadata.get("location", ""),
                "timestamp":    metadata.get(
                    "timestamp",
                    datetime.now(timezone.utc).isoformat(),
                ),
            },
        }
        try:
            self.store(entry)
            logger.info(f"[long_term] 항목 추가: {entry_id}")
            return entry_id
        except Exception as e:  # noqa: BLE001
            logger.error(f"[long_term] 추가 실패: {e}")
            return ""

    def update_entry(
        self, character_id: str, entry_id: str, new_content: str, new_metadata: dict
    ) -> bool:
        """기존 항목을 동일 ID로 덮어쓴다 (upsert). 성공하면 True."""
        entry = {
            "id": entry_id,
            "content": new_content,
            "metadata": {
                "character_id": character_id,
                "session_id":   new_metadata.get("session_id", "manual"),
                "turn_range":   new_metadata.get("turn_range", ""),
                "importance":   float(new_metadata.get("importance", 0.5)),
                "tags":         new_metadata.get("tags", []),
                "location":     new_metadata.get("location", ""),
                "timestamp":    new_metadata.get(
                    "timestamp",
                    datetime.now(timezone.utc).isoformat(),
                ),
            },
        }
        try:
            self.store(entry)
            logger.info(f"[long_term] 항목 수정: {entry_id}")
            return True
        except Exception as e:  # noqa: BLE001
            logger.error(f"[long_term] 수정 실패: {entry_id} — {e}")
            return False

    def seed(self, entries: list[dict]) -> None:
        """M_default.json 초기 데이터를 일괄 삽입한다 (이미 있으면 upsert로 덮어씀)."""
        for entry in entries:
            self.store(entry)
        logger.info(f"[long_term] seed 완료: {len(entries)}개 항목")
