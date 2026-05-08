"""Upload the finished MP4 to YouTube using the YouTube Data API v3."""
from __future__ import annotations

import logging
import os

import google.oauth2.credentials
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http

from src import config
from src.utils import retry

log = logging.getLogger(__name__)

YOUTUBE_API_SERVICE = "youtube"
YOUTUBE_API_VERSION = "v3"

# YouTube resumable upload retries only on transient server errors
_RETRYABLE_STATUS = {500, 502, 503, 504}


def upload_video(video_path: str, readings: dict, content: dict) -> str:
    """Upload video_path to YouTube. Returns the video URL."""
    if not all([config.YOUTUBE_CLIENT_ID,
                config.YOUTUBE_CLIENT_SECRET,
                config.YOUTUBE_REFRESH_TOKEN]):
        raise EnvironmentError(
            "YouTube credentials not set. "
            "Run scripts/youtube_auth_setup.py to generate them."
        )

    youtube = _get_authenticated_service()
    metadata = _build_metadata(readings, content)
    video_id = _resumable_upload(youtube, video_path, metadata)
    url = f"https://www.youtube.com/watch?v={video_id}"
    log.info("Uploaded: %s", url)
    return url


def _get_authenticated_service():
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=config.YOUTUBE_REFRESH_TOKEN,
        client_id=config.YOUTUBE_CLIENT_ID,
        client_secret=config.YOUTUBE_CLIENT_SECRET,
        token_uri=config.YOUTUBE_TOKEN_URI,
    )
    return googleapiclient.discovery.build(
        YOUTUBE_API_SERVICE, YOUTUBE_API_VERSION,
        credentials=creds,
        cache_discovery=False,
    )


def _build_metadata(readings: dict, content: dict) -> dict:
    date_str = readings.get("date", "")
    liturgical_day = readings.get("liturgical_day", "Daily Mass")

    # Human-readable date for title
    display_date = _format_date_title(date_str)
    title = f"Catholic Daily Mass Readings — {display_date}"

    fr = readings.get("first_reading") or {}
    gospel = readings.get("gospel") or {}

    description_lines = [
        f"📖 {liturgical_day}",
        "",
        "Today's Readings:",
    ]
    if fr.get("reference"):
        description_lines.append(f"• First Reading: {fr['reference']}")
    psalm = readings.get("psalm") or {}
    if psalm.get("reference"):
        description_lines.append(f"• Psalm: {psalm['reference']}")
    sr = readings.get("second_reading") or {}
    if sr.get("reference"):
        description_lines.append(f"• Second Reading: {sr['reference']}")
    if gospel.get("reference"):
        description_lines.append(f"• Gospel: {gospel['reference']}")
    description_lines += [
        "",
        "Summary:",
        content.get("summary", ""),
        "",
        "Reflection:",
        content.get("reflection", ""),
        "",
        "─" * 40,
        "🙏 Subscribe for daily Mass readings.",
    ]

    tags = list(config.YOUTUBE_TAGS)
    for book_field in ("first_reading", "gospel", "second_reading"):
        ref = (readings.get(book_field) or {}).get("reference", "")
        if ref:
            book = ref.split()[0]
            if book and book not in tags:
                tags.append(book)

    return {
        "snippet": {
            "title": title[:100],
            "description": "\n".join(description_lines)[:5000],
            "tags": tags[:30],
            "categoryId": config.YOUTUBE_CATEGORY_ID,
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": config.YOUTUBE_PRIVACY,
            "selfDeclaredMadeForKids": False,
        },
    }


def _resumable_upload(youtube, video_path: str, metadata: dict) -> str:
    """Execute the upload with exponential-backoff retry on 5xx errors."""
    body = {
        "snippet": metadata["snippet"],
        "status": metadata["status"],
    }
    media = googleapiclient.http.MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10 MB chunks
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    attempt = 0
    max_attempts = 10

    while response is None:
        attempt += 1
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                log.info("Upload progress: %d%%", pct)
        except googleapiclient.errors.HttpError as exc:
            if attempt >= max_attempts:
                raise
            if exc.resp.status in _RETRYABLE_STATUS:
                wait = min(2 ** attempt, 64)
                log.warning("Upload error %s — retry %d/%d in %ds",
                            exc.resp.status, attempt, max_attempts, wait)
                import time
                time.sleep(wait)
            else:
                raise

    return response["id"]


def _format_date_title(date_str: str) -> str:
    try:
        import datetime
        d = datetime.date.fromisoformat(date_str)
        return d.strftime("%A, %-d %B %Y") if os.name != "nt" else d.strftime("%A, %d %B %Y")
    except Exception:
        return date_str
