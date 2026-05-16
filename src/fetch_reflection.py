"""Fetch daily reflection — primary: catholic-daily-reflections.com, fallback: archdiocesanministries.org.au"""
from __future__ import annotations

import datetime
import logging
import re

import requests
from bs4 import BeautifulSoup

from src.utils import retry

log = logging.getLogger(__name__)

_API_URL = "https://catholic-daily-reflections.com/wp-json/wp/v2/posts"
_ARCHDIOCESE_BASE = "https://archdiocesanministries.org.au"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; steady-hanrahan/1.0; "
        "+https://github.com/cfca/steady-hanrahan)"
    )
}

# Paragraph text that signals we've hit the page footer/navigation
_STOP_PHRASES = {
    "Easter Prayers", "More Gospel Reflections", "Divine Mercy",
    "Saints/Feasts", "Mass Reading Options", "Filed Under", "Tagged",
}


def fetch_reflection(date: datetime.date) -> str | None:
    """Return the reflection text for the given date, or None if not found.

    Tries catholic-daily-reflections.com first; falls back to
    archdiocesanministries.org.au if the primary returns nothing.
    """
    try:
        text = _fetch(date)
        if text:
            return text
    except Exception as exc:
        log.warning("Primary reflection fetch failed (%s) — trying fallback", exc)

    try:
        text = _fetch_archdiocese(date)
        if text:
            log.info("Used archdiocesanministries.org.au fallback reflection")
            return text
    except Exception as exc:
        log.warning("Fallback reflection fetch failed (%s) — will use AI", exc)

    return None


@retry(max_attempts=3, delay=5, exceptions=(requests.RequestException,))
def _fetch(date: datetime.date) -> str | None:
    # Fetch the 3 most recent posts — site publishes a day early so we check a few
    resp = requests.get(
        _API_URL,
        params={"per_page": 3, "orderby": "date", "order": "desc"},
        headers=_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    posts = resp.json()

    for post in posts:
        content_html = post.get("content", {}).get("rendered", "")
        post_date = _extract_content_date(content_html)
        if post_date == date:
            log.info(
                "Found reflection for %s: %s",
                date,
                post.get("link", ""),
            )
            return _extract_reflection_text(content_html)

    log.warning("No reflection found for %s on catholic-daily-reflections.com", date)
    return None


def _extract_content_date(html: str) -> datetime.date | None:
    """Parse the date mentioned in the first paragraph of the post content."""
    soup = BeautifulSoup(html, "html.parser")
    first_p = soup.find("p")
    if not first_p:
        return None
    text = first_p.get_text(" ", strip=True)
    # Format: "May 8, 2026 Friday of the Fifth Week of Easter..."
    m = re.search(r"([A-Z][a-z]+ \d{1,2},\s*\d{4})", text)
    if not m:
        return None
    try:
        return datetime.datetime.strptime(m.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def _extract_reflection_text(html: str) -> str:
    """Extract the reflection body paragraphs from the post HTML."""
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.find_all("p")

    reflection_parts: list[str] = []
    # Skip: P0 (date header), P1 (image caption), P2 ("Video")
    # Keep: P3 onwards until footer phrases
    for p in paragraphs[3:]:
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        if any(phrase in text for phrase in _STOP_PHRASES):
            break
        reflection_parts.append(text)

    return "\n\n".join(reflection_parts).strip()


@retry(max_attempts=3, delay=5, exceptions=(requests.RequestException,))
def _fetch_archdiocese(date: datetime.date) -> str | None:
    """Fetch reflection from archdiocesanministries.org.au for the given date."""
    day_name = date.strftime("%A").lower()        # "friday"
    month    = date.strftime("%B").lower()        # "may"
    slug     = f"{day_name}-{date.day}-{month}-{date.year}"
    url      = f"{_ARCHDIOCESE_BASE}/{slug}/"

    resp = requests.get(url, headers=_HEADERS, timeout=20)
    if resp.status_code == 404:
        log.warning("Archdiocese reflection not found for %s (%s)", date, url)
        return None
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the <h2>Reflection</h2> heading then collect all following <p> tags
    reflection_h2 = None
    for h2 in soup.find_all("h2"):
        if h2.get_text(strip=True).lower() == "reflection":
            reflection_h2 = h2
            break

    if not reflection_h2:
        log.warning("No 'Reflection' heading found on %s", url)
        return None

    _STOP_TEXT = {"Upcoming Events", "Reflection by", "Filed Under", "Tagged"}

    parts: list[str] = []
    for sibling in reflection_h2.find_all_next():
        if sibling.name in ("h2", "h3", "footer"):
            break
        if sibling.name == "p":
            text = sibling.get_text(" ", strip=True)
            if not text:
                continue
            if any(phrase in text for phrase in _STOP_TEXT):
                break
            parts.append(text)

    result = "\n\n".join(parts).strip()
    if result:
        log.info("Archdiocese reflection fetched: %s", url)
    return result or None


if __name__ == "__main__":
    from src.utils import setup_logging
    setup_logging()
    text = fetch_reflection(datetime.date.today())
    if text:
        print(text)
    else:
        print("No reflection found for today.")
