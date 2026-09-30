"""Pick the best run from a screening phase and print its recipe.

Used by the phase chaining scripts so the next batch can target the current
winner without a human in the loop. Selection is on validation BPB only; the
test split is never read.

Usage:
  ./.venv_project1/bin/python scripts/pick_best_phase.py runs/2026-09-26_phase8
  # -> "p8_bs4_lr750 4 0.00075 28909568"   (name, batch, lr, targets)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 2:
        print('usage: pick_best_phase.py <phase-dir> [--exclude-substr S]')
        raise SystemExit(2)
    base = ROOT / sys.argv[1]
    exclude = ''
    if '--exclude-substr' in sys.argv:
        exclude = sys.argv[sys.argv.index('--exclude-substr') + 1]

    rows = []
    for metrics in sorted(base.glob('*/metrics.json')):
        if exclude and exclude in metrics.parent.name:
            continue
        d = json.loads(metrics.read_text())
        rows.append((d['validation']['bpb'], metrics.parent.name, d))
    if not rows:
        print('none')
        raise SystemExit(1)

    _, name, d = min(rows, key=lambda r: r[0])
    a = d['args']
    print(f"{name} {a['batch_size']} {a['lr']} {d['processed_targets']} {d['validation']['bpb']}")


if __name__ == '__main__':
    main()
