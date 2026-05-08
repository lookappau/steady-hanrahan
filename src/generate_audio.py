"""Generate TTS narration (one MP3 per slide) using Microsoft Edge TTS."""
from __future__ import annotations

import asyncio
import logging
import os
import re

import edge_tts
from mutagen.mp3 import MP3

from src import config
from src.utils import split_into_chunks

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_slide_scripts(readings: dict, content: dict) -> list[dict]:
    """Convert readings + AI content into ordered list of slide dicts.

    Each dict has:
        slide_id      int
        slide_type    str  ("title"|"context"|"reading"|"psalm"|"acclamation"|
                            "summary"|"reflection"|"prayer"|"closing")
        heading       str
        body          str  (displayed on slide)
        narration     str  (spoken by TTS — may differ from body for intro phrases)
        label         str  (small section label, e.g. "First Reading")
        reference     str  (scripture reference, shown in footer)
    """
    slides: list[dict] = []
    date_str = readings.get("date", "")
    liturgical_day = readings.get("liturgical_day", "Daily Mass")
    liturgical_season = readings.get("liturgical_season", "")

    # --- 00: Title ---
    slides.append(_make_slide(
        slide_type="title",
        heading="Daily Mass Readings",
        body=date_str,
        label=liturgical_season,
        reference="",
        narration=(
            f"Welcome to CFCA's Daily Mass Readings. "
            f"Today is {_format_date_spoken(date_str)}, {liturgical_day}."
        ),
    ))

    # --- 01: Liturgical Context ---
    slides.append(_make_slide(
        slide_type="context",
        heading=liturgical_day,
        body=f"Season: {liturgical_season}",
        label="Liturgical Day",
        reference="",
        narration=(
            f"Today we celebrate {liturgical_day}. "
            f"We are in the season of {liturgical_season}."
        ),
    ))

    # --- First Reading (may split) ---
    fr = readings.get("first_reading")
    if fr:
        chunks = split_into_chunks(fr["text"])
        for i, chunk in enumerate(chunks):
            intro = _reading_intro(fr["reference"]) if i == 0 else ""
            narration = (intro + " " + chunk).strip() if intro else chunk
            slides.append(_make_slide(
                slide_type="reading",
                heading=fr["reference"],
                body=chunk,
                label="First Reading" + (f" (cont.)" if i > 0 else ""),
                reference=fr["reference"],
                narration=narration,
            ))

    # --- Psalm ---
    psalm = readings.get("psalm")
    if psalm:
        antiphon_match = re.search(r"^(.+?)(?:\n|\.)", psalm["text"])
        antiphon = antiphon_match.group(1).strip() if antiphon_match else ""
        narration = (
            f"Responsorial Psalm. {psalm['reference']}. "
            f"The response is: {antiphon}. "
            + psalm["text"]
        )
        slides.append(_make_slide(
            slide_type="psalm",
            heading=psalm["reference"],
            body=psalm["text"],
            label="Responsorial Psalm",
            reference=psalm["reference"],
            narration=narration,
        ))

    # --- Second Reading (Sundays) ---
    sr = readings.get("second_reading")
    if sr:
        chunks = split_into_chunks(sr["text"])
        for i, chunk in enumerate(chunks):
            intro = _reading_intro(sr["reference"]) if i == 0 else ""
            narration = (intro + " " + chunk).strip() if intro else chunk
            slides.append(_make_slide(
                slide_type="reading",
                heading=sr["reference"],
                body=chunk,
                label="Second Reading" + (" (cont.)" if i > 0 else ""),
                reference=sr["reference"],
                narration=narration,
            ))

    # --- Gospel Acclamation ---
    acc = readings.get("gospel_acclamation")
    if acc:
        slides.append(_make_slide(
            slide_type="acclamation",
            heading="Gospel Acclamation",
            body=acc["text"],
            label="Alleluia",
            reference=acc.get("reference", ""),
            narration=f"Gospel Acclamation. Alleluia. {acc['text']}. Alleluia.",
        ))

    # --- Gospel (may split) ---
    gospel = readings.get("gospel") or {}
    chunks = split_into_chunks(gospel.get("text", ""))
    for i, chunk in enumerate(chunks):
        intro = _gospel_intro(gospel.get("reference", "")) if i == 0 else ""
        narration = (intro + " " + chunk).strip() if intro else chunk
        slides.append(_make_slide(
            slide_type="reading",
            heading=gospel.get("reference", "Gospel"),
            body=chunk,
            label="Gospel" + (" (cont.)" if i > 0 else ""),
            reference=gospel.get("reference", ""),
            narration=narration,
        ))

    # --- Summary ---
    slides.append(_make_slide(
        slide_type="summary",
        heading="Summary",
        body=content["summary"],
        label="Today's Theme",
        reference="",
        narration=content["summary"],
    ))

    # --- Reflection ---
    slides.append(_make_slide(
        slide_type="reflection",
        heading="Reflection",
        body=content["reflection"],
        label="For Your Prayer",
        reference="",
        narration="Take a moment to reflect. " + content["reflection"].replace("\n", " "),
    ))

    # --- Prayer ---
    slides.append(_make_slide(
        slide_type="prayer",
        heading="Closing Prayer",
        body=content["prayer"],
        label="Let Us Pray",
        reference="",
        narration=content["prayer"],
    ))

    # --- Closing ---
    slides.append(_make_slide(
        slide_type="closing",
        heading="God bless you.",
        body="Brought to you by CFCA\nCatholic Filipino Community of Australia",
        label="",
        reference="",
        narration=(
            "Thank you for joining us for today's Daily Mass Readings. "
            "God bless you and your family. "
            "Subscribe for daily readings, and we will see you tomorrow."
        ),
    ))

    # Number slides
    for i, slide in enumerate(slides):
        slide["slide_id"] = i

    return slides


