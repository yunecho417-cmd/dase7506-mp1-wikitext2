#!/usr/bin/env python3
"""Build the English edition of the integrated experiment decision flowchart.

The Chinese original was produced by ``build_experiment_decision_flow.mjs``
through a private PowerPoint runtime.  This script re-emits the same box-and-
arrow layout with English copy, wrapping every block to its own box width so
Latin text does not overflow the way the CJK original would not.

Output: ``output/figures/journal_en/decision_flow.svg`` and ``.png``.

Usage:
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python build_english_decision_flow.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT / "output/figures/journal_en"

W, H = 1100, 1140
FONT = "Helvetica Neue,Helvetica,Arial,sans-serif"

BLUE = "#527F99"
GREEN = "#598E78"
INK = "#263943"
BODY = "#253843"
SOFT = "#4D5E67"
NOTE = "#576772"
NOTE_GREEN = "#355F50"
LINK = "#6C7E88"

NODE_W, NODE_H = 480, 236
LEFT_X, RIGHT_X = 35, 585
PAD = 18
INNER_W = NODE_W - 2 * PAD


def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def char_width(size: float) -> float:
    """Mean advance width for Helvetica-class text, in user units."""
    return 0.52 * size


def wrap_lines(text: str, width: float, size: float) -> list[str]:
    """Greedy wrap that never breaks a word, honouring explicit newlines."""
    max_chars = max(8, int(width / char_width(size)))
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        row = ""
        for word in paragraph.split(" "):
            candidate = word if not row else f"{row} {word}"
            if row and len(candidate) > max_chars:
                lines.append(row)
                row = word
            else:
                row = candidate
        lines.append(row)
    return lines


def block(lines: list[str], x: float, y: float, size: float, color: str,
          bold: bool = False, leading: float = 1.28) -> str:
    """Emit a multi-line text block whose first baseline sits at ``y + size``."""
    spans = "".join(
        f'<tspan x="{x}" dy="{size * leading if i else 0}">{esc(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<text x="{x}" y="{y + size * 0.86}" font-size="{size}"'
        f' font-weight="{700 if bold else 400}" fill="{color}">{spans}</text>'
    )


def node(title: str, evidence: str, meaning: str, action: str, x: float, y: float,
         color: str = BLUE) -> tuple[str, tuple[float, float, float, float]]:
    """Draw one decision box and return its SVG plus its bounding box."""
    fill = "#F5F8FA" if color == BLUE else "#F3F8F5"
    parts = [
        f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="10" ry="10"'
        f' fill="{fill}" stroke="{color}" stroke-width="1.7"/>'
    ]
    cursor = y + 12
    for text, size, text_color, bold, gap in (
        (title, 20.5, color, True, 9),
        (evidence, 19, BODY, False, 8),
        ("Meaning   " + meaning, 18.5, SOFT, False, 8),
        ("Decision   " + action, 18.5, color, True, 0),
    ):
        lines = wrap_lines(text, INNER_W, size)
        parts.append(block(lines, x + PAD, cursor, size, text_color, bold))
        cursor += len(lines) * size * 1.28 + gap
    return "".join(parts), (x, y, x + NODE_W, y + NODE_H)


def connector(a: tuple[float, float, float, float], b: tuple[float, float, float, float],
              side_a: str = "right", side_b: str = "left") -> str:
    points = {
        "left": lambda box: (box[0], (box[1] + box[3]) / 2),
        "right": lambda box: (box[2], (box[1] + box[3]) / 2),
        "top": lambda box: ((box[0] + box[2]) / 2, box[1]),
        "bottom": lambda box: ((box[0] + box[2]) / 2, box[3]),
    }
    x1, y1 = points[side_a](a)
    x2, y2 = points[side_b](b)
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINK}"'
        f' stroke-width="2.2" marker-end="url(#arrow)"/>'
    )


def build() -> str:
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7"'
        ' markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{LINK}"/></marker></defs>',
        '<rect width="100%" height="100%" fill="white"/>',
        # No baked-in title or subtitle: the report body carries them under the
        # bold "Fig. N" lead.  The two colour banners are a legend, so they stay.
        f'<g font-family="{FONT}" transform="translate(0,-90)">',
        block(["Blue   development before the v1 freeze"], 35, 112, 21, BLUE, True),
    ]

    n1, b1 = node("1   Compare blocks at the same budget",
                  "LN+GELU 2.101695\nRMS+SwiGLU 2.040526",
                  "2.91% lower at about 1.08M parameters",
                  "Keep the block pair, then check capacity", LEFT_X, 140)
    n2, b2 = node("2   Enlarge capacity and screen hyperparameters",
                  "w320 d8 1.820432; LR 1e-3 is lowest\ndropout 0.05 adds 0.033451 BPB",
                  "Capacity helps, added regularization does not",
                  "Keep dropout 0 and extend training", RIGHT_X, 140)
    n3, b3 = node("3   Judge the marginal return of training length",
                  "9.83M to 28.91M targets\n1.820432 falls to 1.622441",
                  "The last 7.2M returns only 0.0032",
                  "Skip the 58M run, replicate seeds instead", RIGHT_X, 396)
    n4, b4 = node("4   Select and freeze v1",
                  "seed 17 scores 1.622441\nseed 137 scores 1.631858",
                  "Both seeds support a long-training gain",
                  "Freeze seed 17 and record test 1.646152", LEFT_X, 396)
    n5, b5 = node("5   Localise the gain and stop enlarging",
                  "SwiGLU alone lowers BPB by 0.056130\nd10 1.872762 is worse than d8 1.820432",
                  "The block gain comes mainly from SwiGLU",
                  "Keep w320 d8 and inspect position encoding", LEFT_X, 680, GREEN)
    n6, b6 = node("6   Screen RoPE and extra components",
                  "RoPE tied at seed 17 scores 1.754858\n0.0656 below learned tied 1.820432",
                  "Untied weights add only 0.0068 on average",
                  "Prioritise a long RoPE tied run", RIGHT_X, 680, GREEN)
    n7, b7 = node("7   A regression changes the checkpoint rule",
                  "First long run: 1.620751 at 19.66M\n28.91M ends higher at 1.634776",
                  "Longer training does not guarantee better validation",
                  "Declare three validation points, keep the best", RIGHT_X, 940, GREEN)
    n8, b8 = node("8   Replicate across seeds and register a candidate",
                  "CPU FP32 mean 1.600116 +/- 0.011642\nseed 137 is lowest at 1.588095",
                  "All three runs select the 19.66M weights",
                  "Freeze as v2, then score test once", LEFT_X, 940, GREEN)

    svg += [n1, n2, n3, n4, n5, n6, n7, n8]
    svg += [
        connector(b1, b2),
        connector(b2, b3, "bottom", "top"),
        connector(b3, b4, "left", "right"),
        connector(b4, b5, "bottom", "top"),
        connector(b5, b6),
        connector(b6, b7, "bottom", "top"),
        connector(b7, b8, "left", "right"),
        block(["Green   post-freeze development that uses validation only"],
              350, 652, 21, GREEN, True),
    ]

    svg.append("</g></svg>")
    return "".join(svg)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg = build()
    svg_path = OUT_DIR / "decision_flow.svg"
    svg_path.write_text(svg, encoding="utf-8")
    if any("\u4e00" <= ch <= "\u9fff" for ch in svg):
        print("warning: CJK characters remain")

    if "--skip-png" not in sys.argv:
        import cairosvg

        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(OUT_DIR / "decision_flow.png"),
            output_width=W * 2,
            output_height=H * 2,
        )
    print(f"decision flow -> {svg_path}")


if __name__ == "__main__":
    main()
