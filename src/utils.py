"""Shared utilities: logging, retry, text helpers, directory setup."""
import functools
import logging
import os
import time
from src import config


def setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def ensure_dirs() -> None:
    for d in (config.SLIDES_DIR, config.AUDIO_DIR, config.OUTPUT_DIR):
        os.makedirs(d, exist_ok=True)


def retry(max_attempts: int = 3, delay: float = 5.0, backoff: float = 2.0,
          exceptions: tuple = (Exception,)):
    """Decorator: exponential-backoff retry."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            log = logging.getLogger(fn.__module__)
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    log.warning(
                        "Attempt %d/%d failed (%s). Retrying in %.0fs...",
                        attempt, max_attempts, exc, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def wrap_text(text: str, max_chars: int = config.MAX_CHARS_PER_LINE) -> list[str]:
    """Word-wrap text to a list of lines, each ≤ max_chars."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


def split_into_chunks(text: str, max_words: int = config.MAX_WORDS_PER_SLIDE) -> list[str]:
    """Split text into chunks of ≤ max_words, breaking at sentence boundaries."""
    sentences: list[str] = []
    for raw in text.replace("\n", " ").split("."):
        s = raw.strip()
        if s:
            sentences.append(s + ".")

    chunks: list[str] = []
    current_words: list[str] = []
    for sentence in sentences:
        s_words = sentence.split()
        if current_words and len(current_words) + len(s_words) > max_words:
            chunks.append(" ".join(current_words))
            current_words = s_words
        else:
            current_words.extend(s_words)
    if current_words:
        chunks.append(" ".join(current_words))
    return chunks if chunks else [text]
