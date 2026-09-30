"""Generate the MP1 architecture and data-flow diagram as a vector SVG."""
import argparse
import html
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def esc(value):
    return html.escape(str(value))


class Diagram:
    def __init__(self):
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="920" '
            'viewBox="0 0 1400 920">',
            '<rect width="1400" height="920" fill="#FFFFFF"/>',
            '<defs><marker id="arrow" markerWidth="10" markerHeight="10" '
            'refX="8" refY="3" orient="auto" markerUnits="strokeWidth">'
            '<path d="M0,0 L0,6 L9,3 z" fill="#4B5563"/></marker></defs>',
            '<style>'
            'text{font-family:Arial,Helvetica,sans-serif;fill:#111827}'
            '.title{font-size:24px;font-weight:700}'
            '.subtitle{font-size:12px;fill:#4B5563}'
            '.lane{font-size:16px;font-weight:700}'
            '.head{font-size:13px;font-weight:700}'
            '.body{font-size:11px}'
            '.small{font-size:10px;fill:#4B5563}'
            '</style>',
        ]

    def text(self, x, y, value, css='body', anchor='middle', color=None):
        style = f' style="fill:{color}"' if color else ''
        self.parts.append(
            f'<text x="{x}" y="{y}" class="{css}" text-anchor="{anchor}"'
            f'{style}>{esc(value)}</text>')

    def box(self, x, y, w, h, title, lines, fill, stroke='#CBD5E1'):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')
        self.text(x + w / 2, y + 21, title, 'head')
        for index, line in enumerate(lines):
            self.text(x + w / 2, y + 40 + index * 15, line, 'body')

    def arrow(self, x1, y1, x2, y2, label=None):
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            'stroke="#4B5563" stroke-width="1.5" marker-end="url(#arrow)"/>')
        if label:
            self.text((x1 + x2) / 2, (y1 + y2) / 2 - 6, label, 'small')

    def finish(self):
        return '\n'.join(self.parts + ['</svg>', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--output', type=Path,
        default=ROOT / 'results/2026-09-23/architecture_data_flow.svg')
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output

    d = Diagram()
    d.text(700, 35, 'MP1 architecture and end-to-end data flow', 'title')
    d.text(700, 57,
           'Training data flows left to right; frozen evaluation is isolated below.',
           'subtitle')

    d.text(28, 105, '1  Data preparation', 'lane', 'start')
    y = 125
    boxes = [
        (35, 185, 'WikiText-2 train', ['raw UTF-8 bytes', 'training split only']),
        (245, 185, 'Integrity check', ['SHA-256 manifest', 'reject changed data']),
        (455, 185, 'BPE tokenizer', ['fixed vocab = 2048', 'fitted on train']),
        (665, 185, 'Token IDs', ['tensor [N]', 'N = 3,613,343']),
        (875, 185, 'BatchLoader', ['32 windows', '257 tokens each']),
        (1085, 185, 'Shift inputs', ['x = tokens[:-1]', 'y = tokens[1:]']),
    ]
    for x, w, title, lines in boxes:
        d.box(x, y, w, 76, title, lines, '#EFF6FF', '#93C5FD')
    for index in range(len(boxes) - 1):
        x, w, _, _ = boxes[index]
        nx, _, _, _ = boxes[index + 1]
        d.arrow(x + w, y + 38, nx, y + 38)

    d.text(28, 250, '2  Student model forward path', 'lane', 'start')
    d.box(35, 275, 210, 86, 'Input representation',
          ['token embedding [B,T,320]', 'learned position embedding', 'dropout = 0'],
          '#ECFDF5', '#6EE7B7')
    d.arrow(245, 318, 285, 318, 'hidden states')

    d.parts.append(
        '<rect x="285" y="255" width="725" height="225" rx="12" '
        'fill="#F8FAFC" stroke="#64748B" stroke-width="1.5"/>')
    d.text(647, 279, 'Transformer block × 8', 'lane')
    block_boxes = [
        (310, 305, 120, 'RMSNorm', ['pre-norm']),
        (460, 305, 150, 'Q K V', ['4 heads', 'head dim 80']),
        (640, 305, 170, 'Causal SDPA', ['future masked', 'context 256']),
        (840, 305, 140, 'Projection', ['bias free', '+ residual']),
        (390, 395, 125, 'RMSNorm', ['pre-norm']),
        (555, 395, 205, 'SwiGLU FFN', ['SiLU(gate) × up', 'hidden ≈ 853']),
        (800, 395, 150, 'Down projection', ['bias free', '+ residual']),
    ]
    for x, by, w, title, lines in block_boxes:
        d.box(x, by, w, 62, title, lines, '#FFFFFF', '#CBD5E1')
    for a, b in [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6)]:
        x, by, w, _, _ = block_boxes[a]
        nx, nby, _, _, _ = block_boxes[b]
        d.arrow(x + w, by + 31, nx, nby + 31)
    d.arrow(910, 367, 910, 395)
    d.arrow(390, 426, 335, 426)
    d.arrow(335, 426, 335, 337, 'next block')

    d.arrow(1010, 367, 1045, 367)
    d.box(1045, 300, 150, 72, 'Final RMSNorm', ['width 320'],
          '#ECFDF5', '#6EE7B7')
    d.arrow(1195, 336, 1220, 336)
    d.box(1220, 290, 145, 92, 'Tied LM head',
          ['shared token weights', 'logits [B,T,2048]'],
          '#ECFDF5', '#6EE7B7')

    d.text(28, 515, '3  Optimization and checkpoint production', 'lane', 'start')
    train_boxes = [
        (70, 545, 200, 'Cross-entropy', ['next-token targets', 'all 256 positions']),
        (315, 545, 190, 'Backpropagation', ['gradient clip = 1.0']),
        (550, 545, 200, 'AdamW update', ['lr = 1e-3', 'weight decay = 0.1']),
        (795, 545, 220, 'Cosine schedule', ['3% warmup', 'minimum lr = 10%']),
        (1060, 545, 250, 'Checkpoint', ['10,570,560 parameters', '40.345 MiB']),
    ]
    for x, by, w, title, lines in train_boxes:
        d.box(x, by, w, 72, title, lines, '#FFF7ED', '#FDBA74')
    for index in range(len(train_boxes) - 1):
        x, by, w, _, _ = train_boxes[index]
        nx, nby, _, _, _ = train_boxes[index + 1]
        d.arrow(x + w, by + 36, nx, nby + 36)
    d.arrow(1292, 382, 1292, 545, 'logits')

    d.text(28, 660, '4  Frozen evaluation and reporting', 'lane', 'start')
    eval_boxes = [
        (35, 690, 175, 'Frozen checkpoint', ['seed 17 selected', 'no test tuning']),
        (245, 690, 190, 'Independent windows', ['256 targets/window', 'reset every call']),
        (470, 690, 190, 'Log probabilities', ['log-softmax FP32', 'shape [B,T,2048]']),
        (695, 690, 180, 'Target NLL', ['gather true token', 'mask final short window']),
        (910, 690, 200, 'BPB aggregation', ['Σ NLL / ln(2)', '/ raw UTF-8 bytes']),
        (1145, 690, 220, 'Dated outputs', ['JSON + window NLL', 'time, RAM, asset size']),
    ]
    for x, by, w, title, lines in eval_boxes:
        d.box(x, by, w, 80, title, lines, '#F5F3FF', '#C4B5FD')
    for index in range(len(eval_boxes) - 1):
        x, by, w, _, _ = eval_boxes[index]
        nx, nby, _, _, _ = eval_boxes[index + 1]
        d.arrow(x + w, by + 40, nx, nby + 40)

    d.box(285, 810, 250, 65, 'Validation-only selection',
          ['compare recipes and seeds', 'choose lowest full-validation BPB'],
          '#FEFCE8', '#FACC15')
    d.box(575, 810, 220, 65, 'Freeze manifest',
          ['checkpoint + code hashes', 'configuration locked'],
          '#FEFCE8', '#FACC15')
    d.box(835, 810, 255, 65, 'Test once after freeze',
          ['428,405 scored targets', 'final test BPB = 1.646152'],
          '#FEFCE8', '#FACC15')
    d.arrow(535, 842, 575, 842)
    d.arrow(795, 842, 835, 842)
    d.arrow(962, 810, 962, 770)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(d.finish())
    print(f'wrote {output.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
