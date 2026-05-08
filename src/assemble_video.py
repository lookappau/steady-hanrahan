"""Assemble slide PNGs + MP3s into a single MP4 using MoviePy."""
from __future__ import annotations

import logging
import os

from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

from src import config

log = logging.getLogger(__name__)


def assemble_video(slide_paths: list[str], audio_paths: list[str],
                   output_path: str) -> str:
    """Combine slides and audio into a single MP4. Returns output_path."""
    if len(slide_paths) != len(audio_paths):
        raise ValueError(
            f"Slide/audio count mismatch: {len(slide_paths)} slides, {len(audio_paths)} audio"
        )

    clips = []
    total_duration = 0.0

    for i, (slide_path, audio_path) in enumerate(zip(slide_paths, audio_paths)):
        audio = AudioFileClip(audio_path)
        duration = audio.duration
        total_duration += duration

        img = ImageClip(slide_path).with_duration(duration).with_audio(audio)
        clips.append(img)
        log.debug("Clip %02d: %.1fs", i, duration)

    log.info("Total video duration: %.0f seconds (%.1f minutes)", total_duration, total_duration / 60)

    final = concatenate_videoclips(clips, method="compose")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    log.info("Encoding video → %s", output_path)
    final.write_videofile(
        output_path,
        fps=config.FPS,
        codec=config.VIDEO_CODEC,
        audio_codec=config.AUDIO_CODEC,
        preset=config.ENCODE_PRESET,
        threads=config.ENCODE_THREADS,
        logger=None,  # suppress moviepy progress bar (GitHub Actions log is noisy)
    )

    for clip in clips:
        clip.close()
    final.close()

    log.info("Video written: %s (%.1f MB)", output_path,
             os.path.getsize(output_path) / 1_048_576)
    return output_path


if __name__ == "__main__":
    import glob
    from src.utils import setup_logging
    setup_logging()
    slides = sorted(glob.glob("tmp/slides/slide_*.png"))
    audios = sorted(glob.glob("tmp/audio/audio_*.mp3"))
    out = assemble_video(slides, audios, "tmp/output/test_video.mp4")
    print("Output:", out)
