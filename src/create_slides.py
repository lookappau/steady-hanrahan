"""Generate PNG slide images (1920×1080) using Pillow."""
from __future__ import annotations

import logging
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from src import config
from src.utils import wrap_text, hex_to_rgb

log = logging.getLogger(__name__)

W, H = config.RESOLUTION
MARGIN = config.MARGIN


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_all_slides(slide_scripts: list[dict]) -> list[str]:
    """Render one PNG per slide. Returns ordered list of PNG paths."""
    paths: list[str] = []
    for slide in slide_scripts:
        sid = slide["slide_id"]
        out = os.path.join(config.SLIDES_DIR, f"slide_{sid:02d}.png")
        _render_slide(slide, out)
        paths.append(out)
        log.info("Slide %02d rendered: %s", sid, out)
    return paths


# ---------------------------------------------------------------------------
# Font loading
# ---------------------------------------------------------------------------

def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(config.FONT_DIR, filename)
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        log.warning("Font %s not found — using default font", path)
        return ImageFont.load_default()


def _fonts() -> dict:
    return {
        "title":   _load_font("CrimsonText-Bold.ttf",    config.FONT_SIZES["title"]),
        "heading": _load_font("CrimsonText-Bold.ttf",    config.FONT_SIZES["heading"]),
        "body":    _load_font("CrimsonText-Regular.ttf", config.FONT_SIZES["body"]),
        "label":   _load_font("CrimsonText-Italic.ttf",  config.FONT_SIZES["label"]),
        "meta":    _load_font("CrimsonText-Regular.ttf", config.FONT_SIZES["meta"]),
        "italic":  _load_font("CrimsonText-Italic.ttf",  config.FONT_SIZES["body"]),
    }


# ---------------------------------------------------------------------------
# Slide rendering dispatch
# ---------------------------------------------------------------------------

def _render_slide(data: dict, output_path: str) -> None:
    img = Image.new("RGB", (W, H), _c("bg_deep"))

    bg_path = data.get("bg_image", "")
    if bg_path and os.path.exists(bg_path):
        try:
            bg = Image.open(bg_path).convert("RGBA")
            bg = bg.resize((W, H), Image.LANCZOS)
            r, g, b, a = bg.split()
            a = a.point(lambda x: int(x * 0.20))
            bg = Image.merge("RGBA", (r, g, b, a))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, bg)
            img = img.convert("RGB")
        except Exception as exc:
            log.warning("Could not apply background image %s: %s", bg_path, exc)

    draw = ImageDraw.Draw(img)
    fonts = _fonts()

    slide_type = data.get("slide_type", "reading")

    if slide_type == "title":
        _layout_title(draw, img, fonts, data)
    elif slide_type == "closing":
        _layout_closing(draw, img, fonts, data)
    elif slide_type == "reflection":
        _layout_reflection(draw, img, fonts, data)
    elif slide_type == "prayer":
        _layout_prayer(draw, img, fonts, data)
    elif slide_type == "psalm":
        _layout_psalm(draw, img, fonts, data)
    else:
        _layout_standard(draw, img, fonts, data)

    img.save(output_path, "PNG")


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _layout_title(draw: ImageDraw.Draw, img: Image.Image,
                  fonts: dict, data: dict) -> None:
    _draw_background_accent(draw)
    _draw_logo(img, MARGIN, MARGIN, config.LOGO_SIZE)
    _draw_channel_name(draw, fonts)

    # Large title centred
    title_lines = wrap_text("Daily Mass Readings", max_chars=30)
    y = 280
    for line in title_lines:
        _draw_centred(draw, line, y, fonts["title"], _c("gold"))
        y += config.FONT_SIZES["title"] + 16

    # Date
    date_str = data.get("body", "")
    _draw_centred(draw, _format_date_display(date_str), y + 20, fonts["heading"], _c("cream"))

    # Liturgical season label
    label = data.get("label", "")
    if label:
        _draw_centred(draw, label, y + 120, fonts["label"], _c("muted"))

    _draw_rule(draw, H - 120)
    _draw_centred(draw, "Catholic Daily Mass Readings",
                  H - 90, fonts["meta"], _c("muted"))


