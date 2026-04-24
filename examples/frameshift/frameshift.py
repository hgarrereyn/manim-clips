"""FrameShift — a full Manim presentation built with manim-clips.

Combines two decks into one continuously-numbered presentation:
    Part 1 (FrameShiftSlides):   microbiology intro, PNG mutation walkthrough,
                                 TPM packet, fuzzer comparison table.
    Part 2 (OurApproachSlides):  our approach bullets, Crick & Brenner,
                                 recovering structure in PNG, algorithm,
                                 highlights.

Run from the repo root:

    cd examples/frameshift
    python frameshift.py            # render all slides (cached)
    python frameshift.py --force    # regenerate every GIF

Produces one GIF per slide under ./slides_output/ — drop them into Keynote.
Requires aflpp.png to be in the working directory (included alongside this
file).
"""

import argparse
import random

from manim import *
from manim_clips import SlideScene, render_slides


# ──────────────────────────────────────────────────────────────────────────
# Shared style + layout constants
# ──────────────────────────────────────────────────────────────────────────

BG_COLOR = "#0E0E10"
TEXT_COLOR = "#F5F5F5"
AUTHOR_COLOR = "#9A9A9A"
HIGHLIGHT = "#EF4444"
BOX_COLOR = "#60A5FA"
ARROW_COLOR = "#B0B0B0"
BULLET_COLOR = "#60A5FA"
GREY_COLOR = "#6B7280"
CHECK_COLOR = "#22C55E"

DNA_FONT = 40
DNA_FONT_NAME = "Menlo"
AA_FONT = 40
LETTER_BUFF = 0.16
BOX_BUFF = 0.06
BOX_FILL_OPACITY = 0.12
BOX_CORNER_RADIUS = 0.12
BOX_STROKE = 2.5
ROW_VERT = 1.2

TOP_DNA_Y = 2.2
EX2_DNA_Y = 0.2
EX3_DNA_Y = -1.8
DNA_X_SHIFT = 0.55

MARKER_DX = -1.0
LABEL_DX = -1.8


# ── Fixed monospace grid (Part 2) ──
# Every DNA letter lives at x = base_x + slot_idx * CELL_W. Every reading-frame
# box has width 3 * CELL_W - BOX_GAP and is centered on the middle cell — boxes
# are all identical, tile perfectly, and re-align exactly under integer slot
# shifts.
_REF_GLYPH = Text("A", font=DNA_FONT_NAME, font_size=DNA_FONT)
CELL_W = _REF_GLYPH.width + LETTER_BUFF
GLYPH_H = _REF_GLYPH.height
BOX_GAP = 0.08
BOX_W = 3 * CELL_W - BOX_GAP
BOX_H = GLYPH_H + 2 * BOX_BUFF


# ──────────────────────────────────────────────────────────────────────────
# PNG parse data — shared by Part 1's "png_mutations" slide and Part 2's
# "recovering_structure" slide.
# ──────────────────────────────────────────────────────────────────────────

# Byte-role palette. Bytes get colored by the role they play in the PNG spec.
SIG_COLOR = "#FCD34D"   # signature — gold
SIZE_COLOR = "#F97316"  # chunk size fields — orange
TYPE_COLOR = "#22D3EE"  # chunk type fields — cyan
DATA_COLOR = "#94A3B8"  # chunk data — slate
CRC_COLOR = "#475569"   # CRC — dim (usually disabled for fuzzing)
HL_COLOR = "#FDE047"    # parser cursor — bright yellow (Part 1 only)

HEX_FONT = 22
HEX_BUFF = 0.06

# Full chunk list of example.png — drives per-offset coloring.
chunks_list = [
    ("IHDR", 13), ("gAMA", 4), ("sRGB", 1), ("cHRM", 32),
    ("bKGD", 2), ("pHYs", 9), ("IDAT", 947),
    ("tEXt", 37), ("tEXt", 37), ("tEXt", 7), ("tEXt", 19),
    ("IEND", 0),
]

# Real first 170 bytes of example.png — covers the signature + IHDR, gAMA,
# sRGB, cHRM, bKGD, pHYs, and the start of IDAT. Enough for the parser walk;
# the row scrolls left as each chunk is consumed.
hex_bytes_list = [
    "89", "50", "4e", "47", "0d", "0a", "1a", "0a", "00", "00", "00", "0d", "49", "48", "44", "52",
    "00", "00", "00", "4e", "00", "00", "00", "54", "08", "00", "00", "00", "00", "09", "8c", "5e",
    "3c", "00", "00", "00", "04", "67", "41", "4d", "41", "00", "00", "b1", "8f", "0b", "fc", "61",
    "05", "00", "00", "00", "01", "73", "52", "47", "42", "00", "ae", "ce", "1c", "e9", "00", "00",
    "00", "20", "63", "48", "52", "4d", "00", "00", "7a", "26", "00", "00", "80", "84", "00", "00",
    "fa", "00", "00", "00", "80", "e8", "00", "00", "75", "30", "00", "00", "ea", "60", "00", "00",
    "3a", "98", "00", "00", "17", "70", "9c", "ba", "51", "3c", "00", "00", "00", "02", "62", "4b",
    "47", "44", "00", "ff", "87", "8f", "cc", "bf", "00", "00", "00", "09", "70", "48", "59", "73",
    "00", "00", "00", "48", "00", "00", "00", "48", "00", "46", "c9", "6b", "3e", "00", "00", "03",
    "b3", "49", "44", "41", "54", "58", "c3", "9d", "d8", "4b", "48", "54", "61", "14", "07", "f0",
]

# (start, end_inclusive, label_text, color) for each field drawn above the
# hex row. sRGB's 1-byte data is skipped — "data" text would overflow badly.
field_labels_defs = [
    (0, 7, "signature", SIG_COLOR),
    (8, 11, "size=13", SIZE_COLOR),
    (12, 15, "IHDR", TYPE_COLOR),
    (16, 28, "data", DATA_COLOR),
    (29, 32, "crc", CRC_COLOR),
    (33, 36, "size=4", SIZE_COLOR),
    (37, 40, "gAMA", TYPE_COLOR),
    (41, 44, "data", DATA_COLOR),
    (45, 48, "crc", CRC_COLOR),
    (49, 52, "size=1", SIZE_COLOR),
    (53, 56, "sRGB", TYPE_COLOR),
    (58, 61, "crc", CRC_COLOR),
    (62, 65, "size=32", SIZE_COLOR),
    (66, 69, "cHRM", TYPE_COLOR),
    (70, 101, "data", DATA_COLOR),
    (102, 105, "crc", CRC_COLOR),
    (106, 109, "size=2", SIZE_COLOR),
    (110, 113, "bKGD", TYPE_COLOR),
    (114, 115, "data", DATA_COLOR),
    (116, 119, "crc", CRC_COLOR),
    (120, 123, "size=9", SIZE_COLOR),
    (124, 127, "pHYs", TYPE_COLOR),
    (128, 136, "data", DATA_COLOR),
    (137, 140, "crc", CRC_COLOR),
    (141, 144, "size=947", SIZE_COLOR),
    (145, 148, "IDAT", TYPE_COLOR),
    (149, 159, "data", DATA_COLOR),
]

# (chunk_name, start_byte, end_byte_inclusive) for the blue "reading frame"
# boxes. Used by Part 2's recovering_structure slide.
chunk_boxes_defs = [
    ("IHDR", 8, 32),
    ("gAMA", 33, 48),
    ("sRGB", 49, 61),
    ("cHRM", 62, 105),
    ("bKGD", 106, 119),
    ("pHYs", 120, 140),
    ("IDAT", 141, 159),  # truncated
]

# Chunk names drawn along the chunk-list row — includes chunks past the end
# of the visible hex dump (tEXt ×4, IEND).
png_chunk_names = [
    "IHDR", "gAMA", "sRGB", "cHRM", "bKGD", "pHYs",
    "IDAT", "tEXt", "tEXt", "tEXt", "tEXt", "IEND",
]

# Byte index at which both decks insert a single red byte to demonstrate a
# frameshift. Falls inside gAMA's data region.
INSERT_IDX = 43


def byte_color_for_offset(offset):
    """Color a PNG byte by its role (signature / size / type / data / crc)."""
    if offset < 8:
        return SIG_COLOR
    cur = 8
    for _name, size in chunks_list:
        if cur <= offset < cur + 4:
            return SIZE_COLOR
        if cur + 4 <= offset < cur + 8:
            return TYPE_COLOR
        if cur + 8 <= offset < cur + 8 + size:
            return DATA_COLOR
        if cur + 8 + size <= offset < cur + 12 + size:
            return CRC_COLOR
        cur += 12 + size
    return DATA_COLOR


# ──────────────────────────────────────────────────────────────────────────
# Part 1 helpers (original FrameShift deck)
# ──────────────────────────────────────────────────────────────────────────

def make_dna_row(dna_str, color=TEXT_COLOR, font_size=DNA_FONT):
    letters = [
        Text(c, font=DNA_FONT_NAME, font_size=font_size, color=color)
        for c in dna_str
    ]
    row = VGroup(*letters).arrange(RIGHT, buff=LETTER_BUFF)
    triplets = [
        VGroup(*letters[i:i + 3])
        for i in range(0, len(letters), 3)
    ]
    return row, triplets


def make_aa_row(aa_str, triplets, y_offset=ROW_VERT, color=TEXT_COLOR, font_size=AA_FONT):
    aas = []
    for aa_char, triplet in zip(aa_str, triplets):
        aa = Text(aa_char, font=DNA_FONT_NAME, font_size=font_size, color=color)
        aa.move_to(triplet.get_center() + DOWN * y_offset)
        aas.append(aa)
    return VGroup(*aas), aas


def make_boxes(triplets, color=BOX_COLOR, stroke_width=2.5, buff=BOX_BUFF,
               fill_opacity=BOX_FILL_OPACITY):
    return [
        SurroundingRectangle(
            t, buff=buff, color=color, stroke_width=stroke_width,
            fill_color=color, fill_opacity=fill_opacity,
            corner_radius=BOX_CORNER_RADIUS,
        )
        for t in triplets
    ]


def make_arrows(triplets, aas, color=ARROW_COLOR, stroke_width=10):
    return [
        Arrow(
            t.get_bottom(),
            a.get_top(),
            buff=0.12,
            color=color,
            stroke_width=stroke_width,
            tip_length=0.35,
            max_tip_length_to_length_ratio=0.35,
            max_stroke_width_to_length_ratio=20,
        )
        for t, a in zip(triplets, aas)
    ]


