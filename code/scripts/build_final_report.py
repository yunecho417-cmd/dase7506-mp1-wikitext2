#!/usr/bin/env python3
"""Build the submission-ready MP1 report as a compact scientific PDF."""

import json
import statistics

from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "output" / "pdf" / "MP1_Final_Report.pdf"

NAVY = HexColor("#18324B")
BLUE = HexColor("#2F6BFF")
TEAL = HexColor("#16A39A")
ORANGE = HexColor("#E78518")
RED = HexColor("#D94C4C")
INK = HexColor("#1D2733")
MID = HexColor("#5C6876")
GRID = HexColor("#DCE3EA")
LIGHT = HexColor("#F4F7FA")
PALE_BLUE = HexColor("#EAF0FF")
PALE_TEAL = HexColor("#E8F7F5")
WHITE = colors.white


def register_fonts():
    regular = "/System/Library/AssetsV2/com_apple_MobileAsset_Font8/53fe5be564086fefc7523ccd0a31200acf92e0e5.asset/AssetData/STHEITI.ttf"
    bold = "/System/Library/Fonts/STHeiti Medium.ttc"
    pdfmetrics.registerFont(TTFont("CN", regular))
    pdfmetrics.registerFont(TTFont("CN-Bold", bold, subfontIndex=0))
    pdfmetrics.registerFontFamily("CN", normal="CN", bold="CN-Bold")


register_fonts()
BASE = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle(
        "title", fontName="CN-Bold", fontSize=25, leading=32, textColor=NAVY,
        alignment=TA_LEFT, spaceAfter=8,
    ),
    "subtitle": ParagraphStyle(
        "subtitle", fontName="CN", fontSize=11, leading=17, textColor=MID,
        spaceAfter=12,
    ),
    "h1": ParagraphStyle(
        "h1", fontName="CN-Bold", fontSize=15, leading=20, textColor=NAVY,
        spaceBefore=2, spaceAfter=7,
    ),
    "h2": ParagraphStyle(
        "h2", fontName="CN-Bold", fontSize=10.5, leading=15, textColor=BLUE,
        spaceBefore=6, spaceAfter=4,
    ),
    "body": ParagraphStyle(
        "body", fontName="CN", fontSize=8.6, leading=13.2, textColor=INK,
        spaceAfter=5, wordWrap="CJK",
    ),
    "small": ParagraphStyle(
        "small", fontName="CN", fontSize=7.2, leading=10.5, textColor=MID,
        wordWrap="CJK",
    ),
    "tiny": ParagraphStyle(
        "tiny", fontName="CN", fontSize=6.5, leading=8.5, textColor=MID,
        wordWrap="CJK",
    ),
    "metric": ParagraphStyle(
        "metric", fontName="CN-Bold", fontSize=18, leading=21, textColor=NAVY,
        alignment=TA_CENTER,
    ),
    "metric_label": ParagraphStyle(
        "metric_label", fontName="CN", fontSize=7.2, leading=9.5, textColor=MID,
        alignment=TA_CENTER,
    ),
    "callout": ParagraphStyle(
        "callout", fontName="CN", fontSize=8.6, leading=13, textColor=INK,
        leftIndent=7, rightIndent=7, spaceBefore=3, spaceAfter=3, wordWrap="CJK",
    ),
}


def p(text, style="body"):
    return Paragraph(text, STYLES[style])


def section(title):
    return p(title, "h1")


def subsection(title):
    return p(title, "h2")


def styled_table(data, widths, header=True, font_size=7.4, row_bgs=None):
    cooked = []
    for r, row in enumerate(data):
        style = "small"
        cooked.append([cell if hasattr(cell, "wrap") else Paragraph(str(cell), STYLES[style]) for cell in row])
    t = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "CN"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2.2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "CN-Bold"),
        ]
    for i in range(1 if header else 0, len(data)):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
    if row_bgs:
        for row, bg in row_bgs.items():
            commands.append(("BACKGROUND", (0, row), (-1, row), bg))
    t.setStyle(TableStyle(commands))
    return t


def metric_cards(items):
    cells = []
    for value, label, color in items:
        cells.append([
            Paragraph(value, ParagraphStyle("m", parent=STYLES["metric"], textColor=color)),
            p(label, "metric_label"),
        ])
    tables = []
    for cell in cells:
        tab = Table([[cell[0]], [cell[1]]], colWidths=[42 * mm], rowHeights=[11 * mm, 8 * mm])
        tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), WHITE),
            ("BOX", (0, 0), (-1, -1), 0.65, GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        tables.append(tab)
    outer = Table([tables], colWidths=[45 * mm] * len(tables), hAlign="LEFT")
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return outer


def arrow(d, x1, y1, x2, y2, color=BLUE, width=1.5):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width))
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    size = 4.5
    pts = []
    for delta in (2.55, -2.55):
        pts.extend([x2 + size * math.cos(a + delta), y2 + size * math.sin(a + delta)])
    d.add(Polygon([x2, y2] + pts, fillColor=color, strokeColor=color))


