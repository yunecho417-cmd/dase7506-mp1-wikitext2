"""Build the v3 release bundle that the course submission links to.

What the course asks for (GUIDE section 4 and code/README.md section 5):

* immutable code with exact installation, training and evaluation instructions;
* the matching checkpoint bundle, evaluable **without retraining**;
* a report of at most 10 pages, inside the code repository;
* all inference assets downloadable for verification;
* training, seed and search costs disclosed.

This script assembles all of that, deliberately excluding anything that would
make the score irreproducible on its face:

* `code/runs/**/*.pt` is omitted (1.98 GB across 54 files); only the frozen
  submitted checkpoint ships;
* `code/runs/**/metrics.json` **is** included (about 300 KB) because the report's
  appendix indexes those files and a verifier must be able to check them;
* the output directory is separate from the v2 bundle so that one is preserved.

It then verifies itself: it re-runs the supplied evaluator inside the bundle on
the complete test split and compares the four recorded hashes.

Usage
-----
    ./.venv_project1/bin/python scripts/build_release_bundle.py_v3 [--clean]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
CODE = PROJECT / 'code'
DEST = PROJECT / 'tmp/release_bundle_v3'
ZIP = PROJECT / 'tmp/release_bundle_v3.zip'

V3_CHECKPOINT = CODE / 'runs/2026-09-26_phase8/p8_bs4_lr1500/checkpoint_calibrated.pt'
V3_MANIFEST = CODE / 'results/2026-09-26/freeze_manifest_v3.json'
REPORTS = [
    ('DASE7506_Project_1_TECH_Report_English_v3_Submission_10pg.docx',
     'the ten-page English submission edition (the one the course limits apply to)'),
    ('DASE7506_Project_1_TECH_Report_中文_v3_10页版.docx',
     'the ten-page Chinese submission edition'),
    ('DASE7506_Project_1_TECH_Report_English_v3版.docx',
     'the full English edition'),
    ('DASE7506_Project_1_TECH_Report_中文_v3版.docx',
     'the full Chinese edition'),
]
CODE_FILES = [
    'README.md', 'requirements.txt', 'PACKAGE_MANIFEST.json', 'RUN_LOG_TEMPLATE.csv',
    'common.py', 'evaluate.py', 'model.py', 'student.py',
    'train.py', 'train_student.py',
]
RESULT_ENTRIES = ['grid.tsv', '2026-09-23', '2026-09-25', '2026-09-26']


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(src: Path, dst: Path, counter: list) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    counter[0] += 1
    counter[1] += dst.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true',
                        help='delete the existing bundle directory before rebuilding '
                             '(destructive; default refreshes files in place)')
    args = parser.parse_args()

    if args.clean and DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True, exist_ok=True)
    counter = [0, 0]

    # ---- guide and fixed package files ------------------------------------ #
    copy_file(PROJECT / 'GUIDE.md', DEST / 'guide/GUIDE.md', counter)
    copy_file(PROJECT / 'REQUIREMENTS.md', DEST / 'guide/REQUIREMENTS.md', counter)
    for name in CODE_FILES:
        copy_file(CODE / name, DEST / 'code' / name, counter)

    for folder, pattern in (('configs', '*.json'), ('data', '*'), ('tests', 'test_*.py'),
                            ('scripts', '*.py')):
        for src in sorted((CODE / folder).glob(pattern)):
            if src.is_file():
                copy_file(src, DEST / 'code' / folder / src.name, counter)

    # ---- evidence --------------------------------------------------------- #
    for entry in RESULT_ENTRIES:
        src = CODE / 'results' / entry
        if src.is_file():
            copy_file(src, DEST / 'code/results' / entry, counter)
        elif src.is_dir():
            for item in sorted(src.rglob('*')):
                if item.is_file():
                    copy_file(item, DEST / 'code/results' / item.relative_to(CODE / 'results'),
                              counter)

    # Per-run metrics.json and curve.json only: these are the files the report's
    # appendix indexes, including the A.0 group of earlier v1/v2-stage runs used
    # by sections 5.4 to 5.6. A verifier must be able to open them; the *.pt
    # files stay out (1.98 GB) because the shipped checkpoint is authoritative.
    metrics_count = 0
    for src in sorted((CODE / 'runs').rglob('*')):
        if src.is_file() and src.name in ('metrics.json', 'curve.json'):
            rel = src.relative_to(CODE / 'runs')
            copy_file(src, DEST / 'code/runs' / rel, counter)
            metrics_count += 1

    # ---- the frozen predictor --------------------------------------------- #
    copy_file(V3_CHECKPOINT, DEST / 'code/checkpoint/checkpoint.pt', counter)
    copy_file(V3_MANIFEST, DEST / 'code/checkpoint/freeze_manifest_v3.json', counter)

    # ---- reports ---------------------------------------------------------- #
    report_lines = []
    for name, description in REPORTS:
        src = PROJECT / 'output/docx' / name
        if not src.exists():
            raise SystemExit(f'missing report {src}')
        copy_file(src, DEST / 'code/report' / name, counter)
        report_lines.append((name, description, sha256(src)))

    # ---- figures (source of the report figures) ---------------------------- #
    for src in sorted((PROJECT / 'output/figures/v3').glob('*')):
        if src.is_file() and src.suffix in ('.svg', '.png', '.json'):
            copy_file(src, DEST / 'code/report/figures' / src.name, counter)

    # ---- README and checksums --------------------------------------------- #
    manifest = json.loads(V3_MANIFEST.read_text())
    calibration = manifest['calibration']
    search = manifest['search_accounting']

    readme = f"""# MP1 submission bundle — frozen v3

