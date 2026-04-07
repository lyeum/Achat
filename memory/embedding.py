"""공유 임베딩 함수 싱글턴.

LongTermMemory와 WorldRetriever가 동일한 SentenceTransformer 인스턴스를
재사용하도록 캐싱한다.

device 정책:
  - 기본값 "cpu" — LLM이 VRAM 대부분을 점유(~7.5 GB / 8 GB)하므로
    임베딩 모델을 GPU에 올리면 OOM 발생.
  - config에 embedding_device: "cuda" 를 명시하면 GPU 사용 가능.
"""
from __future__ import annotations

from threading import Lock

_cache: dict[tuple[str, str], object] = {}
_lock = Lock()


def get_embedding_function(model_name: str, device: str = "cpu"):
    """model_name + device 조합으로 캐시된 EmbeddingFunction을 반환한다.

    최초 호출 시 SentenceTransformer를 로드하고 이후 호출은 캐시를 반환한다.
    """
    key = (model_name, device)
    if key in _cache:
        return _cache[key]

    with _lock:
        if key in _cache:          # double-checked locking
            return _cache[key]
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(model_name=model_name, device=device)
        _cache[key] = ef
    return ef
