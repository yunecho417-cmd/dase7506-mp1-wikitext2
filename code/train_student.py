"""Student trainer for MP1.

Implements the recipe documented in the repository README and experiment log:

  * selectable with- or without-replacement window sampling;
  * selectable classroom-baseline or warmup/cosine learning-rate schedule;
  * optional EMA / tail weight averaging: averaged weights are what gets saved,
    so averaging costs nothing at inference time.
  * optional multi-token prediction (MTP) auxiliary loss: extra Linear(width,width)
    probes sharing the tied output embedding. Training-only, zero inference cost
    and zero extra checkpoint bytes.

Nothing outside this file, student.py and configs/ is modified; model.py,
common.py, evaluate.py and data/ stay byte-identical for clean comparisons.
"""
import argparse
import json
import math
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch import nn

from common import PROTOCOL, ROOT, load_data, make_model, sha, windows

TRAIN_TOKENS_PER_EPOCH = 3_613_343  # measured: WikiText-2 train split, BPE-2048


def get_lr(step, total, peak, warmup, min_frac):
    if step < warmup:
        return peak * (step + 1) / max(1, warmup)
    progress = (step - warmup) / max(1, total - warmup)
    return peak * (min_frac + (1 - min_frac) * .5 * (1 + math.cos(math.pi * progress)))


def get_baseline_lr(step, total, peak, warmup_steps, min_frac):
    """Match the supplied trainer's warmup multiplied by full-horizon cosine."""
    warmup_scale = min(1., (step + 1) / max(1, warmup_steps))
    cosine = min_frac + (1 - min_frac) * .5 * (1 + math.cos(math.pi * step / total))
    return peak * warmup_scale * cosine


class PermutationBatchLoader:
    """Streams batches from a shuffled permutation of every legal window start."""

    def __init__(self, tokens, context, seed):
        self.tokens = tokens
        self.context = context
        self.n_starts = len(tokens) - context - 1
        self.generator = torch.Generator().manual_seed(seed)
        self.order = self._shuffle()
        self.pointer = 0

    def _shuffle(self):
        return torch.randperm(self.n_starts, generator=self.generator)

    def next(self, batch_size):
        needed = batch_size
        starts = []
        while needed > 0:
            take = min(needed, len(self.order) - self.pointer)
            starts.append(self.order[self.pointer:self.pointer + take])
            self.pointer += take
            needed -= take
            if self.pointer >= len(self.order):
                self.order = self._shuffle()
                self.pointer = 0
        starts = torch.cat(starts)
        spans = starts[:, None] + torch.arange(self.context + 1)
        return self.tokens[spans]


class RandomBatchLoader:
    """Sample legal window starts with replacement, matching the supplied trainer."""

    def __init__(self, tokens, context, seed):
        self.tokens = tokens
        self.context = context
        self.n_starts = len(tokens) - context - 1
        self.generator = torch.Generator().manual_seed(seed)

    def next(self, batch_size):
        starts = torch.randint(self.n_starts, (batch_size,), generator=self.generator)
        spans = starts[:, None] + torch.arange(self.context + 1)
        return self.tokens[spans]


@torch.no_grad()
def validate(model, tokens, byte_count, device, batch_size=32):
    """Same windows / same masking / same normalisation as evaluate.score()."""
    previous = model.training
    model.eval()
    nll, count = 0., 0
    for x, y in windows(tokens, batch_size):
        logits = model(x.to(device)).float()
        losses = F.cross_entropy(logits.flatten(0, 1), y.to(device).flatten(), reduction='sum')
        nll += losses.item()
        count += (y != -100).sum().item()
    model.train(previous)
    return {'bpb': nll / math.log(2) / byte_count, 'token_ppl': math.exp(nll / count),
            'nll_nats': nll, 'validation_targets': count}


class TailAverager:
    def __init__(self, parameters, decay, start_step):
        self.decay = decay
        self.start_step = start_step
        self.shadow = [p.detach().clone().float() for p in parameters]
        self.active = False

    @torch.no_grad()
    def update(self, parameters, step):
        if step < self.start_step:
            return
        if not self.active:
            for s, p in zip(self.shadow, parameters):
                s.copy_(p.detach().float())
            self.active = True
            return
        for s, p in zip(self.shadow, parameters):
            s.mul_(self.decay).add_(p.detach().float(), alpha=1 - self.decay)

    @torch.no_grad()
    def apply_to(self, parameters):
        if not self.active:
            return False
        for p, s in zip(parameters, self.shadow):
            p.data.copy_(s.to(p.dtype))
        return True


