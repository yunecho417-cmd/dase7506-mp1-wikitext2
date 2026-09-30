"""Summarise the 2026-09-26 screening batches.

Reads every `metrics.json` under the phase directories plus the historical grid
and prints one sorted table, so a whole batch can be judged at a glance.

Usage:  ./.venv_project1/bin/python scripts/collect_phase_results.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASES = ['runs/2026-09-26_phase1', 'runs/2026-09-26_phase2', 'runs/2026-09-26_phase3']
FIELDS = ['run', 'targets', 'params', 'mib', 'cfg', 'bs', 'lr', 'minlr', 'wd',
          'drop', 'ema', 'val_bpb', 'train_s', 'impl']


def shorten(cfg, name):
    parts = [f"w{cfg['width']}d{cfg['depth']}"]
    if cfg.get('pos', 'learned') == 'rope':
        parts.append('rope')
    if not cfg.get('tie', 1):
        parts.append('untied')
    reg = []
    for key, tag in (('dropout', 'do'), ('droppath', 'dp'),
                     ('token_drop', 'td'), ('emb_dropout', 'ed')):
        if cfg.get(key):
            reg.append(f"{tag}{cfg[key]}")
    if reg:
        parts.append('+'.join(reg))
    return ' '.join(parts)


def row(path):
    d = json.loads(path.read_text())
    a, cfg = d['args'], d['config']
    return {
        'run': path.parent.name,
        'targets': d['processed_targets'],
        'params': d['parameters'],
        'mib': round(d['asset_mib'], 2),
        'cfg': shorten(cfg, path.parent.name),
        'bs': a['batch_size'],
        'lr': a['lr'],
        'minlr': a['min_lr_frac'],
        'wd': a['wd'],
        'drop': cfg.get('dropout', 0.),
        'ema': a['ema'],
        'val_bpb': round(d['validation']['bpb'], 6),
        'train_s': round(d['train_seconds']),
        'impl': d['implementation_sha256'][:8],
    }


def main():
    history = []
    grid = ROOT / 'results/grid.tsv'
    if grid.exists():
        head = grid.read_text().splitlines()[0].split('\t')
        for line in grid.read_text().splitlines()[1:]:
            cells = dict(zip(head, line.split('\t')))
            history.append({'run': cells['run'], 'cfg': cells['cfg'],
                            'val_bpb': round(float(cells['val_bpb']), 6)})

    rows = []
    for phase in PHASES:
        base = ROOT / phase
        if not base.exists():
            continue
        for metrics in sorted(base.glob('*/metrics.json')):
            try:
                rows.append(row(metrics))
            except (KeyError, ValueError) as error:
                print(f'skip {metrics}: {error}', file=sys.stderr)
    if not rows:
        print('no phase results yet')
        return

    width = {key: max(len(key), *(len(str(r[key])) for r in rows)) for key in FIELDS}
    print('  '.join(key.rjust(width[key]) for key in FIELDS))
    for r in sorted(rows, key=lambda r: r['val_bpb']):
        print('  '.join(str(r[k]).rjust(width[k]) for k in FIELDS))

    print(f'\nbest of this batch: {min(r["val_bpb"] for r in rows):.6f}')

    if history:
        print('\nreference points (historical grid, seed 17 unless noted):')
        keep = ['R0_baseline', 'lr1e3_a', 'ablation_rope_s17', 'ablation_rope_s137',
                'ablation_rope_untied_s17', 'ablation_rope_untied_ema099_s17',
                'capacity_w320d10_s17', 'capacity_w384d8_s17',
                '2026-09-25_rope_long_best_seed137', '2026-09-25_rope_long_best_seed17',
                '2026-09-25_rope_long_seed17', 'a_e8_lr1e3']
        for h in history:
            if h['run'] in keep:
                print(f"  {h['run']:<38} {h['cfg']:<22} val {h['val_bpb']:.6f}")


if __name__ == '__main__':
    main()
