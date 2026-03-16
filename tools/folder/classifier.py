"""
classifier.py — 파일 분류 도구

LLM 파라미터:
  {"target": "/path/to/dir", "rule": "확장자별" | "종류별", "dry_run": true}

확장자별: 확장자 그대로 폴더 생성 (images/, docs/ 등)
종류별:   MIME 타입 기반으로 대분류 폴더에 이동

사용 예:
  tool = ClassifierTool()
  params = tool.parse_params(llm_output)
  result = tool.execute(params)
"""

from __future__ import annotations

import shutil
from pathlib import Path

from loguru import logger

from tools.base import BaseTool

# 종류별 분류 매핑 (확장자 → 폴더명)
CATEGORY_MAP: dict[str, str] = {
    # 이미지
    ".jpg": "images", ".jpeg": "images", ".png": "images",
    ".gif": "images", ".bmp": "images", ".webp": "images",
    ".svg": "images", ".ico": "images", ".tiff": "images",
    # 동영상
    ".mp4": "videos", ".mkv": "videos", ".avi": "videos",
    ".mov": "videos", ".wmv": "videos", ".flv": "videos",
    # 오디오
    ".mp3": "audio", ".wav": "audio", ".flac": "audio",
    ".aac": "audio", ".ogg": "audio", ".m4a": "audio",
    # 문서
    ".pdf": "docs", ".docx": "docs", ".doc": "docs",
    ".xlsx": "docs", ".xls": "docs", ".pptx": "docs",
    ".txt": "docs", ".md": "docs", ".csv": "docs",
    # 코드
    ".py": "code", ".js": "code", ".ts": "code",
    ".html": "code", ".css": "code", ".json": "code",
    ".yaml": "code", ".yml": "code", ".sh": "code",
    # 압축
    ".zip": "archives", ".tar": "archives", ".gz": "archives",
    ".7z": "archives", ".rar": "archives",
}


class ClassifierTool(BaseTool):
    name = "folder_classify"
    system_prompt = (
        "너는 파일 분류 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        '{"target": "<분류할 디렉토리 경로>", "rule": "확장자별" 또는 "종류별", "dry_run": true 또는 false}\n'
        "dry_run이 true이면 실제로 파일을 이동하지 않고 미리보기만 한다.\n"
        "경로가 명시되지 않으면 target은 현재 디렉토리(\".\")로 설정해라."
    )

    def execute(self, params: dict) -> str:
        target = Path(params.get("target", ".")).expanduser().resolve()
        rule = params.get("rule", "종류별")
        dry_run = params.get("dry_run", True)

        if not target.exists():
            return f"오류: 경로가 존재하지 않습니다 — {target}"
        if not target.is_dir():
            return f"오류: 디렉토리가 아닙니다 — {target}"

        files = [f for f in target.iterdir() if f.is_file()]
        if not files:
            return f"분류할 파일이 없습니다: {target}"

        moves: list[tuple[Path, Path]] = []
        for f in files:
            ext = f.suffix.lower()
            if rule == "확장자별":
                folder_name = ext.lstrip(".") if ext else "no_ext"
            else:
                folder_name = CATEGORY_MAP.get(ext, "others")

            dest_dir = target / folder_name
            dest = dest_dir / f.name
            moves.append((f, dest))

        if dry_run:
            lines = [f"[미리보기] {m[0].name} → {m[1].parent.name}/" for m in moves]
            return f"총 {len(moves)}개 파일 분류 예정 (dry_run=True, 실제 이동 없음)\n" + "\n".join(lines)

        moved = 0
        skipped = 0
        for src, dst in moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                logger.warning(f"건너뜀 (이미 존재): {dst.name}")
                skipped += 1
                continue
            shutil.move(str(src), str(dst))
            moved += 1
            logger.debug(f"이동: {src.name} → {dst.parent.name}/")

        return f"완료: {moved}개 이동 / {skipped}개 건너뜀 (대상: {target})"
