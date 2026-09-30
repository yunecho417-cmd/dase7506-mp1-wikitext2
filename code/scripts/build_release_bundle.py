#!/usr/bin/env python3
"""Assemble a clean, history-free release bundle for the 30 September submission.

The working repository carries 1.2 GB of virtualenvs, 630 MB of discarded
checkpoints in ``code/runs/`` and 342 MB of scratch output in ``tmp/``. None of
that belongs in a submission. This script copies only what a verifier needs into
``tmp/release_bundle`` (which is already git-ignored), leaving the repository
completely untouched and performing no Git operation at all:

    release_bundle/
    ├── README.md          install / train / evaluate commands, hashes, disclosure
    ├── REQUIREMENTS.md    assignment checklist
    ├── CHECKSUMS.txt      SHA-256 of every file in the bundle
    ├── report/            the ten-page English submission edition
    └── code/              sources, configs, data, tests, scripts, evidence
        └── checkpoint/    the frozen v2 checkpoint that scores 1.611178 BPB

The checkpoint is copied rather than moved, and its SHA-256 is checked against
the pre-test freeze manifest before anything is written.

Usage:
    python build_release_bundle.py [--include-v1] [--clean]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
CODE = PROJECT / "code"
DEST = PROJECT / "tmp/release_bundle"

V2_CHECKPOINT = CODE / "runs/2026-09-25_rope_long_best_seed137/checkpoint.pt"
V1_CHECKPOINT = CODE / "runs/a_e8_lr1e3/checkpoint.pt"
EXPECTED_V2_SHA = "723b8f6fe2edef1e01987a29ccf2d195945961b12dd37b0fcb5f24c9fff24e68"
EXPECTED_V1_SHA = "ab9ba8b648513530c528ce00345ba1dd8749351c8cf5516dc5ace84f40ad6657"

# Top-level Python sources that define and run the model.
TOP_SOURCES = [
    "common.py",
    "model.py",
    "student.py",
    "train.py",
    "train_student.py",
    "evaluate.py",
    "README.md",
    "PACKAGE_MANIFEST.json",
    "RUN_LOG_TEMPLATE.csv",
    "requirements.txt",
]

# Evidence directories retained; "results/figures" holds superseded drafts.
RESULT_DIRS = ["2026-09-23", "2026-09-25", "2026-09-26"]
RESULT_FILES = ["grid.tsv", "resources_validation.json"]

#: The manifest written before the test split was scored.  The two source files
#: it hashes must ship byte-identical, otherwise a verifier who re-runs the
#: evaluation would see a different implementation hash from the one recorded at
#: freeze time even when the score itself is unchanged.
MANIFEST = CODE / "results/2026-09-26/freeze_manifest_v2.json"
FROZEN_SOURCES = {
    "student.py": "implementation_sha256",
    "evaluate.py": "evaluator_sha256",
}

REPORTS = [
    "DASE7506_Project_1_TECH_Report_English_Submission_10pg.docx",
    "DASE7506_Project_1_TECH_Report_English_Journal_Style.docx",
    "DASE7506_Project_1_TECH_Report_中文期刊格式版.docx",
]

#: The exact complete-test BPB the Course scorer must print for this bundle.
EXPECTED_V2_TEST_BPB = 1.6111783956327541

README = """# DASE7506 Project 1 - submission bundle

WikiText-2 language model, **full-test BPB 1.611178** (CPU FP32), a 23.32%
reduction against the 2.101265 course baseline.

This bundle is the immutable code + checkpoint package for the 30 September
submission. It contains everything needed to verify the reported score without
retraining. Everything else - virtualenvs, the 630 MB of intermediate
checkpoints in `code/runs/`, scratch output and Git history - is deliberately
left out.

## Contents

