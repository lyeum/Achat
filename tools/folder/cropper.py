"""
cropper.py — 폴더 내 이미지 일괄 크롭 도구

방향(top/bottom/left/right)의 가장자리를 기준으로 지정한 크기만큼 잘라낸다.

  top    : (0, 0, width|원본폭, height)
  bottom : (0, 원본높이-height, width|원본폭, 원본높이)
  left   : (0, 0, width, height|원본높이)
  right  : (원본폭-width, 0, 원본폭, height|원본높이)
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from tools.base import BaseTool

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
_DIRECTION_ALIASES = {
    "top": "top", "위": "top", "상": "top",
    "bottom": "bottom", "아래": "bottom", "하": "bottom",
    "left": "left", "왼쪽": "left", "좌": "left",
    "right": "right", "오른쪽": "right", "우": "right",
}


class CropperTool(BaseTool):
    name = "image_crop"
    system_prompt = (
        "너는 이미지 일괄 크롭 도구의 파라미터를 추출하는 역할이다.\n"
        "사용자의 요청을 분석해서 아래 JSON 형식으로만 응답해라:\n"
        '{"target": "<폴더 경로>", "direction": "top|bottom|left|right",'
        ' "width": <정수 or null>, "height": <정수 or null>, "dry_run": false}\n'
        "direction은 크롭할 가장자리 방향이다 (top=위, bottom=아래, left=왼쪽, right=오른쪽).\n"
        "width/height 중 해당 방향에 필요한 값만 설정하고 나머지는 null로 설정해라.\n"
        "  top/bottom: height 필수, width 선택 (null이면 원본 폭 유지)\n"
        "  left/right: width 필수,  height 선택 (null이면 원본 높이 유지)"
    )

    def execute(self, params: dict) -> str:
        from PIL import Image  # type: ignore

        target    = params.get("target", "")
        direction = _DIRECTION_ALIASES.get(str(params.get("direction", "top")).lower(), "top")
        width     = params.get("width")
        height    = params.get("height")
        dry_run   = bool(params.get("dry_run", False))

        folder = Path(target).expanduser().resolve()
        if not folder.is_dir():
            return f"오류: 폴더를 찾을 수 없습니다 — {target}"

        # 필수 치수 검증
        if direction in ("top", "bottom") and not height:
            return "오류: top/bottom 크롭은 height가 필요합니다."
        if direction in ("left", "right") and not width:
            return "오류: left/right 크롭은 width가 필요합니다."

        images = sorted(f for f in folder.iterdir() if f.suffix.lower() in _IMG_EXTS)
        if not images:
            return f"'{folder.name}' 폴더에 이미지 파일이 없습니다."

        results: list[str] = []
        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    iw, ih = img.size

                    w = int(width)  if width  else iw
                    h = int(height) if height else ih

                    if direction == "top":
                        box = (0, 0, min(w, iw), min(h, ih))
                    elif direction == "bottom":
                        box = (0, max(ih - h, 0), min(w, iw), ih)
                    elif direction == "left":
                        box = (0, 0, min(w, iw), min(h, ih))
                    else:  # right
                        box = (max(iw - w, 0), 0, iw, min(h, ih))

                    crop_w = box[2] - box[0]
                    crop_h = box[3] - box[1]
                    preview = f"{img_path.name}: {iw}×{ih} → {crop_w}×{crop_h} ({direction})"

                    if dry_run:
                        results.append(f"[미리보기] {preview}")
                    else:
                        cropped = img.crop(box)
                        dst = img_path.parent / f"crop_{img_path.name}"
                        if img_path.suffix.lower() in (".jpg", ".jpeg") and cropped.mode in ("RGBA", "P"):
                            cropped = cropped.convert("RGB")
                        cropped.save(dst)
                        results.append(f"완료: {preview} → {dst.name}")
            except Exception as e:  # noqa: BLE001
                results.append(f"실패: {img_path.name} — {e}")

        header = f"{'[미리보기] ' if dry_run else ''}크롭 결과 — {folder.name} ({len(images)}개)"
        logger.info(f"[CropperTool] {header}")
        return header + "\n" + "\n".join(results)
