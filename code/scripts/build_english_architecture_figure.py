#!/usr/bin/env python3
"""Rebuild Fig. 1 (architecture and end-to-end data flow) with clean connectors.

The original figure shipped with a hand-placed arrow set that had five defects:

1. the ``logits`` arrow terminated on the top edge of the *Checkpoint* box, so
   the model output appeared to feed the checkpoint instead of the loss;
2. no connector between lane 1 (Shift inputs) and lane 2 (Input representation);
3. no connector between lane 3 (Checkpoint) and lane 4 (Frozen checkpoint), so
   the pipeline appeared to dead-end twice;
4. the ``next block`` loop arrowhead ended inside the first RMSNorm box;
5. the ``hidden states``, ``next block`` and ``logits`` labels were drawn on top
   of their own lines at 10 px, without a halo.

This generator re-lays the same boxes and labels on the same lanes, but routes
every connector through explicit channels outside the box areas and draws all
floating labels with a white halo.

Output: ``output/figures/journal_en/architecture_data_flow.svg`` and ``.png``.

Usage:
    DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib python build_english_architecture_figure.py
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
OUT_DIR = PROJECT / "output/figures/journal_en"

W, H = 1400, 840

INK = "#111827"
MUTED = "#4B5563"
LINE = "#4B5563"

LANE_BLUE = ("#EFF6FF", "#93C5FD")
LANE_GREEN = ("#ECFDF5", "#6EE7B7")
LANE_SLATE = ("#F8FAFC", "#CBD5E1")
LANE_ORANGE = ("#FFF7ED", "#FDBA74")
LANE_PURPLE = ("#F5F3FF", "#C4B5FD")
LANE_YELLOW = ("#FEFCE8", "#FACC15")
GROUP = ("#FFFFFF", "#64748B")


# --------------------------------------------------------------------------- #
# primitives
# --------------------------------------------------------------------------- #
def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rect(x: float, y: float, w: float, h: float, fill: str, stroke: str, width: float = 1.3) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}"'
        f' stroke="{stroke}" stroke-width="{width}"/>'
    )


def text(x: float, y: float, body: str, cls: str, anchor: str = "middle", halo: bool = False) -> str:
    """A text run.  ``halo`` paints a white outline first so labels stay legible
    wherever they cross a connector."""
    out = []
    if halo:
        out.append(
            f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}"'
            f' stroke="#FFFFFF" stroke-width="3.4" stroke-linejoin="round">{esc(body)}</text>'
        )
    out.append(f'<text x="{x}" y="{y}" class="{cls}" text-anchor="{anchor}">{esc(body)}</text>')
    return "".join(out)


def box(x: float, y: float, w: float, h: float, title: str, lines: list[str],
        palette: tuple[str, str], *, title_cls: str = "head", line_cls: str = "body") -> str:
    """A pipeline box with a bold title and centred detail lines."""
    parts = [rect(x, y, w, h, palette[0], palette[1])]
    step = 15.5
    start = y + h / 2 - (len(lines) + 1) * step / 2 + step * 0.85
    parts.append(text(x + w / 2, start, title, title_cls))
    for i, line in enumerate(lines):
        parts.append(text(x + w / 2, start + step * (i + 1), line, line_cls))
    return "".join(parts)


def arrow(points: list[tuple[float, float]]) -> str:
    """Elbow connector; the arrowhead lands on the last point."""
    head = points[-1]
    body = points[:-1]
    d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(body))
    out = [f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="1.5"/>']
    out.append(
        f'<line x1="{body[-1][0]}" y1="{body[-1][1]}" x2="{head[0]}" y2="{head[1]}"'
        f' stroke="{LINE}" stroke-width="1.5" marker-end="url(#arrow)"/>'
    )
    return "".join(out)


def harrow(x1: float, x2: float, y: float) -> str:
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{LINE}" stroke-width="1.5" marker-end="url(#arrow)"/>'


def varrow(x: float, y1: float, y2: float) -> str:
    return f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{LINE}" stroke-width="1.5" marker-end="url(#arrow)"/>'


# --------------------------------------------------------------------------- #
# layout
# --------------------------------------------------------------------------- #
LANE1_BOXES = [
    ("WikiText-2 train", ["raw UTF-8 bytes", "training split only"]),
    ("Integrity check", ["SHA-256 manifest", "reject changed data"]),
    ("BPE tokenizer", ["fixed vocab = 2048", "fitted on train"]),
    ("Token IDs", ["tensor [N]", "N = 3,613,343"]),
    ("BatchLoader", ["32 windows", "257 tokens each"]),
    ("Shift inputs", ["x = tokens[:-1]", "y = tokens[1:]"]),
]

LANE3_BOXES = [
    ("Cross-entropy", ["next-token targets", "all 256 positions"]),
    ("Backpropagation", ["gradient clip = 1.0"]),
    ("AdamW update", ["lr = 1e-3", "weight decay = 0.1"]),
    ("Cosine schedule", ["3% warmup", "minimum lr = 10%"]),
    ("Checkpoint", ["10,488,640 parameters", "40.033 MiB"]),
]

LANE4_BOXES = [
    ("Frozen checkpoint", ["seed 137 selected", "no test tuning"]),
    ("Independent windows", ["256 targets/window", "reset every call"]),
    ("Log probabilities", ["log-softmax FP32", "shape [B,T,2048]"]),
    ("Target NLL", ["gather true token", "mask final short window"]),
    ("BPB aggregation", ["\u03a3 NLL / ln(2)", "/ raw UTF-8 bytes"]),
    ("Dated outputs", ["JSON + window NLL", "time, RAM, asset size"]),
]

LANE5_BOXES = [
    ("Validation-only selection", ["compare recipes and seeds", "choose lowest full-validation BPB"]),
    ("Freeze manifest", ["checkpoint + code hashes", "configuration locked"]),
    ("Test once after freeze", ["428,405 scored targets", "final test BPB = 1.611178"]),
]


def build() -> str:
    svg: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        "<style>text{font-family:Arial,Helvetica,sans-serif}"
        f".title{{font-size:24px;font-weight:700;fill:{INK}}}"
        f".subtitle{{font-size:12px;fill:{MUTED}}}"
        f".lane{{font-size:16px;font-weight:700;fill:{INK}}}"
        f".head{{font-size:13px;font-weight:700;fill:{INK}}}"
        f".body{{font-size:11px;fill:{INK}}}"
        f".note{{font-size:10px;fill:{MUTED}}}</style>",
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3"'
        ' orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L0,6 L9,3 z" fill="{LINE}"/></marker></defs>',
        f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
        # No baked-in title or subtitle; the report body carries them.
        '<g transform="translate(0,-68)">',
    ]

    # ---- lane 1: data preparation ---------------------------------------- #
    svg.append(text(28, 100, "1  Data preparation", "lane", "start"))
    for i, (title, lines) in enumerate(LANE1_BOXES):
        svg.append(box(35 + i * 210, 112, 185, 76, title, lines, LANE_BLUE))
    for i in range(len(LANE1_BOXES) - 1):
        svg.append(harrow(220 + i * 210, 245 + i * 210, 150))

    # ---- lane 1 -> lane 2 ------------------------------------------------- #
    # Routed through an explicit channel above the Transformer group.
    svg.append(arrow([(1177.5, 188), (1177.5, 236), (120, 236), (120, 268)]))

    # ---- lane 2: student forward path ------------------------------------ #
    svg.append(text(28, 214, "2  Student model forward path", "lane", "start"))
    svg.append(box(35, 268, 170, 86, "Input representation",
                   ["token embedding [B,T,320]", "rotary position embedding", "dropout = 0"], LANE_GREEN))
    svg.append(rect(285, 252, 725, 220, *GROUP, width=1.6))
    svg.append(text(647, 276, "Transformer block \u00d7 8", "head"))

    # inner top row
    svg.append(box(310, 298, 120, 62, "RMSNorm", ["pre-norm"], LANE_SLATE))
    svg.append(box(460, 298, 150, 62, "Q K V", ["4 heads", "head dim 80"], LANE_SLATE))
    svg.append(box(640, 298, 170, 62, "Causal SDPA", ["future masked", "context 256"], LANE_SLATE))
    svg.append(box(840, 298, 140, 62, "Projection", ["bias free", "+ residual"], LANE_SLATE))
    for x1 in (430, 610, 810):
        svg.append(harrow(x1, x1 + 30, 329))

    # inner bottom row runs right to left
    svg.append(box(830, 388, 150, 62, "Down projection", ["bias free", "+ residual"], LANE_SLATE))
    svg.append(box(585, 388, 205, 62, "SwiGLU FFN", ["SiLU(gate) \u00d7 up", "hidden \u2248 853"], LANE_SLATE))
    svg.append(box(420, 388, 125, 62, "RMSNorm", ["pre-norm"], LANE_SLATE))
    svg.append(varrow(910, 360, 388))
    svg.append(harrow(830, 790, 419))
    svg.append(harrow(585, 545, 419))
    # residual loop back into the first RMSNorm; the arrowhead stops on its edge
    svg.append(arrow([(420, 419), (345, 419), (345, 360)]))
    svg.append(text(382, 380, "next block", "note", "middle", halo=True))

    # lane 2 exit
    svg.append(harrow(1010, 1045, 332))
    svg.append(box(1045, 296, 150, 72, "Final RMSNorm", ["width 320"], LANE_GREEN))
    svg.append(harrow(1195, 1220, 332))
    svg.append(box(1220, 286, 145, 92, "Tied LM head", ["shared token weights", "logits [B,T,2048]"], LANE_GREEN))
    svg.append(text(280, 301, "hidden states", "note", "end", halo=True))
    svg.append(harrow(205, 285, 311))

    # ---- logits bus: model output -> loss --------------------------------- #
    # Runs down the right side, left along a dedicated channel, then into the
    # Cross-entropy box.  It no longer touches the Checkpoint box.
    svg.append(arrow([(1292, 378), (1292, 524), (170, 524), (170, 540)]))
    svg.append(text(700, 516, "logits", "note", "middle", halo=True))

    # ---- lane 3: optimization and checkpoint production ------------------- #
    svg.append(text(28, 496, "3  Optimization and checkpoint production", "lane", "start"))
    for i, (title, lines) in enumerate(LANE3_BOXES):
        x = [70, 315, 550, 795, 1060][i]
        w = [200, 190, 200, 220, 250][i]
        svg.append(box(x, 540, w, 72, title, lines, LANE_ORANGE))
    for x1, x2 in ((270, 315), (505, 550), (750, 795), (1015, 1060)):
        svg.append(harrow(x1, x2, 576))

    # ---- lane 3 -> lane 4 ------------------------------------------------- #
    svg.append(arrow([(1185, 612), (1185, 668), (122, 668), (122, 692)]))

    # ---- lane 4: frozen evaluation ---------------------------------------- #
    svg.append(text(28, 652, "4  Frozen evaluation and reporting", "lane", "start"))
    for i, (title, lines) in enumerate(LANE4_BOXES):
        x = [35, 245, 470, 695, 910, 1145][i]
        w = [175, 190, 190, 180, 200, 220][i]
        svg.append(box(x, 692, w, 80, title, lines, LANE_PURPLE))
    for x1, x2 in ((210, 245), (435, 470), (660, 695), (875, 910), (1110, 1145)):
        svg.append(harrow(x1, x2, 732))

    # ---- validation-only sub-procedure ------------------------------------ #
    for i, (title, lines) in enumerate(LANE5_BOXES):
        x = [285, 575, 835][i]
        w = [250, 220, 255][i]
        svg.append(box(x, 812, w, 65, title, lines, LANE_YELLOW))
    svg.append(harrow(535, 575, 844))
    svg.append(harrow(795, 835, 844))
    svg.append(varrow(1010, 812, 772))

    return "".join(svg) + "</g></svg>"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg = build()
    path = OUT_DIR / "architecture_data_flow.svg"
    path.write_text(svg, encoding="utf-8")
    if any("\u4e00" <= ch <= "\u9fff" for ch in svg):
        print("warning: CJK characters remain")

    if "--skip-png" not in sys.argv:
        import cairosvg

        cairosvg.svg2png(
            url=str(path),
            write_to=str(OUT_DIR / "architecture_data_flow.png"),
            output_width=W * 2,
            output_height=H * 2,
        )
    print(f"architecture figure -> {path}")


if __name__ == "__main__":
    main()