def box(d, x, y, w, h, title, detail="", fill=LIGHT, stroke=GRID, title_color=NAVY):
    d.add(Rect(x, y, w, h, rx=4, ry=4, fillColor=fill, strokeColor=stroke, strokeWidth=0.8))
    d.add(String(x + w / 2, y + h - 12, title, fontName="CN-Bold", fontSize=7.5,
                 textAnchor="middle", fillColor=title_color))
    if detail:
        lines = detail.split("\n")
        for i, line in enumerate(lines):
            d.add(String(x + w / 2, y + h - 25 - i * 9, line, fontName="CN", fontSize=6.2,
                         textAnchor="middle", fillColor=MID))


def pipeline_drawing():
    d = Drawing(515, 245)
    d.add(String(0, 232, "端到端数据流：训练、选择、冻结与一次性测试", fontName="CN-Bold", fontSize=10, fillColor=NAVY))
    xs = [0, 91, 182, 273, 364, 455]
    names = [
        ("原始文本", "WikiText-2\nUTF-8 + SHA"),
        ("固定分词", "BPE-2048\nToken IDs"),
        ("批处理", "257 tokens\nx / y 平移"),
        ("Transformer", "8 blocks\nnext-token logits"),
        ("优化", "CE + AdamW\ncosine schedule"),
        ("验证", "完整 validation\nBPB 选择"),
    ]
    for i, ((title, detail), x) in enumerate(zip(names, xs)):
        box(d, x, 153, 60, 56, title, detail, PALE_BLUE if i < 3 else PALE_TEAL)
        if i < len(xs) - 1:
            arrow(d, x + 60, 181, xs[i + 1] - 4, 181)
    box(d, 320, 55, 82, 52, "冻结清单", "checkpoint / code\ntokenizer hashes", PALE_BLUE)
    box(d, 433, 55, 82, 52, "Test 仅一次", "CPU FP32\nBPB + resources", PALE_TEAL)
    arrow(d, 485, 153, 361, 111, ORANGE)
    arrow(d, 402, 81, 429, 81, ORANGE)
    d.add(String(0, 121, "训练路径", fontName="CN-Bold", fontSize=7, fillColor=BLUE))
    d.add(String(320, 40, "选择规则在 test 前确定，test 不参与调参", fontName="CN", fontSize=6.8, fillColor=MID))
    box(d, 0, 55, 132, 52, "评测窗口", "每个窗口独立 / causal\n每个 target 恰好计数一次", LIGHT)
    box(d, 160, 55, 132, 52, "BPB", "sum NLL / ln(2)\n除以原始 UTF-8 bytes", LIGHT)
    arrow(d, 132, 81, 156, 81, TEAL)
    d.add(Line(485, 55, 485, 27, strokeColor=TEAL, strokeWidth=1.2))
    d.add(Line(485, 27, 65, 27, strokeColor=TEAL, strokeWidth=1.2))
    d.add(Line(65, 27, 65, 51, strokeColor=TEAL, strokeWidth=1.2))
    return d


def transformer_drawing():
    d = Drawing(515, 220)
    d.add(String(0, 207, "模型内部数据流", fontName="CN-Bold", fontSize=10, fillColor=NAVY))
    box(d, 0, 126, 75, 50, "Token + Position", "[B,T] -> [B,T,320]", PALE_BLUE)
    box(d, 103, 114, 245, 75, "Transformer block x 8", "Pre-RMSNorm -> Q,K,V (4 heads) -> causal SDPA -> residual\nPre-RMSNorm -> SwiGLU FFN (2.667x) -> residual", PALE_TEAL)
    box(d, 376, 126, 65, 50, "Final RMSNorm", "[B,T,320]", PALE_BLUE)
    box(d, 466, 126, 49, 50, "Tied head", "2048 logits", PALE_BLUE)
    arrow(d, 75, 151, 99, 151)
    arrow(d, 348, 151, 372, 151)
    arrow(d, 441, 151, 462, 151)
    d.add(String(103, 98, "Causality", fontName="CN-Bold", fontSize=7, fillColor=ORANGE))
    d.add(String(153, 98, "attention mask 阻止未来 token 影响当前预测", fontName="CN", fontSize=6.8, fillColor=MID))
    d.add(String(103, 85, "Efficiency", fontName="CN-Bold", fontSize=7, fillColor=TEAL))
    d.add(String(153, 85, "无 bias 线性层 + tied embeddings 控制资产大小", fontName="CN", fontSize=6.8, fillColor=MID))
    d.add(String(103, 72, "Stability", fontName="CN-Bold", fontSize=7, fillColor=BLUE))
    d.add(String(153, 72, "RMSNorm + residual + gradient clipping", fontName="CN", fontSize=6.8, fillColor=MID))
    d.add(Rect(0, 0, 515, 50, fillColor=LIGHT, strokeColor=GRID, strokeWidth=0.6))
    d.add(String(12, 33, "10,570,560 params", fontName="CN-Bold", fontSize=9, fillColor=NAVY))
    d.add(String(145, 33, "context 256", fontName="CN-Bold", fontSize=9, fillColor=NAVY))
    d.add(String(255, 33, "dropout 0", fontName="CN-Bold", fontSize=9, fillColor=NAVY))
    d.add(String(355, 33, "40.345 MiB", fontName="CN-Bold", fontSize=9, fillColor=NAVY))
    d.add(String(12, 15, "输入和输出权重共享；位置采用 learned embedding；最终输出为 log-probabilities。", fontName="CN", fontSize=6.8, fillColor=MID))
    return d