def main():
    started_total = time.perf_counter()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--implementation', default='student')
    p.add_argument('--config', type=Path, default=ROOT / 'configs/ours_a.json')
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--device', default='mps', choices=['cpu', 'mps', 'cuda'])
    p.add_argument('--precision', default='bf16', choices=['fp32', 'bf16'])
    p.add_argument('--threads', type=int, default=4)
    p.add_argument('--seed', type=int, default=17)
    p.add_argument('--batch-size', type=int, default=32)
    p.add_argument('--epochs', type=float, default=8.)
    p.add_argument('--targets', type=int, default=0, help='Overrides --epochs when > 0.')
    p.add_argument('--lr', type=float, default=2e-3)
    p.add_argument('--wd', type=float, default=.1)
    p.add_argument('--warmup-frac', type=float, default=.03)
    p.add_argument('--baseline-warmup-steps', type=int, default=100)
    p.add_argument('--min-lr-frac', type=float, default=.1)
    p.add_argument('--schedule', choices=['cosine', 'baseline'], default='cosine')
    p.add_argument('--sampling', choices=['without-replacement', 'with-replacement'],
                   default='without-replacement')
    p.add_argument('--beta2', type=float, default=.95)
    p.add_argument('--clip', type=float, default=1.)
    p.add_argument('--label-smoothing', type=float, default=0.)
    p.add_argument('--ema', type=float, default=0., help='EMA decay; 0 disables averaging.')
    p.add_argument('--ema-start-frac', type=float, default=.8)
    p.add_argument('--mtp-k', type=int, default=0, help='Extra future targets; 0 disables MTP.')
    p.add_argument('--mtp-weight', type=float, default=.15)
    p.add_argument('--evals', type=int, default=4, help='Validation evaluations during training.')
    p.add_argument('--eval-at-targets', default='',
                   help='Comma-separated processed-target counts; overrides --evals when set.')
    p.add_argument('--select-best-validation', action='store_true',
                   help='Save the lowest-BPB checkpoint among declared validation points.')
    p.add_argument('--log-every', type=int, default=100)
    args = p.parse_args()

    if args.run_dir.exists() and any(args.run_dir.iterdir()):
        p.error('Run directory already contains results. Use a new --run-dir.')
    if args.select_best_validation and args.ema > 0:
        p.error('--select-best-validation and --ema are separate ablations; do not combine them.')

    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    torch.set_float32_matmul_precision('highest')
    device = torch.device(args.device)
    use_amp = args.precision == 'bf16' and args.device != 'cpu'
    amp_dtype = torch.bfloat16

    data = load_data()
    config = json.loads(args.config.read_text())
    model, implementation_sha = make_model(args.implementation, config, device)
    parameters = list(model.parameters())

    width = config['width']
    mtp = None
    if args.mtp_k > 0:
        mtp = nn.ModuleList([nn.Linear(width, width, bias=False) for _ in range(args.mtp_k)]).to(device)
        for head in mtp:
            nn.init.normal_(head.weight, std=.02)
        parameters = parameters + list(mtp.parameters())

    total_targets = args.targets or int(round(args.epochs * TRAIN_TOKENS_PER_EPOCH))
    per_step = args.batch_size * 256
    steps = max(1, math.ceil(total_targets / per_step))
    warmup = max(1, int(args.warmup_frac * steps))

    optimizer = torch.optim.AdamW(parameters, lr=args.lr, weight_decay=args.wd,
                                  betas=(.9, args.beta2), eps=1e-8)
    averager = TailAverager(model.parameters(), args.ema, int(args.ema_start_frac * steps)) \
        if args.ema > 0 else None

    loader_cls = PermutationBatchLoader \
        if args.sampling == 'without-replacement' else RandomBatchLoader
    loader = loader_cls(data['train'][0], 256, args.seed)
    args.run_dir.mkdir(parents=True, exist_ok=True)

    printable = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    print(json.dumps({'config': config, 'args': printable, 'steps': steps,
                      'parameters': sum(q.numel() for q in model.parameters()),
                      'total_targets': steps * per_step}), flush=True)

    history, curve, started = [], [], time.perf_counter()
    best_state, best_metrics, best_step = None, None, None
    eval_seconds = 0.
    if args.eval_at_targets:
        requested_targets = [int(value.strip()) for value in args.eval_at_targets.split(',')
                             if value.strip()]
        eval_points = {min(steps, max(1, math.ceil(value / per_step)))
                       for value in requested_targets}
    else:
        eval_points = set(max(1, round(steps * i / args.evals))
                          for i in range(1, args.evals + 1)) if args.evals > 0 else set()

    for step in range(steps):
        if args.schedule == 'baseline':
            learning_rate = get_baseline_lr(
                step, steps, args.lr, args.baseline_warmup_steps, args.min_lr_frac)
        else:
            learning_rate = get_lr(step, steps, args.lr, warmup, args.min_lr_frac)
        for group in optimizer.param_groups:
            group['lr'] = learning_rate
        batch = loader.next(args.batch_size).to(device)
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=use_amp):
            hidden = model.features(batch[:, :-1])
            logits = model.head(hidden).float()
            loss = F.cross_entropy(logits.flatten(0, 1), batch[:, 1:].flatten(),
                                   label_smoothing=args.label_smoothing)
            if mtp is not None:
                embed = model.token.weight
                for k, head in enumerate(mtp, start=1):
                    future = head(hidden[:, :-k, :]) if k < hidden.shape[1] else None
                    if future is None:
                        continue
                    aux = future @ embed.T
                    target = batch[:, 1 + k:].reshape(-1)
                    loss = loss + args.mtp_weight / k * F.cross_entropy(
                        aux.reshape(-1, aux.shape[-1]), target)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, args.clip)
        optimizer.step()
        if averager is not None:
            averager.update(model.parameters(), step)

        if (step + 1) % args.log_every == 0 or step + 1 == steps:
            row = {'step': step + 1, 'lr': learning_rate, 'loss': loss.item(),
                   'seconds': time.perf_counter() - started - eval_seconds}
            history.append(row)
            print(json.dumps(row), flush=True)
        if (step + 1) in eval_points:
            began = time.perf_counter()
            metrics = validate(model, *data['validation'], device)
            eval_seconds += time.perf_counter() - began
            curve.append({'step': step + 1,
                          'processed_targets': (step + 1) * per_step,
                          **metrics})
            if args.select_best_validation and (
                    best_metrics is None or metrics['bpb'] < best_metrics['bpb']):
                best_state = {key: value.detach().cpu().clone()
                              for key, value in model.state_dict().items()}
                best_metrics = dict(metrics)
                best_step = step + 1
            print(json.dumps({'validation': curve[-1]}), flush=True)

    train_seconds = time.perf_counter() - started - eval_seconds
    final = validate(model, *data['validation'], device)
    used_average = False
    average_curve = []
    if averager is not None:
        snapshot = {k: v.detach().clone() for k, v in model.state_dict().items()}
        used_average = averager.apply_to(model.parameters())
        average_curve.append({'weights': 'averaged', **validate(model, *data['validation'], device)})
        average_curve.append({'weights': 'live', **final})
        model.load_state_dict(snapshot)
        if average_curve[0]['bpb'] < final['bpb']:
            final = average_curve[0]
            used_average = True
        else:
            print(json.dumps({'warning': 'averaged weights were worse; keeping live weights'}), flush=True)
    if used_average:
        averager.apply_to(model.parameters())

    selected_step = steps
    if args.select_best_validation and best_state is not None \
            and best_metrics['bpb'] < final['bpb']:
        model.load_state_dict(best_state)
        final = best_metrics
        selected_step = best_step

    checkpoint = args.run_dir / 'checkpoint.pt'
    torch.save({'protocol': PROTOCOL, 'implementation': args.implementation, 'config': config,
                'model': model.cpu().state_dict(), 'seed': args.seed,
                'train_tokens': selected_step * per_step}, checkpoint)
    result = {'protocol': PROTOCOL, 'run_dir': str(args.run_dir), 'args': printable,
              'config': config, 'seed': args.seed, 'steps': steps,
              'parameters': sum(q.numel() for q in model.parameters()),
              'asset_mib': checkpoint.stat().st_size / 2 ** 20,
              'processed_targets': steps * per_step,
              'checkpoint_processed_targets': selected_step * per_step,
              'selected_step': selected_step,
              'train_seconds': train_seconds, 'validation_seconds': eval_seconds,
              'validation': final, 'used_averaged_weights': used_average,
              'averaging_comparison': average_curve, 'history': history, 'curve': curve,
              'checkpoint_sha256': sha(checkpoint), 'implementation_sha256': implementation_sha,
              'torch_version': str(torch.__version__),
              'process_seconds': time.perf_counter() - started_total}
    (args.run_dir / 'metrics.json').write_text(json.dumps(result, indent=2) + '\n')
    (args.run_dir / 'curve.json').write_text(json.dumps(curve, indent=2) + '\n')
    print(json.dumps(result | {'history': [], 'curve': []}, indent=2), flush=True)


if __name__ == '__main__':
    main()