DASE7506 Project 1. This bundle is the immutable code and checkpoint the course
website submission links to. It reproduces the reported score **without
retraining**.

## The reported score

| Item | Value |
|---|---|
| Complete test BPB (protocol `7506-mp1-wt2-v2`, CPU FP32) | **{1.5713485149197057:.6f}** |
| Validation BPB (uncalibrated recipe score) | {manifest['validation_bpb_uncalibrated']:.6f} |
| Validation BPB (with the frozen calibration temperature) | {calibration['validation_bpb_after']:.6f} |
| Course baseline test BPB | 2.101265 |
| Improvement over baseline | 25.22% |
| Parameters | {manifest['parameters']:,} |
| Inference assets | 40.0 MiB of the 64 MiB limit |
| CPU scoring time | 3.187x of the 5x limit |
| Peak RSS | 1.941 GiB of the 4 GiB limit |

## What the predictor is

A width-320 / depth-8 pre-norm decoder-only Transformer (RMSNorm, SwiGLU, RoPE,
tied embeddings), trained from random initialisation with AdamW at batch size 4
windows and peak learning rate 1.5e-3, a three percent warmup and a cosine decay
to zero over 28,909,568 processed targets. Inference additionally divides the
logits by a calibration temperature of T = {calibration['temperature']}, fitted
on the validation split only.

Batch size, learning rate and the temperature are the only differences from the
previous frozen v2 predictor; the inference graph, parameter count and inference
assets are identical.

## Layout

```
guide/                     the course guide, for reference
code/                      everything needed to reproduce the score
  checkpoint/checkpoint.pt the frozen predictor ({V3_CHECKPOINT.stat().st_size / 2**20:.1f} MiB)
  report/                  the report and its figure sources
  results/                 freeze manifests, test and resource measurements
  runs/*/metrics.json      per-run evidence for the report appendix ({metrics_count} files)
  data/, tests/, configs/  supplied files, unmodified
README.md                  this file
CHECKSUMS.txt              SHA-256 of every file in this bundle
```

## Verify the score (no training)

Requires Python 3.12 and PyTorch 2.7.1. From this bundle's root:

```bash
cd code
python -m venv .venv && source .venv/bin/activate
python -m pip install torch==2.7.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python evaluate.py --checkpoint checkpoint/checkpoint.pt --split test --device cpu --precision fp32
```

The reported value is the `bpb` field of `checkpoint/test_cpu_fp32.json`, which
must equal **1.571349**. The evaluator also self-checks the implementation,
evaluator and tokenizer hashes printed in that file.

## Reproduce the training run

```bash
cd code
python train_student.py --implementation student --config configs/ours_a_rope.json \\
  --run-dir runs/reproduce_v3 --device cpu --precision fp32 --threads 4 \\
  --seed 17 --batch-size 4 --targets 28909568 --lr 1.5e-3 --wd 0.1 \\
  --warmup-frac 0.03 --min-lr-frac 0.0 --schedule cosine \\
  --sampling without-replacement --beta2 0.95 --clip 1.0 --evals 0
```

