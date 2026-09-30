"""Measure the calibration headroom of a frozen checkpoint.

The leaderboard metric is bits per byte, i.e. a proper scoring rule. If the
model's logits are systematically over-confident, rescaling them by a single
temperature T (fitted on validation) improves the score at zero inference cost,
and the rescaled output is still a normalised, causal, stateless distribution.

This script only *measures* the headroom; it does not modify any model. It also
runs a half-split generalisation check: T is fitted on the even-numbered
validation batches and then scored on the odd-numbered ones, which shows the
gain is not an artefact of fitting on the same data being reported.

Usage:
  ./.venv_project1/bin/python scripts/fit_temperature.py \
      --checkpoint runs/2026-09-26_phase1/h28p9/checkpoint.pt --split validation
"""
import argparse
import json
import math
import sys
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import load_data, make_model, setup, windows  # noqa: E402

GRID = [.80, .85, .90, .925, .95, .975, 1.0, 1.025, 1.05, 1.075,
        1.10, 1.15, 1.20, 1.30, 1.40, 1.60, 1.80, 2.00]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', required=True, type=Path)
    p.add_argument('--split', choices=['validation', 'test'], default='validation')
    p.add_argument('--device', default='cpu')
    p.add_argument('--precision', default='fp32')
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--output', type=Path)
    args = p.parse_args()

    device, precision = setup(args.device, args.precision, args.threads)
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    model, _ = make_model(checkpoint['implementation'], checkpoint['config'], device)
    model.load_state_dict(checkpoint['model'])
    model.eval()
    tokens, byte_count = load_data()[args.split]

    nll = {t: 0. for t in GRID}
    nll_even = {t: 0. for t in GRID}   # even batches -> half A, where T is fitted
    nll_odd = {t: 0. for t in GRID}    # odd batches  -> half B, held out
    entropy_sum, count = 0., 0
    with torch.no_grad():
        for batch_index, (x, y) in enumerate(windows(tokens, 32)):
            logits = model(x.to(device)).float().cpu()
            mask = y != -100
            targets = y.clamp_min(0)
            gathered = targets.unsqueeze(-1)
            bucket = nll_even if batch_index % 2 == 0 else nll_odd
            for t in GRID:
                scaled = logits / t
                term = torch.logsumexp(scaled, dim=-1) - scaled.gather(-1, gathered).squeeze(-1)
                value = term[mask].sum().item()
                nll[t] += value
                bucket[t] += value
            logp = F.log_softmax(logits, dim=-1)
            entropy_sum += (-(logp.exp() * logp).sum(-1))[mask].sum().item()
            count += int(mask.sum())

    scored = {t: v / math.log(2) / byte_count for t, v in nll.items()}
    best_t = min(scored, key=scored.get)
    base = scored[1.0]

    half_bytes = byte_count / 2
    scored_a = {t: v / math.log(2) / half_bytes for t, v in nll_even.items()}
    scored_b = {t: v / math.log(2) / half_bytes for t, v in nll_odd.items()}
    best_t_a = min(scored_a, key=scored_a.get)

    print(f'checkpoint      {args.checkpoint}')
    print(f'split           {args.split}   targets={count}   bytes={byte_count}')
    print(f'BPB at T=1.0    {base:.6f}   (the frozen, uncalibrated score)')
    print(f'best T          {best_t}')
    print(f'BPB at best T   {scored[best_t]:.6f}   gain {base - scored[best_t]:+.6f}')
    print(f'mean predictive entropy {entropy_sum / count:.4f} nats '
          f'(max possible {math.log(2048):.4f})')
    print()
    print('half-split generalisation check (T fitted on the even half only):')
    print(f'  T* fitted on half A   {best_t_a}')
    print(f'  half A  T=1.0 {scored_a[1.0]:.6f}  ->  T=T* {scored_a[best_t_a]:.6f}'
          f'   gain {scored_a[1.0] - scored_a[best_t_a]:+.6f}')
    print(f'  half B  T=1.0 {scored_b[1.0]:.6f}  ->  T=T* {scored_b[best_t_a]:.6f}'
          f'   gain {scored_b[1.0] - scored_b[best_t_a]:+.6f}   <-- held out')
    print()
    for t in GRID:
        flag = ' <-- best' if t == best_t else ('  <-- current' if t == 1.0 else '')
        print(f'  T={t:<6.3f} BPB={scored[t]:.6f}  delta={scored[t] - base:+.6f}{flag}')

    if args.output:
        args.output.write_text(json.dumps(
            {'checkpoint': str(args.checkpoint), 'split': args.split,
             'bpb_by_temperature': scored, 'best_temperature': best_t,
             'gain_over_t1': base - scored[best_t],
             'mean_predictive_entropy_nats': entropy_sum / count,
             'holdout': {'t_fitted_on_even_half': best_t_a,
                         'half_a_at_t1': scored_a[1.0],
                         'half_a_at_t_star': scored_a[best_t_a],
                         'half_b_at_t1': scored_b[1.0],
                         'half_b_at_t_star': scored_b[best_t_a]}}, indent=2) + '\n')


if __name__ == '__main__':
    main()
