#!/usr/bin/env python3
"""Render exact Chinese text for three native Xiaohongshu text-card variants."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


WIDTH, HEIGHT = 1080, 1440
VARIANTS = {
    "black_accent_card": {"pattern_id": "CP01", "background": "#6ADBCB", "card": "#050505", "text": "#FFFFFF", "accent": "#64EDC0", "font_size": 96, "max_lines": 7},
    "paper_meme_card": {"pattern_id": "CP02", "background": "#FFF3DB", "card": "#FFF3DB", "text": "#32170F", "accent": "#FF8527", "font_size": 86, "max_lines": 7},
    "highlight_note_card": {"pattern_id": "CP03", "background": "#FFFBA2", "card": "#FFFBA2", "text": "#20282C", "accent": "#77E6EA", "font_size": 92, "max_lines": 7},
}
FONT_CANDIDATES = [
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


class InputError(ValueError):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def choose_font_path(supplied: str | None) -> Path:
    if supplied:
        path = Path(supplied).expanduser().resolve()
        if not path.is_file():
            raise InputError("invalid_input", f"font_path does not exist: {path}")
        return path
    for path in FONT_CANDIDATES:
        if path.is_file():
            return path
    raise InputError("missing_font", "no Chinese-capable local font found")


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    if not text:
        return 0.0
    box = draw.textbbox((0, 0), text, font=font)
    return float(box[2] - box[0])


def accent_ranges(headline: str, terms: list[str]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for term in terms:
        if not term:
            raise InputError("invalid_input", "accent_terms cannot contain empty values")
        start = headline.find(term)
        if start < 0:
            raise InputError("invalid_input", f"accent term is not present in headline: {term}")
        ranges.append((start, start + len(term)))
    return ranges


def wrap_headline(draw: ImageDraw.ImageDraw, headline: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[list[tuple[str, int]]]:
    lines: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    current_text = ""
    for index, char in enumerate(headline):
        if char == "\n":
            lines.append(current)
            current, current_text = [], ""
            continue
        proposed = current_text + char
        if current and text_width(draw, proposed, font) > max_width:
            lines.append(current)
            current, current_text = [(char, index)], char
        else:
            current.append((char, index))
            current_text = proposed
    lines.append(current)
    return [line for line in lines if line]


def is_accent(index: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= index < end for start, end in ranges)


def draw_grid(draw: ImageDraw.ImageDraw) -> None:
    for x in range(24, WIDTH, 48):
        for y in range(24, HEIGHT, 48):
            draw.line((x - 5, y, x + 5, y), fill="#F3D9C5", width=2)
            draw.line((x, y - 5, x, y + 5), fill="#F3D9C5", width=2)


def paste_optional_sticker(image: Image.Image, payload: dict[str, Any]) -> None:
    supplied = payload.get("sticker_path")
    if not supplied:
        return
    if payload.get("sticker_rights_status") not in {"owned", "authorized"}:
        raise InputError("invalid_input", "sticker_path requires sticker_rights_status=owned|authorized")
    path = Path(str(supplied)).expanduser().resolve()
    if not path.is_file():
        raise InputError("invalid_input", f"sticker_path does not exist: {path}")
    try:
        with Image.open(path) as source:
            sticker = ImageOps.contain(source.convert("RGBA"), (340, 280))
            sticker.load()
    except Exception as exc:
        raise InputError("invalid_input", f"sticker cannot be decoded: {exc}") from exc
    x = (WIDTH - sticker.width) // 2
    y = HEIGHT - sticker.height - 110
    image.paste(sticker, (x, y), sticker)


def render(payload: dict[str, Any]) -> dict[str, Any]:
    variant = payload.get("variant")
    if variant not in VARIANTS:
        raise InputError("invalid_input", f"unknown variant: {variant}")
    headline = payload.get("headline")
    if not isinstance(headline, str) or not headline.strip():
        raise InputError("invalid_input", "headline must be a non-empty string")
    terms = payload.get("accent_terms", [])
    if not isinstance(terms, list) or not all(isinstance(term, str) for term in terms):
        raise InputError("invalid_input", "accent_terms must be an array of strings")
    if len(terms) > 2:
        raise InputError("invalid_input", "no more than two accent terms are allowed")
    output_value = payload.get("output_path")
    if not isinstance(output_value, str) or not output_value:
        raise InputError("invalid_input", "output_path is required")

    config = dict(VARIANTS[variant])
    accent = str(payload.get("accent_color") or config["accent"])
    image = Image.new("RGB", (WIDTH, HEIGHT), config["background"])
    draw = ImageDraw.Draw(image)
    if variant == "black_accent_card":
        draw.rounded_rectangle((54, 54, WIDTH - 54, HEIGHT - 54), radius=72, fill=config["card"])
    elif variant == "paper_meme_card":
        draw_grid(draw)

    font_path = choose_font_path(payload.get("font_path"))
    font = ImageFont.truetype(str(font_path), int(config["font_size"]))
    meta_font = ImageFont.truetype(str(font_path), 30)
    ranges = accent_ranges(headline, terms)
    max_width = WIDTH - 224
    lines = wrap_headline(draw, headline, font, max_width)
    if len(lines) > int(config["max_lines"]):
        raise InputError("text_overflow", f"headline wraps to {len(lines)} lines; maximum is {config['max_lines']}")

    line_height = int(config["font_size"] * 1.45)
    text_height = len(lines) * line_height
    start_y = max(250, (HEIGHT - text_height) // 2 - 20)
    bottom_limit = HEIGHT - (330 if payload.get("sticker_path") else 150)
    if start_y + text_height > bottom_limit:
        raise InputError("text_overflow", "headline collides with the lower safe area")

    meta = str(payload.get("meta") or "NATIVE NOTE")
    meta_fill = "#8E8E8E" if variant == "black_accent_card" else "#C8AE91"
    draw.text((118, 112), meta[:40], font=meta_font, fill=meta_fill)

    for line_number, line in enumerate(lines):
        y = start_y + line_number * line_height
        x = 112.0
        runs: list[tuple[float, float]] = []
        run_start: float | None = None
        for char, original_index in line:
            width = text_width(draw, char, font)
            accented = is_accent(original_index, ranges)
            if variant == "highlight_note_card" and accented and run_start is None:
                run_start = x
            if variant == "highlight_note_card" and not accented and run_start is not None:
                runs.append((run_start, x))
                run_start = None
            x += width
        if run_start is not None:
            runs.append((run_start, x))
        if variant == "highlight_note_card":
            for left, right in runs:
                draw.rounded_rectangle((left - 8, y + 14, right + 8, y + int(config["font_size"]) + 15), radius=14, fill=accent)

        x = 112.0
        for char, original_index in line:
            accented = is_accent(original_index, ranges)
            fill = config["text"]
            stroke_width = 0
            stroke_fill = None
            if variant != "highlight_note_card" and accented:
                fill = accent
            if variant == "paper_meme_card":
                stroke_width = 5
                stroke_fill = "#FFF9EF"
            draw.text((x, y), char, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
            x += text_width(draw, char, font)

    paste_optional_sticker(image, payload)
    output_path = Path(output_value).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return {
        "status": "rendered_prototype",
        "output_state": "prototype_only",
        "performance_evidence": "not_performance_evidence",
        "pattern_id": config["pattern_id"],
        "variant": variant,
        "output_path": str(output_path),
        "sha256": digest,
        "width": WIDTH,
        "height": HEIGHT,
        "font_path": str(font_path),
        "line_count": len(lines),
        "accent_terms": terms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise InputError("invalid_input", "input JSON must be an object")
        receipt = render(payload)
    except InputError as exc:
        emit({"status": exc.status, "reason": str(exc)})
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        emit({"status": "invalid_input", "reason": str(exc)})
        return 2
    emit(receipt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
