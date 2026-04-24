"""Slide-aware Scene subclasses.

`SlideMixin` is the core — it adds `next_slide()` / `next_sub_slide()` markers
to any `manim.Scene` subclass and tracks the time at which each boundary was
crossed. `SlideScene` and `ThreeDSlideScene` are ready-to-use convenience
classes; for anything more exotic (e.g. `MovingCameraScene`) just mix
`SlideMixin` into your own base:

    class MyScene(SlideMixin, MovingCameraScene):
        ...
"""

from __future__ import annotations

from manim import Scene, ThreeDScene


class SlideMixin:
    """Adds slide-marker support to any Scene subclass.

    Two marker kinds:
        self.next_slide("name")          -> top-level slide, emits 01_name.gif
        self.next_sub_slide("part")      -> sub-slide of the current top-level,
                                            shares the top-level number and
                                            gets a letter suffix:
                                            01a_name_part.gif, etc.

    Sub-slides each produce their own GIF so you can click through builds at
    your own pace — useful when a logical slide reveals content in phases.
    """

    def setup(self):
        super().setup()
        self._slide_markers: list[dict] = []
        self._slide_num: int = 0
        self._sub_num: int = 0
        self._current_slide_name: str | None = None

    def next_slide(self, name: str) -> None:
        self._slide_num += 1
        self._sub_num = 0
        self._current_slide_name = name
        self._slide_markers.append({
            "slide_num": self._slide_num,
            "sub_num": 0,
            "parent": name,
            "sub_name": None,
            "t": self.renderer.time,
        })

    def next_sub_slide(self, sub_name: str) -> None:
        if self._current_slide_name is None:
            raise RuntimeError("Call next_slide() before next_sub_slide().")
        self._sub_num += 1
        self._slide_markers.append({
            "slide_num": self._slide_num,
            "sub_num": self._sub_num,
            "parent": self._current_slide_name,
            "sub_name": sub_name,
            "t": self.renderer.time,
        })

    def get_slide_segments(self) -> list[tuple[str, float, float]]:
        """Return (slug, start_time, end_time) for each non-empty segment.

        Slugs are pre-formatted filenames (without extension):
            01_title                for plain slides
            02a_intro_fade_in       for sub-slides
        Empty segments (zero duration) are filtered, so you can call
        next_slide() and next_sub_slide() back-to-back without producing a
        stray GIF for the parent slide.
        """
        segments = []
        for i, m in enumerate(self._slide_markers):
            start = m["t"]
            end = (
                self._slide_markers[i + 1]["t"]
                if i + 1 < len(self._slide_markers)
                else self.renderer.time
            )
            if end <= start:
                continue
            if m["sub_num"] == 0:
                slug = f"{m['slide_num']:02d}_{m['parent']}"
            else:
                sub_letter = chr(ord("a") + m["sub_num"] - 1)
                slug = (
                    f"{m['slide_num']:02d}{sub_letter}_"
                    f"{m['parent']}_{m['sub_name']}"
                )
            segments.append((slug, start, end))
        return segments


class SlideScene(SlideMixin, Scene):
    """2D slide scene."""


class ThreeDSlideScene(SlideMixin, ThreeDScene):
    """3D slide scene."""
