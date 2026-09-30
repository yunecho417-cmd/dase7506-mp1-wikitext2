# MP1 submission bundle — frozen v3

DASE7506 Project 1. This bundle is the immutable code and checkpoint the course
website submission links to. It reproduces the reported score **without
retraining**.

## The reported score

| Item | Value |
|---|---|
| Complete test BPB (protocol `7506-mp1-wt2-v2`, CPU FP32) | **1.571349** |
| Validation BPB (uncalibrated recipe score) | 1.556890 |
| Validation BPB (with the frozen calibration temperature) | 1.549498 |
| Course baseline test BPB | 2.101265 |
| Improvement over baseline | 25.22% |
| Parameters | 10,488,640 |
| Inference assets | 40.0 MiB of the 64 MiB limit |
| CPU scoring time | 3.187x of the 5x limit |
| Peak RSS | 1.941 GiB of the 4 GiB limit |

## What the predictor is

A width-320 / depth-8 pre-norm decoder-only Transformer (RMSNorm, SwiGLU, RoPE,
tied embeddings), trained from random initialisation with AdamW at batch size 4
windows and peak learning rate 1.5e-3, a three percent warmup and a cosine decay
to zero over 28,909,568 processed targets. Inference additionally divides the
logits by a calibration temperature of T = 1.075, fitted
on the validation split only.

Relative to v2, v3 jointly changes the seed, batch size, peak learning rate,
cosine-decay floor and selected checkpoint. The model architecture and parameter
count are unchanged; temperature scaling adds one elementwise division and about
1 KB to the inference assets.

## Layout

```
guide/                     the course guide, for reference
code/                      everything needed to reproduce the score
  checkpoint/checkpoint.pt the frozen predictor (40.0 MiB)
  report/                  the report and its figure sources
  results/                 freeze manifests, test and resource measurements
  runs/*/metrics.json      per-run evidence for the report appendix (133 files)
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
python train_student.py --implementation student --config configs/ours_a_rope.json \
  --run-dir runs/reproduce_v3 --device cpu --precision fp32 --threads 4 \
  --seed 17 --batch-size 4 --targets 28909568 --lr 1.5e-3 --wd 0.1 \
  --warmup-frac 0.03 --min-lr-frac 0.0 --schedule cosine \
  --sampling without-replacement --beta2 0.95 --clip 1.0 --evals 0
```

This is not bit-reproducible: the MPS bf16 kernels used during development are
non-deterministic, and three runs of one configuration span 0.020 BPB in
validation (standard deviation 0.010). The report quantifies that floor and
grades every claim against it.

## Frozen hashes

| Artefact | SHA-256 |
|---|---|
| `code/checkpoint/checkpoint.pt` | `ba65ec2e216ca5054e9624efa6577e1af9ce14944ced39a4c2f89c4c6acd65d7` |
| `code/student.py` | `6888d7dfc53cd0ae1470d8842591c76025aeed8620367b86c43b772334cbfcd6` |
| `code/evaluate.py` | `128bcb2dab0be0d427505bddb4671e3ab3a8f78e114be79a689c0f9029af133d` |
| `code/data/tokenizer.json` | `020d1bc6aa4449c4f352b2e03d0e0fb4f39287f15297705e421b1fa7d817262e` |
| freeze manifest written at | `2026-09-26T12:53:30+08:00` (test result field empty at that moment) |

## What is deliberately not included

- `code/runs/**/*.pt`: 54 checkpoints totalling 1.98 GB. Only the submitted
  predictor ships here.
- Git history and scratch directories.

## Search cost disclosure

This freeze snapshot covers 24 controlled runs and
542,427,904 processed targets, on top of 33 runs and
429,047,808 targets during v1 and v2 development. Training duration and search
size are unlimited under the course rules and are disclosed here as required.

## Reports

- `code/report/DASE7506_Project_1_TECH_Report_English_v3_Submission_10pg.pdf` — the ten-page English submission edition (PDF)
  `273280519653431195a8acdae92cc6b6d4956b57059357d8e5e86042ba631f40`
- `code/report/DASE7506_Project_1_TECH_Report_English_v3_Submission_10pg.docx` — the editable ten-page English submission edition
  `13e22f783832dadba833180c321004509c0f8933d3b553ec661e75706707f6bd`
- `code/report/DASE7506_Project_1_TECH_Report_中文_v3_10页版.pdf` — the ten-page Chinese submission edition (PDF)
  `f880b089011e3a0087a174a6bf779e312919bcf42eed00c9f0f2173b61034bbf`
- `code/report/DASE7506_Project_1_TECH_Report_中文_v3_10页版.docx` — the editable ten-page Chinese submission edition
  `4f3717db7825967df8004c3fb90ed1b8eed9bd05bd8dd44c72c375559ba8294d`

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
