from pathlib import Path

import yaml
from loguru import logger

REQUIRED_FIELDS = ["id", "name", "speech_style", "rules", "memory_voice", "state"]


def load_character(yaml_path: str | Path) -> dict:
    """CH_*.yaml 파일을 로드해 dict를 반환한다.

    필수 필드 누락 시 경고를 출력하지만 예외는 발생시키지 않는다.
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"캐릭터 파일 없음: {path}")

    with open(path, encoding="utf-8") as f:
        data: dict = yaml.safe_load(f)

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        logger.warning(f"[character_load] 누락 필드 {missing} — {path.name}")

    return data
