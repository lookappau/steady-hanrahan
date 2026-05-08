#!/usr/bin/env python3
"""steady-hanrahan — Daily Catholic Mass Readings Video Pipeline."""
import datetime
import logging
import sys
import zoneinfo

from src import config
from src.utils import setup_logging, ensure_dirs
from src.fetch_readings import fetch_readings
from src.generate_content import generate_all_content
from src.generate_audio import build_slide_scripts, generate_all_audio
from src.create_slides import create_all_slides
from src.assemble_video import assemble_video
from src.upload_youtube import upload_video


def main() -> None:
    setup_logging()
    log = logging.getLogger(__name__)
    ensure_dirs()

    today = datetime.datetime.now(zoneinfo.ZoneInfo("Australia/Adelaide")).date()
    log.info("=== steady-hanrahan starting for %s ===", today)

    try:
        log.info("[1/6] Fetching readings...")
        readings = fetch_readings(today)

        log.info("[2/6] Generating summary and reflection...")
        content = generate_all_content(readings, today)

        log.info("[3/6] Building slide scripts and generating audio...")
        slide_scripts = build_slide_scripts(readings, content)
        audio_paths = generate_all_audio(slide_scripts)

        log.info("[4/6] Creating slide images...")
        slide_paths = create_all_slides(slide_scripts)

        log.info("[5/6] Assembling video...")
        video_path = assemble_video(
            slide_paths,
            audio_paths,
            f"{config.OUTPUT_DIR}/mass_readings_{today.strftime('%Y%m%d')}.mp4",
        )

        log.info("[6/6] Uploading to YouTube...")
        url = upload_video(video_path, readings, content)
        log.info("=== SUCCESS: %s ===", url)

    except Exception:
        log.exception("Pipeline failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
