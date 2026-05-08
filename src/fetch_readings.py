"""Fetch daily Catholic Mass readings from Universalis (Australia)."""
from __future__ import annotations

import datetime
import logging
import re

import requests
from bs4 import BeautifulSoup

from src import config
from src.utils import retry

log = logging.getLogger(__name__)

GOSPEL_BOOKS = {
    "Matthew", "Mark", "Luke", "John",
    "Mt", "Mk", "Lk", "Jn",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; steady-hanrahan/1.0; "
        "+https://github.com/cfca/steady-hanrahan)"
    )
}


class ReadingsFetchError(RuntimeError):
    pass


def fetch_readings(date: datetime.date) -> dict:
    """Return structured readings dict for the given date."""
    date_str = date.strftime("%Y%m%d")
    try:
        return _fetch_universalis(date_str)
    except Exception as exc:
        log.warning("Universalis fetch failed (%s). Trying fallback...", exc)

    try:
        return _fetch_catholic_readings_api(date)
    except Exception as exc:
        raise ReadingsFetchError(
            f"All reading sources failed for {date}: {exc}"
        ) from exc


@retry(max_attempts=3, delay=5, exceptions=(requests.RequestException,))
def _fetch_universalis(date_str: str) -> dict:
    url = config.UNIVERSALIS_URL.format(date=date_str)
    log.info("Fetching readings from %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return _parse_universalis_html(resp.text, date_str)


def _parse_universalis_html(html: str, date_str: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # --- Liturgical day ---
    liturgical_day = _extract_liturgical_day(soup)

    # --- Collect all reading blocks ---
    blocks = _extract_reading_blocks(soup)

    if len(blocks) < 2:
        raise ReadingsFetchError("Too few reading blocks parsed from Universalis HTML")

    result: dict = {
        "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
        "liturgical_day": liturgical_day,
        "liturgical_season": _infer_season(liturgical_day),
        "first_reading": None,
        "psalm": None,
        "gospel_acclamation": None,
        "gospel": None,
    }

    for block in blocks:
        ref = block["reference"]
        if _is_psalm(ref):
            result["psalm"] = block
        elif _is_gospel(ref):
            result["gospel"] = block
        elif _is_acclamation(ref, block.get("text", "")):
            result["gospel_acclamation"] = block
        elif result["first_reading"] is None:
            result["first_reading"] = block

    # Second reading (Sunday) — slot if first already filled and no gospel yet
    _assign_second_reading(result, blocks)

    if not result["gospel"]:
        raise ReadingsFetchError("Gospel not found in parsed readings")

    return result


def _extract_liturgical_day(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(["h2", "h3"]):
        text = tag.get_text(strip=True)
        days = ("Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday", "Saturday")
        if any(d in text for d in days) or "feast" in text.lower() or "solemnity" in text.lower():
            return text
    # Fallback: look for any heading near the top
    first_h = soup.find(["h1", "h2"])
    return first_h.get_text(strip=True) if first_h else "Daily Mass"


def _extract_reading_blocks(soup: BeautifulSoup) -> list[dict]:
    blocks: list[dict] = []
    headings = soup.find_all("h4")
    for h4 in headings:
        reference = h4.get_text(strip=True)
        if not reference or len(reference) > 120:
            continue
        text_parts: list[str] = []
        for sib in h4.find_next_siblings():
            if sib.name in ("h4", "h2", "h3", "h1"):
                break
            if sib.name == "p":
                t = sib.get_text(" ", strip=True)
                if t:
                    text_parts.append(t)
        text = " ".join(text_parts)
        if text:
            blocks.append({"reference": reference, "text": text, "title": reference})
    return blocks


def _is_psalm(ref: str) -> bool:
    return bool(re.search(r"\bPs(alm)?\b", ref, re.IGNORECASE))


def _is_gospel(ref: str) -> bool:
    return any(book in ref for book in GOSPEL_BOOKS)


def _is_acclamation(ref: str, text: str) -> bool:
    keywords = ("Alleluia", "alleluia", "Gospel Acclamation", "Acclamation")
    return any(k in ref or k in text for k in keywords)


def _infer_season(liturgical_day: str) -> str:
    day_lower = liturgical_day.lower()
    seasons = {
        "advent": "Advent",
        "christmas": "Christmas",
        "lent": "Lent",
        "easter": "Eastertide",
        "holy week": "Holy Week",
        "ordinary": "Ordinary Time",
    }
    for key, season in seasons.items():
        if key in day_lower:
            return season
    return "Ordinary Time"


def _assign_second_reading(result: dict, blocks: list[dict]) -> None:
    """On Sundays there may be a second reading between psalm and gospel."""
    filled = {k for k, v in result.items() if v is not None and k not in ("date", "liturgical_day", "liturgical_season")}
    if "gospel_acclamation" not in filled:
        # Not a Sunday, nothing to do
        return
    # Check if any block is not yet assigned
    assigned_refs = {
        (result[k] or {}).get("reference")
        for k in ("first_reading", "psalm", "gospel_acclamation", "gospel")
    }
    for block in blocks:
        if block["reference"] not in assigned_refs and not _is_psalm(block["reference"]) and not _is_gospel(block["reference"]) and not _is_acclamation(block["reference"], block["text"]):
            result["second_reading"] = block
            break


@retry(max_attempts=3, delay=5, exceptions=(requests.RequestException,))
def _fetch_catholic_readings_api(date: datetime.date) -> dict:
    url = f"https://catholicreadings.org/api/daily?date={date.isoformat()}"
    log.info("Fetching fallback readings from %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return {
        "date": date.isoformat(),
        "liturgical_day": data.get("liturgical_day", "Daily Mass"),
        "liturgical_season": "Ordinary Time",
        "first_reading": {
            "reference": data.get("first_reading_reference", ""),
            "text": data.get("first_reading", ""),
            "title": data.get("first_reading_reference", ""),
        },
        "psalm": {
            "reference": data.get("psalm_reference", ""),
            "text": data.get("psalm", ""),
            "title": data.get("psalm_reference", ""),
        },
        "gospel_acclamation": None,
        "gospel": {
            "reference": data.get("gospel_reference", ""),
            "text": data.get("gospel", ""),
            "title": data.get("gospel_reference", ""),
        },
    }


# --- Manual test entry point ---
if __name__ == "__main__":
    import json
    from src.utils import setup_logging
    setup_logging()
    readings = fetch_readings(datetime.date.today())
    print(json.dumps(readings, indent=2, ensure_ascii=False))
