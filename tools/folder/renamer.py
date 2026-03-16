"""
renamer.py — 파일 이름 일괄 변환 도구

LLM 파라미터:
  {
    "target": "/path/to/dir",
    "pattern": "*.jpg",          # 대상 파일 glob 패턴
    "rule": "날짜_원본명",        # 변환 규칙 (아래 규칙 목록 참조)
    "prefix": "",                 # 접두사 추가 (선택)
    "suffix": "",                 # 접미사 추가 (선택, 확장자 앞)
    "dry_run": true
  }

지원 규칙:
  - "날짜_원본명"   : YYYYMMDD_원본명.ext  (파일 수정 시간 기준)
  - "번호_원본명"   : 001_원본명.ext
  - "원본명_번호"   : 원본명_001.ext
  - "소문자"        : 파일명 전체 소문자
  - "공백제거"      : 파일명의 공백을 _로 교체
  - "prefix추가"    : {prefix}원본명.ext  (params["prefix"] 사용)
  - "suffix추가"    : 원본명{suffix}.ext  (params["suffix"] 사용)
"""

from __future__ import annotations

import datetime
from pathlib import Path

from loguru import logger

from tools.base import BaseTool


class RenamerTool(BaseTool):
    name = "file_rename"
    system_prompt = (
        "너는 파일 이름 일괄 변환 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        "{\n"
        '  "target": "<디렉토리 경로>",\n'
        '  "pattern": "<glob 패턴, 기본 *>",\n'
        '  "rule": "<규칙명>",\n'
        '  "prefix": "<접두사, 선택>",\n'
        '  "suffix": "<접미사, 선택>",\n'
        '  "dry_run": true 또는 false\n'
        "}\n"
        "규칙: 날짜_원본명 / 번호_원본명 / 원본명_번호 / 소문자 / 공백제거 / prefix추가 / suffix추가"
    )

    def _new_name(self, f: Path, rule: str, idx: int, prefix: str, suffix: str) -> str:
        stem = f.stem
        ext = f.suffix

        if rule == "날짜_원본명":
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            date_str = mtime.strftime("%Y%m%d")
            return f"{date_str}_{stem}{ext}"
        elif rule == "번호_원본명":
            return f"{idx:03d}_{stem}{ext}"
        elif rule == "원본명_번호":
            return f"{stem}_{idx:03d}{ext}"
        elif rule == "소문자":
            return f"{stem.lower()}{ext.lower()}"
        elif rule == "공백제거":
            return f"{stem.replace(' ', '_')}{ext}"
        elif rule == "prefix추가":
            return f"{prefix}{stem}{ext}"
        elif rule == "suffix추가":
            return f"{stem}{suffix}{ext}"
        else:
            return f.name  # 알 수 없는 규칙 → 변경 없음

    def execute(self, params: dict) -> str:
        target = Path(params.get("target", ".")).expanduser().resolve()
        pattern = params.get("pattern", "*")
        rule = params.get("rule", "소문자")
        prefix = params.get("prefix", "")
        suffix = params.get("suffix", "")
        dry_run = params.get("dry_run", True)

        if not target.exists() or not target.is_dir():
            return f"오류: 디렉토리가 존재하지 않습니다 — {target}"

        files = sorted(f for f in target.glob(pattern) if f.is_file())
        if not files:
            return f"대상 파일이 없습니다: {target}/{pattern}"

        renames: list[tuple[Path, Path]] = []
        for idx, f in enumerate(files, start=1):
            new_name = self._new_name(f, rule, idx, prefix, suffix)
            dst = f.parent / new_name
            if dst != f:
                renames.append((f, dst))

        if not renames:
            return "변경할 파일이 없습니다 (이미 규칙에 맞는 이름)."

        if dry_run:
            lines = [f"[미리보기] {s.name} → {d.name}" for s, d in renames]
            return f"총 {len(renames)}개 변환 예정 (dry_run=True)\n" + "\n".join(lines)

        renamed = 0
        skipped = 0
        for src, dst in renames:
            if dst.exists():
                logger.warning(f"건너뜀 (충돌): {dst.name}")
                skipped += 1
                continue
            src.rename(dst)
            logger.debug(f"변환: {src.name} → {dst.name}")
            renamed += 1

        return f"완료: {renamed}개 변환 / {skipped}개 건너뜀 (대상: {target})"
