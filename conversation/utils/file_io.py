"""conversation/utils/file_io.py — YAML / JSON 파일 입출력 헬퍼.

사용 예:
    from conversation.utils.file_io import load_yaml, load_json, save_json

    data = load_yaml("conversation/character/CH_Haru.yaml")
    mem  = load_json("conversation/memory_act/M_default.json")
    save_json({"key": "value"}, "/tmp/out.json")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from loguru import logger


def load_yaml(path: str | Path) -> dict:
    """YAML 파일을 읽어 dict로 반환한다.

    Raises:
        FileNotFoundError: 파일이 없을 때
        yaml.YAMLError:    YAML 파싱 오류
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"YAML 파일 없음: {p}")
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    logger.debug(f"[file_io] YAML 로드: {p}")
    return data or {}


def load_json(path: str | Path) -> Any:
    """JSON 파일을 읽어 Python 객체로 반환한다.

    Raises:
        FileNotFoundError: 파일이 없을 때
        json.JSONDecodeError: JSON 파싱 오류
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSON 파일 없음: {p}")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    logger.debug(f"[file_io] JSON 로드: {p}")
    return data


def save_json(data: Any, path: str | Path, indent: int = 2, ensure_ascii: bool = False) -> None:
    """Python 객체를 JSON 파일로 저장한다. 부모 디렉토리가 없으면 자동 생성.

    Args:
        data:         저장할 Python 객체
        path:         저장 경로
        indent:       들여쓰기 (기본 2)
        ensure_ascii: ASCII 강제 변환 여부 (기본 False — 한글 유지)
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
    logger.debug(f"[file_io] JSON 저장: {p}")


def load_jsonl(path: str | Path) -> list[dict]:
    """JSONL(JSON Lines) 파일을 읽어 dict 리스트로 반환한다.

    Raises:
        FileNotFoundError: 파일이 없을 때
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSONL 파일 없음: {p}")
    records: list[dict] = []
    with open(p, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning(f"[file_io] JSONL 파싱 오류 (줄 {lineno}): {e}")
    logger.debug(f"[file_io] JSONL 로드: {p} ({len(records)}건)")
    return records
