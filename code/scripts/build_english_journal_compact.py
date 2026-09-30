#!/usr/bin/env python3
"""Build the ten-page English submission edition of the MP1 report.

The complete journal-format report runs to 33 pages. The course guide caps the
submitted report at ten pages, so this script derives a submission edition from
``DASE7506_Project_1_TECH_Report_English_Journal_Style.docx`` by

* dropping the three appendices (33-run index, wall-chart plate, figure map);
* dropping the secondary figures and tables whose numbers are not needed to
  support the claims (learning-rate loss curves, trainer sweep, capacity cost,
  untied/EMA/MTP detail);
* renumbering the surviving figures and tables so the sequences stay contiguous
  and rewriting every cross-reference through the same mapping;
* renumbering the surviving subsection headings;
* pruning the image parts that are no longer referenced.

Output:
``output/docx/DASE7506_Project_1_TECH_Report_English_Submission_10pg.docx``

Usage:
    python build_english_journal_compact.py
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Cm
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / "output/docx/DASE7506_Project_1_TECH_Report_English_Journal_Style.docx"
TARGET = PROJECT / "output/docx/DASE7506_Project_1_TECH_Report_English_Submission_10pg.docx"

# --------------------------------------------------------------------------- #
# Blocks removed from the complete edition.  Indices follow the full report
# after the duplicated 8.3 paragraph has been deleted.
# --------------------------------------------------------------------------- #
DROP_RANGES = [
    (45, 46),      # Fig. 4 learning-rate sweep (numbers stay in Table 5)
    (53, 68),      # 5.1 loss curves, 5.2 regularization scope
    (70, 71),      # Fig. 7 v1 validation curves
    (92, 93),      # Table 11, redundant with Table 9
    (111, 121),    # Table 14 and 7.1 trainer sweep
    (125, 126),    # Table 16, duplicate of the Table 13 2x2 layout
    (131, 135),    # Fig. 12 and Table 17 capacity cost
    (146, 161),    # 7.5 untied weights, 7.6 EMA and MTP
    (176, 180),    # Fig. 17 and Table 23
    (139, 140),    # Fig. 13 position and weight sharing (numbers stay in Table 12)
    (183, 190),    # 8.2 training-loss section
    (192, 195),    # Fig. 19 and Table 25
    (218, 297),    # Appendices A, B and C
]
DROP_BLANKS = [9, 12, 16, 22, 41, 49, 74, 81, 85, 94, 102, 109, 127, 143, 168, 173, 206]

# Two further paragraphs removed for page margin: one is meta-commentary, the
# other repeats the seed-selection rule already stated in Section 6.
DROP_PROSE = [
    "The decision sequence narrows one question at a time",
    "Finally, seed 17 is selected as validation, and only after freezing",
]

# Old figure / table number -> new number, in document order.
FIG_MAP = {1: 1, 2: 2, 3: 3, 8: 4, 9: 5, 11: 6, 16: 7}
TAB_MAP = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 8: 6, 9: 7, 10: 8, 12: 9,
           13: 10, 18: 11, 21: 12, 22: 13, 26: 14}

# Subsection headings renumbered because their siblings were removed.
HEADING_FIXES = {
    69: ("5.3 Long Training", "5.1 Long Training"),
    122: ("7.2 Splitting", "7.1 Splitting"),
    130: ("7.3 Why Deeper", "7.2 Why Deeper"),
    138: ("7.4 Short experiments", "7.3 Short experiments"),
    191: ("8.3 Pairing", "8.2 Pairing"),
}

# Cross-references repaired before renumbering, so they use the ORIGINAL
# table numbers and are then carried through TAB_MAP like everything else.
TEXT_FIXES = [
    ("Initial baseline", "Table 3 and Table 5", "Table 3 and the Section 5 sweep"),
    ("Ablation of the key mechanism",
     "The 2\u00d72 control in Table 7 and the screening in Table 8",
     "The 2x2 control in Table 13 and the checkpoint screening in Table 21"),
    ("Quality and computational cost analysis",
     "Table 3 and Table 6 with reasons for stopping 58M",
     "Table 3 and Table 4 with the reasons for stopping at 28.91M"),
    ("5x CPU, 4 GiB, and 64 MiB limits", "Table 6", "Table 10 and Table 22"),
]

# --------------------------------------------------------------------------- #
# Condensed prose.  The machine-translated body is verbose; these rewrites keep
# every number and claim while cutting roughly a third of the text so the
# edition fits the ten-page budget.  Keys are the leading words of the original
# paragraph, so the mapping survives any change to the block order.
# --------------------------------------------------------------------------- #
CONDENSE = {
    "Abstract: This project trains a decoder-only Transformer": "Abstract: We train a decoder-only Transformer from random initialization under the "
       "fixed WikiText-2, BPE-2048 and 256-token causal protocol and report two predictors, "
       "both frozen before any test scoring. v1 is an 8-block, width-320 model with learned "
       "positions and tied weights; v2 keeps the same blocks but uses RoPE and selects its "
       "checkpoint on complete validation across three seeds. The frozen v2 predictor reaches "
       "1.611178 test BPB, 23.32% below the 2.101265 baseline and 0.034974 BPB below v1, with "
       "CPU time, peak memory and assets at 3.713x, 1.939 GiB and 40.033 MiB. A tied-budget "
       "ablation attributes most of the gain to the SwiGLU block, and a late-training "
       "regression shows that checkpoints must be chosen on complete validation rather than on "
       "training loss. ",
    "Train the language model from scratch, improve its architecture": "The task is to train a language model from scratch, improve its architecture or "
       "training, and reach the lowest reproducible test bits per byte (BPB) inside the "
       "resource limits. This project trains a compact decoder-only Transformer from random "
       "initialization under the fixed WikiText-2 data, BPE-2048 tokenizer, 256-token "
       "context and causal evaluation protocol.",
    "The goal is to minimize the full test split bits per byte": "The objective is the lowest BPB on the complete test split, with no external text, "
       "no pretrained weights and no tuning on test. Inside each independent window the "
       "model predicts the next token from the preceding text, and every target except the "
       "first token of a split is scored exactly once.",
    "Train is only used to update parameters.": "Training data only updates parameters; validation selects the structure, learning "
       "rate, regularization, seed and checkpoint, and the test split is scored once after "
       "the freeze. Once the seed is chosen, SHA-256 hashes are recorded for the checkpoint, "
       "student.py, evaluate.py and tokenizer.json. Test scores never feed back into the "
       "architecture or the hyperparameter choice.",
    "Fair comparisons fix data, tokenizer, context, batch size": "Fair comparisons hold the data, tokenizer, context, batch size and evaluator fixed, "
       "and every short run processes 9,830,400 training targets. When model size or budget "
       "changes, BPB and compute cost are reported together so extra compute is never booked "
       "as the benefit of a single mechanism.",
    "The frozen v1 model contains 8 decoder blocks": "The frozen v1 model has 8 decoder blocks of width 320 with 4 attention heads. Each "
       "block uses pre-RMSNorm, causal scaled dot-product attention and a SwiGLU feed-forward "
       "network, with no bias in the linear layers; the embedding is tied to the output head, "
       "positions are learned and dropout is 0, giving 10,570,560 parameters. v2 keeps every "
       "block and hyperparameter and only replaces the learned positions with RoPE, changing "
       "the count to 10,488,640. ",
    "The training sample consists of 257 consecutive tokens": "Each sample is a span of 257 consecutive tokens: the first 256 are the input and the "
       "last 256 the targets. A batch holds 32 windows, so each step processes 8,192 targets. "
       "AdamW uses peak LR 1e-3, weight decay 0.1 and betas (0.9, 0.95), warming up over 3% "
       "and then decaying to 10% on a cosine curve with gradient clipping at 1.0. Training "
       "runs on MPS in BF16; all reported scores are recomputed on CPU in FP32. ",
    "Each recipe and seed was independently trained": "Every recipe and seed is trained independently from random initialization. The "
       "28.91M-target long run is retrained with an extended schedule rather than continued "
       "from the 9.83M checkpoint. v1 keeps the final weights; the later RoPE runs "
       "additionally save the best checkpoint from the predeclared validation points.",
    "The course baseline of 2.071087 is the starting point": "The 2.071087 course baseline reproduces the supplied reference and cannot replace "
       "the 2.101695 controlled baseline used here. The block pair first returns 2.91% and "
       "widening to w320 d8 returns a further 10.79%, after which the budget moves to "
       "hyperparameters and training length. Section 7 isolates each component at a tied "
       "budget.",
    "The initial question is:": "The first question is whether replacing the block pays off at a matched parameter "
       "count and target budget. LN+GELU scores 2.101695 and RMSNorm+SwiGLU scores 2.040526, a "
       "0.061169 BPB reduction that justifies the new block. The pair cannot split the "
       "contribution between normalisation and the feed-forward change, so Section 7.1 runs "
       "the 2x2 control. ",
    "Then the model was scaled to w320 d8": "Scaling to w320 d8 lowers the short-budget score to 1.820432; the size of the gain "
       "suggests the smaller model was capacity limited, so the learning rate is re-screened "
       "before any further scaling. Extending the budget lowers the score to 1.622441, but "
       "that step also changes the budget and the schedule, so the 0.197991 gap is not a "
       "purely structural improvement. ",
    "The decision sequence narrows the problem in sequence": "The decision sequence narrows one question at a time: first whether the block pair "
       "helps, then the right size and learning rate, and finally the marginal return of a "
       "longer budget. It is neither a full factorial search nor an exhaustive seed sweep.",
    "After determining w320 d8, we first checked": "With w320 d8 fixed, we first check whether the learning rate limits optimisation. "
       "Across six short runs at seed 17 and 9.83M targets, 1e-3 is lowest and 7.5e-4 trails "
       "by only 0.006146; 1.25e-3, 2e-3 and 4e-3 are all worse, so 1e-3 is fixed for long "
       "training.",
    "Dropout 0.05 raised BPB from 1.820432": "Dropout 0.05 raises the score from 1.820432 to 1.853883 and weight decay 0.2 "
       "returns almost nothing. At this budget stronger regularization is not the priority, "
       "so dropout 0 and weight decay 0.1 are kept and the budget is spent on longer "
       "training. A single parity result cannot be read as proof that the two settings are "
       "equivalent.",
    "After expanding the full training budget from 9.83M": "Extending the budget from 9.83M to 28.91M targets lowers the score from 1.820432 to "
       "1.622441, so the recipe still benefits from more updates. Over the final 7.2M "
       "targets the score improves only from 1.625607 to 1.622441, which is why the 58M run, "
       "at roughly double the cost, was not executed.",
    "Then seed 137 is added, resulting in 1.631858": "Adding seed 137 gives 1.631858. Both seeds support a long-training gain, but the "
       "0.009417 spread shows that initialization still matters. We take the lower "
       "validation seed as prescribed; two seeds support the recipe but cannot estimate "
       "population variance.",
    "seed 17 dropped by about 0.164352": "Between the first two validation points seed 17 falls by 0.164352, then by 0.057641, "
       "and by only 0.003166 at the end. Because the marginal return collapses, the next "
       "seed replicates the recipe instead of doubling the budget. Seed 137 ends at 1.631858, "
       "0.009417 above seed 17, and both curves confirm that the long recipe beats the short "
       "one.",
    "Two predictors were frozen before any test scoring. v1 is the development": "Two predictors were frozen before any test scoring. v1 is the recipe selected on "
       "validation; v2 is the seed-137 RoPE run whose checkpoint is taken at the predeclared "
       "19.66M-target point, with hashes recorded before the test split was scored. Each "
       "freeze records the checkpoint, implementation, evaluator and tokenizer hashes, and "
       "only the frozen configuration is scored. No test result selected, altered or rejected "
       "either predictor. ",
    "Against the course baseline the frozen v1 predictor": "Relative to the course baseline, frozen v1 is 0.455113 BPB lower (21.66%) and "
       "frozen v2 is 0.490087 BPB lower (23.32%). Both score the same targets over the same "
       "raw byte count, so the gaps come from probability quality rather than from a change "
       "in score coverage. The 0.034974 BPB gap between v2 and v1 is measured under one "
       "frozen protocol.",
    "The final V1 seed 17 training time was 1,143 s": "Training v1 took 1,143 s for seed 17 and 1,093 s for seed 137. The 33 retained "
       "non-smoke runs total 15,530 s (about 4.31 hours) by their train_seconds fields, "
       "excluding CPU re-scoring, resource measurement, data preparation and document "
       "generation.",
    "The three long RoPE training sessions recorded approximately": "The three long RoPE runs took about 1,436, 1,399 and 1,349 s. Although the selected "
       "weights come from 19.66M targets, all three searches ran to 28.91M, so the full "
       "search volume is disclosed. Times come from single-machine logs and indicate project "
       "investment, not a hardware-independent mechanism cost.",
    "All three models score the same test text": "All three models score the same test text over the same targets with the same "
       "tokenizer, so the BPB gaps are differences in total predictive negative "
       "log-likelihood on identical text. v2 improves on the baseline by (2.101265 - "
       "1.611178) / 2.101265, about 23.32%, and on v1 by 0.034974 BPB. Token perplexity "
       "falls in step, but the ranking is expressed in BPB.",
    "Measurements use CPU FP32 with four threads": "Measurements use CPU FP32 with four threads and three independent processes after "
       "one warm-up; the median time is reported and peak RSS is the largest value across "
       "processes. Both frozen predictors are measured on the test split under one protocol "
       "on one machine, so their time ratios share a baseline.",
    "The following experiment was completed after the v1 test": "The experiments below were run after the v1 test and use validation only, to explain "
       "the mechanism and to screen later candidates. Short runs are fixed at 9.83M targets "
       "and recorded on MPS. When an extra component returns less than 0.01 BPB it is not "
       "promoted to long training; that threshold controls search cost and is not a "
       "significance test.",
    "With fixed LayerNorm, SwiGLU improved by 0.056130": "With LayerNorm fixed, SwiGLU returns 0.056130 BPB; with GELU fixed, RMSNorm returns "
       "only 0.006411. Most of the block gain therefore comes from the feed-forward "
       "replacement. This group uses seed 17 alone, so a single difference is not evidence "
       "of a stable cross-seed effect.",
    "Accordingly, RMSNorm+SwiGLU is retained": "RMSNorm+SwiGLU is kept as the base block, and swapping the normalisation alone is "
       "dropped as a search direction. The attribution rests on seed 17 and is not yet shown "
       "to hold under a different seed.",
    "After increasing to layer 10, BPB is 1.872762": "Depth 10 scores 1.872762, 0.052330 worse than d8, and width 384 scores 1.829156, "
       "0.008725 worse. Parameters, assets and recorded training time all grow while quality "
       "at this budget does not, so w320 d8 is retained.",
    "This result only negates the priority of": "This only rejects the priority of scaling immediately at matched targets and "
       "hyperparameters; a larger model may need a different learning rate or a longer "
       "budget, which the current runs do not cover. The search budget therefore moves to the "
       "positional representation.",
    "Replacing learned position with RoPE while continuing": "Replacing learned positions with RoPE while keeping tied input/output weights lowers "
       "the score from 1.820432 to 1.754858, a 0.065574 gain. Untying the head also helps but "
       "adds a large output matrix. RoPE tied needs about 40.033 MiB, slightly less than the "
       "40.345 MiB of learned tied, so RoPE is promoted to a long-training candidate.",
    "seed 137 was registered as a candidate on the lowest": "Seed 137 is registered as the candidate on the lowest CPU FP32 validation score, "
       "1.588095 BPB. Resource measurement used the validation split, four threads, one "
       "warm-up and three independent process repeats, and the checkpoint hash was recorded. "
       "The candidate has since been frozen as v2 and scored once on test; the manifest "
       "records the hashes and the pre-test freeze timestamp.",
    "The initial long training reached 1.620751 near 19.66M": "The first long run reaches 1.620751 near 19.66M targets but ends at 1.634776, a "
       "regression of about 0.014025. Because only the last checkpoint was saved, the "
       "intermediate score could not be submitted, so independent re-runs were started under "
       "a new saving rule.",
    "The new run pre-declares three complete validation points": "The re-run predeclares three validation points at 9.83M, 19.66M and 28.91M targets, "
       "saves the weights at each improvement and still completes the full search budget. "
       "This separates the training investment from the point at which the submitted weights "
       "were produced.",
    "Among the two common seeds the long RoPE recipe averages": "Across the two shared seeds the long RoPE recipe averages about 0.032644 BPB below "
       "v1 in MPS validation; adding seed 233 gives a three-seed mean of 1.600116 with a "
       "sample standard deviation of 0.011642. The paired two-seed mean and the three-seed "
       "summary answer different questions and must not be mixed.",
    "The CPU FP32 validation of seed 137 is 1.588095, so the run": "The CPU FP32 validation of seed 137 is 1.588095, so that run is registered as the "
       "v2 candidate, frozen with recorded hashes and scored once on test at 1.611178 BPB. "
       "The paired gap also includes the change of positional representation and of "
       "checkpoint rule, so it is not an isolated RoPE effect.",
    "Course fixed code, data, and tokenizer are checked via manifest": "Course code, data and tokenizer are checked through manifest hashes. Evaluation caches "
       "no validation or test answers, sees no future tokens, keeps no cross-window state and "
       "needs no network. Contract tests cover causality, probability normalisation, sample "
       "independence, window reset, misaligned target gradients and the final short window; "
       "trainer tests cover sampling, the schedule and best-checkpoint retention. ",
    "The v1 freeze checkpoint is at code/runs/a_e8_lr1e3": "The v1 checkpoint is code/runs/a_e8_lr1e3/checkpoint.pt, SHA-256 ab9ba8b6...6657; the "
       "v2 checkpoint is code/runs/2026-09-25_rope_long_best_seed137/checkpoint.pt, SHA-256 "
       "723b8f6f...4e68. Scores, resource measurements and freeze manifests are under "
       "code/results/2026-09-23/ and code/results/2026-09-26/. Environment: Python 3.13.12, "
       "PyTorch 2.7.1, NumPy 2.5.3 and tokenizers 0.21.4; Python 3.12 is recommended for "
       "release. ",
    "Two predictors were frozen before any test scoring. Frozen v1 lowers": "Two predictors were frozen before any test scoring: v1 lowers test BPB from 2.101265 "
       "to 1.646152 and v2 lowers it further to 1.611178, 23.32% below the baseline, with CPU "
       "time, memory and assets all inside their limits. The study keeps the efficient block "
       "pair, scales capacity, then fixes the learning rate, the regularization and the "
       "budget. A tied-budget control attributes most of the block gain to SwiGLU; the "
       "positional experiments and the late-training regression produce RoPE and the "
       "best-checkpoint rule. ",
    "The three RoPE seeds reach a mean CPU FP32 validation": "The three RoPE seeds average 1.600116 in CPU FP32 validation with a sample standard "
       "deviation of 0.011642; seed 137 is lowest at 1.588095 and inside the resource "
       "thresholds, and freezing it yields the 1.611178 test score. Negative results also "
       "shaped the path: deeper and wider models were dropped, and untied weights, EMA and "
       "MTP were stopped below the 0.01 BPB threshold.",
    "v1 only compared two seeds, RoPE long training compared three": "v1 compares two seeds, the RoPE long recipe three and most short ablations only seed "
       "17, so differences of a few thousandths remain uncertain and 0.01 BPB is a search "
       "threshold rather than a significance bound. The RoPE recipe also changes checkpoint "
       "selection, so the long-training gain is not attributable to position encoding alone. "
       "No 58M run was made, so a longer recalibrated budget is not excluded. ",
    "Training runs on MPS BF16 while official scores": "Training runs on MPS BF16 while official scores use CPU FP32, and not every short "
       "screen is re-verified on CPU. Resources are measured on one machine, so absolute "
       "times depend on hardware and load. Both frozen predictors are now measured on the "
       "test split under a single protocol.",
    "OpenAI Codex assisted with code diagnosis": "OpenAI Codex assisted with code diagnosis, experiment planning, implementation review, "
       "script repair, result consolidation, figures and layout. Every training and evaluation "
       "number was produced by the project scripts and kept as machine-readable evidence. "
       "Codex supplied no external text, pretrained weights, or validation or test answers. "
       "The submitter is responsible for understanding the code and checking the evidence. ",
}

SUBTITLE = "WikiText-2 model optimization; the frozen v2 predictor reaches 1.611178 test BPB"

# A4 with 3.175 cm side margins leaves 14.65 cm of text width. Journal figures
# are set narrower than the measure, and the tall flowchart is capped by height.
MAX_FIG_WIDTH = Cm(9.2)
MAX_FIG_HEIGHT = Cm(6.2)

NOTE_AFTER_ABSTRACT = (
    "The complete run index, all 33 retained experiments and the extended figure "
    "plate stay in the repository; this edition is the ten-page submission report."
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def iter_blocks(doc):
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def drop_set() -> set[int]:
    dropped = set(DROP_BLANKS)
    for start, end in DROP_RANGES:
        dropped.update(range(start, end + 1))
    return dropped


def remap(text: str) -> str:
    """Apply the figure/table renumbering to a piece of prose."""
    def fig(m):
        return f"Fig. {FIG_MAP[int(m.group(1))]}" if int(m.group(1)) in FIG_MAP else m.group(0)

    def tab(m):
        return f"Table {TAB_MAP[int(m.group(1))]}" if int(m.group(1)) in TAB_MAP else m.group(0)

    text = re.sub(r"Fig\.\s*(\d+)", fig, text)
    text = re.sub(r"Table\s+(\d+)", tab, text)
    return text


def set_caption(paragraph, text: str) -> None:
    paragraph.clear()
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Pt(0)
    fmt.space_before = Pt(2)
    fmt.space_after = Pt(5)
    fmt.keep_together = True
    match = re.match(r"^((?:Fig\.|Table)\s*\d+\.)\s*(.*)$", text)
    lead_text, body_text = (match.group(1), match.group(2)) if match else ("", text)
    if lead_text:
        lead = paragraph.add_run(f"{lead_text} ")
        lead.bold = True
        lead.font.size = Pt(9)
        lead.font.color.rgb = RGBColor.from_string("252B2F")
    body = paragraph.add_run(body_text)
    body.font.size = Pt(9)
    body.font.color.rgb = RGBColor.from_string("252B2F")


def prune_media(path: Path) -> None:
    """Drop image parts that no paragraph still references."""
    with zipfile.ZipFile(path) as z:
        document = z.read("word/document.xml").decode("utf-8")
        rels = z.read("word/_rels/document.xml.rels").decode("utf-8")
        payload = {name: z.read(name) for name in z.namelist()}

    used = set(re.findall(r'r:embed="(rId\d+)"', document))
    kept, removed = [], []
    for rel in re.findall(r"<Relationship\b[^>]*/>", rels):
        rid = re.search(r'Id="(rId\d+)"', rel).group(1)
        target = re.search(r'Target="([^"]+)"', rel).group(1)
        if target.startswith("media/") and rid not in used:
            removed.append(target)
            continue
        kept.append(rel)
    new_rels = re.sub(
        r"(<Relationships\b[^>]*>).*?(</Relationships>)",
        lambda m: m.group(1) + "".join(kept) + m.group(2),
        rels,
        flags=re.S,
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as out:
        for name, data in payload.items():
            if name == "word/_rels/document.xml.rels":
                out.writestr(name, new_rels)
                continue
            if any(name.endswith(t) for t in removed):
                continue
            out.writestr(name, data)
    return len(removed)


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #
def main() -> None:
    shutil.copy2(SOURCE, TARGET)
    doc = Document(TARGET)
    blocks = list(iter_blocks(doc))
    dropped = drop_set()

    # ---- heading renumbering before anything moves ------------------------ #
    for index, (old_prefix, new_prefix) in HEADING_FIXES.items():
        if index < len(blocks):
            block = blocks[index]
            if isinstance(block, Paragraph) and block.text.startswith(old_prefix):
                block.text = block.text.replace(old_prefix, new_prefix, 1)

    # ---- subtitle; the draft version note becomes the scope note ---------- #
    if len(blocks) > 1 and isinstance(blocks[1], Paragraph):
        blocks[1].text = SUBTITLE
    if len(blocks) > 3 and isinstance(blocks[3], Paragraph):
        blocks[3].text = NOTE_AFTER_ABSTRACT

    # ---- remove the dropped blocks ---------------------------------------- #
    for index in sorted(dropped, reverse=True):
        if index >= len(blocks):
            continue
        block = blocks[index]
        element = block._p if isinstance(block, Paragraph) else block._tbl
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    # ---- condense the verbose prose --------------------------------------- #
    blocks = list(iter_blocks(doc))
    for block in blocks:
        if isinstance(block, Paragraph) and " ".join(block.text.split()).startswith(tuple(DROP_PROSE)):
            block._p.getparent().remove(block._p)
    blocks = list(iter_blocks(doc))
    for block in blocks:
        if not isinstance(block, Paragraph):
            continue
        text = " ".join(block.text.split())
        for prefix, replacement in CONDENSE.items():
            if text.startswith(prefix):
                block.text = replacement
                break

    doc.save(TARGET)

    # ---- renumber captions and rewrite cross-references ------------------- #
    doc = Document(TARGET)
    blocks = list(iter_blocks(doc))
    containers: list[Paragraph] = []
    for block in blocks:
        if isinstance(block, Paragraph):
            containers.append(block)
        else:
            for row in block.rows:
                for cell in row.cells:
                    containers.extend(cell.paragraphs)

    for block in blocks:
        if not isinstance(block, Table):
            continue
        for row in block.rows:
            label = row.cells[0].text
            for needle, old, new in TEXT_FIXES:
                if needle in label and old in row.cells[1].text:
                    row.cells[1].text = row.cells[1].text.replace(old, new)

    for paragraph in containers:
        text = " ".join(paragraph.text.split())
        if not text:
            continue
        fixed = remap(text)
        if fixed != text:
            paragraph.text = fixed

    fig_no = 0
    tab_no = 0
    for block in blocks:
        if not isinstance(block, Paragraph):
            continue
        text = " ".join(block.text.split())
        match = re.match(r"^(Fig\.|Table)\s*(\d+)\.\s*(.*)$", text)
        if not match:
            continue
        kind, _, rest = match.groups()
        if kind == "Fig.":
            fig_no += 1
            set_caption(block, f"Fig. {fig_no}. {rest}")
        else:
            tab_no += 1
            set_caption(block, f"Table {tab_no}. {rest}")

    # ---- tighten body spacing to buy page margin --------------------------- #
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    for block in blocks:
        if not isinstance(block, Paragraph):
            continue
        text = " ".join(block.text.split())
        if not text or block.style.name.startswith("Heading") or block.style.name == "Title":
            continue
        fmt = block.paragraph_format
        fmt.line_spacing = 1.0
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(4)
        if re.match(r"^(Fig\.|Table)\s*\d+\.", text):
            block.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # ---- size the figures so the edition fits the page budget -------------- #
    for shape in doc.inline_shapes:
        aspect = shape.width / shape.height
        width = min(MAX_FIG_WIDTH, MAX_FIG_HEIGHT * aspect)
        shape.width = int(width)
        shape.height = int(width / aspect)

    # ---- keep every table centred and compact ------------------------------ #
    from docx.shared import Pt as _Pt
    for block in blocks:
        if not isinstance(block, Table):
            continue
        block.alignment = WD_TABLE_ALIGNMENT.CENTER
        for row in block.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_after = _Pt(0)
                    paragraph.paragraph_format.line_spacing = 1.0
                    for run in paragraph.runs:
                        run.font.size = _Pt(8)

    # ---- let the text run on from section to section ---------------------- #
    # The parent edition is already continuous; this pass only guards against a
    # rebuilt source reintroducing the inherited per-heading page breaks.
    removed = 0
    for element in doc.element.body.iter(qn("w:pageBreakBefore")):
        element.getparent().remove(element)
        removed += 1
    for element in doc.element.body.iter(qn("w:br")):
        if element.get(qn("w:type")) == "page":
            element.getparent().remove(element)
            removed += 1
    for pPr in doc.element.body.iter(qn("w:pPr")):
        if len(pPr) == 0:
            pPr.getparent().remove(pPr)
    if removed:
        print(f"removed {removed} forced page breaks")

    doc.core_properties.title = "DASE7506 Project 1 Technical Report (English submission edition)"
    doc.core_properties.comments = "Ten-page submission edition; frozen v2 test BPB 1.611178."
    doc.save(TARGET)

    removed = prune_media(TARGET)
    print(f"wrote {TARGET}  ({fig_no} figures, {tab_no} tables, {removed} unused images removed)")


if __name__ == "__main__":
    main()