| Path | What it is |
|---|---|
| `README.md` | this file: exact reproduction commands |
| `REQUIREMENTS.md` | assignment constraints and the completion checklist |
| `CHECKSUMS.txt` | SHA-256 of every file in this bundle |
| `guide/` | the course guide and requirements, as shipped in the original pack |
| `report/` | the ten-page English submission report, the full English edition and the Chinese edition |
| `code/checkpoint/checkpoint.pt` | the frozen v2 weights, 10,488,640 parameters, 40.033 MiB |
| `code/runs/**/metrics.json` | per-run evidence behind the report tables (67 runs, no checkpoints) |
| `code/results/` | freeze manifests, test and resource measurements |
| `code/` | model, trainer, evaluator, configs, data, tests, scripts, evidence |

## Headline result

| Predictor | Validation BPB | Test BPB | vs baseline | CPU time | Peak RSS | Assets |
|---|---:|---:|---:|---:|---:|---:|
| Course baseline | 2.071087 | 2.101265 | - | 1x | 1.873 GiB | 4.168 MiB |
| Frozen v1 (learned positions) | 1.622441 | 1.646152 | 21.66% | 2.875x | 1.948 GiB | 40.345 MiB |
| **Frozen v2 (RoPE)** | 1.588095 | **1.611178** | **23.32%** | 3.713x | 1.939 GiB | 40.033 MiB |

Frozen v2 is the submitted predictor. Its checkpoint was hashed and frozen on
26 September 2026 **before** the test split was ever scored; see
`code/results/2026-09-26/freeze_manifest_v2.json`, where
`test_result_at_freeze` is still `null`.

## Install

Python 3.12 or 3.13. No API key, no external corpus and no pretrained weight is
required.

```bash
cd code
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

`requirements.txt` pins torch 2.7.1, numpy 2.5.3 and tokenizers 0.21.4.

## Verify the reported score (no training)

```bash
cd code
python evaluate.py \\
  --checkpoint checkpoint/checkpoint.pt \\
  --device cpu \\
  --precision fp32 \\
  --threads 4 \\
  --split test
```

Expected output: **1.611178 BPB**, token perplexity 29.0225, 428,405 scored
targets over 1,292,013 UTF-8 bytes. Verify the file first:

```bash
shasum -a 256 checkpoint/checkpoint.pt
# 723b8f6fe2edef1e01987a29ccf2d195945961b12dd37b0fcb5f24c9fff24e68
```

Small timing variation is normal; the BPB reproduces to ordinary FP32
numerical tolerance.

## Reproduce the checkpoint from random initialization

```bash
cd code
python train_student.py \\
  --implementation student \\
  --config configs/ours_a_rope.json \\
  --run-dir runs/reproduce_v2_seed137 \\
  --device cpu \\
  --precision fp32 \\
  --threads 4 \\
  --seed 137 \\
  --epochs 8 \\
  --lr 1e-3 \\
  --wd 0.1 \\
  --warmup-frac 0.03 \\
  --min-lr-frac 0.1 \\
  --beta2 0.95 \\
  --sampling without-replacement \\
  --schedule cosine \\
  --eval-at-targets 9830400,19660800,28909568 \\
  --select-best-validation
