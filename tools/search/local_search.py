"""
local_search.py — 로컬 파일 검색 도구 (SQLite FTS5 기반)

LLM 파라미터:
  {
    "query": "<검색어>",
    "path": "/검색할 디렉토리",   # 기본 홈 디렉토리
    "ext": "py,txt,md",            # 확장자 필터 (선택, 쉼표 구분)
    "rebuild": false               # 인덱스 재구축 여부 (선택)
  }

동작:
  1. 대상 경로를 재귀 탐색하여 텍스트 파일 인덱싱 (SQLite FTS5)
  2. FTS5 MATCH 쿼리로 검색 → 상위 N개 결과 반환
  3. 인덱스 DB는 XDG_CACHE_HOME 또는 ~/.cache/achat/ 에 저장
  4. 같은 경로를 재검색할 때 mtime이 바뀐 파일만 갱신 (증분 인덱싱)

주의:
  - 바이너리 파일 / 1 MB 초과 파일은 건너뜀
  - FTS5 는 Python 표준 sqlite3에 포함 (추가 의존성 없음)
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from loguru import logger

from tools.base import BaseTool

# ── 설정 ──────────────────────────────────────────────────────────────

MAX_FILE_BYTES = 1 * 1024 * 1024   # 1 MB
MAX_RESULTS = 10
HWP_EXTS = {".hwp", ".hwpx"}
DEFAULT_EXTS = {".py", ".txt", ".md", ".rst", ".yaml", ".yml",
                ".json", ".toml", ".cfg", ".ini", ".sh", ".bat", ".log",
                ".hwp", ".hwpx"}

_CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "achat"
_DB_PATH = _CACHE_DIR / "local_search.db"


# ── DB 초기화 ─────────────────────────────────────────────────────────

def _get_conn(db_path: Path = _DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS file_meta (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS file_fts
            USING fts5(path UNINDEXED, content, tokenize='unicode61');
    """)
    conn.commit()
    return conn


# ── 인덱싱 ────────────────────────────────────────────────────────────

def _is_text(path: Path) -> bool:
    """바이너리 파일 여부를 간단히 판별한다."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" not in chunk
    except OSError:
        return False


def _read_hwp(path: Path) -> str | None:
    """hwp / hwpx 파일에서 텍스트를 추출한다.

    hwpx (zip 기반 XML):
        내부 section XML 파일에서 태그를 제거해 순수 텍스트를 반환한다.
    hwp (구형 바이너리):
        UTF-16 LE 디코딩으로 한글 텍스트를 부분 추출한다.
        OLE 파서 없이 처리하므로 일부 내용이 누락될 수 있다.
    """
    import re

    ext = path.suffix.lower()

    if ext == ".hwpx":
        import zipfile
        try:
            with zipfile.ZipFile(path) as z:
                parts: list[str] = []
                for name in z.namelist():
                    # 본문 XML만 추출 (섹션 파일: Contents/section0.xml 등)
                    if "section" in name.lower() and name.endswith(".xml"):
                        try:
                            xml = z.read(name).decode("utf-8", errors="ignore")
                            parts.append(re.sub(r"<[^>]+>", " ", xml))
                        except Exception:  # noqa: BLE001
                            continue
                return " ".join(parts) if parts else None
        except Exception:  # noqa: BLE001
            return None

    # .hwp 구형 바이너리 — UTF-16 LE 부분 추출
    try:
        raw = path.read_bytes()[:MAX_FILE_BYTES]
        text = raw.decode("utf-16-le", errors="ignore")
        # 제어문자 제거 (개행/탭 유지)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
        text = " ".join(text.split())
        return text if len(text) > 20 else None  # noqa: PLR2004
    except Exception:  # noqa: BLE001
        return None


def _index_directory(conn: sqlite3.Connection, root: Path, allowed_exts: set[str], rebuild: bool) -> int:
    """root 아래 텍스트 파일을 FTS5 테이블에 인덱싱한다. 갱신된 파일 수를 반환."""
    if rebuild:
        conn.execute("DELETE FROM file_meta")
        conn.execute("DELETE FROM file_fts")
        conn.commit()

    updated = 0
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in allowed_exts:
            continue
        if f.stat().st_size > MAX_FILE_BYTES:
            continue

        path_str = str(f)
        mtime = f.stat().st_mtime

        row = conn.execute(
            "SELECT mtime FROM file_meta WHERE path = ?", (path_str,)
        ).fetchone()

        if row and abs(row[0] - mtime) < 0.01:
            continue  # 변경 없음

        # 파일 읽기 (hwp/hwpx는 전용 추출, 나머지는 텍스트로)
        if f.suffix.lower() in HWP_EXTS:
            text = _read_hwp(f)
            if text is None:
                continue
        else:
            if not _is_text(f):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

        if row:
            conn.execute("DELETE FROM file_fts WHERE path = ?", (path_str,))
            conn.execute("UPDATE file_meta SET mtime = ? WHERE path = ?", (mtime, path_str))
        else:
            conn.execute("INSERT INTO file_meta VALUES (?, ?)", (path_str, mtime))

        conn.execute("INSERT INTO file_fts (path, content) VALUES (?, ?)", (path_str, text))
        updated += 1

    conn.commit()
    logger.debug(f"[local_search] 인덱싱 완료 — {updated}개 파일 갱신 ({root})")
    return updated


# ── 검색 ─────────────────────────────────────────────────────────────

def _search(conn: sqlite3.Connection, query: str, limit: int = MAX_RESULTS) -> list[tuple[str, str]]:
    """FTS5 MATCH 쿼리. [(path, snippet), ...] 반환."""
    rows = conn.execute(
        """
        SELECT path,
               snippet(file_fts, 1, '[', ']', '...', 20)
        FROM file_fts
        WHERE file_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    return rows


