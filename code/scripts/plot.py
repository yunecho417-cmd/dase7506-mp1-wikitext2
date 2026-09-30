"""Generate a compact, dependency-free, publication-style SVG summary.

The figure uses a restrained, color-blind-safe palette, four aligned panels,
direct annotations and vector text/lines suitable for SCI, CVPR and ACL papers.
Only Python's standard library is required.
"""
import argparse
import csv
import html
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COLORS = {
    'blue': '#0072B2',
    'orange': '#D55E00',
    'green': '#009E73',
    'purple': '#CC79A7',
    'gray': '#6B7280',
    'grid': '#E5E7EB',
    'axis': '#6B7280',
    'text': '#111827',
    'light': '#EEF2F7',
}


def read_grid(path):
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    for row in rows:
        for key in ('targets', 'params', 'lr', 'wd', 'drop', 'ema', 'mib',
                    'val_bpb', 'val_ppl', 'train_s'):
            row[key] = float(row[key]) if row.get(key) not in ('', None) else None
    return rows


def curve_for(run):
    path = ROOT / 'runs' / run / 'curve.json'
    if not path.exists():
        return []
    raw = json.loads(path.read_text())
    batch_size = 32
    metrics_path = path.with_name('metrics.json')
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text())
        batch_size = int((metrics.get('args') or {}).get('batch_size', 32))
    points = []
    for point in raw:
        processed = point.get('processed_targets')
        if processed is None:
            processed = int(point['step']) * batch_size * 256
        points.append((processed / 1e6, float(point['bpb'])))
    return points


def find_row(rows, name):
    return next((row for row in rows if row['run'] == name), None)


def esc(value):
    return html.escape(str(value))