def line_chart():
    d = Drawing(515, 220)
    left, bottom, width, height = 48, 35, 420, 145
    d.add(String(0, 207, "训练量与验证 BPB", fontName="CN-Bold", fontSize=10, fillColor=NAVY))
    xmin, xmax, ymin, ymax = 0, 30, 1.58, 2.24
    for val in [1.6, 1.8, 2.0, 2.2]:
        y = bottom + (val - ymin) / (ymax - ymin) * height
        d.add(Line(left, y, left + width, y, strokeColor=GRID, strokeWidth=0.5))
        d.add(String(left - 7, y - 2, f"{val:.1f}", fontName="CN", fontSize=6.5, textAnchor="end", fillColor=MID))
    for val in [0, 10, 20, 30]:
        x = left + (val - xmin) / (xmax - xmin) * width
        d.add(String(x, bottom - 13, str(val), fontName="CN", fontSize=6.5, textAnchor="middle", fillColor=MID))
    d.add(Line(left, bottom, left, bottom + height, strokeColor=INK, strokeWidth=0.8))
    d.add(Line(left, bottom, left + width, bottom, strokeColor=INK, strokeWidth=0.8))
    d.add(String(left + width / 2, 8, "processed targets (million)", fontName="CN", fontSize=7, textAnchor="middle", fillColor=MID))
    series = [
        ("w320 d8, seed 17", [(7.225, 1.847600), (14.451, 1.683248), (21.684, 1.625607), (28.910, 1.622441)], BLUE),
        ("w320 d8, seed 137", [(7.225, 1.846897), (14.451, 1.682641), (21.684, 1.635717), (28.910, 1.631858)], ORANGE),
    ]
    for label, pts, color in series:
        mapped = []
        for xval, yval in pts:
            x = left + (xval - xmin) / (xmax - xmin) * width
            y = bottom + (yval - ymin) / (ymax - ymin) * height
            mapped.append((x, y))
        for a, b in zip(mapped, mapped[1:]):
            d.add(Line(a[0], a[1], b[0], b[1], strokeColor=color, strokeWidth=1.8))
        for x, y in mapped:
            d.add(Circle(x, y, 2.7, fillColor=WHITE, strokeColor=color, strokeWidth=1.5))
    d.add(Line(335, 199, 350, 199, strokeColor=BLUE, strokeWidth=2))
    d.add(String(355, 196, "seed 17", fontName="CN", fontSize=6.8, fillColor=MID))
    d.add(Line(411, 199, 426, 199, strokeColor=ORANGE, strokeWidth=2))
    d.add(String(431, 196, "seed 137", fontName="CN", fontSize=6.8, fillColor=MID))
    d.add(String(470, 39, "1.622", fontName="CN-Bold", fontSize=7, fillColor=BLUE))
    return d


def lr_chart():
    d = Drawing(515, 188)
    left, bottom, width, height = 52, 34, 410, 112
    d.add(String(0, 175, "Peak learning rate 扫描（相同 9.83M targets）", fontName="CN-Bold", fontSize=10, fillColor=NAVY))
    labels = ["5e-4", "7.5e-4", "1e-3", "1.25e-3", "2e-3", "4e-3"]
    vals = [1.887329, 1.826578, 1.820432, 1.850677, 1.995888, 1.972859]
    ymin, ymax = 1.78, 2.04
    for val in [1.8, 1.9, 2.0]:
        y = bottom + (val - ymin) / (ymax - ymin) * height
        d.add(Line(left, y, left + width, y, strokeColor=GRID, strokeWidth=0.5))
        d.add(String(left - 7, y - 2, f"{val:.1f}", fontName="CN", fontSize=6.5, textAnchor="end", fillColor=MID))
    gap = width / len(vals)
    for i, (label, val) in enumerate(zip(labels, vals)):
        x = left + i * gap + 10
        bar_h = (val - ymin) / (ymax - ymin) * height
        color = BLUE if i == 2 else HexColor("#A9B7C6")
        d.add(Rect(x, bottom, 38, bar_h, fillColor=color, strokeColor=None))
        d.add(String(x + 19, bottom - 12, label, fontName="CN", fontSize=6.3, textAnchor="middle", fillColor=MID))
        d.add(String(x + 19, bottom + bar_h + 4, f"{val:.3f}", fontName="CN-Bold", fontSize=6.1, textAnchor="middle", fillColor=color if i == 2 else MID))
    d.add(String(475, 92, "lower is better", fontName="CN", fontSize=6.5, fillColor=MID))
    return d