# ── Tool ─────────────────────────────────────────────────────────────

class LocalSearchTool(BaseTool):
    name = "local_search"
    system_prompt = (
        "너는 로컬 파일 검색 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        '{"query": "<검색어>", "path": "<디렉토리 경로>", "ext": "<확장자 목록, 쉼표 구분>", "rebuild": false}\n'
        "path가 명시되지 않으면 홈 디렉토리로 설정해라.\n"
        "ext가 명시되지 않으면 빈 문자열로 설정해라 (기본 확장자 사용).\n"
        "rebuild는 인덱스를 처음부터 다시 만들어야 할 때만 true로 설정해라."
    )

    def execute(self, params: dict) -> str:
        query = params.get("query", "").strip()
        root_str = params.get("path", str(Path.home()))
        ext_raw = params.get("ext", "")
        rebuild = params.get("rebuild", False)

        if not query:
            return "오류: 검색어가 없습니다."

        root = Path(root_str).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            return f"오류: 디렉토리가 존재하지 않습니다 — {root}"

        # 확장자 집합 결정
        if ext_raw:
            allowed_exts = {
                ("." + e.strip().lstrip(".")).lower()
                for e in ext_raw.split(",")
                if e.strip()
            }
        else:
            allowed_exts = DEFAULT_EXTS

        conn = _get_conn()
        try:
            updated = _index_directory(conn, root, allowed_exts, rebuild)
            results = _search(conn, query)
        except sqlite3.OperationalError as e:
            conn.close()
            return f"오류: 검색 중 DB 오류 — {e}"
        finally:
            conn.close()

        if not results:
            return f"'{query}'에 대한 검색 결과가 없습니다. (인덱싱: {updated}개 파일 갱신)"

        lines = [f"검색 결과 — '{query}' ({len(results)}건, 인덱싱 {updated}개 갱신)"]
        for i, (path, snippet) in enumerate(results, start=1):
            lines.append(f"\n[{i}] {path}")
            lines.append(f"    {snippet}")
        return "\n".join(lines)