def _layout_closing(draw: ImageDraw.Draw, img: Image.Image,
                    fonts: dict, data: dict) -> None:
    _draw_background_accent(draw)
    _draw_logo(img, W // 2 - 150, 200, config.LOGO_LARGE_SIZE)
    _draw_rule(draw, 540)
    _draw_centred(draw, data.get("heading", ""), 580, fonts["title"], _c("gold"))
    y = 700
    for line in data.get("body", "").split("\n"):
        _draw_centred(draw, line.strip(), y, fonts["meta"], _c("muted"))
        y += config.FONT_SIZES["meta"] + 10
    _draw_rule(draw, H - 120)
    _draw_centred(draw, "Subscribe for daily readings", H - 90, fonts["meta"], _c("muted"))


def _layout_reflection(draw: ImageDraw.Draw, img: Image.Image,
                       fonts: dict, data: dict) -> None:
    _draw_background_accent(draw)
    _draw_logo(img, MARGIN, MARGIN, config.LOGO_SIZE)
    _draw_channel_name(draw, fonts)
    _draw_rule(draw, config.RULE_Y_TOP)

    y = config.RULE_Y_TOP + 30
    _draw_label(draw, data.get("label", ""), y, fonts)
    y += 50

    _draw_centred(draw, data.get("heading", ""), y, fonts["heading"], _c("gold"))
    y += config.FONT_SIZES["heading"] + 20

    body = data.get("body", "")
    text_h = _text_block_height(body, max_chars=78,
                                font_size=config.FONT_SIZES["body"],
                                line_gap=8, para_gap=16)
    available = (H - 60) - y
    y += max(0, (available - text_h) // 2)

    for line in body.split("\n"):
        line = line.strip()
        if not line:
            continue
        wrapped = wrap_text(line, max_chars=78)
        for i, wl in enumerate(wrapped):
            color = _c("gold") if i == 0 and line[0].isdigit() else _c("cream")
            _draw_centred(draw, wl, y, fonts["body"], color)
            y += config.FONT_SIZES["body"] + 8
            if y > H - 100:
                break
        y += 16
        if y > H - 100:
            break

    _draw_rule(draw, H - 60)
    _draw_footer(draw, data.get("reference", ""), fonts)


def _layout_prayer(draw: ImageDraw.Draw, img: Image.Image,
                   fonts: dict, data: dict) -> None:
    _draw_background_accent(draw)
    _draw_logo(img, MARGIN, MARGIN, config.LOGO_SIZE)
    _draw_channel_name(draw, fonts)
    _draw_rule(draw, config.RULE_Y_TOP)

    y = config.RULE_Y_TOP + 30
    _draw_label(draw, data.get("label", ""), y, fonts)
    y += 50

    _draw_centred(draw, data.get("heading", ""), y, fonts["heading"], _c("gold"))
    y += config.FONT_SIZES["heading"] + 40

    body = data.get("body", "")
    text_h = _text_block_height(body, max_chars=52,
                                font_size=config.FONT_SIZES["body"], line_gap=10)
    available = (H - 60) - y
    y += max(0, (available - text_h) // 2)

    for line in wrap_text(body, max_chars=52):
        _draw_centred(draw, line, y, fonts["italic"], _c("cream"))
        y += config.FONT_SIZES["body"] + 10

    _draw_rule(draw, H - 60)
    _draw_footer(draw, "", fonts)


def _layout_psalm(draw: ImageDraw.Draw, img: Image.Image,
                  fonts: dict, data: dict) -> None:
    _draw_background_accent(draw)
    _draw_logo(img, MARGIN, MARGIN, config.LOGO_SIZE)
    _draw_channel_name(draw, fonts)
    _draw_rule(draw, config.RULE_Y_TOP)

    y = config.RULE_Y_TOP + 30
    _draw_label(draw, data.get("label", ""), y, fonts)
    y += 50

    _draw_centred(draw, data.get("heading", ""), y, fonts["heading"], _c("gold"))
    y += config.FONT_SIZES["heading"] + 20

    # Psalm text — italic for antiphon-like lines, regular for stanzas
    text = data.get("body", "")
    lines = text.split("\n") if "\n" in text else wrap_text(text, max_chars=78)
    first = True
    for line in lines:
        line = line.strip()
        if not line:
            y += 12
            continue
        font = fonts["italic"] if first else fonts["body"]
        color = _c("gold") if first else _c("cream")
        _draw_centred(draw, line, y, font, color)
        y += config.FONT_SIZES["body"] + 6
        if first:
            y += 10
            first = False
        if y > H - 100:
            break

    _draw_rule(draw, H - 60)
    _draw_footer(draw, data.get("reference", ""), fonts)


def _layout_standard(draw: ImageDraw.Draw, img: Image.Image,
                     fonts: dict, data: dict) -> None:
    _draw_background_accent(draw)
    _draw_logo(img, MARGIN, MARGIN, config.LOGO_SIZE)
    _draw_channel_name(draw, fonts)
    _draw_rule(draw, config.RULE_Y_TOP)

    y = config.RULE_Y_TOP + 30
    _draw_label(draw, data.get("label", ""), y, fonts)
    y += 50

    _draw_centred(draw, data.get("heading", ""), y, fonts["heading"], _c("gold"))
    y += config.FONT_SIZES["heading"] + 20

    text = data.get("body", "")
    text_h = _text_block_height(text, max_chars=78,
                                font_size=config.FONT_SIZES["body"], line_gap=8)
    available = (H - 60) - y
    y += max(0, (available - text_h) // 2)

    for line in wrap_text(text, max_chars=78):
        _draw_centred(draw, line, y, fonts["body"], _c("cream"))
        y += config.FONT_SIZES["body"] + 8
        if y > H - 100:
            break

    _draw_rule(draw, H - 60)
    _draw_footer(draw, data.get("reference", ""), fonts)


# ---------------------------------------------------------------------------
# Drawing primitives
# ---------------------------------------------------------------------------

def _c(name: str) -> tuple[int, int, int]:
    return hex_to_rgb(config.COLORS[name])


def _draw_background_accent(draw: ImageDraw.Draw) -> None:
    """Thin gold strip at very top and bottom of frame."""
    draw.rectangle([(0, 0), (W, 6)], fill=_c("gold"))
    draw.rectangle([(0, H - 6), (W, H)], fill=_c("gold"))


def _draw_rule(draw: ImageDraw.Draw, y: int) -> None:
    x0 = MARGIN
    x1 = W - MARGIN
    draw.rectangle([(x0, y), (x1, y + config.RULE_THICKNESS)], fill=_c("gold"))


def _draw_channel_name(draw: ImageDraw.Draw, fonts: dict) -> None:
    x = MARGIN + config.LOGO_SIZE[0] + 24
    draw.text((x, MARGIN + 10), "Catholic Daily Mass Readings",
              font=fonts["heading"], fill=_c("gold"))


def _draw_label(draw: ImageDraw.Draw, text: str, y: int, fonts: dict) -> None:
    if text:
        _draw_centred(draw, text, y, fonts["label"], _c("muted"))


def _draw_text_left(draw: ImageDraw.Draw, text: str, y: int,
                    font: ImageFont.FreeTypeFont, color: tuple) -> None:
    draw.text((MARGIN, y), text, font=font, fill=color)


def _draw_centred(draw: ImageDraw.Draw, text: str, y: int,
                  font: ImageFont.FreeTypeFont, color: tuple) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    x = (W - tw) // 2
    draw.text((x, y), text, font=font, fill=color)


def _draw_footer(draw: ImageDraw.Draw, reference: str, fonts: dict) -> None:
    y = H - 50
    if reference:
        draw.text((MARGIN, y), reference, font=fonts["meta"], fill=_c("muted"))


def _text_block_height(body: str, max_chars: int,
                       font_size: int, line_gap: int, para_gap: int = 0) -> int:
    """Pre-calculate total pixel height of body text before drawing."""
    total = 0
    paragraphs = [p.strip() for p in body.split("\n") if p.strip()]
    for i, para in enumerate(paragraphs):
        lines = wrap_text(para, max_chars=max_chars)
        total += len(lines) * (font_size + line_gap)
        if i < len(paragraphs) - 1:
            total += para_gap
    return total


def _draw_logo(img: Image.Image, x: int, y: int,
               size: tuple[int, int]) -> None:
    if not os.path.exists(config.LOGO_PATH):
        return
    try:
        logo = Image.open(config.LOGO_PATH).convert("RGBA")
        logo = logo.resize(size, Image.LANCZOS)
        img.paste(logo, (x, y), logo)
    except Exception as exc:
        log.warning("Could not load logo: %s", exc)


def _format_date_display(date_str: str) -> str:
    try:
        import datetime
        d = datetime.date.fromisoformat(date_str)
        return d.strftime("%A, %-d %B %Y") if os.name != "nt" else d.strftime("%A, %d %B %Y")
    except Exception:
        return date_str


if __name__ == "__main__":
    import datetime, json
    from src.utils import setup_logging, ensure_dirs
    from src.fetch_readings import fetch_readings
    from src.generate_content import generate_all_content
    from src.generate_audio import build_slide_scripts
    setup_logging()
    ensure_dirs()
    readings = fetch_readings(datetime.date.today())
    content = generate_all_content(readings)
    scripts = build_slide_scripts(readings, content)
    paths = create_all_slides(scripts)
    print("Slides created:", len(paths))
    for p in paths:
        print(" ", p)
