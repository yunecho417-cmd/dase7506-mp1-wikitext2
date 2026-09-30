# Report Editions — Declaration

**Branch:** `v2` · **Version:** v2 (frozen) · **Test BPB:** 1.611178 · **Baseline:** 2.101265 (25.22% → this version: 23.32% improvement)

This branch carries **two English report editions**. The difference matters, so it is stated here explicitly.

## Which edition is authoritative

| Edition | File | Pages | Role |
|---|---|---:|---|
| **Submission edition** | `report/DASE7506_Project_1_TECH_Report_English_v2_Submission_10pg.pdf` (`.docx` same name) | 10 | The edition written against the page budget. **This is the submitted deliverable.** |
| **Extended full edition** | `report/DASE7506_Project_1_TECH_Report_English_v2_Full_Journal.pdf` | 32 | Working record of everything behind the decisions. **Supplementary, not a second submission.** |

The extended edition exists only because the ten-page limit forces cuts. It keeps the full
evidence — every screening run, the decision basis behind each hyper-parameter, the resource
measurements and the complete appendix tables — so that the reasoning recorded in the short
version can be audited. It is **not** intended to satisfy any requirement on its own, and it is
not the artefact handed to the grader.

## Language

Both editions here are **English only**. The project also has Chinese editions; they are kept
outside this repository.

## Reproducibility note

`checkpoint/checkpoint.pt` is included so the reported score can be reproduced without
retraining (see root `README.md` for the exact commands). This repository is **private**; please
do not redistribute the branch content while the course is running.

## Known differences between the two editions

The extended edition additionally contains the full ablation appendices, per-run evidence and
the complete resource tables that were compressed or dropped to reach ten pages. Both editions
report the same frozen numbers; nothing in the extended edition contradicts the submission
edition.
