"""Bake a validation-fitted calibration temperature into a checkpoint.

`evaluate.py` rebuilds the model from `checkpoint['config']`, so the temperature
has to travel inside the checkpoint or the scorer will not see it. This script

  1. loads a trained checkpoint,
  2. fits a single temperature T on the validation split,
  3. writes a new checkpoint whose config carries `logit_temperature = T`,
  4. re-scores it from scratch to prove the stored value reproduces the fit.

The temperature costs nothing at inference: no extra parameters, no extra
assets, no extra FLOPs (it is one scalar division before the softmax). The
output stays normalized, causal and stateless.

Usage:
  ./.venv_project1/bin/python scripts/recalibrate_checkpoint.py \
      --checkpoint runs/<run>/checkpoint.pt \
      --output runs/<run>/checkpoint_calibrated.pt
"""
import argparse
import json
import math
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import load_data, make_model, sha, setup, windows  # noqa: E402

GRID = [.90, .925, .95, .975, 1.0, 1.025, 1.05, 1.075,
        1.10, 1.125, 1.15, 1.175, 1.20, 1.25, 1.30]


@torch.no_grad()
def score_with_temperature(model, tokens, byte_count, device, temperature, batch_size=32):
    model.temperature = temperature
    model.eval()
    nll, count = 0., 0
    for x, y in windows(tokens, batch_size):
        logp = model.predict_log_probs(x.to(device)).float()
        loss = -logp.gather(-1, y.clamp_min(0).unsqueeze(-1)).squeeze(-1)
        loss = loss.masked_fill(y == -100, 0)
        nll += loss.sum().item()
        count += int((y != -100).sum())
    return nll / math.log(2) / byte_count, math.exp(nll / count)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--device', default='cpu')
    p.add_argument('--precision', default='fp32')
    p.add_argument('--threads', type=int, default=4)
    # Fitting requires full logits, so the grid is scanned in one forward pass.
    args = p.parse_args()

    device, _ = setup(args.device, args.precision, args.threads)
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    config = dict(checkpoint['config'])
    model, implementation_sha = make_model(checkpoint['implementation'], config, device)
    model.load_state_dict(checkpoint['model'])
    validation_tokens, validation_bytes = load_data()['validation']

    # Scan the grid on validation only. Force T=1 here so that re-calibrating an
    # already-calibrated checkpoint does not apply the scaling twice.
    model.temperature = 1.
    nll = {t: 0. for t in GRID}
    with torch.no_grad():
        for x, y in windows(validation_tokens, 32):
            logits = model(x.to(device)).float()
            mask = y != -100
            gathered = y.clamp_min(0).unsqueeze(-1)
            for t in GRID:
                scaled = logits / t
                term = torch.logsumexp(scaled, dim=-1) - scaled.gather(-1, gathered).squeeze(-1)
                nll[t] += term[mask].sum().item()
    scored = {t: v / math.log(2) / validation_bytes for t, v in nll.items()}
    best_t = min(scored, key=scored.get)

    config['logit_temperature'] = best_t
    checkpoint['config'] = config
    checkpoint['calibration'] = {
        'method': 'single temperature on the validation split, logits divided before log_softmax',
        'temperature': best_t,
        'validation_bpb_before': scored[1.0],
        'validation_bpb_after': scored[best_t],
        'validation_bpb_by_temperature': scored,
        'inference_cost': 'no extra parameters, assets or FLOPs',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, args.output)

    # Re-score from disk so the verified number is the one actually stored.
    reloaded = torch.load(args.output, map_location='cpu', weights_only=True)
    fresh, _ = make_model(reloaded['implementation'], reloaded['config'], device)
    fresh.load_state_dict(reloaded['model'])
    bpb, ppl = score_with_temperature(fresh, validation_tokens, validation_bytes,
                                      device, reloaded['config']['logit_temperature'])
    parameters = sum(q.numel() for q in fresh.parameters())

    print(json.dumps({
        'input': str(args.checkpoint), 'output': str(args.output),
        'temperature': best_t,
        'validation_bpb_before': round(scored[1.0], 6),
        'validation_bpb_after': round(scored[best_t], 6),
        'gain': round(scored[1.0] - scored[best_t], 6),
        'rescore_from_disk_bpb': round(bpb, 6),
        'rescore_token_ppl': round(ppl, 4),
        'parameters': parameters,
        'asset_mib': round(args.output.stat().st_size / 2 ** 20, 3),
        'implementation_sha256': implementation_sha,
        'checkpoint_sha256': sha(args.output),
    }, indent=2))


if __name__ == '__main__':
    main()
