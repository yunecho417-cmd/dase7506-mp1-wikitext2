"""Measure the three MP1 inference limits in isolated CPU processes.

Each repetition loads one checkpoint in a fresh process, scores one complete
split in FP32, and reports scoring time, peak resident memory and asset size.
The baseline is measured in the same invocation, with the same split and thread
count, so the time ratio does not depend on a stale hard-coded number.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = ROOT / 'runs/R0_baseline/checkpoint.pt'


def _child_source(checkpoint, split, threads):
    checkpoint_json = json.dumps(str(Path(checkpoint).resolve()))
    split_json = json.dumps(split)
    return f"""
import json
import resource
import sys
import torch
from common import load_data, make_model
from evaluate import score

torch.set_num_threads({threads})
torch.set_float32_matmul_precision('highest')
checkpoint_path = {checkpoint_json}
checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
model, _ = make_model(checkpoint['implementation'], checkpoint['config'], torch.device('cpu'))
model.load_state_dict(checkpoint['model'])
result = score(model, *load_data()[{split_json}], torch.device('cpu'), 'fp32')
result.pop('window_nll_nats')
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
result['peak_rss_gib'] = peak / (2**30 if sys.platform == 'darwin' else 2**20)
print('@@MP1@@' + json.dumps(result))
"""


def _one_run(checkpoint, split, threads):
    env = os.environ.copy()
    env.update({
        'OMP_NUM_THREADS': str(threads),
        'MKL_NUM_THREADS': str(threads),
        'VECLIB_MAXIMUM_THREADS': str(threads),
        'PYTHONPATH': str(ROOT),
    })
    completed = subprocess.run(
        [sys.executable, '-c', _child_source(checkpoint, split, threads)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f'Failed to measure {checkpoint}:\n{completed.stdout}\n{completed.stderr}')
    lines = [line for line in completed.stdout.splitlines()
             if line.startswith('@@MP1@@')]
    if len(lines) != 1:
        raise RuntimeError(f'Missing measurement payload for {checkpoint}.')
    return json.loads(lines[0][len('@@MP1@@'):])


def measure(checkpoint, split, threads, warmups, repeats):
    checkpoint = Path(checkpoint).resolve()
    for _ in range(warmups):
        _one_run(checkpoint, split, threads)
    observations = [_one_run(checkpoint, split, threads) for _ in range(repeats)]
    seconds = [row['seconds'] for row in observations]
    memory = [row['peak_rss_gib'] for row in observations]
    return {
        'checkpoint': str(checkpoint.relative_to(ROOT)),
        'split': split,
        'threads': threads,
        'precision': 'fp32',
        'repetitions': repeats,
        'bpb': statistics.median(row['bpb'] for row in observations),
        'token_ppl': statistics.median(row['token_ppl'] for row in observations),
        'scoring_seconds_median': statistics.median(seconds),
        'scoring_seconds_min': min(seconds),
        'scoring_seconds_max': max(seconds),
        'peak_rss_gib_max': max(memory),
        'asset_mib': checkpoint.stat().st_size / 2**20,
        'observations': observations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoints', nargs='+', type=Path)
    parser.add_argument('--baseline', type=Path, default=DEFAULT_BASELINE)
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--split', choices=['validation', 'test'], default='validation')
    parser.add_argument('--warmups', type=int, default=1)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'results/resources_validation.json')
    args = parser.parse_args()
    if args.threads < 1 or args.repeats < 1 or args.warmups < 0:
        parser.error('threads and repeats must be positive; warmups cannot be negative.')

    baseline = measure(args.baseline, args.split, args.threads,
                       args.warmups, args.repeats)
    rows = []
    for checkpoint in args.checkpoints:
        if checkpoint.resolve() == args.baseline.resolve():
            row = dict(baseline)
        else:
            row = measure(checkpoint, args.split, args.threads,
                          args.warmups, args.repeats)
        row['time_vs_baseline'] = (
            row['scoring_seconds_median'] /
            baseline['scoring_seconds_median'])
        row['within_limits'] = {
            'time': row['time_vs_baseline'] <= 5.0,
            'memory': row['peak_rss_gib_max'] <= 4.0,
            'assets': row['asset_mib'] <= 64.0,
        }
        rows.append(row)

    payload = {
        'protocol': '7506-mp1-wt2-v2',
        'method': 'fresh process per repetition; median time; maximum peak RSS',
        'limits': {'time_vs_baseline': 5.0, 'peak_rss_gib': 4.0,
                   'asset_mib': 64.0},
        'baseline': baseline,
        'models': rows,
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + '\n')

    print(f"{'checkpoint':44s} {'bpb':>8s} {'sec':>8s} {'xbase':>8s} "
          f"{'RSS GiB':>9s} {'MiB':>8s} {'pass':>6s}")
    for row in rows:
        passed = all(row['within_limits'].values())
        print(f"{row['checkpoint']:44s} {row['bpb']:8.4f} "
              f"{row['scoring_seconds_median']:8.3f} "
              f"{row['time_vs_baseline']:8.3f} "
              f"{row['peak_rss_gib_max']:9.3f} {row['asset_mib']:8.1f} "
              f"{str(passed):>6s}")
    print(f'Wrote {output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
