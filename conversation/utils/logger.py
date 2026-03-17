"""conversation/utils/logger.py — loguru 로거 설정 헬퍼.

사용 예:
    from conversation.utils.logger import setup_logger
    setup_logger()          # 기본 설정 (INFO, 파일 로테이션)
    setup_logger(level="DEBUG")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "achat"
_LOG_PATH  = _CACHE_DIR / "logs" / "achat.log"

_configured = False


def setup_logger(
    level: str = "INFO",
    log_file: Path | str | None = None,
    rotation: str = "10 MB",
    retention: str = "7 days",
) -> None:
    """loguru 로거를 초기화한다. 중복 호출 시 무시.

    Args:
        level:     로그 레벨 (DEBUG / INFO / WARNING / ERROR)
        log_file:  파일 경로 (None이면 기본 ~/.cache/achat/logs/achat.log)
        rotation:  파일 로테이션 기준 (기본 "10 MB")
        retention: 오래된 로그 보존 기간 (기본 "7 days")
    """
    global _configured
    if _configured:
        return

    logger.remove()  # 기본 핸들러 제거

    # 콘솔 핸들러 (색상 있는 간결한 포맷)
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    # 파일 핸들러 (로테이션 포함)
    file_path = Path(log_file) if log_file else _LOG_PATH
    file_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(file_path),
        level="DEBUG",   # 파일에는 DEBUG 이상 전부 기록
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
    )

    _configured = True
    logger.debug(f"[logger] 초기화 완료 — 레벨: {level}, 파일: {file_path}")