def resource_chart():
    d = Drawing(515, 215)
    d.add(String(0, 202, "资源上限占用", fontName="CN-Bold", fontSize=10, fillColor=NAVY))
    items = [
        ("CPU time", 57.50, "2.875x / 5x", BLUE),
        ("Peak RSS", 48.70, "1.948 / 4 GiB", TEAL),
        ("Assets", 63.04, "40.345 / 64 MiB", ORANGE),
    ]
    for i, (name, pct, detail, color) in enumerate(items):
        y = 152 - i * 53
        d.add(String(0, y + 6, name, fontName="CN-Bold", fontSize=8, fillColor=NAVY))
        d.add(Rect(85, y, 335, 18, fillColor=LIGHT, strokeColor=GRID, strokeWidth=0.5))
        d.add(Rect(85, y, 335 * pct / 100.0, 18, fillColor=color, strokeColor=None))
        d.add(String(427, y + 5, f"{pct:.1f}%", fontName="CN-Bold", fontSize=8, fillColor=color))
        d.add(String(85, y - 12, detail, fontName="CN", fontSize=6.7, fillColor=MID))
    d.add(String(85, 5, "所有条形均低于 100%，且 test 正式测量的三个约束全部通过。", fontName="CN", fontSize=7, fillColor=MID))
    return d


