"""Rebuild a compact, deterministic TSV index from completed run metrics."""
import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIELDS = [
    'run', 'implementation', 'targets', 'search_targets', 'params', 'cfg', 'lr', 'wd',
    'drop', 'ema', 'sampling', 'schedule', 'beta2', 'pos', 'tie', 'mtp_k',
    'mib', 'val_bpb', 'val_ppl', 'train_s', 'seed', 'checkpoint_sha256',
]


def row_from_metrics(path):
    metrics = json.loads(path.read_text())
    config = metrics['config']
    run_args = metrics.get('args') or {}
    run = path.parent.name
    checkpoint = path.parent / 'checkpoint.pt'
    ffn = config.get('ffn', 'gelu')
    norm = config.get('norm', 'ln')
    search_targets = metrics.get('processed_targets', metrics.get('train_tokens', ''))
    targets = metrics.get('checkpoint_processed_targets', search_targets)
    asset_mib = metrics.get('asset_mib')
    if asset_mib is None and checkpoint.exists():
        asset_mib = checkpoint.stat().st_size / 2**20
    validation = metrics['validation']
    implementation = metrics.get('implementation',
                                 run_args.get('implementation', 'student'))
    return {
        'run': run,
        'implementation': implementation,
        'targets': targets,
        'search_targets': search_targets,
        'params': metrics['parameters'],
        'cfg': f"w{config['width']}d{config['depth']}-{norm}-{ffn}",
        'lr': run_args.get('lr', 0.001 if implementation == 'model' else ''),
        'wd': run_args.get('wd', 0.1 if implementation == 'model' else ''),
        'drop': config.get('dropout', 0.0),
        'ema': run_args.get('ema', 0.0),
        'sampling': run_args.get(
            'sampling', 'with-replacement' if implementation == 'model'
            else 'without-replacement'),
        'schedule': run_args.get(
            'schedule', 'baseline' if implementation == 'model' else 'cosine'),
        'beta2': run_args.get('beta2', 0.999 if implementation == 'model' else 0.95),
        'pos': config.get('pos', 'learned'),
        'tie': config.get('tie', 1),
        'mtp_k': run_args.get('mtp_k', 0),
        'mib': round(asset_mib, 3) if asset_mib is not None else '',
        'val_bpb': round(validation['bpb'], 6),
        'val_ppl': round(validation['token_ppl'], 4),
        'train_s': round(metrics['train_seconds'], 3),
        'seed': metrics.get('seed', run_args.get('seed', '')),
        'checkpoint_sha256': metrics.get('checkpoint_sha256', ''),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='*', help='Optional run directory names.')
    parser.add_argument('--include-smoke', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/grid.tsv')
    args = parser.parse_args()

    if args.runs:
        paths = [ROOT / 'runs' / name / 'metrics.json' for name in args.runs]
    else:
        paths = sorted((ROOT / 'runs').glob('*/metrics.json'))
    rows = []
    for path in paths:
        if not path.exists():
            print(f'skip missing {path.relative_to(ROOT)}')
            continue
        if not args.include_smoke and 'smoke' in path.parent.name.lower():
            continue
        rows.append(row_from_metrics(path))
    rows.sort(key=lambda row: (int(row['targets'] or 0), row['run']))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)
    print(f'wrote {len(rows)} runs to {args.output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
