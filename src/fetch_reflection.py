"""Fetch daily reflection from catholic-daily-reflections.com."""
from __future__ import annotations

import datetime
import logging
import re

import requests
from bs4 import BeautifulSoup

from src.utils import retry

log = logging.getLogger(__name__)

_API_URL = "https://catholic-daily-reflections.com/wp-json/wp/v2/posts"
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
    """Return the reflection text for the given date, or None if not found."""
    try:
        return _fetch(date)
    except Exception as exc:
        log.warning("Reflection fetch failed (%s) — will use AI fallback", exc)
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


if __name__ == "__main__":
    from src.utils import setup_logging
    setup_logging()
    text = fetch_reflection(datetime.date.today())
    if text:
        print(text)
    else:
        print("No reflection found for today.")