class FrameShiftSlides(SlideScene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # === Slide 1: Title ===
        self.next_slide("title")

        title_main = Text(
            "FrameShift",
            font_size=96,
            weight=BOLD,
            color=TEXT_COLOR,
        )
        title_sub = Text(
            "Resizing Fuzzer Inputs Without Breaking Them",
            font_size=40,
            color=TEXT_COLOR,
        )
        title = VGroup(title_main, title_sub).arrange(DOWN, buff=0.4).move_to(UP * 0.8)

        max_width = config.frame_width - 1.5
        if title_sub.width > max_width:
            title_sub.scale(max_width / title_sub.width)
            title = VGroup(title_main, title_sub).arrange(DOWN, buff=0.4).move_to(UP * 0.8)

        authors = Text(
            "Harrison Green   ·   Claire Le Goues   ·   Fraser Brown",
            font_size=28,
            color=AUTHOR_COLOR,
        ).next_to(title, DOWN, buff=1.0)

        self.play(Write(title_main), Write(title_sub), run_time=1.5)
        self.play(Write(authors), run_time=1.0)
        self.wait(1.5)

        # === Slide 2: Microbiology (4 sub-slides) ===
        self.next_slide("microbiology")

        # ── 2a: title ──
        self.next_sub_slide("title")
        self.play(FadeOut(title), FadeOut(authors), run_time=0.6)

        micro_title = Text(
            "Microbiology",
            font_size=60,
            weight=BOLD,
            color=TEXT_COLOR,
        )
        self.play(Write(micro_title), run_time=1.2)
        self.wait(0.4)

        # ── 2b: DNA + AA sequence (top half) ──
        self.next_sub_slide("dna")

        # Slide the centered title up to become the slide header.
        self.play(
            micro_title.animate.to_edge(UP, buff=0.5),
            run_time=0.8,
        )

        dna_str = "ATGCATTGCAAGCTAGATGCTTAC"
        aa_str = "MHCKLDAY"

        top_dna_row, top_triplets = make_dna_row(dna_str)
        top_dna_row.move_to(UP * 1.3)

        top_aa_group, top_aas = make_aa_row(aa_str, top_triplets, y_offset=ROW_VERT)
        top_boxes = make_boxes(top_triplets)
        top_arrows = make_arrows(top_triplets, top_aas)

        self.play(Write(top_dna_row), run_time=1.5)
        # Staggered cascade: each triplet draws its box, then quickly its
        # arrow, then its AA — with each triplet offset from the last.
        top_triplet_seqs = [
            Succession(
                Create(top_boxes[i], run_time=0.4),
                GrowArrow(top_arrows[i], run_time=0.15),
                Write(top_aas[i], run_time=0.15),
            )
            for i in range(len(top_boxes))
        ]
        self.play(LaggedStart(*top_triplet_seqs, lag_ratio=0.35))
        self.wait(0.4)

        # ── 2c: missense mutation ──
        self.next_sub_slide("missense")

        # TGC (triplet 2) → TGG: last base C → G; AA C → W.
        old_base = top_triplets[2][2]
        new_base = Text(
            "G", font=DNA_FONT_NAME, font_size=DNA_FONT, color=HIGHLIGHT
        ).move_to(old_base)

        old_aa = top_aas[2]
        new_aa = Text("W", font=DNA_FONT_NAME, font_size=AA_FONT, color=HIGHLIGHT).move_to(old_aa)

        self.play(Transform(old_base, new_base), run_time=0.6)
        self.play(top_arrows[2].animate.set_color(HIGHLIGHT), run_time=0.35)
        self.play(Transform(old_aa, new_aa), run_time=0.6)
        self.wait(0.5)

        # ── 2d: frameshift (bottom half) ──
        self.next_sub_slide("frameshift")

        # Bottom half starts as a fresh unmutated copy: 18 letters in 6 old triplets.
        bot_letters = [
            Text(c, font=DNA_FONT_NAME, font_size=DNA_FONT, color=TEXT_COLOR)
            for c in dna_str
        ]
        bot_dna_row = VGroup(*bot_letters).arrange(RIGHT, buff=LETTER_BUFF)
        bot_triplets = [
            VGroup(*bot_letters[i:i + 3])
            for i in range(0, len(dna_str), 3)
        ]
        bot_dna_row.move_to(DOWN * 1.7)

        bot_old_boxes = [
            SurroundingRectangle(
                t, buff=BOX_BUFF, color=BOX_COLOR, stroke_width=2.5,
                fill_color=BOX_COLOR, fill_opacity=BOX_FILL_OPACITY,
                corner_radius=BOX_CORNER_RADIUS,
            )
            for t in bot_triplets
        ]
        bot_aas = [
            Text(c, font=DNA_FONT_NAME, font_size=AA_FONT, color=TEXT_COLOR).move_to(t.get_center() + DOWN * ROW_VERT)
            for c, t in zip(aa_str, bot_triplets)
        ]
        bot_arrows = make_arrows(bot_triplets, bot_aas)

        self.play(
            FadeIn(bot_dna_row),
            FadeIn(VGroup(*bot_old_boxes)),
            FadeIn(VGroup(*bot_aas)),
            FadeIn(VGroup(*bot_arrows)),
            run_time=0.6,
        )
        self.wait(0.4)

        # Build target layout: insert 'G' at new index 3 (between old triplets 0 and 1).
        # Original 18 bases:   A T G   C A T   T G C   A A G   C T A   G A T
        # After insertion:     A T G [G] C A T T G C A A G C T A G A T   (19 bases)
        # In the new frame the groupings restart at index 0:
        #   ATG | GCA | TTG | CAA | GCT | AGA | T
        # Old triplet 0 (ATG) stays put, and only the letters to the right of the
        # insertion physically shift. The original blue reading frame stays fixed
        # so we can overlay the new red reading frame on top afterward.
        target_chars = list(dna_str)
        target_chars.insert(3, "G")  # 19 characters

        # Placeholder row in the new frame — used only to extract positions.
        target_ph = [
            Text(c, font=DNA_FONT_NAME, font_size=DNA_FONT, color=TEXT_COLOR)
            for c in target_chars
        ]
        target_row_ph = VGroup(*target_ph).arrange(RIGHT, buff=LETTER_BUFF)
        target_row_ph.move_to(DOWN * 1.7)
        # Anchor the left edge so old triplet 0 (ATG) stays put — only letters
        # to the right of the insertion appear to move.
        target_row_ph.shift(bot_letters[0].get_center() - target_ph[0].get_center())

        target_positions = [p.get_center() for p in target_ph]
        target_new_triplets_ph = [
            VGroup(*target_ph[i:i + 3])
            for i in range(0, len(dna_str), 3)
        ]

        # Inserted base (red) lands at new index 3.
        inserted_G = Text(
            "G", font=DNA_FONT_NAME, font_size=DNA_FONT, color=HIGHLIGHT
        ).move_to(target_positions[3])

        # Map each original letter to its new index.
        def new_idx(orig_idx):
            return orig_idx if orig_idx < 3 else orig_idx + 1

        # New reading-frame boxes are the same shape as the original ones, but
        # shifted to the post-insertion codon boundaries.
        new_frame_boxes = [
            SurroundingRectangle(
                tg, buff=BOX_BUFF, color=HIGHLIGHT, stroke_width=2.5,
                fill_color=HIGHLIGHT, fill_opacity=BOX_FILL_OPACITY,
                corner_radius=BOX_CORNER_RADIUS,
            )
            for tg in target_new_triplets_ph
        ]

        # "frameshift!" label sits just above the shifted region of the DNA
        # and is written in alongside the slide itself.
        shifted_x_start = target_positions[4][0]
        shifted_x_end = target_positions[-1][0]
        frameshift_label = Text(
            "frameshift!",
            font_size=28,
            weight=BOLD,
            color=HIGHLIGHT,
        ).move_to([(shifted_x_start + shifted_x_end) / 2, -1.05, 0])

        # Phase 1: physically insert the letter and shift only the downstream DNA.
        # The old (blue) reading-frame boxes travel with their triplets so that
        # after the shift they sit misaligned against the new codon boundaries.
        shift_anims = [FadeIn(inserted_G, shift=DOWN * 0.3)]
        for orig_idx, letter in enumerate(bot_letters):
            shift_anims.append(letter.animate.move_to(target_positions[new_idx(orig_idx)]))
        for i, box in enumerate(bot_old_boxes):
            first_letter_idx = 3 * i
            if first_letter_idx >= 3:
                delta = target_positions[new_idx(first_letter_idx)] - bot_letters[first_letter_idx].get_center()
                shift_anims.append(box.animate.shift(delta))
        shift_anims.append(Write(frameshift_label))

        self.play(*shift_anims, run_time=1.6)
        self.wait(0.3)

        # Phase 2: staggered cascade for the new reading frame. For each
        # codon, draw the red frame box; if the codon actually changed, the
        # arrow quickly flips red and the AA transforms into the new-frame
        # residue. New codons after inserting G at index 3:
        #   ATG | GCA | TTG | CAA | GCT | AGA | TGC | TTA   →   M A L Q A R C L
        # Codon 0 (ATG) is unchanged, so we skip the arrow/AA recolor there.
        new_aa_str = "MALQARCL"
        new_bot_aas = [
            Text(c, font=DNA_FONT_NAME, font_size=AA_FONT, color=HIGHLIGHT).move_to(bot_aas[i].get_center())
            for i, c in enumerate(new_aa_str)
        ]
        frame_seqs = []
        for i in range(len(new_frame_boxes)):
            # Codon 0 (ATG) occupies the same position as the old blue frame,
            # so the new frame matches — no red box or recolor needed.
            if i == 0:
                continue
            steps = [
                Create(new_frame_boxes[i], run_time=0.5),
                bot_arrows[i].animate(run_time=0.15).set_color(HIGHLIGHT),
                Transform(bot_aas[i], new_bot_aas[i], run_time=0.15),
            ]
            frame_seqs.append(Succession(*steps))
        self.play(LaggedStart(*frame_seqs, lag_ratio=0.35))
        self.wait(1.0)

        # === Slide 3: Zoom out into a universe of binary-format names ===
        self.next_slide("formats")

        # Full-page border at the frame edge. It's basically invisible while
        # stationary (stroke sits right on the viewport edge), but becomes
        # clearly visible as the whole scene shrinks during the zoom-out.
        border = Rectangle(
            width=config.frame_width,
            height=config.frame_height,
            color=TEXT_COLOR,
            stroke_width=3,
        )
        self.add(border)

        formats_rest = [
            "JPEG", "PDF", "GIF", "BMP", "TIFF", "WEBP", "HEIC", "SVG", "ICO",
            "MP3", "MP4", "AVI", "MOV", "WAV", "FLAC", "OGG", "MKV", "WEBM",
            "ZIP", "TAR", "GZ", "7Z", "ELF", "MACH-O", "DEB", "APK", "DMG",
            "ISO", "DOCX", "XLSX", "PPTX", "EPUB", "PSD", "SQLITE", "PARQUET",
            "WASM", "TTF", "WOFF", "PROTOBUF", "MSGPACK", "CBOR", "DICOM",
        ]
        rng = random.Random(42)

        # DNA anchors the center — the morph target, and the only blue word.
        # All other format names render in plain white.
        dna_label = Text(
            "DNA", font_size=46, color="#5B86C4", weight=BOLD
        ).move_to(ORIGIN)
        png = Text(
            "PNG", font_size=58, color=TEXT_COLOR, weight=BOLD
        ).move_to([2.8, -0.7, 0])

        # Collision-avoiding placement for the rest. Each candidate bbox must
        # not overlap any already-placed bbox (with a small buffer) before it
        # gets accepted.
        PAD = 0.22

        def bbox_of(mob):
            return (
                mob.get_left()[0] - PAD,
                mob.get_right()[0] + PAD,
                mob.get_bottom()[1] - PAD,
                mob.get_top()[1] + PAD,
            )

        def overlaps(a, b):
            return not (a[1] < b[0] or a[0] > b[1] or a[3] < b[2] or a[2] > b[3])

        placed_bboxes = [bbox_of(dna_label), bbox_of(png)]
        format_mobs = [png]

        for word in formats_rest:
            size = rng.choice([18, 20, 22, 24, 26, 28])
            candidate = Text(word, font_size=size, color=TEXT_COLOR)
            w, h = candidate.width, candidate.height
            for _ in range(400):
                x = rng.uniform(-6.2 + w / 2, 6.2 - w / 2)
                y = rng.uniform(-3.3 + h / 2, 3.3 - h / 2)
                cand_bbox = (
                    x - w / 2 - PAD,
                    x + w / 2 + PAD,
                    y - h / 2 - PAD,
                    y + h / 2 + PAD,
                )
                if not any(overlaps(cand_bbox, pb) for pb in placed_bboxes):
                    candidate.move_to([x, y, 0])
                    placed_bboxes.append(cand_bbox)
                    format_mobs.append(candidate)
                    break

        # Parallax starfield: each word saves its final resting state, then
        # is pushed outward radially + scaled up + faded out. Restore pulls
        # it back. Bigger final-size words travel more (they read as
        # "closer" to the camera), smaller ones barely move.
        zoom_anims = []
        for m in format_mobs:
            x, y = m.get_center()[0], m.get_center()[1]
            size = m.font_size
            m.save_state()
            m.scale(0.9 + size / 28)
            m.shift([x * 0.35, y * 0.35, 0])
            m.set_opacity(0)
            zoom_anims.append(
                Restore(
                    m,
                    run_time=0.9 + size / 55,
                    rate_func=rate_functions.ease_out_cubic,
                )
            )

        # Clear out the microbiology slide: VMobjects get FadeOut'd (shifting
        # to origin while shrinking), non-VMobject tracking ghosts left by
        # earlier Succession/LaggedStart animations are removed silently
        # (FadeOut can't animate them anyway). The border is kept — it morphs
        # into the DNA label, giving the zoom-out a clear visual through-line.
        old_mobs = [m for m in self.mobjects if m is not border]
        non_vmobs = [m for m in old_mobs if not isinstance(m, VMobject)]
        vmob_old = [m for m in old_mobs if isinstance(m, VMobject)]
        if non_vmobs:
            self.remove(*non_vmobs)

        self.add(*format_mobs)
        fade_outs = [
            FadeOut(m, target_position=ORIGIN, scale=0.03, run_time=1.2)
            for m in vmob_old
        ]
        self.play(
            *fade_outs,
            ReplacementTransform(border, dna_label, run_time=1.3),
            LaggedStart(*zoom_anims, lag_ratio=0.025),
        )
        # LaggedStart rolls its animated mobjects into a wrapper Group at
        # end-of-animation, which hides them from self.mobjects lookups.
        # Re-add them as top-level so later slides can reference png et al.
        self.add(*format_mobs)
        self.wait(1.5)

        # === Slide 4: Mutations in PNG ===
        self.next_slide("png_mutations")

        # ── 4a: parallax zoom into PNG → slide title ──
        self.next_sub_slide("title")

        # Everything except PNG flies outward (relative to PNG's center) and
        # scales up while fading, as if the camera is accelerating into PNG.
        # PNG itself morphs into a frame-sized rectangle — the new slide.
        png_center = png.get_center()
        fly_anims = []
        for m in self.mobjects:
            if m is png:
                continue
            direction = m.get_center() - png_center
            dist = (direction[0] ** 2 + direction[1] ** 2) ** 0.5
            shift = direction * 2.5
            scale = 1.6 + dist * 0.2
            fly_anims.append(
                FadeOut(
                    m,
                    shift=shift,
                    scale=scale,
                    run_time=1.2,
                    rate_func=rate_functions.ease_in_cubic,
                )
            )

        png_slide_frame = Rectangle(
            width=config.frame_width,
            height=config.frame_height,
            color=TEXT_COLOR,
            stroke_width=3,
        )
        self.play(
            *fly_anims,
            ReplacementTransform(png, png_slide_frame, run_time=1.3),
        )
        self.remove(png_slide_frame)
        self.wait(0.2)

        png_title = Text(
            "Mutations in PNG", font_size=52, weight=BOLD, color=TEXT_COLOR
        ).to_edge(UP, buff=0.5)

        legend = Text(
            "PNG ::= sig (size type data crc)*",
            font_size=30,
            color=TEXT_COLOR,
            weight=BOLD,
            t2c={
                "sig": SIG_COLOR,
                "size": SIZE_COLOR,
                "type": TYPE_COLOR,
                "data": DATA_COLOR,
                "crc": CRC_COLOR,
            },
        ).move_to([0, 2.7, 0])

        self.play(Write(png_title), Write(legend), run_time=1.0)
        self.wait(0.3)

        # ── 4b: missense — hex dump + animated parser walk (top half) ──
        self.next_sub_slide("missense")

        byte_mobjs = [
            Text(
                b, font=DNA_FONT_NAME, font_size=HEX_FONT,
                color=byte_color_for_offset(i),
            )
            for i, b in enumerate(hex_bytes_list)
        ]
        hex_row = VGroup(*byte_mobjs).arrange(RIGHT, buff=HEX_BUFF)

        field_labels = []
        for start, end, text, color in field_labels_defs:
            first = byte_mobjs[start]
            last = byte_mobjs[end]
            label = Text(text, font=DNA_FONT_NAME, font_size=18, color=color, weight=BOLD)
            center_x = (first.get_center()[0] + last.get_center()[0]) / 2
            label_y = first.get_top()[1] + 0.26
            label.move_to([center_x, label_y, 0])
            field_labels.append(label)

        # The hex row + field labels live together and scroll as one unit.
        # Blue chunk boxes will be added to this group as they're drawn so
        # they scroll with their bytes on subsequent jumps.
        hex_container = VGroup(hex_row, *field_labels)
        HEX_ROW_Y = 1.7
        INITIAL_LEFT_X = -6.8
        hex_container.shift([
            INITIAL_LEFT_X - byte_mobjs[0].get_center()[0],
            HEX_ROW_Y,
            0,
        ])

        self.play(
            Write(hex_row, run_time=1.4),
            LaggedStart(
                *[Write(l) for l in field_labels],
                lag_ratio=0.05,
                run_time=1.4,
            ),
        )
        self.wait(0.3)

        # Parser walk: (name, size, size_range, type_range, full_chunk_range)
        parser_chunks = [
            ("IHDR", 13, (8, 11), (12, 15), (8, 32)),
            ("gAMA", 4, (33, 36), (37, 40), (33, 48)),
            ("sRGB", 1, (49, 52), (53, 56), (49, 61)),
            ("cHRM", 32, (62, 65), (66, 69), (62, 105)),
            ("bKGD", 2, (106, 109), (110, 113), (106, 119)),
            ("pHYs", 9, (120, 123), (124, 127), (120, 140)),
            ("IDAT", 947, (141, 144), (145, 148), (141, 159)),  # data truncated
        ]

        # Chunk names list: static, grows rightward near y=0 so the bottom
        # half of the slide is free for the upcoming frameshift example.
        # Font 22 + tight buff fits all 12 chunks (incl. the final tEXt×4
        # + IEND) across the frame width.
        CHUNK_LIST_Y = 0.4
        CHUNK_LIST_START_X = -6.5

        def chunk_name_mob(name, prev_list):
            label = Text(name, font=DNA_FONT_NAME, font_size=22, color=TEXT_COLOR, weight=BOLD)
            if prev_list:
                label.next_to(prev_list[-1], RIGHT, buff=0.28)
            else:
                label.move_to([CHUNK_LIST_START_X + label.width / 2, CHUNK_LIST_Y, 0])
            return label

        # The yellow parser cursor stays pinned at FOCUS_X; on every jump we
        # shift the whole hex_container so that the next size field lands
        # under the cursor.
        FOCUS_X = -4.0

        def rect_around(start, end_inclusive, color, buff, stroke_width,
                        fill_opacity=0.0, corner_radius=0.0):
            return SurroundingRectangle(
                VGroup(*byte_mobjs[start:end_inclusive + 1]),
                buff=buff, color=color, stroke_width=stroke_width,
                fill_color=color, fill_opacity=fill_opacity,
                corner_radius=corner_radius,
            )

        def make_chunk_brace(chunk, tail_mobs=()):
            """Sideways brace under chunk's data region + size number label."""
            chunk_start = chunk[4][0]
            chunk_end = chunk[4][1]
            actual_size = chunk[1]
            full_chunk_len = 12 + actual_size
            displayed_len = chunk_end - chunk_start + 1
            data_start = chunk_start + 8
            # If the chunk is fully rendered in the dump, the last 4 bytes
            # are CRC. If it's truncated (e.g. IDAT), everything from type
            # onward is visible "data" and there's no CRC in view.
            if displayed_len == full_chunk_len:
                data_end = chunk_end - 4
            else:
                data_end = chunk_end
            if data_end < data_start:
                data_end = data_start
            data_group = VGroup(*byte_mobjs[data_start:data_end + 1], *tail_mobs)
            brace = Brace(
                data_group, direction=DOWN, color=SIZE_COLOR, buff=0.08,
            )
            size_label = Text(
                str(chunk[1]), font=DNA_FONT_NAME, font_size=26, color=SIZE_COLOR, weight=BOLD,
            ).next_to(brace, DOWN, buff=0.08)
            return brace, size_label

        # Step 0: highlight the signature.
        current_hl = rect_around(0, 7, HL_COLOR, buff=0.05, stroke_width=3,
                                fill_opacity=BOX_FILL_OPACITY, corner_radius=BOX_CORNER_RADIUS)
        self.play(Create(current_hl), run_time=0.5)
        self.wait(0.3)

        # Step 1: first jump — into IHDR's size field. Brace appears under
        # IHDR's data region, labeled with the size we just read.
        first = parser_chunks[0]
        new_hl_target = rect_around(first[2][0], first[2][1], HL_COLOR, buff=0.05, stroke_width=3,
                                fill_opacity=BOX_FILL_OPACITY, corner_radius=BOX_CORNER_RADIUS)
        first_brace, first_size_label = make_chunk_brace(first)
        scroll_delta = FOCUS_X - new_hl_target.get_center()[0]
        new_hl_target.shift(RIGHT * scroll_delta)
        # Fade brace+label in from their pre-scroll positions and move them to
        # post-scroll in lockstep with the bytes. Transforming to a shifted,
        # opaque copy handles fade+translate in one animation without fighting
        # hex_container's shift.
        first_brace_target = first_brace.copy().shift(RIGHT * scroll_delta)
        first_size_label_target = first_size_label.copy().shift(RIGHT * scroll_delta)
        first_brace.set_opacity(0)
        first_size_label.set_opacity(0)
        self.add(first_brace, first_size_label)
        self.play(
            Transform(current_hl, new_hl_target),
            Transform(first_brace, first_brace_target),
            Transform(first_size_label, first_size_label_target),
            hex_container.animate.shift(RIGHT * scroll_delta),
            run_time=0.7,
        )
        hex_container.add(first_brace, first_size_label)
        self.wait(0.3)

        chunk_names = []
        # Track the per-chunk blue "reading frame" boxes in parser_chunks
        # order so we can reference and manipulate them later (e.g. on the
        # frameshift slide).
        blue_boxes = []

        # Middle steps: for each transition, first draw the prev chunk's
        # box + arrow + name (while it's still in view), then shift the
        # highlight (and maybe scroll) to the next size field.
        for i in range(1, len(parser_chunks)):
            prev = parser_chunks[i - 1]
            cur = parser_chunks[i]

            # Blue box around the entire previous chunk (size+type+data+crc).
            # Buff is tighter than the yellow highlight so adjacent chunk
            # boxes sit shoulder-to-shoulder without overlapping.
            prev_box = rect_around(
                prev[4][0], prev[4][1], BOX_COLOR, buff=0.06, stroke_width=2.5,
                fill_opacity=BOX_FILL_OPACITY, corner_radius=BOX_CORNER_RADIUS,
            )
            name_label = chunk_name_mob(prev[0], chunk_names)
            # Arrow springs from the chunk's type field (the four bytes that
            # name the chunk) down to the chunk-name row — same visual style
            # as the DNA → AA arrows.
            prev_type_bytes = VGroup(*byte_mobjs[prev[3][0]:prev[3][1] + 1])
            arrow = Arrow(
                prev_type_bytes.get_bottom(),
                name_label.get_top(),
                buff=0.12,
                color=ARROW_COLOR,
                stroke_width=10,
                tip_length=0.35,
                max_tip_length_to_length_ratio=0.35,
                max_stroke_width_to_length_ratio=20,
            )
            self.play(
                Create(prev_box),
                GrowArrow(arrow),
                Write(name_label),
                run_time=0.7,
            )
            self.play(FadeOut(arrow), run_time=0.25)
            hex_container.add(prev_box)  # scroll with bytes from now on
            blue_boxes.append(prev_box)
            chunk_names.append(name_label)

            # Jump to cur's size field. Scroll the hex_container so that the
            # target lands under the fixed FOCUS_X cursor position.
            new_hl_target = rect_around(
                cur[2][0], cur[2][1], HL_COLOR, buff=0.05, stroke_width=3,
                fill_opacity=BOX_FILL_OPACITY, corner_radius=BOX_CORNER_RADIUS,
            )
            # For the last (truncated) chunk, fade the "..." in first so the
            # incoming brace spans it from the start — no stretch-after.
            is_last_transition = (i == len(parser_chunks) - 1)
            if is_last_transition:
                hex_ellipsis = Text(
                    "...", font=DNA_FONT_NAME, font_size=HEX_FONT + 4,
                    color=DATA_COLOR, weight=BOLD,
                ).next_to(byte_mobjs[-1], RIGHT, buff=0.2)
                self.play(FadeIn(hex_ellipsis, shift=LEFT * 0.15), run_time=0.4)
                hex_container.add(hex_ellipsis)
                new_brace, new_size_label = make_chunk_brace(cur, tail_mobs=(hex_ellipsis,))
            else:
                new_brace, new_size_label = make_chunk_brace(cur)

            scroll_delta = FOCUS_X - new_hl_target.get_center()[0]
            new_hl_target.shift(RIGHT * scroll_delta)

            new_brace_target = new_brace.copy().shift(RIGHT * scroll_delta)
            new_size_label_target = new_size_label.copy().shift(RIGHT * scroll_delta)
            new_brace.set_opacity(0)
            new_size_label.set_opacity(0)
            self.add(new_brace, new_size_label)

            self.play(
                Transform(current_hl, new_hl_target),
                Transform(new_brace, new_brace_target),
                Transform(new_size_label, new_size_label_target),
                hex_container.animate.shift(RIGHT * scroll_delta),
                run_time=0.9,
            )
            hex_container.add(new_brace, new_size_label)
            current_brace = new_brace
            current_size_label = new_size_label
            self.wait(0.15)

        # Final step: box the whole truncated IDAT chunk (bytes + ellipsis)
        # and label it on the chunk-name row. Ellipsis + IDAT brace were
        # placed during the last loop transition.
        last = parser_chunks[-1]

        last_box = SurroundingRectangle(
            VGroup(*byte_mobjs[last[4][0]:last[4][1] + 1], hex_ellipsis),
            buff=0.06, color=BOX_COLOR, stroke_width=2.5,
            fill_color=BOX_COLOR, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )
        last_name = chunk_name_mob(last[0], chunk_names)
        last_type_bytes = VGroup(*byte_mobjs[last[3][0]:last[3][1] + 1])
        last_arrow = Arrow(
            last_type_bytes.get_bottom(),
            last_name.get_top(),
            buff=0.12,
            color=ARROW_COLOR,
            stroke_width=10,
            tip_length=0.35,
            max_tip_length_to_length_ratio=0.35,
            max_stroke_width_to_length_ratio=20,
        )
        self.play(
            Create(last_box),
            GrowArrow(last_arrow),
            Write(last_name),
            run_time=0.7,
        )
        self.play(FadeOut(last_arrow), run_time=0.25)
        hex_container.add(last_box)
        blue_boxes.append(last_box)
        chunk_names.append(last_name)

        # The rest of the chunks in this file (no more hex bytes, just the
        # chunk names staggered into the sequence).
        remaining = ["tEXt", "tEXt", "tEXt", "tEXt", "IEND"]
        remaining_labels = []
        for name_text in remaining:
            label = chunk_name_mob(name_text, chunk_names + remaining_labels)
            remaining_labels.append(label)
        self.play(
            LaggedStart(
                *[Write(l) for l in remaining_labels],
                lag_ratio=0.15,
                run_time=0.9,
            )
        )
        chunk_names.extend(remaining_labels)

        self.wait(0.8)

        # ── 4c: missense — flip one gAMA data byte to FF ──
        self.next_sub_slide("png_missense")

        gama = parser_chunks[1]  # gAMA
        gama_size_center_x = (
            byte_mobjs[gama[2][0]].get_center()[0]
            + byte_mobjs[gama[2][1]].get_center()[0]
        ) / 2
        scroll_back_delta = FOCUS_X - gama_size_center_x
        self.play(
            hex_container.animate.shift(RIGHT * scroll_back_delta),
            run_time=1.0,
        )
        self.wait(0.3)

        MUT_IDX = 43  # inside gAMA's data region (41..44)
        mutated_byte_new = Text(
            "FF", font=DNA_FONT_NAME, font_size=HEX_FONT, color=HIGHLIGHT,
        ).move_to(byte_mobjs[MUT_IDX].get_center())
        self.play(Transform(byte_mobjs[MUT_IDX], mutated_byte_new), run_time=0.6)
        self.wait(0.3)

        # Red arrow from gAMA's type field down to its chunk-name label, and
        # recolor the gAMA label red to show the chunk is affected.
        gama_label = chunk_names[1]
        gama_type_bytes = VGroup(*byte_mobjs[gama[3][0]:gama[3][1] + 1])
        missense_arrow = Arrow(
            gama_type_bytes.get_bottom(),
            gama_label.get_top(),
            buff=0.12, color=HIGHLIGHT,
            stroke_width=10, tip_length=0.35,
            max_tip_length_to_length_ratio=0.35,
            max_stroke_width_to_length_ratio=20,
        )
        self.play(
            GrowArrow(missense_arrow),
            gama_label.animate.set_color(HIGHLIGHT),
            run_time=0.8,
        )
        self.wait(1.0)

        # === Slide 5: Frameshift on PNG (copy state below, insert byte) ===
        self.next_slide("png_frameshift")

        # Retire the missense arrow. The chunk-listing row is already high
        # enough (CHUNK_LIST_Y) that the bottom copy fits below without any
        # shift of the top view.
        self.play(FadeOut(missense_arrow), run_time=0.4)

        # Deep-copy the top as the bottom's starting state, then revert the
        # mutated byte and the red cHRM label so the bottom begins from the
        # un-mutated original — scrolled to the same position as the top.
        hex_container_bot = hex_container.copy()
        hex_row_bot = hex_container_bot.submobjects[0]
        bottom_byte_mobjs = list(hex_row_bot.submobjects)

        # Revert the mutated byte in the copy by morphing its existing mobject
        # back to the original hex + data-role color. Using `.become()` keeps
        # the same mobject reference (and submobject slot), so subsequent
        # shift/fade animations on bottom_byte_mobjs[MUT_IDX] behave normally.
        orig_byte_template = Text(
            hex_bytes_list[MUT_IDX], font=DNA_FONT_NAME, font_size=HEX_FONT,
            color=byte_color_for_offset(MUT_IDX),
        ).move_to(bottom_byte_mobjs[MUT_IDX].get_center())
        bottom_byte_mobjs[MUT_IDX].become(orig_byte_template)

        # Map top-row blue-box + field-label references to their bottom-copy
        # counterparts by looking up positions in hex_container.submobjects.
        blue_box_indices = [hex_container.submobjects.index(b) for b in blue_boxes]
        blue_boxes_bot = [hex_container_bot.submobjects[i] for i in blue_box_indices]
        field_labels_bot = list(
            hex_container_bot.submobjects[1:1 + len(field_labels)]
        )

        chunk_names_bot = [n.copy().set_color(TEXT_COLOR) for n in chunk_names]

        bottom_group = VGroup(hex_container_bot, *chunk_names_bot)
        # Place the whole bottom view in the lower half of the frame. Top
        # chunk-list row ends around y≈0.3 (CHUNK_LIST_Y=0.4), so a 2.5-unit
        # drop leaves the bottom hex row near y≈-0.8 without overlap.
        BOTTOM_DOWN = DOWN * 3.3
        bottom_group.shift(BOTTOM_DOWN)

        self.play(FadeIn(bottom_group), run_time=0.8)
        self.wait(0.4)

        # ── Insert a red byte in gAMA's data region; shift downstream bytes,
        # field labels, and blue chunk boxes alongside so everything that
        # lived to the right of the insertion stays visually aligned. ──
        byte_pitch = bottom_byte_mobjs[1].get_center()[0] - bottom_byte_mobjs[0].get_center()[0]
        SHIFT_VEC = RIGHT * byte_pitch
        insert_anchor = bottom_byte_mobjs[INSERT_IDX].get_center()

        inserted_byte_bot = Text(
            "47", font=DNA_FONT_NAME, font_size=HEX_FONT, color=HIGHLIGHT,
        ).move_to(insert_anchor)

        fs_label = Text(
            "frameshift!", font=DNA_FONT_NAME, font_size=24,
            weight=BOLD, color=HIGHLIGHT,
        ).next_to(bottom_byte_mobjs[INSERT_IDX], UP, buff=0.5)

        # Field labels whose byte range is fully to the right of the
        # insertion travel with their bytes. (The gAMA "data" label at
        # 41..44 straddles the insertion and stays put.)
        field_labels_to_shift = [
            field_labels_bot[i]
            for i, (start, _end, _text, _color) in enumerate(field_labels_defs)
            if start > INSERT_IDX
        ]

        # Blue chunk boxes for chunks fully after gAMA (sRGB onward) shift
        # with their bytes. gAMA itself stretches by one byte so its right
        # edge still covers the shifted CRC.
        boxes_to_shift = blue_boxes_bot[2:]
        gama_blue = blue_boxes_bot[1]

        # Build the gAMA-stretch target: surround the post-shift byte layout.
        # Temporarily apply the downstream shift, snapshot, then undo.
        for b in bottom_byte_mobjs[43:49]:
            b.shift(SHIFT_VEC)
        gama_blue_target = SurroundingRectangle(
            VGroup(
                *bottom_byte_mobjs[33:43],
                inserted_byte_bot,
                *bottom_byte_mobjs[43:49],
            ),
            buff=0.06, color=BOX_COLOR, stroke_width=2.5,
            fill_color=BOX_COLOR, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )
        for b in bottom_byte_mobjs[43:49]:
            b.shift(-SHIFT_VEC)

        self.play(
            FadeIn(inserted_byte_bot, shift=DOWN * 0.3),
            *[b.animate.shift(SHIFT_VEC)
              for b in bottom_byte_mobjs[INSERT_IDX:]],
            *[m.animate.shift(SHIFT_VEC)
              for m in field_labels_to_shift + list(boxes_to_shift)],
            Transform(gama_blue, gama_blue_target),
            Write(fs_label),
            run_time=1.4,
        )
        self.wait(0.4)

        # ── New red reading frame for gAMA (same length as the original) ──
        # Covers 16 bytes at visual slots 33..48, so it now ends one byte
        # before the end of the (shifted) CRC.
        gama_red_frame = SurroundingRectangle(
            VGroup(
                *bottom_byte_mobjs[33:43],
                inserted_byte_bot,
                *bottom_byte_mobjs[43:48],
            ),
            buff=0.06, color=HIGHLIGHT, stroke_width=2.5,
            fill_color=HIGHLIGHT, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )
        self.play(Create(gama_red_frame), run_time=0.8)
        self.wait(0.6)

        # ── 5b: highlight the mis-read "size" field (no scroll) ──
        self.next_sub_slide("mis_size")

        # After the insertion, the parser — which thinks gAMA's CRC sits at
        # the original byte offsets — reads the next chunk's "size" from
        # shifted-positions 49..52 (our byte_mobjs[48..51]). Big-endian
        # value: 0x05000000 = 83886080.
        mis_size_refs = VGroup(*bottom_byte_mobjs[48:52])

        mis_size_hl = SurroundingRectangle(
            mis_size_refs,
            buff=0.05, color=HL_COLOR, stroke_width=3,
            fill_color=HL_COLOR, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )
        mis_brace = Brace(mis_size_refs, direction=DOWN, color=HIGHLIGHT, buff=0.08)
        mis_size_label = Text(
            "size = 83886080", font=DNA_FONT_NAME, font_size=22,
            color=HIGHLIGHT, weight=BOLD,
        ).next_to(mis_brace, DOWN, buff=0.1)

        self.play(
            Create(mis_size_hl),
            GrowFromCenter(mis_brace),
            Write(mis_size_label),
            run_time=0.8,
        )
        self.wait(0.8)

        # ── 5c: interpret next 4 bytes as the new "chunk type" ──
        self.next_sub_slide("mis_type")

        # One byte before the sRGB ASCII in the shifted file: visual slot 53
        # starts at bottom_byte_mobjs[52] → bytes [01, 73, 52, 47] → "\x01sRG".
        mis_type_refs = VGroup(*bottom_byte_mobjs[52:56])
        mis_type_hl = SurroundingRectangle(
            mis_type_refs,
            buff=0.05, color=HIGHLIGHT, stroke_width=3,
            fill_color=HIGHLIGHT, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )
        garbage_label = Text(
            "\\x01sRG", font=DNA_FONT_NAME, font_size=22,
            color=HIGHLIGHT, weight=BOLD,
        ).next_to(chunk_names_bot[1], RIGHT, buff=0.28)
        mis_type_arrow = Arrow(
            mis_type_refs.get_bottom(),
            garbage_label.get_top(),
            buff=0.12, color=ARROW_COLOR,
            stroke_width=10, tip_length=0.35,
            max_tip_length_to_length_ratio=0.35,
            max_stroke_width_to_length_ratio=20,
        )

        # Every chunk after gAMA in the bottom list is invalidated — fade
        # them out now that the parser has derailed.
        invalidated = chunk_names_bot[2:]
        self.play(
            Create(mis_type_hl),
            GrowArrow(mis_type_arrow),
            Write(garbage_label),
            *[FadeOut(n) for n in invalidated],
            run_time=1.0,
        )
        self.play(FadeOut(mis_type_arrow), run_time=0.3)
        self.wait(0.6)

        # ── 5d: next jump lands out of bounds → parse error ──
        self.next_sub_slide("mis_error")

        error_chunk_label = Text(
            "(error)", font=DNA_FONT_NAME, font_size=22,
            color=HIGHLIGHT, weight=BOLD,
        ).next_to(garbage_label, RIGHT, buff=0.28)
        self.play(Write(error_chunk_label), run_time=0.6)
        self.wait(1.2)

        # === Slide 6: The cost of frameshifts ===
        self.next_slide("cost_of_frameshifts")

        # Layout constants for the new slide.
        AXIS_Y = 0.0
        AXIS_LEFT_X = -5.5
        AXIS_RIGHT_X = 5.5
        PNG_TICK_X = -3.2
        TPM_TICK_X = 3.2
        STOP_HEIGHT = 0.9
        TICK_HEIGHT = 0.35

        # Build the "background" of the new slide — axis, stop bars, endpoint
        # labels, and title. We add these first (then push to back) so they
        # are visually behind the PNG content while it collapses into the
        # PNG tick on the left.
        axis_line = Line(
            [AXIS_LEFT_X, AXIS_Y, 0], [AXIS_RIGHT_X, AXIS_Y, 0],
            color=TEXT_COLOR, stroke_width=6,
        )
        left_stop = Line(
            [AXIS_LEFT_X, AXIS_Y - STOP_HEIGHT / 2, 0],
            [AXIS_LEFT_X, AXIS_Y + STOP_HEIGHT / 2, 0],
            color=TEXT_COLOR, stroke_width=14,
        )
        right_stop = Line(
            [AXIS_RIGHT_X, AXIS_Y - STOP_HEIGHT / 2, 0],
            [AXIS_RIGHT_X, AXIS_Y + STOP_HEIGHT / 2, 0],
            color=TEXT_COLOR, stroke_width=14,
        )
        left_label = Text(
            "wasted cycles", font_size=28, color=TEXT_COLOR, weight=BOLD,
        ).next_to(left_stop, UP, buff=0.3)
        right_label = Text(
            "unreachable inputs", font_size=28, color=TEXT_COLOR, weight=BOLD,
        ).next_to(right_stop, UP, buff=0.3)
        cost_title = Text(
            "The cost of frameshifts",
            font_size=52, color=TEXT_COLOR, weight=BOLD,
        ).to_edge(UP, buff=0.5)

        # PNG tick + label at the left end — the target the PNG scene morphs
        # into.
        png_tick = Line(
            [PNG_TICK_X, AXIS_Y - TICK_HEIGHT, 0],
            [PNG_TICK_X, AXIS_Y + TICK_HEIGHT, 0],
            color=TEXT_COLOR, stroke_width=8,
        )
        png_label = Text(
            "PNG", font_size=32, color=TEXT_COLOR, weight=BOLD,
        ).next_to(png_tick, DOWN, buff=0.22)
        png_target = VGroup(png_tick, png_label)

        background = [
            axis_line, left_stop, right_stop, left_label, right_label,
            cost_title,
        ]

        # Snapshot everything currently on stage — that's the old PNG content
        # that needs to collapse. Do this BEFORE adding the background.
        old_mobs = list(self.mobjects)

        # Add the background (behind the PNG content).
        self.add(*background)
        self.bring_to_back(*background)

        # Full-page border at the frame edges. It's invisible while
        # stationary but provides a clear morph source for the collapse into
        # png_target.
        border = Rectangle(
            width=config.frame_width, height=config.frame_height,
            color=TEXT_COLOR, stroke_width=3,
        )
        self.add(border)

        # Flatten old_mobs: iterate into any VGroup/wrapper so that we catch
        # every leaf that's currently rendering (including children that sit
        # under LaggedStart wrappers).
        def collect_leaves(m, out):
            if isinstance(m, VMobject) and not m.submobjects:
                out.append(m)
            elif m.submobjects:
                for sub in m.submobjects:
                    collect_leaves(sub, out)
            else:
                out.append(m)

        leaves = []
        for m in old_mobs:
            collect_leaves(m, leaves)
        # Keep only VMobjects (FadeOut can't animate wrapper Groups).
        leaves = [m for m in leaves if isinstance(m, VMobject)]

        # Remove all the old top-level mobjects up front so their wrappers
        # don't leave ghost copies behind after the FadeOut leaves do their
        # animation on the leaves.
        for m in old_mobs:
            self.remove(m)
        # Re-add the leaves so manim keeps rendering them through the fade.
        self.add(*leaves)

        target_pos = png_target.get_center()
        fade_outs = [
            FadeOut(m, target_position=target_pos, scale=0.04, run_time=1.3)
            for m in leaves
        ]
        self.play(
            *fade_outs,
            ReplacementTransform(border, png_target, run_time=1.3),
        )
        # Re-add png_target as top-level in case ReplacementTransform's
        # wrapper hid it from self.mobjects.
        self.add(png_target)
        self.wait(0.8)

        # ── 6b: TPM joins the axis on the right ──
        self.next_sub_slide("tpm")

        tpm_tick = Line(
            [TPM_TICK_X, AXIS_Y - TICK_HEIGHT, 0],
            [TPM_TICK_X, AXIS_Y + TICK_HEIGHT, 0],
            color=TEXT_COLOR, stroke_width=8,
        )
        tpm_label = Text(
            "TPM", font_size=32, color=TEXT_COLOR, weight=BOLD,
        ).next_to(tpm_tick, DOWN, buff=0.22)
        self.play(
            Create(tpm_tick),
            Write(tpm_label),
            run_time=0.8,
        )
        self.wait(1.0)

        # === Slide 7: Mutations in TPM ===
        self.next_slide("tpm_mutations")

        # ── 7a: parallax zoom into TPM → slide title ──
        self.next_sub_slide("title")

        # Everything except the TPM tick + label flies outward (relative to
        # TPM's center) and scales up while fading, as if the camera were
        # accelerating into TPM. The label morphs into a frame-sized
        # rectangle — the new slide.
        tpm_anchor = tpm_label.get_center()
        fly_anims = []
        for m in self.mobjects:
            if m is tpm_label or m is tpm_tick:
                continue
            direction = m.get_center() - tpm_anchor
            dist = (direction[0] ** 2 + direction[1] ** 2) ** 0.5
            shift = direction * 2.5
            scale = 1.6 + dist * 0.2
            fly_anims.append(
                FadeOut(
                    m, shift=shift, scale=scale,
                    run_time=1.2,
                    rate_func=rate_functions.ease_in_cubic,
                )
            )

        tpm_slide_frame = Rectangle(
            width=config.frame_width, height=config.frame_height,
            color=TEXT_COLOR, stroke_width=3,
        )
        self.play(
            *fly_anims,
            FadeOut(tpm_tick, scale=0.3, run_time=1.0),
            ReplacementTransform(tpm_label, tpm_slide_frame, run_time=1.3),
        )
        self.remove(tpm_slide_frame)
        self.wait(0.2)

        tpm_title = Text(
            "Mutations in TPM", font_size=52, weight=BOLD, color=TEXT_COLOR,
        ).to_edge(UP, buff=0.5)
        self.play(Write(tpm_title), run_time=1.0)
        self.wait(0.3)

        # ── 7b: annotated TPM_PCR_Event packet (Figure 1 from the paper) ──
        self.next_sub_slide("packet")

        # Bytes of the TPM_PCR_Event command packet with payload
        # "Hello World Event!\n\0". 49 bytes total.
        tpm_bytes = [
            "80", "02",                                              # tag
            "00", "00", "00", "31",                                  # cmdSize = 49
            "00", "00", "01", "3c",                                  # cmdCode
            "00", "00", "00", "00",                                  # pcrHandle
            "00", "00", "00", "09",                                  # authSize = 9
            "40", "00", "00", "09", "00", "00", "00", "00", "00",    # authData (9)
            "00", "14",                                              # size = 20
            "48", "65", "6c", "6c", "6f", "20",                      # "Hello "
            "57", "6f", "72", "6c", "64", "20",                      # "World "
            "45", "76", "65", "6e", "74", "21", "0a", "00",          # "Event!\n\0"
        ]

        # Role-based palette — mirrors the PNG colouring.
        TAG_COLOR_T = "#FCD34D"     # gold
        SIZE_COLOR_T = "#F97316"    # orange — size / relation fields
        CODE_COLOR_T = "#22D3EE"    # cyan — type-like fields
        HANDLE_COLOR_T = "#A78BFA"  # violet — handles
        DATA_COLOR_T = "#94A3B8"    # slate — data

        # (start_byte, end_byte_inclusive, label_text, colour)
        tpm_fields = [
            (0, 1, "tag", TAG_COLOR_T),
            (2, 5, "cmdSize", SIZE_COLOR_T),
            (6, 9, "cmdCode", CODE_COLOR_T),
            (10, 13, "pcrHandle", HANDLE_COLOR_T),
            (14, 17, "authSize", SIZE_COLOR_T),
            (18, 26, "authData", DATA_COLOR_T),
            (27, 28, "size", SIZE_COLOR_T),
            (29, 48, "data", DATA_COLOR_T),
        ]

        def tpm_color_for(idx):
            for start, end, _n, col in tpm_fields:
                if start <= idx <= end:
                    return col
            return TEXT_COLOR

        # Measured: at font=16 buff=0.03, the 49-byte row is ~13.94 units wide
        # — nearly edge-to-edge inside the 14.22-wide frame.
        TPM_HEX_FONT = 16
        TPM_HEX_BUFF = 0.03
        tpm_byte_mobjs = [
            Text(
                b, font=DNA_FONT_NAME, font_size=TPM_HEX_FONT,
                color=tpm_color_for(i),
            )
            for i, b in enumerate(tpm_bytes)
        ]
        tpm_hex_row = VGroup(*tpm_byte_mobjs).arrange(RIGHT, buff=TPM_HEX_BUFF)
        tpm_hex_row.move_to([0, 0.6, 0])

        # Field labels above each byte range, coloured to match their bytes.
        tpm_field_label_mobs = []
        for start, end, name, color in tpm_fields:
            first = tpm_byte_mobjs[start]
            last = tpm_byte_mobjs[end]
            label = Text(
                name, font=DNA_FONT_NAME, font_size=14,
                color=color, weight=BOLD,
            )
            center_x = (first.get_center()[0] + last.get_center()[0]) / 2
            label_y = first.get_top()[1] + 0.24
            label.move_to([center_x, label_y, 0])
            tpm_field_label_mobs.append(label)

        # Two inner braces — authSize → authData (9 bytes) and size → data
        # (20 bytes) — both sit just below the byte row.
        auth_group = VGroup(*tpm_byte_mobjs[18:27])
        auth_brace = Brace(
            auth_group, direction=DOWN, color=SIZE_COLOR_T, buff=0.12,
        )
        auth_size_label = Text(
            "9", font=DNA_FONT_NAME, font_size=20,
            color=SIZE_COLOR_T, weight=BOLD,
        ).next_to(auth_brace, DOWN, buff=0.08)

        data_group = VGroup(*tpm_byte_mobjs[29:49])
        data_brace = Brace(
            data_group, direction=DOWN, color=SIZE_COLOR_T, buff=0.12,
        )
        data_size_label = Text(
            "20", font=DNA_FONT_NAME, font_size=20,
            color=SIZE_COLOR_T, weight=BOLD,
        ).next_to(data_brace, DOWN, buff=0.08)

        # Outer brace — cmdSize (49 bytes) encompasses the entire packet,
        # sitting below the two inner braces + size labels.
        cmd_brace = Brace(
            tpm_hex_row, direction=DOWN, color=SIZE_COLOR_T, buff=1.05,
        )
        cmd_size_label = Text(
            "49", font=DNA_FONT_NAME, font_size=20,
            color=SIZE_COLOR_T, weight=BOLD,
        ).next_to(cmd_brace, DOWN, buff=0.08)

        # Reveal in layers: bytes + field labels, then inner braces, then
        # the outer cmdSize brace.
        self.play(
            Write(tpm_hex_row, run_time=1.4),
            LaggedStart(
                *[Write(l) for l in tpm_field_label_mobs],
                lag_ratio=0.05,
                run_time=1.4,
            ),
        )
        self.wait(0.3)
        self.play(
            GrowFromCenter(auth_brace),
            Write(auth_size_label),
            GrowFromCenter(data_brace),
            Write(data_size_label),
            run_time=0.9,
        )
        self.wait(0.3)
        self.play(
            GrowFromCenter(cmd_brace),
            Write(cmd_size_label),
            run_time=0.9,
        )
        self.wait(0.8)

        # ── 7c: fuzzer comparison table (empty numbers) ──
        self.next_sub_slide("fuzzer_table")

        tpm_packet_group = VGroup(
            tpm_hex_row,
            *tpm_field_label_mobs,
            auth_brace, auth_size_label,
            data_brace, data_size_label,
            cmd_brace, cmd_size_label,
        )
        PACKET_UP = UP * 1.3
        self.play(tpm_packet_group.animate.shift(PACKET_UP), run_time=0.8)

        question = Text(
            "How many new commands can SOTA  fuzzers discover "
            "(48 hours x 5 runs)?",
            font_size=24, color=TEXT_COLOR,
        ).move_to([0, -0.55, 0])
        self.play(Write(question), run_time=1.0)
        self.wait(0.2)

        fuzzers = ["AFL++", "LibAFL", "AFL", "NestFuzz", "WEIZZ"]
        TABLE_Y_START = -1.2
        TABLE_ROW_SPACING = 0.5
        TABLE_NAME_RIGHT_X = -0.4   # right edge of the name column
        TABLE_NUM_LEFT_X = 0.4      # left edge of the number column

        name_mobs = []
        num_slot_ys = []
        for i, name in enumerate(fuzzers):
            y = TABLE_Y_START - i * TABLE_ROW_SPACING
            label = Text(
                name, font=DNA_FONT_NAME, font_size=26,
                color=TEXT_COLOR, weight=BOLD,
            )
            # Right-align against TABLE_NAME_RIGHT_X.
            label.move_to(
                [TABLE_NAME_RIGHT_X - label.width / 2, y, 0]
            )
            name_mobs.append(label)
            num_slot_ys.append(y)

        self.play(
            LaggedStart(
                *[FadeIn(m, shift=RIGHT * 0.2) for m in name_mobs],
                lag_ratio=0.12,
                run_time=1.0,
            )
        )
        self.wait(1.0)

        # ── 7d: reveal the "zeros" column ──
        self.next_sub_slide("all_zeros")

        zero_mobs = [
            Text(
                "0", font=DNA_FONT_NAME, font_size=28,
                color=HIGHLIGHT, weight=BOLD,
            ).move_to([TABLE_NUM_LEFT_X + 0.15, y, 0])
            for y in num_slot_ys
        ]
        self.play(
            LaggedStart(
                *[Write(z) for z in zero_mobs],
                lag_ratio=0.15,
                run_time=1.0,
            )
        )
        self.wait(1.5)


# ──────────────────────────────────────────────────────────────────────────
# Part 2 helpers (Our Approach deck — grid-based)
# ──────────────────────────────────────────────────────────────────────────


BOX_H = GLYPH_H + 2 * BOX_BUFF


def grid_row(chars, base_x, base_y, color=TEXT_COLOR):
    """Place each char as a Text mobject at x = base_x + i * CELL_W."""
    letters = []
    for i, c in enumerate(chars):
        t = Text(c, font=DNA_FONT_NAME, font_size=DNA_FONT, color=color)
        t.move_to([base_x + i * CELL_W, base_y, 0])
        letters.append(t)
    return letters


def centered_grid_row(chars, center_x, y, color=TEXT_COLOR):
    """Place letters on the grid, centering the whole row at center_x."""
    base_x = center_x - (len(chars) - 1) * CELL_W / 2
    return grid_row(chars, base_x, y, color=color)


def make_arrow(triplet, aa, color=ARROW_COLOR, stroke_width=10):
    return Arrow(
        triplet.get_bottom(),
        aa.get_top(),
        buff=0.12,
        color=color,
        stroke_width=stroke_width,
        tip_length=0.35,
        max_tip_length_to_length_ratio=0.35,
        max_stroke_width_to_length_ratio=20,
    )


def triplet_box_at(base_x, y, start_slot, color, stroke_width=BOX_STROKE):
    """Fixed-size rounded box spanning slots [start_slot, start_slot+1, start_slot+2].

    Box center x = base_x + (start_slot + 1) * CELL_W (middle cell's x).
    Box width/height are global constants → every box is geometrically identical.
    """
    rect = RoundedRectangle(
        width=BOX_W,
        height=BOX_H,
        corner_radius=BOX_CORNER_RADIUS,
        color=color,
        stroke_width=stroke_width,
        fill_color=color,
        fill_opacity=BOX_FILL_OPACITY,
    )
    rect.move_to([base_x + (start_slot + 1) * CELL_W, y, 0])
    return rect


def triplet_box(three_letters, color, stroke_width=BOX_STROKE):
    """Box around 3 letters already placed on the grid. Derives base_x + start_slot
    from the first letter's center and uses the fixed box geometry."""
    c0 = three_letters[0].get_center()
    rect = RoundedRectangle(
        width=BOX_W,
        height=BOX_H,
        corner_radius=BOX_CORNER_RADIUS,
        color=color,
        stroke_width=stroke_width,
        fill_color=color,
        fill_opacity=BOX_FILL_OPACITY,
    )
    # Center x = midpoint of three grid cells = first cell center + CELL_W
    rect.move_to([c0[0] + CELL_W, c0[1], 0])
    return rect


class OurApproachSlides(SlideScene):
    def construct(self):
        self.camera.background_color = BG_COLOR

        # === Slide 1: Title ===
        self.next_slide("title")

        # When stitched together with FrameShiftSlides, Part 1 leaves its
        # last frame (TPM packet + fuzzer table) on stage. Fade it out first
        # so the title doesn't appear on top of the old content. Harmless
        # when the deck runs standalone — the scene starts empty.
        if self.mobjects:
            self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)

        title = Text(
            "Our Approach",
            font_size=60,
            weight=BOLD,
            color=TEXT_COLOR,
        ).to_edge(UP, buff=0.8)

        self.play(Write(title), run_time=1.2)
        self.wait(0.4)

        # === Slide 2: Bullet points ===
        self.next_slide("bullets")

        bullet_items = [
            "automatically identifies size/offset fields",
            "uses existing coverage instrumentation",
            "language-agnostic",
            "no AI required",
            "no performance loss on unstructured formats",
        ]

        bullets = VGroup()
        for item in bullet_items:
            dot = Dot(color=BULLET_COLOR, radius=0.08)
            label = Text(item, font_size=32, color=TEXT_COLOR)
            row = VGroup(dot, label).arrange(RIGHT, buff=0.3)
            bullets.add(row)
        bullets.arrange(DOWN, aligned_edge=LEFT, buff=0.3)
        bullets.next_to(title, DOWN, buff=0.6).shift(LEFT * 2.0)

        self.play(
            LaggedStart(
                *[Write(row) for row in bullets],
                lag_ratio=0.25,
                run_time=1.8,
            )
        )
        self.wait(0.4)

        # === Slide 3: AFL++ line + image ===
        self.next_slide("aflpp")

        afl_text = Text(
            "Runs by default in AFL++ 4.40c!",
            font_size=36,
            color=TEXT_COLOR,
        )

        img = ImageMobject("aflpp.png")
        img.set_height(1.6)

        radius = min(img.width, img.height) / 2

        big = Square(side_length=max(img.width, img.height) * 1.2)
        big.move_to(img.get_center())
        hole = Circle(radius=radius).move_to(img.get_center())
        corner_mask = Difference(
            big, hole, color=BG_COLOR, fill_opacity=1, stroke_width=0
        )
        corner_mask.move_to(img.get_center())

        group = Group(img, corner_mask)
        row = Group(afl_text, group).arrange(RIGHT, buff=0.6)
        row.next_to(bullets, DOWN, buff=1.0).shift(RIGHT * 1.0)

        img.set_opacity(0)
        self.add(img, corner_mask)

        self.play(
            Write(afl_text),
            img.animate.set_opacity(1),
            run_time=1.2,
        )
        self.wait(1.2)

        # ======================================================================
        # Crick & Brenner (1961) experiment slides
        # ======================================================================

        # === Slide: Title ===
        self.next_slide("cb_title")

        title = Text(
            "Crick & Brenner Experiment (1961)",
            font_size=54,
            weight=BOLD,
            color=TEXT_COLOR,
        ).move_to(ORIGIN)

        # Fade the AFL++ image by animating its opacity while the corner
        # mask stays fully opaque — otherwise the mask fades too and the
        # white image corners flash through during the transition.
        non_afl = [m for m in self.mobjects if m is not img and m is not corner_mask]
        self.play(
            *[FadeOut(m) for m in non_afl],
            img.animate.set_opacity(0),
            run_time=0.5,
        )
        self.remove(corner_mask)
        self.play(Write(title), run_time=1.4)
        self.wait(0.8)

        # === Slide: walkthrough of the experiment ===
        self.next_slide("experiment")

        # ── 2a: shrink title, draw DNA + greyed AAs + green check ──
        self.next_sub_slide("functional")

        self.play(
            title.animate.scale(0.65).to_edge(UP, buff=0.45),
            run_time=0.7,
        )

        dna_str = "ATGCATTGCAAGCTAGATGCTTAC"
        aa_str = "MHCKLDAY"

        top_letters = centered_grid_row(dna_str, DNA_X_SHIFT, TOP_DNA_Y)
        top_dna_row = VGroup(*top_letters)
        top_base_x = top_letters[0].get_center()[0]

        top_triplets = [
            VGroup(*top_letters[i:i + 3])
            for i in range(0, len(dna_str), 3)
        ]

        top_aas = [
            Text(c, font=DNA_FONT_NAME, font_size=AA_FONT, color=GREY_COLOR).move_to(
                top_triplets[i].get_center() + DOWN * ROW_VERT
            )
            for i, c in enumerate(aa_str)
        ]
        top_boxes = [triplet_box(t, BOX_COLOR) for t in top_triplets]
        top_arrows = [make_arrow(t, a) for t, a in zip(top_triplets, top_aas)]

        dna_left_x = top_letters[0].get_center()[0]
        marker_x = dna_left_x + MARKER_DX
        label_x = dna_left_x + LABEL_DX
        marker_y = TOP_DNA_Y - ROW_VERT / 2

        self.play(Write(top_dna_row), run_time=1.3)
        triplet_seqs = [
            Succession(
                Create(top_boxes[i], run_time=0.4),
                GrowArrow(top_arrows[i], run_time=0.15),
                Write(top_aas[i], run_time=0.15),
            )
            for i in range(len(top_boxes))
        ]
        self.play(LaggedStart(*triplet_seqs, lag_ratio=0.3))
        self.wait(0.2)

        marker = Text(
            "✓", font_size=56, color=CHECK_COLOR, weight=BOLD
        ).move_to([marker_x, marker_y, 0])
        self.play(Write(marker), run_time=0.5)
        self.wait(0.4)

        # ── 2b: frameshift insertion → red X ──
        self.next_sub_slide("insertion")

        target_chars = list(dna_str)
        target_chars.insert(3, "G")

        # Post-insertion grid anchored at same base_x as the original row.
        target_ph = grid_row(target_chars, top_base_x, TOP_DNA_Y)
        target_positions = [p.get_center() for p in target_ph]
        target_new_triplets_ph = [
            VGroup(*target_ph[i:i + 3]) for i in range(0, 24, 3)
        ]

        inserted_G = Text(
            "G", font=DNA_FONT_NAME, font_size=DNA_FONT, color=HIGHLIGHT
        ).move_to(target_positions[3])

        def new_idx(orig_idx):
            return orig_idx if orig_idx < 3 else orig_idx + 1

        new_frame_boxes = [
            triplet_box(tg, HIGHLIGHT) for tg in target_new_triplets_ph
        ]

        shift_anims = [FadeIn(inserted_G, shift=DOWN * 0.3)]
        for orig_idx, letter in enumerate(top_letters):
            shift_anims.append(
                letter.animate.move_to(target_positions[new_idx(orig_idx)])
            )
        for i, box in enumerate(top_boxes):
            first_letter_idx = 3 * i
            if first_letter_idx >= 3:
                delta = (
                    target_positions[new_idx(first_letter_idx)]
                    - top_letters[first_letter_idx].get_center()
                )
                shift_anims.append(box.animate.shift(delta))

        self.play(*shift_anims, run_time=1.4)
        self.wait(0.2)

        new_aa_str = "MALQARCL"
        new_top_aa_colors = [TEXT_COLOR] + [HIGHLIGHT] * 7
        new_top_aas = [
            Text(c, font=DNA_FONT_NAME, font_size=AA_FONT, color=new_top_aa_colors[i]).move_to(
                top_aas[i].get_center()
            )
            for i, c in enumerate(new_aa_str)
        ]
        # Skip the red box for codon 0: the new frame's first triplet is
        # ATG — identical to the old frame — so the blue box already covers it.
        frame_seqs = []
        for i in range(len(new_frame_boxes)):
            if i == 0:
                continue
            steps = [
                Create(new_frame_boxes[i], run_time=0.4),
                top_arrows[i].animate(run_time=0.15).set_color(HIGHLIGHT),
                Transform(top_aas[i], new_top_aas[i], run_time=0.15),
            ]
            frame_seqs.append(Succession(*steps))
        self.play(LaggedStart(*frame_seqs, lag_ratio=0.3))
        self.wait(0.2)

        red_x = Text(
            "✗", font_size=56, color=HIGHLIGHT, weight=BOLD
        ).move_to(marker.get_center())
        self.play(Transform(marker, red_x), run_time=0.5)
        self.wait(0.4)

        # ── 2c: three stacked examples — +1, +1/-1, +1/+2 ──
        self.next_sub_slide("restore")

        def mutated_idx(orig_idx):
            return orig_idx if orig_idx < 3 else orig_idx + 1

        mut_str = "ATGGCATTGCAAGCTAGATGCTTAC"
        label_font_size = 34
        restored_label_font = 22

        def build_mutated_example(y_pos):
            # Place the 25-letter mutated row on the same grid (same base_x)
            # as the top row, one cell to the left of where the top's letter 0
            # sits so the inserted letter lines up properly? No — just anchor
            # letter 0 of this row to the top row's letter 0 for column
            # alignment across stacked rows.
            letters = grid_row(mut_str, top_base_x, y_pos)
            letters[3].set_color(HIGHLIGHT)
            dna_row = VGroup(*letters)

            red_triplets = [VGroup(*letters[i:i + 3]) for i in range(0, 24, 3)]
            blue_triplets = [
                VGroup(*[letters[mutated_idx(3 * i + j)] for j in range(3)])
                for i in range(8)
            ]

            red_boxes = [triplet_box(t, HIGHLIGHT) for t in red_triplets]
            blue_boxes = [triplet_box(t, BOX_COLOR) for t in blue_triplets]

            aa_colors = [TEXT_COLOR] + [HIGHLIGHT] * 7
            aas = [
                Text(c, font=DNA_FONT_NAME, font_size=AA_FONT, color=aa_colors[i]).move_to(
                    red_triplets[i].get_center() + DOWN * ROW_VERT
                )
                for i, c in enumerate(new_aa_str)
            ]
            arrows = [
                make_arrow(t, a, color=ARROW_COLOR if i == 0 else HIGHLIGHT)
                for i, (t, a) in enumerate(zip(red_triplets, aas))
            ]
            mk = Text("✗", font_size=56, color=HIGHLIGHT, weight=BOLD).move_to(
                [marker_x, y_pos - ROW_VERT / 2, 0]
            )
            return {
                "letters": letters, "dna_row": dna_row,
                "red_triplets": red_triplets, "blue_triplets": blue_triplets,
                "red_boxes": red_boxes, "blue_boxes": blue_boxes,
                "aas": aas, "arrows": arrows, "marker": mk,
            }

        ex1_label = Text(
            "+1", font_size=label_font_size, weight=BOLD, color=TEXT_COLOR
        ).move_to([label_x, marker_y, 0])

        self.play(Write(ex1_label), run_time=0.6)
        self.wait(0.2)

        self.next_sub_slide("middle_clone")

        ex2 = build_mutated_example(EX2_DNA_Y)
        ex2_label = Text(
            "+1/-1", font_size=label_font_size, weight=BOLD, color=TEXT_COLOR
        ).move_to([label_x, EX2_DNA_Y - ROW_VERT / 2, 0])

        # Skip red box 0 — red codon 0 (ATG) is identical to blue codon 0, so
        # the blue box already covers it.
        self.play(
            FadeIn(ex2["dna_row"]),
            *[FadeIn(b) for b in ex2["blue_boxes"]],
            *[FadeIn(b) for i, b in enumerate(ex2["red_boxes"]) if i != 0],
            *[GrowArrow(a) for a in ex2["arrows"]],
            *[FadeIn(a) for a in ex2["aas"]],
            FadeIn(ex2["marker"]),
            Write(ex2_label),
            run_time=1.0,
        )
        self.wait(0.3)

        self.next_sub_slide("middle_delete")

        del_idx = 9
        del_chars = list(mut_str)
        del_chars.pop(del_idx)
        # Post-delete grid on the SAME base_x as ex2's row → slot i of del_ph
        # sits at the exact same x as slot i of ex2["letters"].
        del_ph = grid_row(del_chars, top_base_x, EX2_DNA_Y)
        del_positions = [p.get_center() for p in del_ph]

        deleted_letter = ex2["letters"][del_idx]
        shift_anims = [FadeOut(deleted_letter, shift=UP * 0.3)]
        for slot, letter in enumerate(ex2["letters"]):
            if slot == del_idx:
                continue
            new_slot = slot if slot < del_idx else slot - 1
            shift_anims.append(letter.animate.move_to(del_positions[new_slot]))

        # Blue boxes 3..7 surround letters that all shift left by exactly one
        # cell (deletion pushes everything right of del_idx one slot left).
        # Shift each box by the delta of one of its contained letters — this
        # preserves the box's exact size, guaranteeing it still tiles with its
        # neighbors and overlays the red frame boxes cleanly.
        box_shift_delta = (
            del_positions[mutated_idx(9) - 1]
            - ex2["letters"][mutated_idx(9)].get_center()
        )
        shift_anims.append(FadeOut(ex2["blue_boxes"][2]))
        for i in range(3, 8):
            shift_anims.append(ex2["blue_boxes"][i].animate.shift(box_shift_delta))
            # Blue box i lands exactly on red box i → frame re-aligned here,
            # so the red box is now redundant.
            shift_anims.append(FadeOut(ex2["red_boxes"][i]))

        self.play(*shift_anims, run_time=1.3)
        self.wait(0.3)

        ex2_final_chars = ["M", "A", "L", "K", "L", "D", "A", "Y"]
        ex2_restore_idx = [3, 4, 5, 6, 7]
        restore_seqs = []
        for i in ex2_restore_idx:
            new_aa = Text(
                ex2_final_chars[i], font=DNA_FONT_NAME, font_size=AA_FONT, color=TEXT_COLOR
            ).move_to(ex2["aas"][i].get_center())
            restore_seqs.append(
                AnimationGroup(
                    Transform(ex2["aas"][i], new_aa),
                    ex2["arrows"][i].animate.set_color(ARROW_COLOR),
                )
            )
        self.play(LaggedStart(*restore_seqs, lag_ratio=0.12, run_time=1.0))
        self.wait(0.2)

        ex2_check = Text(
            "✓", font_size=56, color=CHECK_COLOR, weight=BOLD
        ).move_to(ex2["marker"].get_center())

        self.play(
            Transform(ex2["marker"], ex2_check),
            run_time=0.8,
        )
        self.wait(0.4)

        self.next_sub_slide("bottom_clone")

        ex3 = build_mutated_example(EX3_DNA_Y)
        ex3_label = Text(
            "+1/+2", font_size=label_font_size, weight=BOLD, color=TEXT_COLOR
        ).move_to([label_x, EX3_DNA_Y - ROW_VERT / 2, 0])

        # Skip red box 0 — identical to blue codon 0.
        self.play(
            FadeIn(ex3["dna_row"]),
            *[FadeIn(b) for b in ex3["blue_boxes"]],
            *[FadeIn(b) for i, b in enumerate(ex3["red_boxes"]) if i != 0],
            *[GrowArrow(a) for a in ex3["arrows"]],
            *[FadeIn(a) for a in ex3["aas"]],
            FadeIn(ex3["marker"]),
            Write(ex3_label),
            run_time=1.0,
        )
        self.wait(0.3)

        self.next_sub_slide("bottom_insert")

        ins2_chars = list(mut_str[:9]) + ["C", "C"] + list(mut_str[9:])
        # Post-+2-insert grid on the SAME base_x as ex3's row.
        ins2_ph = grid_row(ins2_chars, top_base_x, EX3_DNA_Y)
        ins2_positions = [p.get_center() for p in ins2_ph]
        ins2_triplets_ph = [
            VGroup(*ins2_ph[i:i + 3]) for i in range(0, 27, 3)
        ]

        inserted_C1 = Text(
            "C", font=DNA_FONT_NAME, font_size=DNA_FONT, color=HIGHLIGHT
        ).move_to(ins2_positions[9])
        inserted_C2 = Text(
            "C", font=DNA_FONT_NAME, font_size=DNA_FONT, color=HIGHLIGHT
        ).move_to(ins2_positions[10])

        shift_anims = [
            FadeIn(inserted_C1, shift=DOWN * 0.3),
            FadeIn(inserted_C2, shift=DOWN * 0.3),
        ]
        for slot, letter in enumerate(ex3["letters"]):
            new_slot = slot if slot < 9 else slot + 2
            shift_anims.append(letter.animate.move_to(ins2_positions[new_slot]))

        # Blue boxes 3..7 surround letters that all shift right by exactly
        # two cells (+2 insertion pushes everything right of slot 9 two slots
        # right). Shift by the delta of one contained letter — preserves size.
        box_shift_delta = (
            ins2_positions[mutated_idx(9) + 2]
            - ex3["letters"][mutated_idx(9)].get_center()
        )
        shift_anims.append(FadeOut(ex3["blue_boxes"][2]))
        for i in range(3, 8):
            shift_anims.append(ex3["blue_boxes"][i].animate.shift(box_shift_delta))
            # +2 insertion: blue box i lands on red box i+1's center, so that
            # red box is redundant. (Red 3 has no blue overlay → stays red;
            # blue 7 lands where the never-created "red 8" would be — so the
            # new 9th red codon box is likewise omitted in Phase B below.)
            if i + 1 < len(ex3["red_boxes"]):
                shift_anims.append(FadeOut(ex3["red_boxes"][i + 1]))

        self.play(*shift_anims, run_time=1.3)
        self.wait(0.3)

        # Blue box 7 (already shifted) covers ins2_triplets_ph[8], so no new
        # red box is created for the 9th codon — blue alone marks it.
        new_aa_8 = Text(
            "Y", font=DNA_FONT_NAME, font_size=AA_FONT, color=TEXT_COLOR
        ).move_to(ins2_triplets_ph[8].get_center() + DOWN * ROW_VERT)
        new_arrow_8 = make_arrow(ins2_triplets_ph[8], new_aa_8, color=ARROW_COLOR)

        new_aa_3 = Text(
            "P", font=DNA_FONT_NAME, font_size=AA_FONT, color=HIGHLIGHT
        ).move_to(ex3["aas"][3].get_center())

        ex3_restore_pairs = [(4, "K"), (5, "L"), (6, "D"), (7, "A")]
        phase_b_anims = [
            GrowArrow(new_arrow_8),
            FadeIn(new_aa_8),
            Transform(ex3["aas"][3], new_aa_3),
        ]
        for idx, ch in ex3_restore_pairs:
            new_aa = Text(
                ch, font=DNA_FONT_NAME, font_size=AA_FONT, color=TEXT_COLOR
            ).move_to(ex3["aas"][idx].get_center())
            phase_b_anims.append(Transform(ex3["aas"][idx], new_aa))
            phase_b_anims.append(ex3["arrows"][idx].animate.set_color(ARROW_COLOR))

        self.play(*phase_b_anims, run_time=1.1)
        self.wait(0.3)

        ex3_check = Text(
            "✓", font_size=56, color=CHECK_COLOR, weight=BOLD
        ).move_to(ex3["marker"].get_center())

        self.play(
            Transform(ex3["marker"], ex3_check),
            run_time=0.8,
        )
        self.wait(1.5)

        # ==================================================================
        # Slide: Recovering structure (PNG analog of Crick & Brenner)
        # Mirrors frameshift_slides.py styling exactly.
        # ==================================================================
        self.next_slide("recovering_structure")
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.5)

        rs_title = Text(
            "Recovering structure in PNG",
            font_size=54, weight=BOLD, color=TEXT_COLOR,
        ).to_edge(UP, buff=0.35)
        self.play(Write(rs_title), run_time=0.8)

        def build_png_view(hex_y, chunk_names_y):
            """Build one PNG hex-dump view in its final missense-state layout."""
            byte_mobjs = [
                Text(
                    b, font=DNA_FONT_NAME, font_size=HEX_FONT,
                    color=byte_color_for_offset(i),
                )
                for i, b in enumerate(hex_bytes_list)
            ]
            hex_row = VGroup(*byte_mobjs).arrange(RIGHT, buff=HEX_BUFF)

            # Field labels above each byte range — styling copied verbatim.
            field_labels = []
            for start, end, text, color in field_labels_defs:
                first = byte_mobjs[start]
                last = byte_mobjs[end]
                label = Text(
                    text, font=DNA_FONT_NAME, font_size=18,
                    color=color, weight=BOLD,
                )
                center_x = (first.get_center()[0] + last.get_center()[0]) / 2
                label_y = first.get_top()[1] + 0.26
                label.move_to([center_x, label_y, 0])
                field_labels.append(label)

            # Blue chunk boxes — identical style to slides.py make_boxes.
            blue_boxes = {}
            for name, s, e in chunk_boxes_defs:
                rect = SurroundingRectangle(
                    VGroup(*byte_mobjs[s:e + 1]),
                    buff=0.06, color=BOX_COLOR, stroke_width=2.5,
                    fill_color=BOX_COLOR, fill_opacity=BOX_FILL_OPACITY,
                    corner_radius=BOX_CORNER_RADIUS,
                )
                blue_boxes[name] = rect

            hex_container = VGroup(hex_row, *field_labels, *blue_boxes.values())
            # Scroll so that gAMA's size field sits left-of-center, giving
            # downstream chunks more horizontal room to be visible.
            GAMA_FOCUS_X = -2.3
            gama_size_center = (
                byte_mobjs[33].get_center()[0]
                + byte_mobjs[36].get_center()[0]
            ) / 2
            hex_container.shift([
                GAMA_FOCUS_X - gama_size_center,
                hex_y - byte_mobjs[0].get_center()[1],
                0,
            ])

            # Chunk-name list — same font/weight/buff as slides.py. Align by
            # top edge so "gAMA"/"tEXt" (with descenders) don't drift up
            # relative to all-caps names like "IHDR".
            name_mobs = []
            for i, s in enumerate(png_chunk_names):
                lbl = Text(
                    s, font=DNA_FONT_NAME, font_size=22,
                    color=TEXT_COLOR, weight=BOLD,
                )
                if i == 0:
                    lbl.move_to([0, chunk_names_y, 0])
                else:
                    lbl.next_to(name_mobs[-1], RIGHT, buff=0.28, aligned_edge=UP)
                name_mobs.append(lbl)
            chunk_names_row = VGroup(*name_mobs)
            chunk_names_row.move_to([0, chunk_names_y, 0])

            return {
                "byte_mobjs": byte_mobjs,
                "hex_row": hex_row,
                "field_labels": field_labels,
                "blue_boxes": blue_boxes,
                "hex_container": hex_container,
                "chunk_names": name_mobs,
                "chunk_names_row": chunk_names_row,
            }

        def mutation_animations(view, inserted_color=HIGHLIGHT):
            """Return (inserted_byte, anims) — a single combined mutation step
            mirroring slides.py's png_frameshift + subsequent sub-slides,
            collapsed into one play call."""
            byte_mobjs = view["byte_mobjs"]
            byte_pitch = (
                byte_mobjs[1].get_center()[0] - byte_mobjs[0].get_center()[0]
            )
            SHIFT_VEC = RIGHT * byte_pitch

            inserted = Text(
                "47", font=DNA_FONT_NAME, font_size=HEX_FONT,
                color=inserted_color,
            ).move_to(byte_mobjs[INSERT_IDX].get_center())

            # Bytes and field labels right of the insertion travel right.
            field_labels_to_shift = [
                view["field_labels"][i]
                for i, (start, _e, _t, _c) in enumerate(field_labels_defs)
                if start > INSERT_IDX
            ]
            # Blue boxes for chunks fully after gAMA shift by one byte;
            # gAMA's own box stretches by one byte.
            post_gama_box_names = ["sRGB", "cHRM", "bKGD", "pHYs", "IDAT"]
            boxes_to_shift = [view["blue_boxes"][n] for n in post_gama_box_names]

            # Stretched gAMA target.
            for b in byte_mobjs[INSERT_IDX:49]:
                b.shift(SHIFT_VEC)
            gama_stretched = SurroundingRectangle(
                VGroup(
                    *byte_mobjs[33:INSERT_IDX],
                    inserted,
                    *byte_mobjs[INSERT_IDX:49],
                ),
                buff=0.06, color=BOX_COLOR, stroke_width=2.5,
                fill_color=BOX_COLOR, fill_opacity=BOX_FILL_OPACITY,
                corner_radius=BOX_CORNER_RADIUS,
            )
            for b in byte_mobjs[INSERT_IDX:49]:
                b.shift(-SHIFT_VEC)

            # Red "parser's reading" frame over the mis-interpreted gAMA
            # (still 16 bytes from the parser's perspective).
            for b in byte_mobjs[INSERT_IDX:48]:
                b.shift(SHIFT_VEC)
            gama_red_frame = SurroundingRectangle(
                VGroup(
                    *byte_mobjs[33:INSERT_IDX],
                    inserted,
                    *byte_mobjs[INSERT_IDX:48],
                ),
                buff=0.06, color=HIGHLIGHT, stroke_width=2.5,
                fill_color=HIGHLIGHT, fill_opacity=BOX_FILL_OPACITY,
                corner_radius=BOX_CORNER_RADIUS,
            )
            for b in byte_mobjs[INSERT_IDX:48]:
                b.shift(-SHIFT_VEC)

            # Everything after gAMA in the chunk-name list becomes invalid.
            invalidated_names = view["chunk_names"][2:]

            # Parser's next read derails: \x01sRG masquerades as a chunk type,
            # and the jump after that lands out of bounds → (error). Both slot
            # in next to gAMA on the chunk-name row.
            garbage_label = Text(
                "\\x01sRG", font=DNA_FONT_NAME, font_size=22,
                color=HIGHLIGHT, weight=BOLD,
            ).next_to(view["chunk_names"][1], RIGHT, buff=0.28, aligned_edge=UP)
            error_label = Text(
                "(error)", font=DNA_FONT_NAME, font_size=22,
                color=HIGHLIGHT, weight=BOLD,
            ).next_to(garbage_label, RIGHT, buff=0.28, aligned_edge=UP)

            anims = [
                FadeIn(inserted, shift=DOWN * 0.3),
                *[m.animate.shift(SHIFT_VEC) for m in byte_mobjs[INSERT_IDX:]],
                *[m.animate.shift(SHIFT_VEC) for m in field_labels_to_shift],
                *[b.animate.shift(SHIFT_VEC) for b in boxes_to_shift],
                Transform(view["blue_boxes"]["gAMA"], gama_stretched),
                Create(gama_red_frame),
                *[FadeOut(n) for n in invalidated_names],
                Write(garbage_label),
                Write(error_label),
            ]
            return inserted, gama_red_frame, garbage_label, error_label, anims

        # Layout: two stacked views.
        TOP_HEX_Y = 1.9
        TOP_NAMES_Y = 0.85
        BOT_HEX_Y = -1.05
        BOT_NAMES_Y = -2.1

        # ── Top view: original PNG ──
        self.next_sub_slide("top_original")
        top = build_png_view(TOP_HEX_Y, TOP_NAMES_Y)
        self.play(
            FadeIn(top["hex_row"]),
            *[FadeIn(l) for l in top["field_labels"]],
            *[FadeIn(b) for b in top["blue_boxes"].values()],
            FadeIn(top["chunk_names_row"]),
            run_time=1.0,
        )
        self.wait(0.3)

        # ── Top: apply +1 insertion in one combined step ──
        self.next_sub_slide("top_mutate")
        top_inserted, top_red_frame, top_garbage, top_error, top_mut_anims = mutation_animations(top)
        self.play(*top_mut_anims, run_time=1.6)
        self.wait(0.5)

        # ── Bottom: copy, starting already in the broken state ──
        self.next_sub_slide("bottom_clone")
        bot = build_png_view(BOT_HEX_Y, BOT_NAMES_Y)

        # Pre-apply the mutation to `bot` instantly (no play).
        bot_byte_pitch = (
            bot["byte_mobjs"][1].get_center()[0]
            - bot["byte_mobjs"][0].get_center()[0]
        )
        BOT_SHIFT = RIGHT * bot_byte_pitch
        for m in bot["byte_mobjs"][INSERT_IDX:]:
            m.shift(BOT_SHIFT)
        for i, (start, _e, _t, _c) in enumerate(field_labels_defs):
            if start > INSERT_IDX:
                bot["field_labels"][i].shift(BOT_SHIFT)
        for n in ["sRGB", "cHRM", "bKGD", "pHYs", "IDAT"]:
            bot["blue_boxes"][n].shift(BOT_SHIFT)

        bot_inserted = Text(
            "47", font=DNA_FONT_NAME, font_size=HEX_FONT, color=HIGHLIGHT,
        ).move_to([
            bot["byte_mobjs"][INSERT_IDX - 1].get_center()[0] + bot_byte_pitch,
            BOT_HEX_Y, 0,
        ])
        bot_gama_stretched = SurroundingRectangle(
            VGroup(
                *bot["byte_mobjs"][33:INSERT_IDX],
                bot_inserted,
                *bot["byte_mobjs"][INSERT_IDX:49],
            ),
            buff=0.06, color=BOX_COLOR, stroke_width=2.5,
            fill_color=BOX_COLOR, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )
        bot["blue_boxes"]["gAMA"] = bot_gama_stretched
        bot_red_frame = SurroundingRectangle(
            VGroup(
                *bot["byte_mobjs"][33:INSERT_IDX],
                bot_inserted,
                *bot["byte_mobjs"][INSERT_IDX:48],
            ),
            buff=0.06, color=HIGHLIGHT, stroke_width=2.5,
            fill_color=HIGHLIGHT, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )

        # Bottom starts already in the mutated state, so it also carries the
        # \x01sRG + (error) chunk-name labels next to gAMA.
        bot_garbage = Text(
            "\\x01sRG", font=DNA_FONT_NAME, font_size=22,
            color=HIGHLIGHT, weight=BOLD,
        ).next_to(bot["chunk_names"][1], RIGHT, buff=0.28, aligned_edge=UP)
        bot_error = Text(
            "(error)", font=DNA_FONT_NAME, font_size=22,
            color=HIGHLIGHT, weight=BOLD,
        ).next_to(bot_garbage, RIGHT, buff=0.28, aligned_edge=UP)

        bot_visible = (
            [bot["hex_row"], bot_inserted, bot_gama_stretched, bot_red_frame]
            + [bot["blue_boxes"]["IHDR"]]
            + [bot["blue_boxes"][n] for n in ["sRGB", "cHRM", "bKGD", "pHYs", "IDAT"]]
            + bot["field_labels"]
            + bot["chunk_names"][:2]
            + [bot_garbage, bot_error]
        )
        self.play(*[FadeIn(m) for m in bot_visible], run_time=1.0)
        self.wait(0.3)

        # ── Bottom fix: gAMA size field 4 → 5 ──
        self.next_sub_slide("bottom_fix")

        # Size field is bytes 33..36 (big-endian). The low byte at 36 holds
        # "04"; bumping it to "05" realigns everything.
        size_byte = bot["byte_mobjs"][36]
        size_byte_new = Text(
            "05", font=DNA_FONT_NAME, font_size=HEX_FONT, color=CHECK_COLOR,
        ).move_to(size_byte.get_center())

        # Update the "size=4" field label → "size=5".
        size_label_idx = next(
            i for i, (s, e, t, _c) in enumerate(field_labels_defs)
            if t == "size=4"
        )
        size_label_old = bot["field_labels"][size_label_idx]
        size_label_new = Text(
            "size=5", font=DNA_FONT_NAME, font_size=18,
            color=CHECK_COLOR, weight=BOLD,
        ).move_to(size_label_old.get_center())

        # Red frame expands from 16 → 17 bytes (to match gAMA's physical
        # data now that size=5 is honored), then fades away.
        red_frame_expanded = SurroundingRectangle(
            VGroup(
                *bot["byte_mobjs"][33:INSERT_IDX],
                bot_inserted,
                *bot["byte_mobjs"][INSERT_IDX:49],
            ),
            buff=0.06, color=HIGHLIGHT, stroke_width=2.5,
            fill_color=HIGHLIGHT, fill_opacity=BOX_FILL_OPACITY,
            corner_radius=BOX_CORNER_RADIUS,
        )
        red_frame_anim = Succession(
            Transform(bot_red_frame, red_frame_expanded, run_time=0.6),
            FadeOut(bot_red_frame, run_time=0.5),
        )

        # sRGB..IEND chunk names Write in; the garbage + error labels go away.
        restored_names = bot["chunk_names"][2:]

        self.play(
            Transform(size_byte, size_byte_new),
            Transform(size_label_old, size_label_new),
            red_frame_anim,
            FadeOut(bot_garbage),
            FadeOut(bot_error),
            LaggedStart(
                *[Write(n) for n in restored_names],
                lag_ratio=0.12,
                run_time=1.4,
            ),
            run_time=1.6,
        )
        self.wait(0.6)

        # ── Arced arrow showing the dependency: the mutated size field
        #    "reaches over" to cover the inserted byte. ──
        self.next_sub_slide("size_to_insert_arc")

        # Source: the updated size byte (transformed into size_byte_new
        # during the fix, but the reference mobject we can anchor on is
        # `size_byte`, which was Transformed in place).
        arc_src = size_byte.get_top() + UP * 0.08
        arc_dst = bot_inserted.get_top() + UP * 0.08

        size_to_insert_arc = CurvedArrow(
            arc_src, arc_dst,
            angle=-PI / 2.2,
            color=CHECK_COLOR,
            stroke_width=4,
            tip_length=0.22,
        )

        self.play(Create(size_to_insert_arc), run_time=0.9)
        self.wait(0.6)

        # ── Coverage annotations under each chunk list ──
        self.next_sub_slide("coverage")

        top_coverage_label = Text(
            "low code coverage",
            font=DNA_FONT_NAME, font_size=26, weight=BOLD, color=HIGHLIGHT,
        ).next_to(top["chunk_names_row"], DOWN, buff=0.35)
        bot_coverage_label = Text(
            "high code coverage",
            font=DNA_FONT_NAME, font_size=26, weight=BOLD, color=CHECK_COLOR,
        ).next_to(bot["chunk_names_row"], DOWN, buff=0.35)

        self.play(
            Write(top_coverage_label),
            Write(bot_coverage_label),
            run_time=1.0,
        )
        self.wait(1.5)

        # ==================================================================
        # Slide: FrameShift Algorithm + Fuzzer Integration
        # ==================================================================
        self.next_slide("algorithm")

        SECTION_FONT = 38
        BODY_FONT = 26
        INDENT = 0.55
        LINE_BUFF = 0.22

        def body_line(text, indent_level):
            """Bullet row: blue dot + text, indented by level * INDENT."""
            dot = Dot(color=BULLET_COLOR, radius=0.06)
            label = Text(text, font_size=BODY_FONT, color=TEXT_COLOR)
            row = VGroup(dot, label).arrange(RIGHT, buff=0.25, aligned_edge=UP)
            row.shift(RIGHT * indent_level * INDENT)
            return row

        def plain_line(text, indent_level):
            """Bare text (no bullet), used for the 'Given an input' line."""
            label = Text(text, font_size=BODY_FONT, color=TEXT_COLOR)
            label.shift(RIGHT * indent_level * INDENT)
            return label

        # ── Section 1: FrameShift Algorithm ──
        sec1_title = Text(
            "FrameShift Algorithm",
            font_size=SECTION_FONT, weight=BOLD, color=TEXT_COLOR,
        )
        sec1_given = plain_line("Given an input", 0)
        sec1_b1 = body_line("For each prospective size field (heuristic)", 1)
        sec1_b2 = body_line("Increment by +x, check if coverage drops", 2)
        sec1_b3 = body_line("Find repair point where we can insert x bytes and coverage increases", 2)
        sec1_b4 = body_line("Learn a size → target field", 2)

        sec1_lines = [sec1_given, sec1_b1, sec1_b2, sec1_b3, sec1_b4]
        sec1_block = VGroup(sec1_title, *sec1_lines).arrange(
            DOWN, aligned_edge=LEFT, buff=LINE_BUFF,
        )
        # Preserve per-line indentation after arrange (arrange resets x).
        sec1_title.align_to(sec1_block, LEFT)
        sec1_given.align_to(sec1_block, LEFT)
        for b, lvl in ((sec1_b1, 1), (sec1_b2, 2), (sec1_b3, 2), (sec1_b4, 2)):
            b.align_to(sec1_block, LEFT).shift(RIGHT * lvl * INDENT)

        # ── Section 2: Fuzzer Integration ──
        sec2_title = Text(
            "Fuzzer Integration",
            font_size=SECTION_FONT, weight=BOLD, color=TEXT_COLOR,
        )
        sec2_b1 = body_line(
            "Run FrameShift on every new corpus entry (10% max-overhead in AFL++)", 1,
        )
        sec2_b2 = body_line(
            "Hook insert/remove mutators to reserialize size fields as needed", 1,
        )
        sec2_b2_sub = body_line(
            "(compatible with compare-logging, dict/token mutations, etc…)", 2,
        )
        sec2_lines = [sec2_b1, sec2_b2, sec2_b2_sub]
        sec2_block = VGroup(sec2_title, *sec2_lines).arrange(
            DOWN, aligned_edge=LEFT, buff=LINE_BUFF,
        )
        sec2_title.align_to(sec2_block, LEFT)
        for b, lvl in ((sec2_b1, 1), (sec2_b2, 1), (sec2_b2_sub, 2)):
            b.align_to(sec2_block, LEFT).shift(RIGHT * lvl * INDENT)

        full_block = VGroup(sec1_block, sec2_block).arrange(
            DOWN, aligned_edge=LEFT, buff=0.7,
        )
        full_block.to_edge(LEFT, buff=1.0).to_edge(UP, buff=0.6)

        # ── Animate section 1 as one sub-slide. Fade out the prior content
        #    quickly, then write the section — both run in this one play
        #    boundary so no empty transition slide appears. ──
        prev_mobs = [m for m in self.mobjects]
        self.play(*[FadeOut(m) for m in prev_mobs], run_time=0.4)
        self.play(
            LaggedStart(
                *[Write(m) for m in [sec1_title, *sec1_lines]],
                lag_ratio=0.25,
            ),
            run_time=1.6,
        )
        self.wait(0.4)

        # ── Animate section 2 as one sub-slide ──
        self.next_sub_slide("fuzzer_section")
        self.play(
            LaggedStart(
                *[Write(m) for m in [sec2_title, *sec2_lines]],
                lag_ratio=0.25,
                run_time=1.4,
            )
        )
        self.wait(1.2)

        # ==================================================================
        # Slide: Highlights (closing)
        # ==================================================================
        self.next_slide("highlights")

        # Fade prior content, write title — in one play, no empty transition.
        prev_mobs = [m for m in self.mobjects]
        self.play(*[FadeOut(m) for m in prev_mobs], run_time=0.4)

        hi_title = Text(
            "Highlights",
            font_size=54, weight=BOLD, color=TEXT_COLOR,
        ).to_edge(UP, buff=0.5)
        self.play(Write(hi_title), run_time=0.7)

        # ── Left column: bullet list ──
        HI_BULLET_FONT = 22
        HI_NESTED_FONT = 20
        HI_BULLET_BUFF = 0.26
        HI_INDENT = 0.55

        def hi_bullet(text, level=0, font_size=HI_BULLET_FONT, color=TEXT_COLOR):
            dot = Dot(color=BULLET_COLOR, radius=0.06)
            label = Text(text, font_size=font_size, color=color)
            row = VGroup(dot, label).arrange(RIGHT, buff=0.22, aligned_edge=UP)
            return row, level

        left_entries = [
            hi_bullet("~10-80% more code coverage on binary format targets"),
            hi_bullet("faster to find bugs (MAGMA)"),
            hi_bullet("handles size and offset fields"),
            hi_bullet(
                "works out-of-the-box for Python (Atheris)\nand Rust (cargo-fuzz)"
            ),
            hi_bullet("case studies"),
            hi_bullet(
                "handles all sorts of formats, including nested fields",
                level=1, font_size=HI_NESTED_FONT,
            ),
            hi_bullet("able to automatically resize an ELF!",
                      level=1, font_size=HI_NESTED_FONT),
            hi_bullet("handles ad-hoc formats from LLM harnesses",
                      level=1, font_size=HI_NESTED_FONT),
            hi_bullet(
                "learns program-specific relations\n"
                "(i.e. fields that matter for specific programs)",
                level=1, font_size=HI_NESTED_FONT,
            ),
        ]

        left_group = VGroup(*[row for row, _ in left_entries]).arrange(
            DOWN, aligned_edge=LEFT, buff=HI_BULLET_BUFF,
        )
        for (row, lvl) in left_entries:
            row.align_to(left_group, LEFT).shift(RIGHT * lvl * HI_INDENT)
        # Place left column flush to the LEFT edge, with its top just below
        # the title. (Avoid `.next_to(title, aligned_edge=LEFT)` — that would
        # anchor the column to the title's x position instead of the frame.)
        content_top_y = hi_title.get_bottom()[1] - 0.4
        left_group.to_edge(LEFT, buff=0.7)
        left_group.shift(UP * (content_top_y - left_group.get_top()[1]))

        self.play(
            LaggedStart(
                *[Write(row) for row, _ in left_entries],
                lag_ratio=0.08,
                run_time=2.6,
            )
        )
        self.wait(0.3)

        # ── Right column: links (sub-slide) ──
        self.next_sub_slide("links")

        LINK_URL_FONT = 26
        LINK_DESC_FONT = 18
        LINK_COLOR = BULLET_COLOR
        DESC_COLOR = "#9A9A9A"

        link_defs = [
            ("c.mov/frameshift", "blog post with more info"),
            ("AFL++ 4.40c", None),
            ("hgarrereyn/LibAFL-FrameShift", "libafl implementation"),
        ]

        link_groups = []
        for url, desc in link_defs:
            url_mob = Text(
                url, font=DNA_FONT_NAME, font_size=LINK_URL_FONT,
                weight=BOLD, color=LINK_COLOR,
            )
            if desc:
                desc_mob = Text(
                    desc, font_size=LINK_DESC_FONT, color=DESC_COLOR,
                )
                grp = VGroup(url_mob, desc_mob).arrange(
                    DOWN, aligned_edge=LEFT, buff=0.1,
                )
            else:
                grp = VGroup(url_mob)
            link_groups.append(grp)

        right_column = VGroup(*link_groups).arrange(
            DOWN, aligned_edge=LEFT, buff=0.7,
        )
        right_column.to_edge(RIGHT, buff=0.7)
        right_column.shift(UP * (content_top_y - right_column.get_top()[1]))

        self.play(
            LaggedStart(
                *[FadeIn(g, shift=UP * 0.2) for g in link_groups],
                lag_ratio=0.25,
                run_time=1.6,
            )
        )
        self.wait(2.0)

        # ==================================================================
        # Slide: fade to black
        # ==================================================================
        self.next_slide("fade_to_black")
        self.play(
            *[FadeOut(m) for m in self.mobjects],
            run_time=1.2,
        )
        self.wait(1.0)


# ──────────────────────────────────────────────────────────────────────────
# Combined presentation — runs Part 1 then Part 2 in one scene
# ──────────────────────────────────────────────────────────────────────────


class FrameShiftPresentation(SlideScene):
    """Full FrameShift talk: Part 1 (microbiology + PNG/TPM) then Part 2
    (our approach + Crick & Brenner + algorithm + highlights).

    The two constructs run back-to-back on the same scene, so slide numbering
    continues across the boundary.
    """

    def construct(self):
        FrameShiftSlides.construct(self)
        OurApproachSlides.construct(self)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render the FrameShift presentation.")
    parser.add_argument(
        "--force", "-f", action="store_true",
        help="Regenerate every GIF even if content hash matches.",
    )
    args = parser.parse_args()
    render_slides(FrameShiftPresentation, bg_color=BG_COLOR, force=args.force)