def generate_all_audio(slide_scripts: list[dict]) -> list[str]:
    """Generate one MP3 per slide. Returns ordered list of MP3 paths."""
    paths: list[str] = []
    for slide in slide_scripts:
        sid = slide["slide_id"]
        out = os.path.join(config.AUDIO_DIR, f"audio_{sid:02d}.mp3")
        _tts_to_file(slide["narration"], out)
        paths.append(out)
        log.info("Audio %02d: %.1fs — %s", sid, get_audio_duration(out), out)
    return paths


def get_audio_duration(mp3_path: str) -> float:
    return MP3(mp3_path).info.length


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tts_to_file(text: str, output_path: str) -> None:
    """Run edge-tts and save to output_path. Falls back to gTTS if edge-tts fails."""
    # Try edge-tts (Australian voices, high quality)
    for voice in (config.VOICE, config.VOICE_FALLBACK):
        try:
            asyncio.run(_async_tts(text, voice, output_path))
            return
        except Exception as exc:
            log.warning("TTS voice %s failed: %s. Trying fallback...", voice, exc)

    # Fall back to gTTS (Google TTS, Australian accent, always free)
    try:
        _gtts_to_file(text, output_path)
        log.info("Used gTTS fallback for %s", output_path)
        return
    except Exception as exc:
        log.warning("gTTS fallback failed: %s", exc)

    log.error("All TTS voices failed for slide — writing silent placeholder")
    _write_silent_mp3(output_path)


def _gtts_to_file(text: str, output_path: str) -> None:
    from gtts import gTTS
    tts = gTTS(text=text, lang="en", tld="com.au", slow=False)
    tts.save(output_path)


async def _async_tts(text: str, voice: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(
        text, voice, rate=config.TTS_RATE, pitch=config.TTS_PITCH
    )
    await communicate.save(output_path)


def _write_silent_mp3(path: str) -> None:
    """Write a minimal 1-second silent MP3 so the pipeline can continue."""
    # Minimal valid MP3 frame (silence)
    silent = bytes([0xFF, 0xFB, 0x90, 0x00] + [0x00] * 413)
    with open(path, "wb") as f:
        for _ in range(38):  # ~1 second
            f.write(silent)


def _make_slide(**kwargs) -> dict:
    return {
        "slide_id": 0,  # will be overwritten
        **kwargs,
    }


def _reading_intro(reference: str) -> str:
    book, chapter_verse = _split_reference(reference)
    return f"A reading from {book}, {chapter_verse}."


def _gospel_intro(reference: str) -> str:
    book, chapter_verse = _split_reference(reference)
    return f"A reading from the Holy Gospel according to {book}, {chapter_verse}."


def _split_reference(reference: str) -> tuple[str, str]:
    """Split 'Acts 15:22-31' → ('Acts', 'chapter 15, verses 22 to 31')."""
    m = re.match(r"^([\w\s]+?)\s+(\d+):(.+)$", reference.strip())
    if not m:
        return reference, ""
    book, chapter, verses = m.group(1), m.group(2), m.group(3)
    verses_spoken = verses.replace("-", " to ").replace(",", " and")
    return book.strip(), f"chapter {chapter}, verses {verses_spoken}"


def _format_date_spoken(date_str: str) -> str:
    """'2026-05-08' → 'Friday, the 8th of May, 2026'."""
    try:
        import datetime
        d = datetime.date.fromisoformat(date_str)
        day = d.day
        suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return d.strftime(f"%A, the {day}{suffix} of %B, %Y")
    except Exception:
        return date_str


if __name__ == "__main__":
    import datetime, json
    from src.utils import setup_logging, ensure_dirs
    from src.fetch_readings import fetch_readings
    from src.generate_content import generate_all_content
    setup_logging()
    ensure_dirs()
    readings = fetch_readings(datetime.date.today())
    content = generate_all_content(readings)
    scripts = build_slide_scripts(readings, content)
    paths = generate_all_audio(scripts)
    for p in paths:
        print(p, f"{get_audio_duration(p):.1f}s")