def callout(text, color=PALE_BLUE):
    t = Table([[p(text, "callout")]], colWidths=[178 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("BOX", (0, 0), (-1, -1), 0.6, GRID),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    if doc.page > 1:
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.5)
        canvas.line(16 * mm, h - 13 * mm, w - 16 * mm, h - 13 * mm)
        canvas.setFont("CN", 6.5)
        canvas.setFillColor(MID)
        canvas.drawString(16 * mm, h - 10 * mm, "HKU DASE 7506 - Mini Project 1")
        canvas.drawRightString(w - 16 * mm, h - 10 * mm, "2026-09-25")
    canvas.setFont("CN", 6.5)
    canvas.setFillColor(MID)
    canvas.drawCentredString(w / 2, 9 * mm, f"{doc.page}")
    canvas.restoreState()


def load_run(name):
    path = ROOT / "code" / "runs" / name / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def cpu_validation_bpb(item):
    name = Path(item["run_dir"]).name
    path = ROOT / "code" / "results" / "2026-09-25" / f"{name}_validation_cpu_fp32.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["bpb"]
    return item["validation"]["bpb"]


def build_story():
    runs = {
        name: load_run(name)
        for name in [
            "recipe_exact_baseline_s17", "recipe_norepl_s17",
            "recipe_norepl_beta095_s17", "recipe_full_student_s17",
            "s0_lr1e3", "ablation_rms_gelu_s17", "ablation_ln_swiglu_s17",
            "s_lr1e3", "lr1e3_a", "capacity_w320d10_s17",
            "capacity_w384d8_s17", "ablation_untied_s17",
            "ablation_rope_s17", "ablation_rope_s137",
            "ablation_rope_untied_s17", "ablation_rope_untied_s137",
            "ablation_rope_untied_ema099_s17", "ablation_rope_untied_mtp1_s17",
            "2026-09-25_rope_long_best_seed17",
            "2026-09-25_rope_long_best_seed137",
            "2026-09-25_rope_long_best_seed233",
        ]
    }
    long_runs = [
        runs["2026-09-25_rope_long_best_seed17"],
        runs["2026-09-25_rope_long_best_seed137"],
        runs["2026-09-25_rope_long_best_seed233"],
    ]
    long_bpbs = [cpu_validation_bpb(item) for item in long_runs]
    short_rope = [runs["ablation_rope_s17"]["validation"]["bpb"], runs["ablation_rope_s137"]["validation"]["bpb"]]
    short_untied = [runs["ablation_rope_untied_s17"]["validation"]["bpb"], runs["ablation_rope_untied_s137"]["validation"]["bpb"]]
    run_count = len(list((ROOT / "code" / "runs").glob("*/metrics.json")))

    story = []

    # Page 1
    story += [
        Spacer(1, 10 * mm), p("Mini Project 1", "title"),
        p("资源受限 WikiText-2 语言模型的设计 消融与冻结评测", "subtitle"),
        Spacer(1, 4 * mm),
        metric_cards([
            ("1.6462", "冻结 v1 test BPB", BLUE), ("-21.66%", "相对基线", TEAL),
            ("2.875x", "CPU 时间比", ORANGE), ("40.35 MiB", "推理资产", NAVY),
        ]),
        Spacer(1, 8 * mm), section("摘要"),
        p("本项目在课程固定的 WikiText-2、BPE-2048 tokenizer、256-token 上下文和因果评测协议下，从随机初始化训练 decoder-only Transformer。冻结 v1 使用 8 层、宽度 320、4 个注意力头、RMSNorm、SwiGLU、learned position 与 tied weights，共 10.57M 参数。所有方法选择只使用 validation，test 在 checkpoint 和代码哈希写入冻结清单后运行。"),
        p("冻结 v1 的 CPU FP32 test BPB 为 1.646152，相比课程基线 2.101265 降低 21.66%。正式资源测量为基线时间的 2.875 倍、峰值 RSS 1.948 GiB、资产 40.345 MiB，均满足 5 倍、4 GiB 和 64 MiB 上限。冻结后的补充消融进一步拆分训练配方、RMSNorm 与 SwiGLU、容量、位置编码、权重共享、EMA 和多步预测；这些实验只报告 validation，不改变 v1 的 test 结论。"),
        callout("主结论：SwiGLU 是小模型 block 改进的主要来源；w320 d8 优于更深或更宽候选；RoPE 在补充实验中稳定降低 validation BPB，但仍保持为 validation-only v2 候选。", PALE_TEAL),
        Spacer(1, 5 * mm), subsection("证据范围"),
        styled_table([
            ["层次", "内容", "证据"],
            ["冻结 v1", "learned position + tied weights；最终 test 与资源合规", "2026-09-23 freeze manifest"],
            ["补充消融", "训练器 4 项、2x2 block、容量、表示、EMA、MTP", f"共 {run_count} 个 metrics.json"],
            ["长训练复现", "RoPE tied；3 seeds；预声明 validation 检查点", "9.83M / 19.66M / 28.91M"],
            ["工程", "契约测试、训练器测试、哈希、结构化结果与构建脚本", "README + REQUIREMENTS + CHANGELOG"],
        ], [30 * mm, 94 * mm, 53 * mm]), PageBreak(),
    ]

    # Page 2
    story += [
        section("1 任务指标与数据纪律"),
        p("目标是在不使用外部文本、预训练权重或 test 调参的前提下，最小化完整 test split 的 bits per byte。每个评测窗口相互独立并严格 causal；除 split 第一个 token 外，每个 target 恰好评分一次。"),
        styled_table([
            ["固定项", "值或规则", "目的"],
            ["Tokenizer", "课程 BPE-2048", "排除词表工程带来的不可比性"],
            ["Context", "256 tokens", "训练与评测一致"],
            ["窗口", "独立 causal 无跨窗口状态", "防止未来信息和隐式长上下文"],
            ["主指标", "BPB = NLL / ln(2) / UTF-8 bytes", "越低越好"],
            ["选择 split", "validation", "架构 超参数 seed checkpoint"],
            ["最终 split", "test 在冻结后运行", "避免 test 泄漏"],
        ], [31 * mm, 58 * mm, 88 * mm]), Spacer(1, 4 * mm), pipeline_drawing(),
        subsection("数据流与选择边界"),
        p("训练文本先经过 manifest 哈希检查，再由固定 tokenizer 转为 token IDs。每个 batch 使用 257-token 连续片段，将前 256 个作为输入、后移一位作为目标。模型输出 next-token log probabilities，交叉熵驱动 AdamW。开发阶段只比较完整 validation BPB；冻结后 test 只用于最终报告。2026-09-25 的后续实验未重新查看或使用 test 选择模型。"),
        callout("冻结 v1 与 validation-only v2 候选在报告中分别标注。更低的补充 validation 分数不能替换已冻结的 test 分数。"), PageBreak(),
    ]

    # Page 3
    story += [
        section("2 冻结 v1 模型与训练配方"), transformer_drawing(),
        styled_table([
            ["组件", "冻结设计", "依据"],
            ["Backbone", "8 blocks width 320", "10.57M 参数在资源上限内"],
            ["Attention", "4 heads causal SDPA", "严格遮挡未来 token"],
            ["Normalization", "Pre RMSNorm", "稳定 residual 优化"],
            ["FFN", "SwiGLU 2.667x", "补充 2x2 消融显示其贡献最大"],
            ["Position", "learned embedding", "v1 冻结配置"],
            ["Weights", "bias-free tied head", "减少冗余参数和资产"],
            ["Regularization", "dropout 0 weight decay 0.1", "0.05 dropout 变差"],
        ], [32 * mm, 49 * mm, 96 * mm]), Spacer(1, 4 * mm),
        subsection("训练设置"),
        styled_table([
            ["项目", "设置", "项目", "设置"],
            ["Batch size", "32", "Targets", "28,909,568"],
            ["Optimizer", "AdamW", "Peak LR", "1e-3"],
            ["Betas", "0.9 / 0.95", "Warmup", "3%"],
            ["Schedule", "cosine to 0.1x", "Gradient clip", "1.0"],
            ["训练", "MPS BF16", "正式评测", "CPU FP32 4 threads"],
        ], [31 * mm, 57 * mm, 31 * mm, 58 * mm]), Spacer(1, 4 * mm),
        callout("实现与证据修复包括 RoPE 广播维、processed targets 横轴、独立进程资源测量、显式 sampling 与 schedule 控制、预声明 validation 检查点和最佳权重保存。", PALE_TEAL), PageBreak(),
    ]

    # Page 4
    story += [
        section("3 冻结前实验链"),
        p("短实验统一处理 9.83M targets；除 seed 稳定性外使用 seed 17。数据、tokenizer、context、batch size 和 evaluator 保持不变。"),
        line_chart(), lr_chart(),
        styled_table([
            ["比较", "Validation BPB", "结论"],
            ["Baseline -> 小型 RMS + SwiGLU", "2.071087 -> 2.040526", "参数相近时高效 block 有收益"],
            ["1.08M -> w320 d8", "2.040526 -> 1.820432", "容量是主要增益来源"],
            ["9.83M -> 28.91M targets", "1.820432 -> 1.622441", "延长训练显著有效"],
            ["Dropout 0 -> 0.05", "1.820432 -> 1.853883", "当前预算下更差"],
            ["WD 0.1 -> 0.2", "1.820432 -> 1.820517", "差异可忽略"],
        ], [55 * mm, 55 * mm, 67 * mm]),
        p("Peak LR 的单 seed 最低点为 1e-3；7.5e-4 只差 0.006146 BPB，因此报告将其写为接近但未充分消解的选择，而不是绝对最优。"), PageBreak(),
    ]

    # Page 5
    story += [
        section("4 补充消融 训练配方 Block 与容量"),
        p("以下结果于 v1 test 冻结后得到，仅用于加强因果解释。所有比较仍使用完整 validation。"),
        subsection("训练配方分解"),
        styled_table([
            ["设置", "Sampling", "Schedule / beta2", "Validation BPB", "相对基准"],
            ["课堂基准配方", "with replacement", "baseline / 0.999", f"{runs['recipe_exact_baseline_s17']['validation']['bpb']:.6f}", "0"],
            ["仅改无放回", "without replacement", "baseline / 0.999", f"{runs['recipe_norepl_s17']['validation']['bpb']:.6f}", "-0.000778"],
            ["再改 beta2", "without replacement", "baseline / 0.95", f"{runs['recipe_norepl_beta095_s17']['validation']['bpb']:.6f}", "+0.030738"],
            ["完整学生配方", "without replacement", "cosine / 0.95", f"{runs['recipe_full_student_s17']['validation']['bpb']:.6f}", "+0.026100"],
        ], [37 * mm, 38 * mm, 47 * mm, 33 * mm, 22 * mm]),
        p("无放回采样几乎中性；beta2 = 0.95 在小 baseline 上明显变差，cosine schedule 只回收部分损失。因此最终架构收益不能归因于 trainer 差异。"),
        subsection("Normalization 与 FFN 的 2x2 消融"),
        styled_table([
            ["Norm", "FFN", "Validation BPB", "相对 LN GELU"],
            ["LayerNorm", "GELU", "2.101695", "0"], ["RMSNorm", "GELU", "2.095283", "-0.006412"],
            ["LayerNorm", "SwiGLU", "2.045564", "-0.056130"], ["RMSNorm", "SwiGLU", "2.040526", "-0.061169"],
        ], [44 * mm, 44 * mm, 44 * mm, 45 * mm], row_bgs={4: PALE_TEAL}),
        p("SwiGLU 贡献约 0.056 BPB，RMSNorm 贡献约 0.005 至 0.006 BPB，两者交互很小。"),
        subsection("容量形状"),
        styled_table([
            ["配置", "参数", "资产", "Validation BPB", "决定"],
            ["w320 d8", "10.571M", "40.345 MiB", "1.820432", "保留"],
            ["w320 d10", "13.029M", "49.728 MiB", "1.872762", "拒绝"],
            ["w384 d8", "15.047M", "57.422 MiB", "1.829156", "拒绝 接近资产上限"],
        ], [36 * mm, 31 * mm, 37 * mm, 37 * mm, 36 * mm]), PageBreak(),
    ]

    # Page 6
    story += [
        section("5 补充消融 位置 权重共享与训练机制"),
        subsection("表示层选择"),
        styled_table([
            ["Position", "Output weights", "Seed", "Validation BPB", "资产"],
            ["learned", "tied", "17", "1.820432", "40.345 MiB"],
            ["learned", "untied", "17", "1.786678", "42.846 MiB"],
            ["RoPE", "tied", "17", "1.754858", "40.033 MiB"],
            ["RoPE", "tied", "137", "1.741184", "40.033 MiB"],
            ["RoPE", "untied", "17", "1.745039", "42.511 MiB"],
            ["RoPE", "untied", "137", "1.737502", "42.511 MiB"],
        ], [38 * mm, 42 * mm, 20 * mm, 40 * mm, 37 * mm]),
        p(f"RoPE tied 的双 seed 均值为 {statistics.mean(short_rope):.6f}；RoPE untied 为 {statistics.mean(short_untied):.6f}。解开权重仅额外改善 {statistics.mean(short_rope) - statistics.mean(short_untied):.6f} BPB，低于预先设定的 0.01 阈值，因此长训练采用更简单且资产更小的 RoPE tied。"),
        subsection("训练期机制"),
        styled_table([
            ["机制", "对照", "Validation BPB", "成本或风险", "决定"],
            ["EMA 0.99", "RoPE untied", f"{runs['ablation_rope_untied_ema099_s17']['validation']['bpb']:.6f}", "仅改善约 0.00135", "拒绝"],
            ["MTP k=1", "RoPE untied", f"{runs['ablation_rope_untied_mtp1_s17']['validation']['bpb']:.6f}", "约增加 12% 训练成本", "拒绝"],
        ], [34 * mm, 40 * mm, 39 * mm, 42 * mm, 22 * mm]),
        p("EMA 的增益小于 seed 波动和决策阈值；MTP 未改善 validation 且增加训练成本。两者都不进入长训练。"),
        subsection("消融决策规则"),
        styled_table([
            ["规则", "应用"],
            ["相同 targets", "所有短筛选均为 9.83M processed targets"],
            ["先资源门控", "资产接近 64 MiB 时不扩大模型"],
            ["至少两个 seed", "RoPE 与 untied 增益用 seed 17 和 137 检查"],
            ["简化优先", "增益小于 0.01 BPB 时保留更简单候选"],
        ], [53 * mm, 124 * mm]), PageBreak(),
    ]

    # Page 7
    long_rows = [["Seed", "Selected targets", "CPU FP32 BPB", "Final MPS BPB", "Selected step"]]
    for item in long_runs:
        long_rows.append([
            str(item["seed"]), f"{item['checkpoint_processed_targets']:,}", f"{cpu_validation_bpb(item):.6f}",
            f"{item['curve'][-1]['bpb']:.6f}", str(item["selected_step"]),
        ])
    story += [
        section("6 RoPE 长训练与 checkpoint 选择"),
        p("第一条 RoPE seed17 长训练只保存了末尾权重。validation 在 19.66M targets 达到 1.620751，末尾回退到 1.634776，暴露出过训练和 checkpoint 丢失风险。随后在命令行预声明 9.83M、19.66M、28.91M 三个评测点，并在这些点中保存最低 validation BPB 权重。"),
        styled_table(long_rows, [27 * mm, 43 * mm, 37 * mm, 35 * mm, 35 * mm], row_bgs={2: PALE_TEAL}),
        Spacer(1, 4 * mm),
        metric_cards([
            (f"{statistics.mean(long_bpbs):.4f}", "3-seed mean BPB", BLUE),
            (f"{statistics.stdev(long_bpbs):.4f}", "sample SD", TEAL),
            (f"{min(long_bpbs):.4f}", "best validation", ORANGE),
            ("19.66M", "selection budget", NAVY),
        ]),
        Spacer(1, 6 * mm), subsection("解释"),
        p("三个 seed 均在预声明的中间检查点优于训练末尾，说明固定保存最后一步会系统性低估该配方。报告同时记录 search targets 28.91M 与 selected-checkpoint targets 19.66M：前者表示实际计算成本，后者表示权重训练到的位置。"),
        p("这组结果将 RoPE tied 确立为 v2 validation-only 候选，但没有再次运行 student-model test。这样可避免在已经看到 v1 test 后用同一 test 继续选择版本。若课程允许新的独立提交轮次，应先写入新的 v2 freeze manifest，再运行一次 test。"),
        callout("选择原则：最低 CPU FP32 validation BPB 决定 v2 候选；test 不参与 RoPE、seed 或 checkpoint 选择。", PALE_TEAL), PageBreak(),
    ]

    # Page 8
    story += [
        section("7 冻结 v1 的最终 test 与资源"),
        metric_cards([
            ("2.1013", "Baseline test BPB", MID), ("1.6462", "Frozen v1 test BPB", BLUE),
            ("0.4551", "绝对 BPB 降低", TEAL), ("21.66%", "相对改进", ORANGE),
        ]), Spacer(1, 5 * mm),
        styled_table([
            ["模型", "Test BPB", "Token PPL", "NLL nats", "Targets", "UTF-8 bytes"],
            ["官方 baseline", "2.101265", "80.8479", "1,881,798.91", "428,405", "1,292,013"],
            ["冻结 v1", "1.646152", "31.2239", "1,474,220.05", "428,405", "1,292,013"],
        ], [33 * mm, 27 * mm, 28 * mm, 36 * mm, 26 * mm, 27 * mm], row_bgs={2: PALE_TEAL}),
        Spacer(1, 6 * mm), resource_chart(),
        styled_table([
            ["Test 资源", "Baseline", "冻结 v1", "上限", "状态"],
            ["CPU FP32 median", "4.209 s", "12.103 s", "<= 5x baseline", "通过 2.875x"],
            ["Peak RSS", "1.873 GiB", "1.948 GiB", "<= 4 GiB", "通过"],
            ["Assets", "4.168 MiB", "40.345 MiB", "<= 64 MiB", "通过"],
        ], [43 * mm, 32 * mm, 36 * mm, 38 * mm, 28 * mm]),
        p("每个模型先预热 1 次，再由全新进程正式运行 3 次；时间取中位数，内存取最大峰值。补充实验不覆盖这组冻结 test 结果。"), PageBreak(),
    ]

    # Page 9
    story += [
        section("8 可复现性 项目结构与迭代记录"), subsection("冻结证据"),
        styled_table([
            ["对象", "SHA-256"],
            ["Frozen v1 checkpoint", "ab9ba8b648513530c528ce00345ba1dd8749351c8cf5516dc5ace84f40ad6657"],
            ["student.py", "399ab947a7c9f74cef024a6d601f82914e2dd79c5d16a2c74d96c20ebeabf5c0"],
            ["evaluate.py", "128bcb2dab0be0d427505bddb4671e3ab3a8f78e114be79a689c0f9029af133d"],
            ["tokenizer.json", "020d1bc6aa4449c4f352b2e03d0e0fb4f39287f15297705e421b1fa7d817262e"],
        ], [43 * mm, 134 * mm]), Spacer(1, 4 * mm), subsection("自动检查"),
        styled_table([
            ["检查", "结果", "防止的问题"],
            ["Future-token invariance", "通过", "未来 token 泄漏"],
            ["Normalization and batch independence", "通过", "输出或样本互相污染"],
            ["State reset and shifted loss", "通过", "跨窗口状态或错位目标"],
            ["Trainer schedule sampling selection", "9 tests 通过", "控制项和 best checkpoint 回归"],
        ], [70 * mm, 30 * mm, 77 * mm]), Spacer(1, 4 * mm), subsection("仓库入口"),
        styled_table([
            ["文件", "用途"],
            ["README.md", "两分钟了解结果 目录 安装 复现与限制"],
            ["REQUIREMENTS.md", "课程约束 证据要求和完成清单"],
            ["ABLATION_PROTOCOL.md", "受控变量 决策阈值和报告字段"],
            ["CHANGELOG.md", "按日期记录每次模型和工程迭代"],
            ["EXPERIMENT_REPORT_ZH.md", "中文实验解释与完整证据链"],
            ["code/results/", "机器可读表格 冻结清单 资源与补充总结"],
        ], [53 * mm, 124 * mm]),
        p("Git 仓库使用多个逻辑提交记录 baseline、模型改进、补充消融和文档发布。Checkpoint 不进入 Git 历史，而通过私有 release 作为可下载资产；run 的 metrics、curve、日志和哈希仍保留。"), PageBreak(),
    ]

    # Page 10
    story += [
        section("9 结论 限制与 AI 使用披露"), subsection("结论"),
        p("冻结 v1 在 test 上达到 1.646152 BPB，较基线降低 21.66%，并满足时间、内存和资产约束。受控补充实验说明 SwiGLU 是 block 改进的主要来源；进一步增深或加宽没有改善；RoPE 在两个短训练 seed 上稳定优于 learned position；EMA、MTP 和 untied head 的额外收益不足以抵消复杂度。长训练必须保存预声明 validation 检查点，否则会错过中期最佳权重。"),
        subsection("限制与下一步"),
        styled_table([
            ["限制", "影响", "处理"],
            ["v2 只看 validation", "没有新的 test 结论", "若允许新轮次 先冻结 v2 再一次测试"],
            ["每个长配方仅 3 seeds", "方差估计仍较粗", "预算允许时扩展到 5 seeds"],
            ["训练在 MPS BF16", "权重不保证跨设备逐位一致", "正式评分统一 CPU FP32"],
            ["单机资源测量", "绝对秒数依赖硬件", "使用同机 baseline 比值"],
            ["Checkpoint 不进 Git", "clone 后不能直接评测", "私有 release 提供哈希匹配资产"],
        ], [47 * mm, 62 * mm, 68 * mm]), Spacer(1, 4 * mm), subsection("AI 使用披露"),
        p("OpenAI Codex 协助代码诊断、实验计划、训练器控制、实验运行、结果整理、图表、文档与私有仓库准备。全部训练和评测由项目脚本实际执行；AI 未提供外部训练文本、预训练权重、validation 或 test 答案。提交者负责核验代码、证据和最终提交。"),
        subsection("参考文献"),
        p("[1] S. Merity et al. Pointer Sentinel Mixture Models. ICLR, 2017."),
        p("[2] A. Vaswani et al. Attention Is All You Need. NeurIPS, 2017."),
        p("[3] B. Zhang and R. Sennrich. Root Mean Square Layer Normalization. NeurIPS, 2019."),
        p("[4] N. Shazeer. GLU Variants Improve Transformer. arXiv:2002.05202, 2020."),
        p("[5] J. Su et al. RoFormer. arXiv:2104.09864, 2021."),
        p("[6] I. Loshchilov and F. Hutter. Decoupled Weight Decay Regularization. ICLR, 2019."),
        Spacer(1, 4 * mm), callout("报告边界：1.646152 是冻结 v1 的 test BPB；更低的 RoPE 数字均为冻结后 validation-only 结果。", PALE_TEAL),
    ]
    return story


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        rightMargin=16 * mm, leftMargin=16 * mm,
        topMargin=17 * mm, bottomMargin=15 * mm,
        title="MP1 Final Report",
        author="HKU DASE Student",
        subject="Resource-constrained language modeling on WikiText-2",
    )
    doc.build(build_story(), onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
