"""Generate AI summary, reflection questions, and prayer using Google Gemini."""
from __future__ import annotations

import logging
import time

import google.generativeai as genai

from src import config
from src.utils import retry

# Seconds to wait between Gemini calls — keeps us well under the free-tier RPM limit
_GEMINI_CALL_DELAY = 5

log = logging.getLogger(__name__)

# --- Fallback content used when Gemini is unavailable ---
_FALLBACK_SUMMARY = (
    "Today's Mass readings invite us to deepen our faith and love for one another. "
    "May these sacred words nourish your spirit as you go about your day. "
    "Blessed are those who hear the word of God and keep it."
)
_FALLBACK_REFLECTION = (
    "1. How is God speaking to you through today's readings?\n"
    "2. What concrete action can you take today to live out the Gospel?\n"
    "3. Who in your life can you share God's love with today?"
)
_FALLBACK_PRAYER = (
    "Lord Jesus, in today's readings you remind us of your great love. "
    "Help us to carry your word in our hearts throughout this day. "
    "May we be witnesses of your mercy to all we meet. Amen."
)


def generate_all_content(readings: dict) -> dict:
    """Return {summary, reflection, prayer} for the given readings."""
    if not config.GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set — using fallback content")
        return {
            "summary": _FALLBACK_SUMMARY,
            "reflection": _FALLBACK_REFLECTION,
            "prayer": _FALLBACK_PRAYER,
        }

    genai.configure(api_key=config.GEMINI_API_KEY)

    summary = _safe_call(_build_summary_prompt(readings), "summary", _FALLBACK_SUMMARY)
    time.sleep(_GEMINI_CALL_DELAY)
    reflection = _safe_call(_build_reflection_prompt(readings, summary), "reflection", _FALLBACK_REFLECTION)
    time.sleep(_GEMINI_CALL_DELAY)
    prayer = _safe_call(_build_prayer_prompt(readings), "prayer", _FALLBACK_PRAYER)

    return {"summary": summary, "reflection": reflection, "prayer": prayer}


def _safe_call(prompt: str, label: str, fallback: str) -> str:
    try:
        return _call_gemini(prompt)
    except Exception as exc:
        log.warning("Gemini call for '%s' failed (%s) — using fallback", label, exc)
        return fallback


@retry(max_attempts=3, delay=10, exceptions=(Exception,))
def _call_gemini(prompt: str) -> str:
    model = genai.GenerativeModel(config.GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text.strip()


def _build_summary_prompt(readings: dict) -> str:
    fr = readings.get("first_reading") or {}
    gospel = readings.get("gospel") or {}
    psalm = readings.get("psalm") or {}
    return (
        "You are writing a short summary of today's Catholic Mass readings for members of CFCA "
        "(Catholic Filipino Community of Australia). "
        "Write 3-4 clear, warm sentences that summarise the theme and key message of today's readings. "
        "Be welcoming and accessible, suitable for all ages. Do not use bullet points or headings. "
        "Write in plain paragraphs only.\n\n"
        f"First Reading ({fr.get('reference','')}):\n{fr.get('text','')[:800]}\n\n"
        f"Psalm ({psalm.get('reference','')}):\n{psalm.get('text','')[:400]}\n\n"
        f"Gospel ({gospel.get('reference','')}):\n{gospel.get('text','')[:800]}"
    )


def _build_reflection_prompt(readings: dict, summary: str) -> str:
    return (
        "Based on today's Catholic Mass readings for CFCA (Catholic Filipino Community of Australia), "
        "write exactly 3 reflection questions that invite personal and communal prayer. "
        "Number each question (1. 2. 3.) and put each on its own line. "
        "Keep each question under 25 words. "
        "Make them suitable for Filipino-Australian Catholic families of all ages. "
        "Do not add any introductory text — just the three numbered questions.\n\n"
        f"Theme summary: {summary}"
    )


def _build_prayer_prompt(readings: dict) -> str:
    gospel = readings.get("gospel") or {}
    return (
        "Write a short closing prayer (50–70 words) inspired by today's Catholic Gospel reading. "
        "Write in first-person plural ('Lord, help us...'). "
        "Make it warm, simple, and suitable for a Filipino-Australian Catholic community. "
        "Do not add a title or label — just the prayer text itself.\n\n"
        f"Gospel ({gospel.get('reference','')}):\n{gospel.get('text','')[:600]}"
    )


if __name__ == "__main__":
    import json, datetime
    from src.utils import setup_logging
    from src.fetch_readings import fetch_readings
    setup_logging()
    readings = fetch_readings(datetime.date.today())
    content = generate_all_content(readings)
    print(json.dumps(content, indent=2, ensure_ascii=False))
