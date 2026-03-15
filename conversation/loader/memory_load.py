import json
from pathlib import Path

from loguru import logger


def load_memory_defaults(json_path: str | Path) -> list[dict]:
    """M_default.json을 읽어 ChromaDB 초기 삽입용 entries 리스트를 반환한다.

    파일이 없거나 비어있으면 빈 리스트를 반환한다.
    """
    path = Path(json_path)
    if not path.exists():
        logger.warning(f"[memory_load] 기본 메모리 파일 없음: {path}")
        return []

    with open(path, encoding="utf-8") as f:
        data: dict = json.load(f)

    entries = data.get("entries", [])
    logger.debug(f"[memory_load] {len(entries)}개 항목 로드 — {path.name}")
    return entries
