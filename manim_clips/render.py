"""Render a SlideScene to individual per-slide GIFs.

Pipeline:
    1. Render the scene once as a single video. Manim's partial-movie-file
       cache handles unchanged animations between runs.
    2. For each slide segment, hash the raw decoded pixels of that time
       range and compare against a manifest from the previous run.
    3. Re-encode GIFs only for segments whose hash changed (or whose GIF
       is missing). Everything else is reused.

This makes iteration cheap: tweak one slide, only that GIF regenerates.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Type

from manim import config

from manim_clips.scene import SlideMixin


QUALITY_PRESETS: dict[str, dict[str, int]] = {
    "low":    {"pixel_width":  854, "pixel_height":  480},
    "medium": {"pixel_width": 1280, "pixel_height":  720},
    "high":   {"pixel_width": 1920, "pixel_height": 1080},
    "fourk":  {"pixel_width": 3840, "pixel_height": 2160},
}


def render_slides(
    scene_class: Type[SlideMixin],
    output_dir: str | Path = "slides_output",
    quality: str = "high",
    fps: int = 30,
    bg_color: str | None = None,
    force: bool = False,
    prefix: str | None = None,
    loop: bool = False,
) -> list[Path]:
    """Render `scene_class` to individual slide GIFs.

    Args:
        scene_class: A Scene class mixing in `SlideMixin` (e.g. `SlideScene`).
        output_dir: Directory for output GIFs (created if missing).
        quality: One of "low", "medium", "high", "fourk".
        fps: GIF frame rate.
        bg_color: Optional scene background color (e.g. "#0E0E10").
        force: Regenerate every GIF even if its hash matches the manifest.
        prefix: Filename prefix for every GIF. Defaults to the invoking
            script's stem so multiple scripts can share one output_dir
            without colliding. Pass "" to disable.
        loop: If True, GIFs loop forever. Default False (play once, stop) —
            better for presentations where you want to land on the final
            frame.

    Returns:
        List of paths to the generated (or cached) GIFs, in slide order.
    """
    if quality not in QUALITY_PRESETS:
        raise ValueError(
            f"Unknown quality {quality!r}. "
            f"Pick one of {sorted(QUALITY_PRESETS)}."
        )
    q = QUALITY_PRESETS[quality]

    config.pixel_width = q["pixel_width"]
    config.pixel_height = q["pixel_height"]
    config.frame_rate = fps
    config.frame_width = 16
    config.frame_height = 9
    # Bigger partial-movie-file cache than manim's default (100). Unchanged
    # animations hash-match across runs and get reused instead of re-rendered.
    config.max_files_cached = 1000
    if bg_color:
        config.background_color = bg_color

    scene = scene_class()
    scene.render()

    video_path = Path(scene.renderer.file_writer.movie_file_path)
    segments = scene.get_slide_segments()

    if not segments:
        print("No slides found — did you call self.next_slide() in construct()?")
        return []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if prefix is None:
        prefix = Path(sys.argv[0]).stem if sys.argv and sys.argv[0] else ""

    def gif_name(slug: str) -> str:
        return f"{prefix}_{slug}.gif" if prefix else f"{slug}.gif"

    manifest_path = out / (
        f".manifest_{prefix}.json" if prefix else ".manifest.json"
    )
    manifest: dict[str, str] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            manifest = {}

    tmp_dir = Path(tempfile.mkdtemp(prefix="manim_clips_"))

    print(f"\nFound {len(segments)} slides. Splitting into GIFs...\n")

    def segment_hash(start: float, duration: float) -> str:
        result = subprocess.run(
            [
                "ffmpeg", "-v", "error",
                "-ss", f"{start:.4f}",
                "-t", f"{duration:.4f}",
                "-i", str(video_path),
                "-an",
                "-c:v", "rawvideo",
                "-pix_fmt", "rgb24",
                "-f", "md5", "-",
            ],
            capture_output=True, text=True, check=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("MD5="):
                return line[4:].strip()
        return ""

    gif_paths: list[Path] = []
    regenerated = 0
    loop_flag = "0" if loop else "-1"
    try:
        for i, (slug, start, end) in enumerate(segments):
            duration = end - start
            name = gif_name(slug)
            gif_path = out / name

            seg_hash = segment_hash(start, duration)

            if (
                not force
                and manifest.get(slug) == seg_hash
                and gif_path.exists()
            ):
                print(
                    f"  [{i+1}/{len(segments)}] {name}  "
                    f"({duration:.1f}s, cached)"
                )
                gif_paths.append(gif_path)
                continue

            palette_path = tmp_dir / f"{slug}_palette.png"
            vf = (
                f"fps={fps},"
                f"scale={q['pixel_width']}:{q['pixel_height']}:flags=lanczos"
            )
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-ss", f"{start:.4f}",
                    "-t", f"{duration:.4f}",
                    "-i", str(video_path),
                    "-vf", f"{vf},palettegen",
                    "-t", f"{duration:.4f}",
                    str(palette_path),
                ],
                capture_output=True, check=True,
            )
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-ss", f"{start:.4f}",
                    "-t", f"{duration:.4f}",
                    "-i", str(video_path),
                    "-i", str(palette_path),
                    "-lavfi", f"{vf} [x]; [x][1:v] paletteuse",
                    "-loop", loop_flag,
                    str(gif_path),
                ],
                capture_output=True, check=True,
            )

            manifest[slug] = seg_hash
            regenerated += 1
            print(f"  [{i+1}/{len(segments)}] {name}  ({duration:.1f}s)")
            gif_paths.append(gif_path)

        live_slugs = {slug for slug, _, _ in segments}
        manifest = {k: v for k, v in manifest.items() if k in live_slugs}
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print(
        f"\nDone! {len(gif_paths)} GIFs at {out.resolve()}/ — "
        f"regenerated {regenerated}, reused {len(gif_paths) - regenerated}."
    )
    return gif_paths
