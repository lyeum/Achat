"""
converter.py — 이미지 확장자 일괄 변환 도구 (Pillow 기반)

지원 포맷: jpg, jpeg, png, webp, bmp, tiff
영상/음성 변환은 ffmpeg 의존으로 미구현 (별도 tools/folder/converter_ffmpeg.py 예정)

LLM 파라미터:
  {"target": "/path", "from_ext": "png", "to_ext": "webp", "dry_run": true}

사용 예:
  tool = ConverterTool()
  params = tool.parse_params(llm_output)
  result = tool.execute(params)
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from tools.base import BaseTool

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}

# Pillow 저장 시 format 명
FORMAT_MAP = {
    ".jpg": "JPEG", ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".bmp": "BMP",
    ".tiff": "TIFF",
}


class ConverterTool(BaseTool):
    name = "image_convert"
    system_prompt = (
        "너는 이미지 파일 변환 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        '{"target": "<디렉토리 경로>", "from_ext": "<원본 확장자>", "to_ext": "<변환할 확장자>", "dry_run": true 또는 false}\n'
        "확장자는 점(.) 없이 소문자로 작성해라. 예: \"png\", \"webp\"\n"
        "경로가 명시되지 않으면 target은 현재 디렉토리(\".\")로 설정해라."
    )

    def execute(self, params: dict) -> str:
        try:
            from PIL import Image
        except ImportError:
            return "오류: Pillow가 설치되지 않았습니다. `uv add Pillow` 실행 후 재시도해주세요."

        target = Path(params.get("target", ".")).expanduser().resolve()
        from_ext = "." + params.get("from_ext", "").lstrip(".").lower()
        to_ext = "." + params.get("to_ext", "").lstrip(".").lower()
        dry_run = params.get("dry_run", True)

        if not target.exists() or not target.is_dir():
            return f"오류: 디렉토리가 존재하지 않습니다 — {target}"

        if from_ext not in SUPPORTED_EXTS:
            return f"오류: 지원하지 않는 원본 포맷 — {from_ext} (지원: {', '.join(SUPPORTED_EXTS)})"
        if to_ext not in SUPPORTED_EXTS:
            return f"오류: 지원하지 않는 변환 포맷 — {to_ext} (지원: {', '.join(SUPPORTED_EXTS)})"
        if from_ext == to_ext:
            return "원본과 변환 포맷이 동일합니다."

        files = list(target.glob(f"*{from_ext}"))
        if not files:
            return f"변환할 파일이 없습니다: {target}/*{from_ext}"

        if dry_run:
            lines = [f"[미리보기] {f.name} → {f.stem}{to_ext}" for f in files]
            return f"총 {len(files)}개 변환 예정 (dry_run=True, 실제 변환 없음)\n" + "\n".join(lines)

        fmt = FORMAT_MAP[to_ext]
        converted = 0
        failed = 0
        for src in files:
            dst = src.with_suffix(to_ext)
            try:
                with Image.open(src) as img:
                    # JPEG는 RGBA 미지원 → RGB 변환
                    if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    img.save(dst, fmt)
                logger.debug(f"변환: {src.name} → {dst.name}")
                converted += 1
            except Exception as e:
                logger.warning(f"변환 실패: {src.name} — {e}")
                failed += 1

        return f"완료: {converted}개 변환 / {failed}개 실패 (대상: {target})"