class SVG:
    def __init__(self, width=1200, height=870):
        self.width = width
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            '<style>'
            'text{font-family:Arial,Helvetica,sans-serif;fill:#111827}'
            '.title{font-size:20px;font-weight:700}'
            '.panel{font-size:15px;font-weight:700}'
            '.axislabel{font-size:12px}'
            '.tick{font-size:10.5px;fill:#4B5563}'
            '.legend{font-size:10.5px}'
            '.note{font-size:10px;fill:#4B5563}'
            '</style>',
        ]

    def line(self, x1, y1, x2, y2, color, width=1, dash=None):
        extra = f' stroke-dasharray="{dash}"' if dash else ''
        self.parts.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            f'stroke="{color}" stroke-width="{width}"{extra}/>')

    def text(self, x, y, value, css='tick', anchor='start', rotate=None,
             color=None):
        transform = f' transform="rotate({rotate} {x:.2f} {y:.2f})"' if rotate else ''
        fill = f' style="fill:{color}"' if color else ''
        self.parts.append(
            f'<text x="{x:.2f}" y="{y:.2f}" class="{css}" '
            f'text-anchor="{anchor}"{transform}{fill}>{esc(value)}</text>')

    def circle(self, x, y, radius, color, fill=True, width=1):
        fill_color = color if fill else 'white'
        self.parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" '
            f'fill="{fill_color}" stroke="{color}" stroke-width="{width}"/>')

    def rect(self, x, y, width, height, color, radius=0):
        self.parts.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" '
            f'height="{height:.2f}" rx="{radius}" fill="{color}"/>')

    def polyline(self, points, color, width=2):
        value = ' '.join(f'{x:.2f},{y:.2f}' for x, y in points)
        self.parts.append(
            f'<polyline points="{value}" fill="none" stroke="{color}" '
            f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')

    def finish(self):
        return '\n'.join(self.parts + ['</svg>', ''])


class Panel:
    def __init__(self, svg, x, y, width, height, title, x_label, y_label,
                 x_range, y_range, x_ticks, y_ticks, log_x=False):
        self.svg = svg
        self.x = x + 58
        self.y = y + 34
        self.width = width - 76
        self.height = height - 79
        self.x_range = x_range
        self.y_range = y_range
        self.log_x = log_x
        svg.text(x, y + 15, title, 'panel')
        for tick in y_ticks:
            py = self.sy(tick)
            svg.line(self.x, py, self.x + self.width, py, COLORS['grid'], .8)
            svg.text(self.x - 8, py + 3.5, f'{tick:.2f}', 'tick', 'end')
        for tick, label in x_ticks:
            px = self.sx(tick)
            svg.line(px, self.y + self.height, px, self.y + self.height + 4,
                     COLORS['axis'], .8)
            svg.text(px, self.y + self.height + 17, label, 'tick', 'middle')
        svg.line(self.x, self.y, self.x, self.y + self.height, COLORS['axis'], 1)
        svg.line(self.x, self.y + self.height, self.x + self.width,
                 self.y + self.height, COLORS['axis'], 1)
        svg.text(self.x + self.width / 2, y + height - 3, x_label,
                 'axislabel', 'middle')
        svg.text(x + 12, self.y + self.height / 2, y_label,
                 'axislabel', 'middle', -90)

    def sx(self, value):
        lo, hi = self.x_range
        if self.log_x:
            value, lo, hi = math.log10(value), math.log10(lo), math.log10(hi)
        return self.x + (value - lo) / (hi - lo) * self.width

    def sy(self, value):
        lo, hi = self.y_range
        return self.y + self.height - (value - lo) / (hi - lo) * self.height

    def plot(self, points, color, radius=4):
        mapped = [(self.sx(x), self.sy(y)) for x, y in points]
        if len(mapped) > 1:
            self.svg.polyline(mapped, color, 2)
        for x, y in mapped:
            self.svg.circle(x, y, radius, color)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--grid', type=Path, default=ROOT / 'results/grid.tsv')
    parser.add_argument('--resources', type=Path,
                        default=ROOT / 'results/resources_validation.json')
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'results/figures/experiment_summary.svg')
    args = parser.parse_args()
    rows = read_grid(args.grid)
    if not rows:
        raise SystemExit('No experiment rows found. Run scripts/collect.py first.')

    svg = SVG()
    svg.text(600, 31, 'MP1 model quality, optimization and resource efficiency',
             'title', 'middle')
    svg.text(600, 49, 'WikiText-2 · BPE-2048 · validation BPB (lower is better)',
             'note', 'middle')

    p1 = Panel(svg, 34, 68, 548, 365, '(a) Learning dynamics',
               'Processed training targets (million)', 'Validation BPB ↓',
               (0, 30), (1.55, 2.25),
               [(0, '0'), (10, '10'), (20, '20'), (30, '30')],
               [1.6, 1.8, 2.0, 2.2])
    selected = [
        ('s0_lr1e3', 'LN + GELU, 1.08M', COLORS['gray']),
        ('s_lr1e3', 'RMS + SwiGLU, 1.08M', COLORS['green']),
        ('lr1e3_a', 'RMS + SwiGLU, 10.57M', COLORS['blue']),
        ('a_e8_lr1e3', '10.57M, longer training', COLORS['orange']),
    ]
    for index, (run, label, color) in enumerate(selected):
        row = find_row(rows, run)
        if not row:
            continue
        points = curve_for(run) or [(row['targets'] / 1e6, row['val_bpb'])]
        p1.plot(points, color)
        lx, ly = p1.x + 9, p1.y + 14 + index * 17
        svg.line(lx, ly - 3, lx + 21, ly - 3, color, 2)
        svg.circle(lx + 10.5, ly - 3, 3.2, color)
        svg.text(lx + 27, ly, label, 'legend')
    baseline = find_row(rows, 'R0_baseline')
    if baseline:
        by = p1.sy(baseline['val_bpb'])
        svg.line(p1.x, by, p1.x + p1.width, by, COLORS['purple'], 1.5, '7 4')
        svg.text(p1.x + p1.width - 3, by - 5, 'official baseline 2.071',
                 'note', 'end')

    p2 = Panel(svg, 618, 68, 548, 365, '(b) Matched-budget learning-rate sweep',
               'Peak learning rate (log scale)', 'Validation BPB ↓',
               (0.0004, 0.005), (1.75, 2.08),
               [(0.0005, '5e−4'), (0.001, '1e−3'), (0.002, '2e−3'),
                (0.004, '4e−3')],
               [1.8, 1.9, 2.0], log_x=True)
    sweep = [row for row in rows
             if row['cfg'].startswith('w320d8-') and row['targets'] is not None
             and abs(row['targets'] - 9_830_400) < 1 and row['lr'] is not None]
    sweep = [row for row in sweep
             if row['wd'] == 0.1 and row['drop'] == 0 and row['ema'] == 0
             and row.get('pos') == 'learned' and row.get('tie') == '1'
             and row.get('mtp_k') in ('0', 0, None)]
    sweep.sort(key=lambda row: row['lr'])
    if sweep:
        p2.plot([(row['lr'], row['val_bpb']) for row in sweep], COLORS['blue'], 4.5)
        best = min(sweep, key=lambda row: row['val_bpb'])
        bx, by = p2.sx(best['lr']), p2.sy(best['val_bpb'])
        svg.circle(bx, by, 7.5, COLORS['orange'], fill=False, width=2)
        svg.text(bx + 10, by - 8, f"best {best['lr']:.4g}, {best['val_bpb']:.3f}",
                 'note')
    svg.text(p2.x + p2.width - 2, p2.y + 13,
             'wd = 0.1, dropout = 0', 'note', 'end')

    p3 = Panel(svg, 34, 462, 548, 365, '(c) Quality–capacity trade-off',
               'Model parameters (million)', 'Validation BPB ↓',
               (0, 11.4), (1.55, 2.15),
               [(0, '0'), (2, '2'), (4, '4'), (6, '6'), (8, '8'),
                (10, '10')],
               [1.6, 1.8, 2.0])
    for row in rows:
        if not row['targets'] or not row['val_bpb']:
            continue
        color = COLORS['orange'] if row['targets'] > 10_000_000 else COLORS['blue']
        radius = 3.5 + 3 * min(row['targets'] / 30_000_000, 1)
        svg.circle(p3.sx(row['params'] / 1e6), p3.sy(row['val_bpb']), radius, color)
    labels = {
        'R0_baseline': ('baseline', 8, -9),
        's_lr1e3': ('efficient 1.08M', 8, 15),
        'lr1e3_a': ('10.57M / 9.83M targets', -8, -10),
        'a_e8_lr1e3': ('10.57M / 28.91M targets', -8, -10),
    }
    for run, (label, dx, dy) in labels.items():
        row = find_row(rows, run)
        if row:
            anchor = 'end' if dx < 0 else 'start'
            svg.text(p3.sx(row['params'] / 1e6) + dx,
                     p3.sy(row['val_bpb']) + dy, label, 'note', anchor)
    svg.text(p3.x + p3.width - 2, p3.y + 13,
             'marker size ∝ processed targets', 'note', 'end')

    panel_x, panel_y, panel_w, panel_h = 618, 462, 548, 365
    svg.text(panel_x, panel_y + 15, '(d) Inference resource headroom', 'panel')
    labels_r = ['CPU time', 'Peak RAM', 'Assets']
    values = [0, 0, 0]
    details = ['not measured', 'not measured', 'not measured']
    if args.resources.exists():
        data = json.loads(args.resources.read_text())
        models = data.get('models', [])
        if models:
            candidate = min(models, key=lambda row: row['bpb'])
            values = [candidate['time_vs_baseline'] / 5,
                      candidate['peak_rss_gib_max'] / 4,
                      candidate['asset_mib'] / 64]
            details = [f"{candidate['time_vs_baseline']:.2f}× of 5×",
                       f"{candidate['peak_rss_gib_max']:.2f} of 4 GiB",
                       f"{candidate['asset_mib']:.1f} of 64 MiB"]
    bar_x, bar_w = panel_x + 105, 375
    colors = [COLORS['blue'], COLORS['green'], COLORS['orange']]
    for index, (label, value, detail, color) in enumerate(
            zip(labels_r, values, details, colors)):
        y = panel_y + 78 + index * 77
        svg.text(bar_x - 13, y + 15, label, 'axislabel', 'end')
        svg.rect(bar_x, y, bar_w, 24, COLORS['light'], 3)
        svg.rect(bar_x, y, min(value, 1) * bar_w, 24, color, 3)
        svg.text(bar_x + 8, y + 17, detail, 'legend', color='white')
        svg.text(bar_x + bar_w + 9, y + 17, f'{value * 100:.0f}%', 'tick')
    svg.line(bar_x + bar_w, panel_y + 58, bar_x + bar_w,
             panel_y + 251, COLORS['axis'], 1.2, '5 4')
    svg.text(bar_x + bar_w, panel_y + 273, 'budget limit', 'note', 'middle')
    svg.text(panel_x + panel_w / 2, panel_y + panel_h - 4,
             'Fraction of allowed inference budget', 'axislabel', 'middle')

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(svg.finish())
    print(f'wrote {args.output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
