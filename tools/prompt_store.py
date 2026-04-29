"""
prompt_store.py — 프롬프트 가이드 ChromaDB 저장소

동일 chroma_dev/ PersistentClient 안의 독립 컬렉션 'prompt_guides'를 관리한다.

컬렉션 스키마:
  id:       "pg_{model_key}_{uuid8}"
  document: 프롬프트 가이드 텍스트 (웹 수집 or 사용자 저장)
  metadata: {
    "model":    정규화 모델명 (소문자, 공백→하이픈),
    "source":   "user" | "crawl",
    "saved_at": ISO-8601 타임스탬프
  }

저장 주체: tools/prompt_store.py (PromptGuideStore)
검색 주체: tools/prompt_store.py (PromptGuideStore)
삭제 영향: force=True 세계관 재인덱싱(rag/index.py)과 무관 — 별도 컬렉션이므로 안전
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from loguru import logger


def _normalize_model(model: str) -> str:
    """모델명을 소문자·하이픈 정규화해 metadata 키로 사용한다."""
    return re.sub(r"[\s_]+", "-", model.strip().lower())


class PromptGuideStore:
    """ChromaDB 'prompt_guides' 컬렉션 저장/조회."""

    _COLLECTION = "prompt_guides"

    def __init__(self, chroma_path: str, embedding_model: str | None = None) -> None:
        import chromadb

        self._client = chromadb.PersistentClient(path=chroma_path)

        if embedding_model:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            self._ef = SentenceTransformerEmbeddingFunction(model_name=embedding_model)
        else:
            self._ef = None  # stub/테스트 환경 — 임베딩 없이 metadata only

        logger.debug(f"[prompt_store] ChromaDB 연결: {chroma_path}")

    def _col(self):
        kwargs: dict = {"name": self._COLLECTION, "metadata": {"hnsw:space": "cosine"}}
        if self._ef:
            kwargs["embedding_function"] = self._ef
        return self._client.get_or_create_collection(**kwargs)

    def save(self, model: str, guide_text: str, source: str = "user") -> None:
        """모델 프롬프트 가이드를 저장한다. 동일 model의 기존 항목은 upsert로 덮어쓴다."""
        model_key = _normalize_model(model)
        doc_id = f"pg_{model_key}_{uuid.uuid4().hex[:8]}"

        self._col().upsert(
            ids=[doc_id],
            documents=[guide_text],
            metadatas=[{
                "model":    model_key,
                "source":   source,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }],
        )
        logger.info(f"[prompt_store] 저장: {doc_id} (model={model_key!r}, source={source!r})")

    def query(self, model: str) -> str | None:
        """모델명으로 저장된 가이드를 조회한다.

        ① metadata where {"model": model_key} exact match 우선
        ② 임베딩 모델이 있으면 semantic fallback
        ③ 없으면 None 반환
        """
        model_key = _normalize_model(model)
        col = self._col()
        if col.count() == 0:
            return None

        # ① exact match
        result = col.get(where={"model": {"$eq": model_key}}, include=["documents"])
        docs = result.get("documents", [])
        if docs:
            logger.info(f"[prompt_store] exact match: model={model_key!r}")
            # 여러 개 저장된 경우 가장 마지막(최신) 항목 반환
            return docs[-1]

        # ② semantic fallback (embedding 없으면 스킵)
        if self._ef is None:
            return None

        try:
            sem = col.query(
                query_texts=[model],
                n_results=1,
                include=["documents", "distances"],
            )
            sem_docs  = sem["documents"][0]
            sem_dists = sem["distances"][0]
            if sem_docs and sem_dists[0] <= 0.4:  # cosine distance ≤ 0.4 → 유사
                logger.info(f"[prompt_store] semantic match: model={model_key!r}, dist={sem_dists[0]:.3f}")
                return sem_docs[0]
        except Exception as e:
            logger.debug(f"[prompt_store] semantic fallback 실패: {e}")

        return None

    def delete(self, model: str) -> int:
        """특정 모델의 가이드 전체 삭제. 삭제된 수 반환."""
        model_key = _normalize_model(model)
        col = self._col()
        result = col.get(where={"model": {"$eq": model_key}})
        ids = result.get("ids", [])
        if ids:
            col.delete(ids=ids)
            logger.info(f"[prompt_store] 삭제: {len(ids)}개 (model={model_key!r})")
        return len(ids)

    def list_models(self) -> list[str]:
        """저장된 모델명 목록을 반환한다 (중복 제거)."""
        col = self._col()
        if col.count() == 0:
            return []
        result = col.get(include=["metadatas"])
        models = list({m["model"] for m in result.get("metadatas", []) if m})
        return sorted(models)