This is not bit-reproducible: the MPS bf16 kernels used during development are
non-deterministic, and three runs of one configuration span 0.020 BPB in
validation (standard deviation 0.010). The report quantifies that floor and
grades every claim against it.

## Frozen hashes

| Artefact | SHA-256 |
|---|---|
| `code/checkpoint/checkpoint.pt` | `{manifest['checkpoint_sha256']}` |
| `code/student.py` | `{manifest['implementation_sha256']}` |
| `code/evaluate.py` | `{manifest['evaluator_sha256']}` |
| `code/data/tokenizer.json` | `{manifest['tokenizer_sha256']}` |
| freeze manifest written at | `{manifest['freeze_timestamp']}` (test result field empty at that moment) |

## What is deliberately not included

- `code/runs/**/*.pt`: 54 checkpoints totalling 1.98 GB. Only the submitted
  predictor ships here.
- Git history and scratch directories.

## Search cost disclosure

This freeze snapshot covers {search['runs_included']} controlled runs and
{search['total_processed_targets']:,} processed targets, on top of 33 runs and
429,047,808 targets during v1 and v2 development. Training duration and search
size are unlimited under the course rules and are disclosed here as required.

## Reports

"""
    for name, description, digest in report_lines:
        readme += f'- `code/report/{name}` — {description}\n  `{digest}`\n'

    readme += """
## AI assistance disclosure

The experiment scripts, figure generation and report typesetting were produced
with AI assistance, including the seven new screening scripts, the temperature
calibration and freeze-manifest tooling, and the figure and Word generation
pipeline. All experimental design, metric decisions and conclusions were
confirmed by the author. No AI component took part in any selection on the test
split, and no training data beyond the supplied text was used.

## Data attribution

WikiText-2 was introduced by Merity, Xiong, Bradbury and Socher in *Pointer
Sentinel Mixture Models*; the text is by Wikipedia contributors and is used
under CC BY-SA 3.0 and the GNU Free Documentation License.
"""
    (DEST / 'README.md').write_text(readme, encoding='utf-8')

    checksums = []
    for path in sorted(DEST.rglob('*')):
        if path.is_file() and path.name != 'CHECKSUMS.txt':
            checksums.append(f'{sha256(path)}  {path.relative_to(DEST).as_posix()}')
    (DEST / 'CHECKSUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')

    # ---- self-verification ------------------------------------------------- #
    print('verifying the bundle in place ...')
    python = CODE / '.venv_project1/bin/python'
    result = subprocess.run(
        [str(python), 'evaluate.py', '--checkpoint', 'checkpoint/checkpoint.pt',
         '--split', 'test', '--device', 'cpu', '--precision', 'fp32',
         '--output', str(DEST / 'code/checkpoint/verify_test_cpu_fp32.json')],
        cwd=DEST / 'code', capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-3000:])
        print(result.stderr[-3000:])
        raise SystemExit('bundle verification failed: evaluator returned non-zero')
    verified = json.loads((DEST / 'code/checkpoint/verify_test_cpu_fp32.json').read_text())
    expected = 1.5713485149197057
    checks = {
        'bpb matches frozen score': abs(verified['bpb'] - expected) < 1e-9,
        'checkpoint hash matches manifest': verified['checkpoint_sha256'] == manifest['checkpoint_sha256'],
        'implementation hash matches manifest': verified['implementation_sha256'] == manifest['implementation_sha256'],
        'evaluator hash matches manifest': verified['evaluator_sha256'] == manifest['evaluator_sha256'],
        'tokenizer hash matches manifest': verified['tokenizer_sha256'] == manifest['tokenizer_sha256'],
    }
    for label, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not all(checks.values()):
        raise SystemExit('bundle verification failed')

    archive = shutil.make_archive(str(ZIP.with_suffix('')), 'zip', DEST)
    files, total = counter[0], counter[1]
    print(f'\nbundle : {DEST.relative_to(PROJECT)}  ({files + 3} files, {total / 2 ** 20:.1f} MiB copied)')
    print(f'archive: {Path(archive).relative_to(PROJECT)}  ({Path(archive).stat().st_size / 2 ** 20:.1f} MiB)')
    print(f'reports: {len(report_lines)}, per-run metrics.json: {metrics_count}')
    print(f'checkpoints included: 1')
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    sys.exit(main())
