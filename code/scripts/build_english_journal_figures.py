#!/usr/bin/env python3
"""Rebuild every evidence chart of the MP1 report in English.

The original Morandi figures were produced as native PowerPoint shapes and
exported to SVG by ``build_morandi_report_charts.mjs``.  That toolchain needs a
private runtime, so this script re-implements the identical projection geometry
in pure Python and re-emits the charts with English titles, subtitles, notes,
category labels and series names.

Two headline figures are regenerated with the frozen v2 predictor included:

* ``06_test``      adds the frozen v2 test bar (1.611178 BPB).
* ``07_resources`` replaces the validation-only RoPE candidate with the frozen
                   v2 test measurement so both bars share one protocol.

Outputs
-------
``output/figures/journal_en/*.svg``  English SVG sources
``output/figures/journal_en/*.png``  2560x1440 raster copies for Word

Usage
-----
    python build_english_journal_figures.py [--skip-png]
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
EVIDENCE = PROJECT / "output/figures/full_report/evidence.json"
WALL_DATA = PROJECT / "output/figures/transparent_walls/data.json"
OUT_DIR = PROJECT / "output/figures/journal_en"

PALETTE = ["#7E919D", "#95A48F", "#B39191", "#9A90A7", "#B5A18A", "#7E9C98"]
INK = "#394248"
MUTED = "#6C7478"
GRID = "#D3D5D3"
FRAME = "#A4AAA9"
FONT = "Arial Unicode MS,Arial,sans-serif"

# Journal convention: a figure carries no baked-in title, subtitle or caption.
# Those live in the body text under the bold "Fig. N" lead.  Turning this off
# restores the presentation-style header block.
BARE = True


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")


def mix(color: str, white: float) -> str:
    """Blend a hex colour towards white by ``white`` (same formula as the JS)."""
    channels = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    blended = [math.floor(v * (1 - white) + 255 * white + 0.5) for v in channels]
    return "#" + "".join(f"{v:02x}" for v in blended)


def fmt(value: float, chart: dict, precise: bool = False) -> str:
    """Reproduce the JS ``fmt`` formatting switch."""
    pattern = chart.get("format", "")
    y_title = chart.get("yTitle", "")
    if pattern == "0%":
        return f"{value * 100:.{1 if precise else 0}f}%"
    if "nats" in y_title:
        return f"{value:.{3 if precise else 1}f}"
    if "MiB" in y_title:
        return f"{value:.{2 if precise else 0}f}"
    if "reduction" in y_title:
        return f"{value:.{6 if precise else 3}f}"
    return f"{value:.{6 if precise else 2}f}"


def _weight(text: str) -> float:
    """Approximate rendered width in units of the font size."""
    return sum(1.0 if ord(ch) > 255 else 0.53 for ch in text)


def wrap(text: str, budget: float) -> str:
    """Wrap text to a width budget expressed in units of the font size.

    Latin prose is broken on spaces so words stay intact; CJK-dominant lines
    fall back to a per-character break, matching the original figure layout.
    """
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        latin = sum(1 for ch in paragraph if ord(ch) <= 255) >= len(paragraph) * 0.8
        if latin and " " in paragraph:
            row = ""
            for word in paragraph.split(" "):
                candidate = word if not row else f"{row} {word}"
                if row and _weight(candidate) > budget:
                    lines.append(row)
                    row = word
                else:
                    row = candidate
            lines.append(row)
        else:
            row, weight = "", 0.0
            for ch in paragraph:
                char_weight = 1.0 if ord(ch) > 255 else 0.53
                if weight + char_weight > budget:
                    lines.append(row)
                    row, weight = "", 0.0
                row += ch
                weight += char_weight
            lines.append(row)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# canvas
# --------------------------------------------------------------------------- #
class Canvas:
    """Collects SVG fragments that mirror the original PowerPoint layout."""

    def __init__(self, title: str, subtitle: str, note: str) -> None:
        self.svg: list[str] = []
        self._grad = 0
        if not BARE:
            self.text(title, 36, 13, 1210, 47, 35, INK, True)
            self.text(subtitle, 36, 68, 1210, 38, 24, MUTED)
            # 54 weight units at font 21 is the width the original note box used.
            self.text(wrap(note, 54), 36, 632, 1208, 78, 21, MUTED)

    # -- primitives -------------------------------------------------------- #
    def text(
        self,
        content: str,
        x: float,
        y: float,
        w: float,
        h: float,
        size: float = 24,
        color: str = INK,
        bold: bool = False,
        align: str = "left",
    ) -> None:
        lines = str(content).split("\n")
        base = y + h / 2 - (len(lines) - 1) * size * 0.6 + size * 0.34
        anchor_x = x + w / 2 if align == "center" else x
        spans = "".join(
            f'<tspan x="{anchor_x}" dy="{size * 1.2 if i else 0}">{esc(line)}</tspan>'
            for i, line in enumerate(lines)
        )
        self.svg.append(
            f'<text x="{anchor_x}" y="{base}" text-anchor="{"middle" if align == "center" else "start"}"'
            f' font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{spans}</text>'
        )

    def poly(
        self,
        points: list[list[float]],
        color: str = GRID,
        width: float = 1,
        fill: str | None = "none",
        closed: bool = False,
    ) -> None:
        path = " ".join(
            f"{'L' if i else 'M'} {x} {y}" for i, (x, y) in enumerate(points)
        ) + (" Z" if closed else "")
        stroke = f' stroke="{color}" stroke-width="{width}"' if color != "none" else ""
        if isinstance(fill, dict) and fill.get("type") == "gradient":
            self._grad += 1
            gid = f"grad{self._grad}"
            self.svg.append(
                f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{color}" stop-opacity=".34"/>'
                f'<stop offset="1" stop-color="{color}" stop-opacity=".10"/>'
                f"</linearGradient></defs>"
            )
            paint, opacity = f"url(#{gid})", "1"
        elif fill and "/" in fill:
            paint, opacity = fill.split("/")
            opacity = str(float(opacity) / 100)
        else:
            paint, opacity = (fill or "none"), "1"
        self.svg.append(
            f'<path d="{path}" fill="{paint}" fill-opacity="{opacity}"{stroke}/>'
        )

    def dot(self, x: float, y: float, color: str) -> None:
        self.svg.append(
            f'<circle cx="{x}" cy="{y}" r="4.2" fill="{color}" stroke="white" stroke-width="1"/>'
        )


# --------------------------------------------------------------------------- #
# plot geometry (ported 1:1 from build_morandi_report_charts.mjs)
# --------------------------------------------------------------------------- #
def draw_plot(ctx: Canvas, chart: dict, rect: dict | None = None, extra: dict | None = None) -> None:
    rect = rect or {"x": 0, "w": 1280}
    extra = extra or {}
    compact = rect["w"] < 1000

    if BARE:
        origin_y = 580 if compact else 560
        height = 360 if compact else 380
    else:
        origin_y = 526 if compact else 512
        height = 280 if compact else 252
    origin = [rect["x"] + (80 if compact else 132), origin_y]
    ux, uy = (370, 38) if compact else (650, 64)
    dx, dy = (58, -45) if compact else (164, -104)

    numeric = chart["xTitle"] in ("Training step", "Processed targets (M)")
    # The numeric branch is the only consumer of xValues; category names are not
    # convert to numbers (JS would silently yield NaN here).
    x_series = [
        [float(v) for v in (s["xValues"] if s.get("xValues") else chart["categories"])] for s in chart["series"]
    ] if numeric else []
    if numeric:
        xmin = 0.0
        if "(M)" in chart["xTitle"]:
            xmax = 30.0
        else:
            xmax = math.ceil(max(max(v) for v in x_series) / 300) * 300
    else:
        xmin, xmax = 0.0, float(max(len(chart["categories"]) - 1, 1))

    ymin, ymax = chart["min"], chart["max"]

    def point(x: float, y: float, d: float = 0) -> list[float]:
        return [
            origin[0] + x * ux + d * dx,
            origin[1] + x * uy + d * dy - (y - ymin) / (ymax - ymin) * height,
        ]

    def px(i: int, k: int) -> float:
        if numeric:
            return (x_series[i][k] - xmin) / (xmax - xmin)
        if chart["type"] == "bar":
            return (k + 0.5) / len(chart["categories"])
        return k / max(len(chart["categories"]) - 1, 1)

    n = len(chart["series"])
    depth = (lambda i: 0.40) if n == 1 else (lambda i: 0.10 + i * 0.72 / (n - 1))

    # ---- coordinate frame ------------------------------------------------ #
    ctx.poly([point(0, ymin), point(1, ymin), point(1, ymin, 1), point(0, ymin, 1)], FRAME, 0.8, "#F5F4F1", True)
    ctx.poly([point(0, ymin, 1), point(1, ymin, 1), point(1, ymax, 1), point(0, ymax, 1)], FRAME, 0.8, "#FAFAF8", True)
    ctx.poly([point(0, ymin), point(0, ymin, 1), point(0, ymax, 1), point(0, ymax)], FRAME, 0.8, "#FCFCFB", True)

    # ---- y grid ---------------------------------------------------------- #
    unit = chart["unit"]
    y = math.ceil((ymin - 1e-9) / unit) * unit
    while y <= ymax + 1e-8:
        ctx.poly([point(0, y), point(0, y, 1), point(1, y, 1)], GRID, 0.9)
        q = point(0, y)
        ctx.text(
            fmt(y, chart),
            q[0] - (67 if compact else 88),
            q[1] - 14,
            59 if compact else 80,
            28,
            19 if compact else 22,
            MUTED,
            False,
            "center",
        )
        y += unit

    # ---- x ticks --------------------------------------------------------- #
    if numeric:
        if "(M)" in chart["xTitle"]:
            xticks = [0, 10, 20, 30]
        elif xmax > 2000:
            xticks = [0, 1200, 2400, 3600]
        else:
            xticks = [0, 300, 600, 900, 1200]
    else:
        xticks = list(range(len(chart["categories"])))

    for val in xticks:
        if numeric:
            x = (val - xmin) / (xmax - xmin)
        elif chart["type"] == "bar":
            x = (val + 0.5) / len(chart["categories"])
        else:
            x = val / max(len(chart["categories"]) - 1, 1)
        ctx.poly([point(x, ymin), point(x, ymin, 1), point(x, ymax, 1)], GRID, 0.85)
        q = point(x, ymin)
        label = str(val) if numeric else short_label(chart["categories"][val])
        width = 124 if compact else (112 if len(chart["categories"]) > 5 else 210)
        ctx.text(
            label,
            q[0] - width / 2,
            q[1] + 8,
            width,
            54 if "\n" in label else 32,
            18 if compact else (22 if numeric else 21),
            INK,
            False,
            "center",
        )

    # ---- series ---------------------------------------------------------- #
    endings: list[dict] = []
    for i in range(n - 1, -1, -1):
        series = chart["series"][i]
        indices = extra.get("colorIndices")
        color = PALETTE[(indices[i] if indices else i) % len(PALETTE)]
        d = depth(i)
        ctx.poly([point(0, ymin, d), point(1, ymin, d)], mix(color, 0.50), 1)

        if chart["type"] == "bar":
            half = (0.18 if compact else 0.19) / len(chart["categories"])
            for k, value in enumerate(series["values"]):
                x, dd = px(i, k), 0.105
                a0, b0 = point(x - half, ymin, d), point(x + half, ymin, d)
                at, bt = point(x - half, value, d), point(x + half, value, d)
                ab, bb = point(x - half, value, d + dd), point(x + half, value, d + dd)
                br = point(x + half, ymin, d + dd)
                ctx.poly([b0, br, bb, bt], color, 1, f"{mix(color, 0.02)}/70", True)
                ctx.poly([at, bt, bb, ab], color, 1, f"{mix(color, 0.34)}/84", True)
                ctx.poly([a0, b0, bt, at], color, 1, f"{color}/56", True)
                t = point(x, value, d)
                ctx.text(fmt(value, chart, True), t[0] - 66, t[1] - 33, 132, 27, 19 if compact else 23, INK, False, "center")
            endings.append({"name": series["name"], "color": color, "value": None, "y": 228 + i * 85})
        else:
            pts = [point(px(i, k), v, d) for k, v in enumerate(series["values"])]
            ctx.poly(
                [point(px(i, 0), ymin, d), *pts, point(px(i, len(pts) - 1), ymin, d)],
                color,
                0.8,
                {"type": "gradient"},
                True,
            )
            ctx.poly(pts, color, 3, "none")
            for p in pts:
                ctx.dot(p[0], p[1], color)
            if (not numeric) or (n == 1 and len(pts) <= 4):
                for k, p in enumerate(pts):
                    if k == len(pts) - 1 and not compact:
                        continue
                    lift = 62 if (not numeric and n > 1 and i == 0 and k == 0) else 31
                    ctx.text(
                        fmt(series["values"][k], chart, True),
                        max(origin[0] + 10, p[0] - 64),
                        p[1] - lift,
                        128,
                        28,
                        18 if compact else 21,
                        INK,
                        False,
                        "center",
                    )
            endings.append(
                {
                    "name": series["name"],
                    "color": color,
                    "value": series["values"][-1],
                    "end": pts[-1],
                    "y": pts[-1][1] - 23,
                }
            )

    # ---- rims ------------------------------------------------------------ #
    ctx.poly([point(0, ymax), point(0, ymax, 1), point(1, ymax, 1), point(1, ymax), point(0, ymax)], FRAME, 1)
    ctx.poly([point(1, ymin), point(1, ymax)], FRAME, 1)
    ctx.poly([point(1, ymin, 1), point(1, ymax, 1)], FRAME, 1)
    ctx.poly([point(0, ymin), point(1, ymin)], FRAME, 1.2)

    ctx.text(chart["yTitle"], rect["x"] + 36, 60 if BARE else 118,
             rect["w"] - 60, 32, 21 if compact else 24, INK)

    # ---- legend ---------------------------------------------------------- #
    if not compact:
        endings.sort(key=lambda a: a["y"])
        gap = 54 if n > 4 else 72
        endings[0]["y"] = max(175, endings[0]["y"])
        for j in range(1, len(endings)):
            endings[j]["y"] = max(endings[j]["y"], endings[j - 1]["y"] + gap)
        excess = max(0, endings[-1]["y"] - 540)
        for a in endings:
            a["y"] -= excess
        for a in endings:
            label = a["name"].replace(" (validation)", "\n(validation)").replace(" (test)", "\n(test)")
            if a.get("end"):
                ctx.poly([a["end"], [995, a["y"] + 15], [1010, a["y"] + 15]], a["color"], 1.1, "none")
            else:
                ctx.poly([[1003, a["y"] + 14], [1022, a["y"] + 14]], a["color"], 5)
            ctx.text(label, 1030, a["y"], 213, 56 if "\n" in label else 27, 22, a["color"], True)
            if a["value"] is not None:
                ctx.text(
                    f"{'Endpoint' if numeric else 'Final'} {fmt(a['value'], chart, True)}",
                    1030,
                    a["y"] + 27,
                    218,
                    27,
                    21,
                    INK,
                )

    if chart.get("xTitle"):
        ctx.text(chart["xTitle"], rect["x"] + 200, 686 if BARE else 603,
                 390 if compact else 700, 30, 20 if compact else 23, INK, False, "center")


# --------------------------------------------------------------------------- #
# English copy
# --------------------------------------------------------------------------- #
SHORT_LABELS = {
    "小型 LN+GELU": "small\nLN+GELU",
    "小型 RMS+SwiGLU": "small\nRMS+SwiGLU",
    "w320 d8 长训练": "w320 d8\nlong run",
    "Dropout 0 / WD 0.1": "Dropout 0\nWD 0.1",
    "Dropout 0.05 / WD 0.1": "Dropout 0.05\nWD 0.1",
    "Dropout 0 / WD 0.2": "Dropout 0\nWD 0.2",
    "再改 beta2=0.95": "then\nbeta2=0.95",
    "完整学生设置": "full\nstudent setup",
    "无放回采样": "without\nreplacement",
    "原始设置": "original\nsetup",
    "Learned / tied": "Learned\ntied",
    "Learned / untied": "Learned\nuntied",
    "RoPE / tied": "RoPE\ntied",
    "RoPE / untied": "RoPE\nuntied",
    "冻结 v1 配方末尾权重": "v1 recipe\nfinal weights",
    "RoPE 最佳权重": "RoPE\nbest weights",
    "CPU 时间 / 5×": "CPU time\n/ 5x limit",
    "峰值 RSS / 4 GiB": "Peak RSS\n/ 4 GiB limit",
    "推理资产 / 64 MiB": "Assets\n/ 64 MiB limit",
    "课程 baseline": "Course\nbaseline",
    "冻结 v1": "Frozen\nv1",
    "冻结 v2": "Frozen\nv2",
    "Course baseline": "Course\nbaseline",
    "Frozen v1": "Frozen\nv1",
    "Frozen v2": "Frozen\nv2",
    "CPU time / 5x limit": "CPU time\n/ 5x limit",
    "Peak RSS / 4 GiB limit": "Peak RSS\n/ 4 GiB limit",
    "Assets / 64 MiB limit": "Assets\n/ 64 MiB limit",
}


def short_label(text: str) -> str:
    return SHORT_LABELS.get(text, text)


EN_TITLES = {
    "01_mainline": "Main optimization stages",
    "02_lr_loss": "Learning rate and training loss",
    "03_lr_validation": "Complete validation results of the learning-rate sweep",
    "04_regularization": "Validation results for the regularization settings",
    "05_v1_curves": "Two-seed validation curves of the frozen v1 recipe",
    "06_test": "Official test results of the frozen predictors",
    "07_resources": "Resource use against the course limits",
    "08_trainer": "Comparison of trainer settings",
    "09_factorial": "2x2 ablation of normalization and feed-forward blocks",
    "10_capacity": "Short-budget comparison of deeper and wider models",
    "11_representation": "Positional representation and weight sharing",
    "12_rope_tying": "Two-seed gain from untied weights under RoPE",
    "13_training_addons": "Additional gain from EMA and MTP",
    "14_rope_initial": "Late regression of the initial long RoPE run",
    "15_rope_three_seeds": "Validation and checkpoint selection across three RoPE seeds",
    "16_paired_long": "Paired comparison of v1 and the long RoPE recipe",
    "17_rope_training": "Training loss of the three RoPE seeds",
    "wall_02_lr_loss_012": "Training curves of the learning-rate sweep  A",
    "wall_02_lr_loss_345": "Training curves of the learning-rate sweep  B",
    "wall_05_v1_curves": "Two-seed validation curves of the frozen v1 recipe",
    "wall_14_rope_initial": "Validation regression of the initial long RoPE run",
    "wall_15_rope_three_seeds": "Validation curves of the three RoPE seeds",
    "wall_17_rope_training": "Training loss of the three RoPE seeds",
}

EN_SUBTITLES = {
    "01_mainline": "One seed, one development record; lower is better",
    "02_lr_loss": "w320 d8, seed 17; every point comes from a retained training log",
    "03_lr_validation": "w320 d8, seed 17, fixed at 9.83M targets",
    "04_regularization": "w320 d8, seed 17, LR 0.001, fixed at 9.83M targets",
    "05_v1_curves": "The two seeds start from independent initialization and both process 28.91M targets",
    "06_test": "CPU FP32, identical tokenizer, evaluator and complete test split",
    "07_resources": "Each bar is divided by its own limit; 100% marks the limit",
    "08_trainer": "Small course architecture, seed 17, fixed at 9.83M targets",
    "09_factorial": "About 1.08M parameters, seed 17, fixed at 9.83M targets",
    "10_capacity": "seed 17, LR 0.001, fixed at 9.83M targets",
    "11_representation": "w320 d8, seed 17, fixed at 9.83M targets",
    "12_rope_tying": "Paired within seed, fixed at 9.83M targets",
    "13_training_addons": "Positive values are the validation BPB reduced against each control",
    "14_rope_initial": "seed 17; only the final checkpoint was kept at the time",
    "15_rope_three_seeds": "All runs search 28.91M targets and keep the best of three predeclared validation points",
    "16_paired_long": "Common seeds 17 and 137, both measured with in-training MPS validation",
    "17_rope_training": "Batch NLL from the long-training logs, not a complete per-step curve",
    "wall_02_lr_loss_012": "w320 d8, seed 17; every point comes from a retained training log",
    "wall_02_lr_loss_345": "w320 d8, seed 17; every point comes from a retained training log",
    "wall_05_v1_curves": "The two seeds start from independent initialization and both process 28.91M targets",
    "wall_14_rope_initial": "seed 17; only the final checkpoint was kept at the time",
    "wall_15_rope_three_seeds": "All runs search 28.91M targets and keep the best of three predeclared validation points",
    "wall_17_rope_training": "Batch NLL from the long-training logs, not a complete per-step curve",
}

EN_NOTES = {
    "01_mainline": "The first three points use a 9.83M-target budget and the long run uses 28.91M. Lines show the development order, not a pure mechanism effect.",
    "02_lr_loss": "The vertical axis is the mean token NLL of the logged batches, not the complete validation BPB.",
    "03_lr_validation": "0.001 is the lowest of the six candidates. The horizontal axis lists discrete settings, not numeric spacing.",
    "04_regularization": "Dropout 0.05 adds 0.033451 BPB while WD 0.2 matches the control. Dropout 0 with WD 0.1 is retained.",
    "05_v1_curves": "Over the last 7.23M targets seed 17 falls by only 0.003166, so seed replication replaced a 58M run.",
    "06_test": "Test BPB falls by 23.32% against the course baseline. Token PPL drops from 80.848 to 29.023. Both frozen predictors were selected on validation before the test split was scored.",
    "07_resources": "Both predictors were scored on the test split under the same protocol, so the time ratios share one baseline. Seconds are not directly comparable across protocols.",
    "08_trainer": "Sampling and training settings change step by step. The results do not support the claim that swapping the trainer alone explains the main gain.",
    "09_factorial": "Against LN+GELU, SwiGLU alone lowers BPB by 0.056130 and RMSNorm alone by 0.006411.",
    "10_capacity": "Neither enlargement improves BPB at this budget. That does not prove a larger model stays worse after sufficient training.",
    "11_representation": "RoPE tied is 0.065574 BPB below learned tied. This figure only contains short experiments from a single seed.",
    "12_rope_tying": "Untied weights give a mean extra gain of 0.006750 BPB across two seeds, below the 0.01 investment threshold for long training.",
    "13_training_addons": "EMA is controlled against the live weights of the same run and MTP against the matched untied recipe. 0.01 is the investment threshold.",
    "14_rope_initial": "The value near 19.66M is the lowest, but the final weights regress. This triggered the rule that keeps the best predeclared validation point.",
    "15_rope_three_seeds": "All three seeds select the 19.66M weights. The figure shows MPS trajectories; the final comparison table recomputes in CPU FP32.",
    "16_paired_long": "A mean reduction of 0.032644 BPB across the two seeds. RoPE also changes checkpoint selection, so the gap covers the whole recipe.",
    "17_rope_training": "Training loss falls overall while validation regresses late in the run, so checkpoint selection follows complete validation.",
    "wall_02_lr_loss_012": "Shares its coordinate range with panel B. The 0.0005 run records steps 400, 800 and 1200; the others record 300, 600, 900 and 1200.",
    "wall_02_lr_loss_345": "Shares its coordinate range with panel A. Training loss monitors the run; the learning rate is selected on complete validation BPB.",
    "wall_05_v1_curves": "Every point comes from a saved complete validation result. Both seeds train to 28.91M targets and the 58M run is not executed.",
    "wall_14_rope_initial": "The intermediate validation value is low, but the matching weights were not kept. This run produced the predeclared validation-point rule.",
    "wall_15_rope_three_seeds": "All three seeds select weights at 19.66M targets. The figure shows in-training MPS validation; CPU FP32 values are listed separately.",
    "wall_17_rope_training": "The dots are the mean token NLL of the retained batch logs, not a complete curve for every step. Lines only join adjacent observations.",
}

EN_SERIES = {
    "MPS validation": "MPS validation",
    "Validation": "Validation",
    "Test BPB": "Test BPB",
    "Assets": "Inference assets",
    "GELU": "GELU",
    "SwiGLU": "SwiGLU",
    "RoPE tied": "RoPE tied",
    "RoPE untied": "RoPE untied",
    "seed 17": "seed 17",
    "seed 137": "seed 137",
    "seed 233": "seed 233",
    "额外 BPB 改善": "Additional BPB reduction",
    "v1 (test)": "Frozen v1 (test)",
    "RoPE 候选 (validation)": "Frozen v2 (test)",
}

BAR_SEMANTICS = "Bars start at zero; depth only separates series."
LINE_SEMANTICS = "The vertical axis is truncated; wall fill is not an error band and depth only separates series."


# --------------------------------------------------------------------------- #
# figure assembly
# --------------------------------------------------------------------------- #
def render_figure(fig_id: str, title: str, subtitle: str, note: str, charts: list[dict]) -> str:
    has_bar = any(c["type"] == "bar" for c in charts)
    semantics = BAR_SEMANTICS if has_bar else LINE_SEMANTICS
    ctx = Canvas(title, subtitle, f"{note}\n{semantics}")
    for k, chart in enumerate(charts):
        if len(charts) == 1:
            rect, extra = None, {}
        else:
            rect = {"x": 650 if k else 0, "w": 630}
            extra = {"colorIndices": [3, 4, 5] if fig_id.endswith("345") else [k]}
        draw_plot(ctx, chart, rect, extra)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">'
        '<rect width="1280" height="720" fill="white"/>'
        f'<g font-family="{FONT}">' + "".join(ctx.svg) + "</g></svg>"
    )


def load_figures() -> list[dict]:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    walls = json.loads(WALL_DATA.read_text(encoding="utf-8"))

    figures: list[dict] = []
    for fig in evidence["figures"]:
        fig_id = fig["id"]
        charts = json.loads(json.dumps(fig["charts"]))
        for chart in charts:
            chart["series"] = [
                {**s, "name": EN_SERIES.get(s["name"], s["name"])} for s in chart["series"]
            ]
            chart["categories"] = [EN_SERIES.get(c, c) for c in chart["categories"]]

        # ---- frozen v2 is now the headline result ------------------------ #
        if fig_id == "06_test":
            chart = charts[0]
            chart["categories"] = ["Course baseline", "Frozen v1", "Frozen v2"]
            chart["series"][0]["values"] = [2.1012651958438786, 1.6461521330206645, 1.6111783956327541]
        elif fig_id == "07_resources":
            chart = charts[0]
            chart["categories"] = ["CPU time / 5x limit", "Peak RSS / 4 GiB limit", "Assets / 64 MiB limit"]
            chart["series"] = [
                {
                    "name": "Frozen v1 (test)",
                    "values": [0.5750462914439047, 0.4869880676269531, 0.6303957253694534],
                },
                {
                    "name": "Frozen v2 (test)",
                    "values": [0.7426159754383851, 0.48494720458984375, 0.6255081444978714],
                },
            ]

        figures.append(
            {
                "id": fig_id,
                "title": EN_TITLES[fig_id],
                "subtitle": EN_SUBTITLES[fig_id],
                "note": EN_NOTES[fig_id],
                "charts": charts,
            }
        )

    # ---- appendix: split learning-rate curves ---------------------------- #
    for wall in walls:
        chart = {
            "categories": [str(p[0]) for p in wall["series"][0]["points"]],
            "series": [
                {
                    "name": s["name"],
                    "values": [p[1] for p in s["points"]],
                    "xValues": [p[0] for p in s["points"]],
                }
                for s in wall["series"]
            ],
            "type": "scatter",
            "min": wall["limits"]["y"][0],
            "max": wall["limits"]["y"][1],
            "unit": wall["ticks"]["y"][1] - wall["ticks"]["y"][0],
            "yTitle": wall["yTitle"],
            "xTitle": wall["xTitle"],
            "format": "0.0",
        }
        # The wall sources use raw x values for the numeric axis; keep them.
        chart["categories"] = [str(p[0]) for p in wall["series"][0]["points"]]
        figures.append(
            {
                "id": wall["id"],
                "title": EN_TITLES[wall["id"]],
                "subtitle": EN_SUBTITLES[wall["id"]],
                "note": EN_NOTES[wall["id"]],
                "charts": [chart],
                "xValues": [p[0] for p in wall["series"][0]["points"]],
            }
        )
    return figures


def render_png(svg_path: Path, png_path: Path) -> None:
    """Rasterise an SVG to 2560x1440 with cairosvg.

    Headless Chrome is unavailable inside the sandbox, so the raster step uses
    the Cairo toolchain that Homebrew already provides on this machine.
    """
    import cairosvg  # imported lazily so --skip-png works without it

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        output_width=2560,
        output_height=1440,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-png", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    figures = load_figures()
    manifest = []
    for fig in figures:
        svg_text = render_figure(fig["id"], fig["title"], fig["subtitle"], fig["note"], fig["charts"])
        svg_path = OUT_DIR / f"{fig['id']}.svg"
        svg_path.write_text(svg_text, encoding="utf-8")
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in svg_text)
        png_path = OUT_DIR / f"{fig['id']}.png"
        if not args.skip_png:
            render_png(svg_path, png_path)
        manifest.append({"id": fig["id"], "svg": svg_path.name, "png": png_path.name, "cjk": has_cjk})
        print(f"{'CJK!' if has_cjk else ' ok '} {fig['id']}")
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"\n{len(manifest)} figures -> {OUT_DIR}")


if __name__ == "__main__":
    main()
