"""Generate AI summary, reflection, and prayer — tries Gemini then Groq."""
from __future__ import annotations

import datetime
import logging
import time

from src import config
from src.utils import retry

_CALL_DELAY = 5  # seconds between AI calls to avoid RPM limits
log = logging.getLogger(__name__)

# --- Fallback content when all AI providers fail ---
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


def generate_all_content(readings: dict, date: datetime.date | None = None) -> dict:
    """Return {summary, reflection, prayer}. Tries Gemini, then Groq, then fallback."""
    from src.fetch_reflection import fetch_reflection

    caller = _get_caller()
    if caller is None:
        log.warning("No AI API key configured — using fallback content")
        website_reflection = fetch_reflection(date) if date else None
        return {
            "summary": _FALLBACK_SUMMARY,
            "reflection": website_reflection or _FALLBACK_REFLECTION,
            "prayer": _FALLBACK_PRAYER,
        }

    summary = _safe_call(caller, _build_summary_prompt(readings), "summary", _FALLBACK_SUMMARY)
    time.sleep(_CALL_DELAY)

    website_reflection = fetch_reflection(date) if date else None
    if website_reflection:
        log.info("Summarising reflection from catholic-daily-reflections.com via AI")
        reflection = _safe_call(
            caller,
            _build_reflection_summarise_prompt(website_reflection),
            "reflection",
            website_reflection,
        )
        time.sleep(_CALL_DELAY)
    else:
        reflection = _safe_call(caller, _build_reflection_prompt(readings, summary), "reflection", _FALLBACK_REFLECTION)
        time.sleep(_CALL_DELAY)

    prayer = _safe_call(caller, _build_prayer_prompt(readings), "prayer", _FALLBACK_PRAYER)

    return {"summary": summary, "reflection": reflection, "prayer": prayer}


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def _get_caller():
    """Return a callable(prompt) -> str using whichever API key is available."""
    if config.GEMINI_API_KEY:
        log.info("Using Gemini (%s)", config.GEMINI_MODEL)
        return _make_gemini_caller()
    if config.GROQ_API_KEY:
        log.info("Using Groq (%s)", config.GROQ_MODEL)
        return _make_groq_caller()
    return None


def _make_gemini_caller():
    from google import genai as google_genai
    client = google_genai.Client(api_key=config.GEMINI_API_KEY)

    @retry(max_attempts=3, delay=10, exceptions=(Exception,))
    def call(prompt: str) -> str:
        response = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
        )
        return response.text.strip()

    return call


def _make_groq_caller():
    from groq import Groq
    client = Groq(api_key=config.GROQ_API_KEY)

    @retry(max_attempts=3, delay=10, exceptions=(Exception,))
    def call(prompt: str) -> str:
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    return call


def _safe_call(caller, prompt: str, label: str, fallback: str) -> str:
    try:
        return caller(prompt)
    except Exception as exc:
        log.warning("AI call for '%s' failed (%s) — using fallback", label, exc)
        return fallback


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _build_summary_prompt(readings: dict) -> str:
    fr = readings.get("first_reading") or {}
    gospel = readings.get("gospel") or {}
    psalm = readings.get("psalm") or {}
    return (
        "You are writing a short summary of today's Catholic Mass readings. "
        "Write 3-4 clear, warm sentences that summarise the theme and key message of today's readings. "
        "Be welcoming and accessible, suitable for all ages. Do not use bullet points or headings. "
        "Write in plain paragraphs only.\n\n"
        f"First Reading ({fr.get('reference','')}):\n{fr.get('text','')[:800]}\n\n"
        f"Psalm ({psalm.get('reference','')}):\n{psalm.get('text','')[:400]}\n\n"
        f"Gospel ({gospel.get('reference','')}):\n{gospel.get('text','')[:800]}"
    )


def _build_reflection_summarise_prompt(website_text: str) -> str:
    return (
        "You are writing a short, inspiring reflection for Catholics based on today's Mass Gospel. "
        "Summarise the following reflection in 3-5 sentences. "
        "Use a warm, encouraging, and spiritually uplifting tone. "
        "Write in plain prose — no bullet points, no headings, no numbered lists. "
        "Do not add a title or any introductory phrase — just the reflection text.\n\n"
        f"Source reflection:\n{website_text[:2000]}"
    )


def _build_reflection_prompt(readings: dict, summary: str) -> str:
    return (
        "Based on today's Catholic Mass readings, "
        "write exactly 3 reflection questions that invite personal and communal prayer. "
        "Number each question (1. 2. 3.) and put each on its own line. "
        "Keep each question under 25 words. "
        "Make them suitable for Catholics of all ages and backgrounds. "
        "Do not add any introductory text — just the three numbered questions.\n\n"
        f"Theme summary: {summary}"
    )


def _build_prayer_prompt(readings: dict) -> str:
    gospel = readings.get("gospel") or {}
    return (
        "Write a short closing prayer (50-70 words) inspired by today's Catholic Gospel reading. "
        "Write in first-person plural ('Lord, help us...'). "
        "Make it warm, simple, and suitable for Catholics of all backgrounds. "
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