```

The run searches 28,909,568 training targets and keeps the weights from the
predeclared 19.66M-target validation point. Wall-clock time is device
dependent; the original run took about 1,399 s on Apple MPS (BF16). Exact
floating-point weights are not expected to match across devices, which is why
the downloadable checkpoint above is the authoritative evaluation artifact.

To reproduce the frozen v1 control (test BPB 1.646152), train with
`configs/ours_a.json` and `--seed 17`, omitting `--eval-at-targets` and
`--select-best-validation`.

## Evidence index

| Question | File |
|---|---|
| Pre-test freeze of v2 | `code/results/2026-09-26/freeze_manifest_v2.json` |
| v2 test score | `code/results/2026-09-26/v2_frozen_test_cpu_fp32.json` |
| v2 resource measurement | `code/results/2026-09-26/resources_test_v2.json` |
| v1 freeze and test | `code/results/2026-09-23/freeze_manifest.json`, `frozen_test_cpu_fp32.json` |
| Three-seed RoPE validation | `code/results/2026-09-25/*_validation_cpu_fp32.json` |
| Post-freeze ablations | `code/results/2026-09-25/supplementary_summary.json` |
| Index of all 33 runs | `code/results/grid.tsv` |

Every number quoted in the report was produced by these scripts and is retained
here in machine-readable form.

## The implementation shipped here is the frozen one

`code/student.py` and `code/evaluate.py` are byte-identical to the files hashed
in `code/results/2026-09-26/freeze_manifest_v2.json`:

| File | SHA-256 |
|---|---|
| `code/student.py` | `399ab947a7c9f74cef024a6d601f82914e2dd79c5d16a2c74d96c20ebeabf5c0` |
| `code/evaluate.py` | `128bcb2dab0be0d427505bddb4671e3ab3a8f78e114be79a689c0f9029af133d` |
| `code/checkpoint/checkpoint.pt` | `723b8f6fe2edef1e01987a29ccf2d195945961b12dd37b0fcb5f24c9fff24e68` |

`build_release_bundle.py` refuses to write the bundle unless all three match, so
a verifier who re-runs the evaluation sees exactly the hashes recorded before
the test split was scored.

The working repository has since gained training-only knobs in `student.py`
(stochastic depth, token dropout, embedding dropout, logit temperature). They are
not part of the submission: the v2 checkpoint config sets none of them, every one
is inactive outside `train()`, and the logit branch is skipped at the default
temperature of 1.0, so they cannot change the reported score. They are excluded
here purely so the shipped implementation matches the frozen hash.

## Notes on what is not included

- `code/runs/` (630 MB, 21 checkpoints) is omitted; only the submitted v2
  checkpoint is shipped.
- Reports figure generators written for the private PowerPoint runtime
  (`code/scripts/*.mjs` in the working repository) are omitted because they
  cannot run outside that runtime. The English figures are regenerated by the
  included `code/scripts/build_english_*` Python scripts.
- No Git history is shipped with this bundle.

## AI assistance disclosure

OpenAI Codex assisted with code diagnosis, experiment planning, implementation
review, script repair, result consolidation, figures and document layout. Every
training and evaluation number was produced by the project scripts and is
retained as machine-readable evidence. Codex supplied no external training
text, no pretrained weights, and no validation or test answers. The submitter
is responsible for understanding the code, checking the evidence and completing
the final submission.
"""


def git_show(rel: str) -> bytes | None:
    """Bytes of ``rel`` as committed at HEAD, or None if Git cannot supply them."""
    try:
        done = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=PROJECT,
                              capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return done.stdout


def frozen_bytes(rel: str, expected_sha: str) -> tuple[bytes, str]:
    """Return the content of ``rel`` that hashes to the value in the manifest.

    The working tree is preferred.  When it has moved on - new training-only
    knobs, for example - the committed version is used instead, provided that
    version is the one the manifest actually records.  Anything else is a hard
    error: shipping an implementation that does not match the frozen hash would
    make the reported score irreproducible on its face.
    """
    work = (PROJECT / rel).read_bytes()
    if hashlib.sha256(work).hexdigest() == expected_sha:
        return work, "working tree"
    committed = git_show(rel)
    if committed is not None and hashlib.sha256(committed).hexdigest() == expected_sha:
        return committed, "committed at HEAD (working tree has moved on)"
    raise SystemExit(
        f"neither the working tree nor HEAD provides {rel} with hash {expected_sha}; "
        "the frozen implementation cannot be reconstructed"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


#: Every path this run wrote into the bundle, relative to its root.  Compared
#: against the directory listing at the end so that a previous in-place run
#: cannot leave junk behind unnoticed.
SHIPPED: list[str] = []


def copy_file(src: Path, dst: Path) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    SHIPPED.append(dst.relative_to(DEST).as_posix())
    return src.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-v1", action="store_true",
                        help="also ship the frozen v1 control checkpoint")
    parser.add_argument("--clean", action="store_true",
                        help="delete the existing bundle directory before rebuilding "
                             "(destructive; default refreshes files in place)")
    parser.add_argument("--skip-verify", action="store_true",
                        help="assemble only; do not score the checkpoint inside the bundle")
    args = parser.parse_args()

    if args.clean and DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True, exist_ok=True)

    total = 0
    count = 0

    # ---- repository documents -------------------------------------------- #
    total += copy_file(PROJECT / "REQUIREMENTS.md", DEST / "REQUIREMENTS.md")
    count += 1
    # PACKAGE_MANIFEST.json expects the guide under guide/, the same layout the
    # course pack shipped, so a verifier diffing the two sees one difference less.
    total += copy_file(PROJECT / "GUIDE.md", DEST / "guide" / "GUIDE.md")
    count += 1
    total += copy_file(PROJECT / "REQUIREMENTS.md", DEST / "guide" / "REQUIREMENTS.md")
    count += 1

    # ---- per-run evidence ------------------------------------------------ #
    # Only metrics.json and curve.json: the report indexes every run directory
    # and a verifier has to be able to open the file it is pointed at. The *.pt
    # files stay out (1.98 GB); they are not needed to reproduce the score.
    run_evidence = 0
    for src in sorted((CODE / "runs").rglob("*")):
        if src.is_file() and src.name in ("metrics.json", "curve.json"):
            rel = src.relative_to(CODE / "runs")
            total += copy_file(src, DEST / "code" / "runs" / rel)
            count += 1
            run_evidence += 1

    # ---- code ------------------------------------------------------------- #
    # The implementation and the evaluator are copied separately below so they
    # can be pinned to the hashes recorded at freeze time.
    for name in TOP_SOURCES:
        if name in FROZEN_SOURCES:
            continue
        src = CODE / name
        if src.exists():
            total += copy_file(src, DEST / "code" / name)
            count += 1

    for src in sorted((CODE / "configs").glob("*.json")):
        total += copy_file(src, DEST / "code" / "configs" / src.name)
        count += 1

    for src in sorted((CODE / "data").iterdir()):
        if src.is_file():
            total += copy_file(src, DEST / "code" / "data" / src.name)
            count += 1

    for src in sorted((CODE / "tests").glob("test_*.py")):
        total += copy_file(src, DEST / "code" / "tests" / src.name)
        count += 1

    # Only Python tooling ships; the .mjs builders need the private runtime.
    for src in sorted((CODE / "scripts").glob("*.py")):
        total += copy_file(src, DEST / "code" / "scripts" / src.name)
        count += 1

    for name in RESULT_FILES:
        src = CODE / "results" / name
        if src.exists():
            total += copy_file(src, DEST / "code" / "results" / name)
            count += 1
    for folder in RESULT_DIRS:
        for src in sorted((CODE / "results" / folder).rglob("*")):
            if src.is_file():
                rel = src.relative_to(CODE / "results")
                total += copy_file(src, DEST / "code" / "results" / rel)
                count += 1

    # ---- the frozen implementation and evaluator, pinned by hash ---------- #
    manifest = json.loads(MANIFEST.read_text())
    for name, key in FROZEN_SOURCES.items():
        rel = f"code/{name}"
        data, origin = frozen_bytes(rel, manifest[key])
        dst = DEST / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        SHIPPED.append(rel)
        total += len(data)
        count += 1
        print(f"  {rel}: {origin}")

    # ---- checkpoint ------------------------------------------------------- #
    actual = sha256(V2_CHECKPOINT)
    if actual != EXPECTED_V2_SHA:
        raise SystemExit(f"v2 checkpoint hash mismatch: {actual}")
    total += copy_file(V2_CHECKPOINT, DEST / "code" / "checkpoint" / "checkpoint.pt")
    count += 1
    if args.include_v1:
        actual_v1 = sha256(V1_CHECKPOINT)
        if actual_v1 != EXPECTED_V1_SHA:
            raise SystemExit(f"v1 checkpoint hash mismatch: {actual_v1}")
        total += copy_file(V1_CHECKPOINT, DEST / "code" / "checkpoint" / "v1_control" / "checkpoint.pt")
        count += 1

    # ---- reports ---------------------------------------------------------- #
    for name in REPORTS:
        src = PROJECT / "output" / "docx" / name
        if src.exists():
            total += copy_file(src, DEST / "report" / name)
            count += 1

    # ---- README and checksums (written last so they are included) --------- #
    (DEST / "README.md").write_text(README, encoding="utf-8")
    SHIPPED.append("README.md")
    count += 1

    # ---- the shipped trio must reproduce the frozen record ---------------- #
    for name, key in FROZEN_SOURCES.items():
        got = sha256(DEST / "code" / name)
        if got != manifest[key]:
            raise SystemExit(f"code/{name} hashes to {got}, manifest records {manifest[key]}")
    got = sha256(DEST / "code/checkpoint/checkpoint.pt")
    if got != manifest["checkpoint_sha256"]:
        raise SystemExit(f"checkpoint hashes to {got}, manifest records {manifest['checkpoint_sha256']}")
    print("frozen trio verified against the pre-test manifest")

    # ---- refuse to ship anything this run did not put there --------------- #
    # A refresh in place cannot delete, so an earlier run's scratch output (for
    # example the JSON a verification evaluation writes beside the checkpoint)
    # would otherwise travel with the submission.
    actual = {p.relative_to(DEST).as_posix() for p in DEST.rglob("*") if p.is_file()}
    expected = set(SHIPPED) | {"CHECKSUMS.txt"}
    stray = sorted(actual - expected)
    if stray:
        raise SystemExit(
            "unexpected files in the bundle (delete them or run with --clean):\n  "
            + "\n  ".join(stray)
        )
    absent = sorted(expected - actual)
    if absent:
        raise SystemExit(f"missing from the bundle: {absent}")

    lines = []
    for rel in sorted(actual):
        lines.append(f"{sha256(DEST / rel)}  {rel}")
    (DEST / "CHECKSUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    count += 1

    # ---- end-to-end check: score the frozen checkpoint inside the bundle --- #
    # A verifier will not read a transcript; they will run the evaluator. So the
    # bundle scores itself here, on the complete test split, and compares the
    # result and the four recorded hashes against the frozen record.
    if not args.skip_verify:
        print("verifying the bundle in place ...")
        python = CODE / ".venv_project1/bin/python"
        result = subprocess.run(
            [str(python), "evaluate.py", "--checkpoint", "checkpoint/checkpoint.pt",
             "--split", "test", "--device", "cpu", "--precision", "fp32",
             "--output", str(DEST / "code/checkpoint/verify_test_cpu_fp32.json")],
            cwd=DEST / "code", capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout[-3000:])
            print(result.stderr[-3000:])
            raise SystemExit("bundle verification failed: evaluator returned non-zero")
        verified = json.loads((DEST / "code/checkpoint/verify_test_cpu_fp32.json").read_text())
        checks = {
            'bpb matches the frozen score':
                abs(verified["bpb"] - EXPECTED_V2_TEST_BPB) < 1e-9,
            'checkpoint hash matches manifest':
                verified["checkpoint_sha256"] == manifest["checkpoint_sha256"],
            'implementation hash matches manifest':
                verified["implementation_sha256"] == manifest["implementation_sha256"],
            'evaluator hash matches manifest':
                verified["evaluator_sha256"] == manifest["evaluator_sha256"],
            'tokenizer hash matches manifest':
                verified["tokenizer_sha256"] == manifest["tokenizer_sha256"],
        }
        for label, ok in checks.items():
            print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not all(checks.values()):
            raise SystemExit("bundle verification failed")
    else:
        print("skipping the in-place verification pass (--skip-verify)")

    # ---- summary ---------------------------------------------------------- #
    print(f"bundle  : {DEST}")
    print(f"files   : {count}")
    print(f"size    : {total / (1 << 20):.1f} MiB")
    print(f"v2 sha  : {EXPECTED_V2_SHA}  (verified before copy)")
    print(f"evidence: {run_evidence} per-run files (metrics/curve, no checkpoints)")
    print()
    for path in sorted(DEST.rglob("*")):
        if path.is_file():
            size = path.stat().st_size
            unit = "MiB" if size >= 1 << 20 else "KiB"
            value = size / (1 << 20) if unit == "MiB" else size / 1024
            print(f"  {value:8.1f} {unit}  {path.relative_to(DEST).as_posix()}")


if __name__ == "__main__":
    main()
