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
        return _fetch_universalis(date_str, date)
    except Exception as exc:
        raise ReadingsFetchError(
            f"Failed to fetch readings for {date}: {exc}"
        ) from exc


@retry(max_attempts=3, delay=5, exceptions=(requests.RequestException,))
def _fetch_universalis(date_str: str, date: datetime.date) -> dict:
    url = config.UNIVERSALIS_URL.format(date=date_str)
    log.info("Fetching readings from %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return _parse_universalis_html(resp.text, date)


def _parse_universalis_html(html: str, date: datetime.date) -> dict:
    """Parse Universalis HTML.

    Structure: each reading section is a <table class="each"> with two <th>:
      - th[0]: section label  (e.g. "First reading", "Gospel")
      - th[1]: scripture ref  (e.g. "Acts 15:22-31", "John 15:12-17")
    Followed by optional <h4> (reading title) and <div class="p|pi"> (text).
    """
    soup = BeautifulSoup(html, "html.parser")
    liturgical_day = _extract_liturgical_day(soup)

    result: dict = {
        "date": date.isoformat(),
        "liturgical_day": liturgical_day,
        "liturgical_season": _infer_season(liturgical_day),
        "first_reading": None,
        "psalm": None,
        "gospel_acclamation": None,
        "gospel": None,
    }

    for table in soup.find_all("table", class_="each"):
        ths = table.find_all("th")
        if len(ths) < 2:
            continue

        label = ths[0].get_text(strip=True).lower()
        reference = ths[1].get_text(strip=True)

        # Collect title (first h4) and text divs until next section or non-reading content
        _STOP_CLASSES = {"podcastentry", "audioclip", "ad", "footer"}
        title = ""
        text_parts: list[str] = []
        for sib in table.find_next_siblings():
            if sib.name == "table" and "each" in (sib.get("class") or []):
                break
            if sib.name == "hr":
                break
            if sib.name == "h4" and not title:
                title = sib.get_text(strip=True)
            if sib.name == "div" and sib.get("class"):
                cls = set(sib.get("class", []))
                if cls & _STOP_CLASSES:
                    break
                t = sib.get_text(" ", strip=True)
                if t:
                    text_parts.append(t)

        text = " ".join(text_parts).strip()
        if not text:
            continue

        block = {
            "reference": reference,
            "title": title or reference,
            "text": text,
        }

        if "first reading" in label:
            result["first_reading"] = block
        elif "second reading" in label:
            result["second_reading"] = block
        elif "psalm" in label:
            result["psalm"] = block
        elif "acclamation" in label or "alleluia" in label:
            result["gospel_acclamation"] = block
        elif label == "gospel" or label.startswith("gospel"):
            result["gospel"] = block

    if not result["gospel"]:
        raise ReadingsFetchError(
            f"Gospel not found in Universalis page. "
            f"Labels found: {_debug_labels(soup)}"
        )

    return result


def _extract_liturgical_day(soup: BeautifulSoup) -> str:
    """Extract the liturgical day description from the page."""
    # Universalis puts it in <span id="feastname">
    feast = soup.find(id="feastname")
    if feast:
        return feast.get_text(strip=True)

    # Fallback: look in body text near the top
    body = soup.get_text(" ")
    for line in body.splitlines():
        line = line.strip()
        if 10 < len(line) < 100 and "week of" in line.lower():
            return line

    return "Daily Mass"


def _infer_season(liturgical_day: str) -> str:
    day_lower = liturgical_day.lower()
    mapping = {
        "advent": "Advent",
        "christmas": "Christmas",
        "lent": "Lent",
        "easter": "Eastertide",
        "holy week": "Holy Week",
        "ordinary": "Ordinary Time",
    }
    for key, season in mapping.items():
        if key in day_lower:
            return season
    return "Ordinary Time"


def _debug_labels(soup: BeautifulSoup) -> list[str]:
    labels = []
    for table in soup.find_all("table", class_="each"):
        ths = table.find_all("th")
        if ths:
            labels.append(ths[0].get_text(strip=True))
    return labels


# --- Manual test entry point ---
if __name__ == "__main__":
    import json
    from src.utils import setup_logging
    setup_logging()
    readings = fetch_readings(datetime.date.today())
    # Print everything except the full reading text (too long)
    summary = {k: (v if not isinstance(v, dict) else {
        "reference": v.get("reference"),
        "title": v.get("title"),
        "text_preview": v.get("text", "")[:120] + "...",
    }) for k, v in readings.items()}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
