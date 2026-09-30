# Report Editions — Declaration

**Branch:** `main` · **Version:** v3 (frozen, current best) · **Test BPB:** 1.571349 · **Baseline:** 2.101265 (**25.22%** improvement)

This branch carries **two English report editions**. The difference matters, so it is stated here explicitly.

## Which edition is authoritative

| Edition | File | Pages | Role |
|---|---|---:|---|
| **Submission edition** | `code/report/DASE7506_Project_1_TECH_Report_English_v3_Submission_10pg.pdf` (`.docx` same name) | 10 | The edition written against the page budget. **This is the submitted deliverable.** |
| **Extended full edition** | `code/report/DASE7506_Project_1_TECH_Report_English_v3_Full_Journal.pdf` | 21 | Working record of everything behind the decisions. **Supplementary, not a second submission.** |

The extended edition exists only because the ten-page limit forces cuts. It keeps the full
evidence — every screening run, the decision basis behind each hyper-parameter, the resource
measurements and the complete appendix tables — so that the reasoning recorded in the short
version can be audited. It is **not** intended to satisfy any requirement on its own, and it is
not the artefact handed to the grader.

## Language

Both editions here are **English only**. The project also has Chinese editions; they are kept
outside this repository.

## Reproducibility note

`code/checkpoint/checkpoint.pt` is included so the reported score can be reproduced without
retraining (see root `README.md` for the exact commands). This repository is **private**; please
do not redistribute the branch content while the course is running.

## Version history

- `v2` branch — earlier frozen version, test BPB 1.611178 (23.32% over baseline). Same
  architecture and parameter count; v3 differs only in seed, batch size 4, peak learning rate
  1.5e-3, full cosine anneal to zero, and the validation-fitted calibration temperature T = 1.075.
- `main` — this version, v3.

## Known differences between the two editions

The extended edition additionally contains the full ablation appendices, per-run evidence and
the complete resource tables that were compressed or dropped to reach ten pages. Both editions
report the same frozen numbers; nothing in the extended edition contradicts the submission
edition.
