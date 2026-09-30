# DASE7506 Project 1 - submission bundle

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
| `report/` | the verified ten-page English submission report in PDF and editable DOCX formats |
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
python evaluate.py \
  --checkpoint checkpoint/checkpoint.pt \
  --device cpu \
  --precision fp32 \
  --threads 4 \
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
python train_student.py \
  --implementation student \
  --config configs/ours_a_rope.json \
  --run-dir runs/reproduce_v2_seed137 \
  --device cpu \
  --precision fp32 \
  --threads 4 \
  --seed 137 \
  --epochs 8 \
  --lr 1e-3 \
  --wd 0.1 \
  --warmup-frac 0.03 \
  --min-lr-frac 0.1 \
  --beta2 0.95 \
  --sampling without-replacement \
  --schedule cosine \
  --eval-at-targets 9830400,19660800,28909568 \
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
