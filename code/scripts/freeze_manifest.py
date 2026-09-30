"""Write a freeze manifest for a candidate predictor BEFORE its test run.

The GUIDE requires the method to be frozen before testing, and the report must
disclose the search cost. This script records both: every hash that pins the
predictor, and the cumulative processed-target count of the whole screening
campaign it was selected from.

It refuses to overwrite an existing manifest, and it records `test_result_at_freeze`
as null so the manifest is provably written before any test number exists.

Usage:
  ./.venv_project1/bin/python scripts/freeze_manifest.py \
      --checkpoint  runs/2026-09-26_phase8/p8_bs4_lr1500/checkpoint_calibrated.pt \
      --output      results/2026-09-26/freeze_manifest_v3.json \
      --selection-rule "..." \
      --search-glob "runs/2026-09-26_phase*/*/metrics.json"
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import PROTOCOL, ROOT, sha  # noqa: E402

TZ = timezone(timedelta(hours=8))


def _count_parameters(config):
    """Build from the config and let nn.Module deduplicate tied weights.

    Counting the state_dict directly is wrong here: with tied embeddings it lists
    token.weight and head.weight as two keys, and after torch.load they are two
    separate tensor objects, so identity-based dedup does not catch them either.
    """
    import torch  # noqa: F401  (kept local so the module imports cheaply)
    from student import build_model
    return sum(p.numel() for p in build_model(config).parameters())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--selection-rule', required=True)
    p.add_argument('--run-metrics', type=Path,
                   help='metrics.json of the training run, for the training arguments and '
                        'the uncalibrated validation score')
    p.add_argument('--search-glob', default='runs/2026-09-26_phase*/*/metrics.json')
    p.add_argument('--notes', default='')
    args = p.parse_args()

    if args.output.exists():
        raise SystemExit(f'refusing to overwrite frozen manifest {args.output}')

    checkpoint = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    if not checkpoint.exists():
        raise SystemExit(f'missing checkpoint {checkpoint}')
    payload = __import__('torch').load(checkpoint, map_location='cpu', weights_only=True)

    search_targets, runs = 0, []
    for metrics in sorted(ROOT.glob(args.search_glob)):
        try:
            d = json.loads(metrics.read_text())
        except (OSError, ValueError):
            continue
        search_targets += d.get('processed_targets', 0)
        runs.append(metrics.parent.name)

    manifest = {
        'status': 'frozen_before_test',
        'freeze_timestamp': datetime.now(TZ).isoformat(timespec='seconds'),
        'protocol': PROTOCOL,
        'decision': 'this predictor is frozen for a single test evaluation '
                    'before any test result for it has been observed',
        'selection_rule': args.selection_rule,
        'checkpoint': str(checkpoint.relative_to(ROOT)),
        'checkpoint_sha256': sha(checkpoint),
        'config_embedded_in_checkpoint': payload['config'],
        # Deduplicate by tensor identity: with tied embeddings the state_dict
        # lists token.weight and head.weight as two keys over one tensor, and a
        # naive sum would over-count the embedding matrix.
        'parameters': _count_parameters(payload['config']),
        'implementation': 'student.py',
        'implementation_sha256': sha(ROOT / 'student.py'),
        'trainer': 'train_student.py',
        'trainer_sha256': sha(ROOT / 'train_student.py'),
        'evaluator_sha256': sha(ROOT / 'evaluate.py'),
        'tokenizer_sha256': sha(ROOT / 'data/tokenizer.json'),
        'training_arguments': None,
        'validation_evidence': None,
        'calibration': payload.get('calibration'),
        'search_accounting': {
            'runs_included': len(runs),
            'run_directories': runs,
            'total_processed_targets': search_targets,
            'glob': args.search_glob,
        },
        'test_result_at_freeze': None,
        'post_test_policy': 'The test result will be reported exactly as observed and will not be '
                            'used to alter, reject, tune, or reselect this frozen predictor.',
        'notes': args.notes,
    }

    if args.run_metrics:
        run_metrics = args.run_metrics if args.run_metrics.is_absolute() \
            else ROOT / args.run_metrics
        source = json.loads(run_metrics.read_text())
        manifest['training_arguments'] = source.get('args')
        manifest['validation_evidence'] = str(run_metrics.relative_to(ROOT))
        manifest['validation_bpb_uncalibrated'] = source['validation']['bpb']
        manifest['checkpoint_processed_targets'] = source.get('checkpoint_processed_targets')
        manifest['selected_step'] = source.get('selected_step')
        manifest['training_seconds'] = source.get('train_seconds')
        manifest['uncalibrated_checkpoint'] = str(
            (run_metrics.parent / 'checkpoint.pt').relative_to(ROOT))
        manifest['uncalibrated_checkpoint_sha256'] = sha(run_metrics.parent / 'checkpoint.pt')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: v for k, v in manifest.items()
                      if k not in ('search_accounting', 'training_arguments',
                                   'config_embedded_in_checkpoint', 'calibration')}, indent=2))
    print(f"\nsearch accounting: {runs.__len__()} runs, "
          f"{search_targets:,} processed targets")
    print(f"\nwrote {args.output}")


if __name__ == '__main__':
    main()
