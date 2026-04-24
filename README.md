# manim-slides

Render [Manim](https://www.manim.community) animations as **one GIF per slide**, so you can drop them into Keynote, PowerPoint, or any HTML deck and click through at your own pace.

Unlike a single long video, each slide is its own file that plays once and lands on its final frame — exactly the behavior a presentation tool expects.

## Install

```bash
pip install manim-slides
```

Requires `ffmpeg` on your `PATH` (Manim needs it too).

## Quick start

```python
from manim import *
from manim_slides import SlideScene, render_slides


class Demo(SlideScene):
    def construct(self):
        self.camera.background_color = "#0E0E10"

        self.next_slide("title")
        title = Text("Hello, slides")
        self.play(Write(title))
        self.wait(1)

        self.next_slide("fade")
        self.play(FadeOut(title))
        self.wait(1)


if __name__ == "__main__":
    render_slides(Demo)
```

Run it:

```bash
python demo.py
```

You'll get `slides_output/demo_01_title.gif` and `slides_output/demo_02_fade.gif`.

## Slide builds (sub-slides)

A logical slide that reveals content in phases — a bullet list, a diagram growing one arrow at a time — usually wants to be *several* GIFs you click through.

```python
self.next_slide("codons")
self.play(Write(dna))

self.next_sub_slide("highlight_start")
self.play(Create(start_box))

self.next_sub_slide("highlight_stop")
self.play(Create(stop_box))
```

Produces `01_codons.gif`, `01a_codons_highlight_start.gif`, `01b_codons_highlight_stop.gif`.
Empty segments (if `next_slide` is followed immediately by `next_sub_slide`) are skipped, so you don't get a stray parent GIF.

## Using with existing Manim scenes

`SlideMixin` is the actual machinery — mix it into any Scene subclass:

```python
from manim import MovingCameraScene
from manim_slides import SlideMixin, render_slides

class MyScene(SlideMixin, MovingCameraScene):
    def construct(self):
        self.next_slide("zoomed")
        ...

render_slides(MyScene)
```

`SlideScene` and `ThreeDSlideScene` are provided for the common cases.

## Incremental rendering

`render_slides` writes a `.manifest_<script>.json` next to the output GIFs. On the next run it hashes each slide's raw pixel bytes and only re-encodes GIFs whose contents changed. Edit one slide, only that GIF regenerates.

Force a full rebuild with `force=True`.

## API

```python
render_slides(
    scene_class,
    output_dir="slides_output",
    quality="high",       # "low" | "medium" | "high" | "fourk"
    fps=30,
    bg_color=None,        # e.g. "#0E0E10"
    force=False,
    prefix=None,          # defaults to the invoking script's stem
    loop=False,           # True = GIFs loop forever
)
```

## Examples

See [`examples/frameshift/frameshift.py`](examples/frameshift/frameshift.py) for a real, multi-part presentation.

## License

MIT
