"""manim-clips — render Manim animations as per-slide GIFs.

Mark slide boundaries inside `construct()` with `self.next_slide(name)` (and
optionally `self.next_sub_slide(name)` for in-slide builds). Then call
`render_slides(YourScene)` to produce one GIF per slide.
"""

from manim_clips.scene import SlideMixin, SlideScene, ThreeDSlideScene
from manim_clips.render import render_slides

__all__ = [
    "SlideMixin",
    "SlideScene",
    "ThreeDSlideScene",
    "render_slides",
]

__version__ = "0.1.0"
