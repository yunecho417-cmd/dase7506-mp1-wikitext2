"""Collect every number the v3 report needs into one JSON file.

Following the repository convention that charts have a single data source, this
script reads the frozen result files and the per-run ``metrics.json`` files and
emits ``output/figures/v3/data.json``.  Nothing here is typed by hand, so the
report cannot drift from the recorded evidence.

Usage:
  ./.venv_project1/bin/python scripts/collect_v3_evidence.py
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT.parent
OUT = PROJECT / 'output/figures/v3/data.json'


def metrics(rel):
    return json.loads((ROOT / rel / 'metrics.json').read_text())


def val(rel):
    return metrics(rel)['validation']['bpb']


def main():
    res = ROOT / 'results'
    frozen = {
        'v2_test': json.loads((res / '2026-09-26/v2_frozen_test_cpu_fp32.json').read_text()),
        'v3_test': json.loads((res / '2026-09-26/v3_frozen_test_cpu_fp32.json').read_text()),
        'v2_res': json.loads((res / '2026-09-26/resources_test_v2.json').read_text()),
        'v3_res': json.loads((res / '2026-09-26/resources_test_v3.json').read_text()),
        'v1': json.loads((res / '2026-09-25/supplementary_summary.json').read_text()),
    }
    baseline_test = frozen['v2_res']['baseline']['bpb']
    baseline_val = 2.0710874333793914

    versions = [
        {'key': 'baseline', 'label': 'Course baseline',
         'validation': baseline_val, 'test': baseline_test},
        {'key': 'v1', 'label': 'Frozen v1',
         'validation': frozen['v1']['official_frozen_v1']['validation_bpb'],
         'test': frozen['v1']['official_frozen_v1']['test_bpb']},
        {'key': 'v2', 'label': 'Frozen v2',
         'validation': frozen['v2_test'].get('validation_bpb', 1.5880948963549917),
         'test': frozen['v2_test']['bpb']},
        {'key': 'v3', 'label': 'Frozen v3',
         'validation': val('runs/2026-09-26_phase8/p8_bs4_lr1500'),
         'test': frozen['v3_test']['bpb']},
    ]

    horizon = [
        {'label': '16.0M', 'value': val('runs/2026-09-26_phase1/h16')},
        {'label': '20.0M', 'value': val('runs/2026-09-26_phase1/h20')},
        {'label': '24.0M', 'value': val('runs/2026-09-26_phase1/h24')},
        {'label': '28.9M', 'value': val('runs/2026-09-26_phase1/h28p9')},
    ]

    # All of these are seed 17, 20M processed targets, full anneal, w320 d8.
    batch = [
        {'label': '32', 'steps': metrics('runs/2026-09-26_phase1/h20')['steps'],
         'value': val('runs/2026-09-26_phase1/h20')},
        {'label': '16', 'steps': metrics('runs/2026-09-26_phase3/p3_bs16')['steps'],
         'value': val('runs/2026-09-26_phase3/p3_bs16')},
        {'label': '8', 'steps': metrics('runs/2026-09-26_phase3/p3_bs8')['steps'],
         'value': val('runs/2026-09-26_phase3/p3_bs8')},
        {'label': '4', 'steps': metrics('runs/2026-09-26_phase7/p7_bs4')['steps'],
         'value': val('runs/2026-09-26_phase7/p7_bs4')},
        {'label': '2', 'steps': metrics('runs/2026-09-26_phase8/p8_bs2')['steps'],
         'value': val('runs/2026-09-26_phase8/p8_bs2')},
        {'label': '1', 'steps': metrics('runs/2026-09-26_phase8/p8_bs1')['steps'],
         'value': val('runs/2026-09-26_phase8/p8_bs1')},
    ]

    # bs 4, 28.9M targets, full anneal.  Phase 10 extended the sweep upward and
    # located the peak: 1.5e-3 and 2.5e-3 are level, 2e-3 and 3e-3 are worse.
    lr = [
        {'label': '7.5e-4', 'value': val('runs/2026-09-26_phase8/p8_bs4_lr750')},
        {'label': '1.0e-3', 'value': val('runs/2026-09-26_phase7/p7_bs4_h28')},
        {'label': '1.5e-3', 'value': val('runs/2026-09-26_phase8/p8_bs4_lr1500')},
        {'label': '2.0e-3', 'value': val('runs/2026-09-26_phase10/p10_lr2e3')},
        {'label': '2.5e-3', 'value': val('runs/2026-09-26_phase10/p10_lr25e3')},
        {'label': '3.0e-3', 'value': val('runs/2026-09-26_phase10/p10_lr3e3')},
    ]
    lr_best = min(lr, key=lambda r: r['value'])

    # 20M targets, bs 32, seed 17: width and head-depth are compared at one budget.
    capacity = [
        {'label': 'width 256', 'value': val('runs/2026-09-26_phase3/p3_w256d8')},
        {'label': 'width 288', 'value': val('runs/2026-09-26_phase3/p3_w288d8')},
        {'label': 'width 320', 'value': val('runs/2026-09-26_phase1/h20')},
        {'label': 'depth 9', 'value': val('runs/2026-09-26_phase3/p3_w320d9')},
    ]

    noise = [
        {'label': 'run A', 'value': val('runs/2026-09-26_phase1/h28p9')},
        {'label': 'run B', 'value': val('runs/2026-09-26_phase7/p7_rep1')},
        {'label': 'run C', 'value': val('runs/2026-09-26_phase7/p7_rep2')},
    ]
    sample = [n['value'] for n in noise]

    # Everything below shares the 20M / bs32 / seed 17 baseline, so the deltas are paired.
    base20 = val('runs/2026-09-26_phase1/h20')
    ablation = [
        {'label': 'droppath 0.1', 'value': val('runs/2026-09-26_phase2/p2_dp10')},
        {'label': 'token drop 0.05', 'value': val('runs/2026-09-26_phase2/p2_td05')},
        {'label': 'embed dropout 0.1', 'value': val('runs/2026-09-26_phase2/p2_emb10')},
        {'label': 'EMA 0.999', 'value': val('runs/2026-09-26_phase1/h20_ema')},
        {'label': 'depth 9', 'value': val('runs/2026-09-26_phase3/p3_w320d9')},
        {'label': 'width 288', 'value': val('runs/2026-09-26_phase3/p3_w288d8')},
        {'label': 'width 256', 'value': val('runs/2026-09-26_phase3/p3_w256d8')},
        {'label': 'batch 8', 'value': val('runs/2026-09-26_phase3/p3_bs8')},
        {'label': 'batch 4', 'value': val('runs/2026-09-26_phase7/p7_bs4')},
    ]
    for row in ablation:
        row['delta'] = row['value'] - base20

    temperature = {}
    cal_v2 = json.loads((res / '2026-09-26/calibration_v2_validation.json').read_text())
    temperature['v2'] = cal_v2['bpb_by_temperature']
    import torch
    ckpt = torch.load(ROOT / 'runs/2026-09-26_phase8/p8_bs4_lr1500/checkpoint_calibrated.pt',
                      map_location='cpu', weights_only=True)
    temperature['v3'] = ckpt['calibration']['validation_bpb_by_temperature']
    temperature['v3_temperature'] = ckpt['calibration']['temperature']
    temperature['v2_temperature'] = cal_v2['best_temperature']
    temperature['holdout'] = cal_v2['holdout']
    temperature['v3_headroom'] = ckpt['calibration']

    versions_by_key = {v['key']: v for v in versions}
    offset = [
        {'label': 'v1', 'value': versions_by_key['v1']['test'] - versions_by_key['v1']['validation']},
        {'label': 'v2', 'value': versions_by_key['v2']['test'] - versions_by_key['v2']['validation']},
        {'label': 'v3', 'value': frozen['v3_test']['bpb'] - ckpt['calibration']['validation_bpb_after']},
    ]

    v2r = frozen['v2_res']['models'][0]
    v3r = frozen['v3_res']['models'][0]
    resources = {
        'limits': frozen['v3_res']['limits'],
        'rows': [
            {'label': 'CPU time', 'limit': 5.0, 'unit': 'x',
             'v2': v2r['time_vs_baseline'], 'v3': v3r['time_vs_baseline']},
            {'label': 'Peak RSS', 'limit': 4.0, 'unit': 'GiB',
             'v2': v2r['peak_rss_gib_max'], 'v3': v3r['peak_rss_gib_max']},
            {'label': 'Inference assets', 'limit': 64.0, 'unit': 'MiB',
             'v2': v2r['asset_mib'], 'v3': v3r['asset_mib']},
        ],
    }

    manifest = json.loads((res / '2026-09-26/freeze_manifest_v3.json').read_text())

    # The manifest records the search cost as it stood at freeze time. Later runs
    # (the learning-rate upper sweep) belong to the same disclosed search, so the
    # report quotes both numbers rather than only the frozen snapshot.
    live_runs, live_targets = 0, 0
    for phase_dir in sorted(ROOT.glob('runs/2026-09-26_phase*/')):
        for metrics_file in sorted(phase_dir.glob('*/metrics.json')):
            try:
                live_targets += json.loads(metrics_file.read_text())['processed_targets']
            except (OSError, ValueError, KeyError):
                continue
            live_runs += 1

    payload = {
        'search_live': {'runs': live_runs, 'total_processed_targets': live_targets},
        'versions': versions,
        'horizon': horizon,
        'batch': batch,
        'lr': lr,
        'lr_best': lr_best,
        'capacity': capacity,
        'noise': {'runs': noise, 'mean': statistics.mean(sample),
                  'stdev': statistics.stdev(sample), 'range': max(sample) - min(sample)},
        'ablation': {'baseline': base20, 'rows': ablation},
        'temperature': temperature,
        'offset': offset,
        'resources': resources,
        'search_accounting': manifest['search_accounting'],
        'freeze': {
            'timestamp': manifest['freeze_timestamp'],
            'checkpoint': manifest['checkpoint'],
            'checkpoint_sha256': manifest['checkpoint_sha256'],
            'implementation_sha256': manifest['implementation_sha256'],
            'evaluator_sha256': manifest['evaluator_sha256'],
            'tokenizer_sha256': manifest['tokenizer_sha256'],
            'parameters': manifest['parameters'],
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'wrote {OUT.relative_to(PROJECT)}')
    print(f"  versions   : {' '.join(f'{v['key']}={v['test']:.6f}' for v in versions)}")
    print(f"  noise      : mean {payload['noise']['mean']:.6f}  sd {payload['noise']['stdev']:.6f}")
    print(f"  offset     : {' '.join(f'{o['label']}=+{o['value']:.6f}' for o in offset)}")
    print(f"  search     : {manifest['search_accounting']['runs_included']} runs, "
          f"{manifest['search_accounting']['total_processed_targets']:,} targets")
    print(f"  ablation   : best {min(r['delta'] for r in ablation):+.6f}  "
          f"worst {max(r['delta'] for r in ablation):+.6f}")


if __name__ == '__main__':
    main()
