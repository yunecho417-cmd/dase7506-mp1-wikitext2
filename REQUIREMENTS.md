# MP1 Requirements

This file is a concise execution checklist derived from `GUIDE.md` and `code/README.md`. Those supplied documents remain the detailed source.

## Objective

- Train from random initialization on the supplied WikiText-2 training text.
- Minimize complete-test bits per byte. Lower BPB is better.
- Report a CPU-reproducible FP32 score.

## Fixed protocol

- Vocabulary: fixed BPE-2048 tokenizer.
- Context: 256 tokens.
- Evaluation windows are independent and causal.
- Every target except the first token of a split is scored exactly once.
- BPB equals total next-token NLL in bits divided by raw UTF-8 bytes.

## Data restrictions

- Learn only from the supplied training split.
- Use validation for architecture, hyperparameter, seed and checkpoint selection.
- Freeze the method before running the student-model test.
- Do not use external text, pretrained weights, cached answers, future tokens, cross-window state or evaluation network access.
- Do not modify the supplied data, tokenizer or fixed evaluator.

## Resource limits

| Resource | Limit |
|---|---:|
| CPU FP32 scoring time | At most 5x baseline |
| Peak evaluation RAM | At most 4 GiB |
| Uncompressed inference assets | At most 64 MiB |

## Required evidence

- Initial supplied baseline.
- Comparison at the same number of processed training targets.
- Ablation of the key mechanism.
- Validation-based development and selection.
- Analysis of prediction quality versus computation.
- Training/search costs, seeds and checkpoint ancestry.

## Deliverables

- Final test BPB.
- Immutable code version with exact reproduction instructions.
- Matching downloadable checkpoint bundle that does not require retraining.
- Report of at most 10 pages including figures, tables and references.
- AI-assistance disclosure.
- Course website submission and subsequent peer review.

## Local completion checklist

- [x] Fixed files and data hashes checked.
- [x] Contract tests pass.
- [x] Baseline reproduced.
- [x] Same-target comparison completed.
- [x] Architecture, size and training-length ablations completed.
- [x] Two final-recipe seeds compared on validation.
- [x] Final checkpoint selected and frozen before test.
- [x] One frozen student-model configuration scored on test; resource repetitions reuse that configuration without test-based selection.
- [x] Test CPU time, RAM and asset limits measured.
- [x] Compact report prepared within 10 pages and preserved separately.
- [x] Comprehensive Chinese working draft prepared with all 33 retained runs and editable chart sources.
- [x] Morandi translucent wall/column charts added with editable PowerPoint shapes and separate embedded-data charts in one deck; no new software or experimental results introduced.
- [ ] Manually edit the comprehensive draft and compress the chosen submission version to the 10-page limit. The complete working draft is not a length-compliant submission.
- [x] Post-freeze trainer, 2x2 block, capacity, representation, EMA and MTP ablations completed.
- [x] Three RoPE long-training seeds selected at predeclared validation points.
- [x] Validation-only v2 candidate independently verified on CPU FP32 and resource measured.
- [x] v2 candidate kept off the test split pending a separate freeze decision.
- [ ] Private Git remote fully pushed and checkpoint release created.
- [ ] Course website submission completed.
