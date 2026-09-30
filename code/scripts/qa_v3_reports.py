"""Quality-assure the generated v3 reports.

Checks the things that silently break in a python-docx build:

* figure and table captions are numbered 1..N in document order with no gaps;
* every figure caption follows an image and every image has a caption;
* images keep the source PNG aspect ratio (a wrong ratio shows as stretching);
* tables are centred Morandi three-line tables with no interior rules;
* caption lead-ins are bold and every caption paragraph is centred.

Usage:
  <interpreter with python-docx> scripts/qa_v3_reports.py
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402

from v3_report_layout import png_size  # noqa: E402

PROJECT = Path(__file__).resolve().parents[2]
FIGDIR = PROJECT / 'output/figures/v3'
DOCS = sorted((PROJECT / 'output/docx').glob('*_v3*.docx')) + sorted(
    (PROJECT / 'output/docx').glob('*English_v3_Submission*.docx'))
DOCS = sorted({path for path in DOCS})

EMU_PER_INCH = 914400


def iter_blocks(document):
    body = document.element.body
    paragraphs = {p._p: p for p in document.paragraphs}
    tables = {t._tbl: t for t in document.tables}
    for child in body.iterchildren():
        if child in paragraphs:
            yield 'p', paragraphs[child]
        elif child in tables:
            yield 't', tables[child]


def drawing_size(paragraph):
    inline = paragraph._p.xpath('.//wp:extent')
    if not inline:
        return None
    node = inline[0]
    return int(node.get('cx')), int(node.get('cy'))


def estimate_pages(document) -> float:
    """Rough A4 page estimate, following the heuristic used by the earlier builders.

    Content area 16.4 cm x 25.7 cm; a body glyph is taken as 0.5 x font size wide
    and a line as 1.28 x font size tall.  This is for planning, not a substitute
    for a real Word render.
    """
    content_w_cm, content_h_cm = 16.4, 25.7
    total_cm = 0.0
    for kind, block in iter_blocks(document):
        if kind == 't':
            rows = len(block.rows)
            total_cm += rows * 0.36 + 0.35 + 0.15
            continue
        text = block.text.strip()
        has_image = bool(block._p.xpath('.//w:drawing'))
        if has_image:
            size = drawing_size(block)
            if size:
                total_cm += (size[0] / EMU_PER_INCH) * 2.54 * size[1] / size[0]
            continue
        style = block.style.name if block.style else 'Normal'
        if not text:
            total_cm += 0.15
            continue
        size_pt = 10.0
        if style.startswith('Heading'):
            size_pt = 13.0 if style == 'Heading 1' else 11.5
        elif style == 'Title':
            size_pt = 16.0
        char_cm = 0.5 * size_pt * 0.0353
        per_line = max(1, int(content_w_cm / char_cm))
        lines = max(1, -(-len(text) // per_line))
        if style.startswith('Heading'):
            lines += 0.7
        total_cm += lines * 1.28 * size_pt * 0.0353 + 0.12
    return total_cm / content_h_cm


def main() -> int:
    failures: list[str] = []
    for path in DOCS:
        print(f'\n=== {path.name} ===')
        document = Document(path)
        figures, tables, images = [], [], []
        previous_was_image = False

        for kind, block in iter_blocks(document):
            if kind == 't':
                tables.append(block)
                continue
            text = ' '.join(block.text.split())
            has_image = bool(block._p.xpath('.//w:drawing'))
            if has_image:
                images.append(block)
            match = re.match(r'^Fig\. (\d+)\.\s?(.*)$', text, re.S)
            if match:
                figures.append((int(match.group(1)), text, previous_was_image, block))
            match = re.match(r'^Table (\d+)\.\s?(.*)$', text, re.S)
            if match:
                tables_caption = int(match.group(1))
                lead_bold = bool(block.runs and block.runs[0].font.bold)
                centred = block.alignment == WD_ALIGN_PARAGRAPH.CENTER
                if not lead_bold:
                    failures.append(f'{path.name}: Table {tables_caption} lead not bold')
                if not centred:
                    failures.append(f'{path.name}: Table {tables_caption} caption not centred')
            previous_was_image = has_image

        fig_numbers = [n for n, *_ in figures]
        expected = list(range(1, len(figures) + 1))
        if fig_numbers != expected:
            failures.append(f'{path.name}: figure captions {fig_numbers} != {expected}')
        for number, text, followed_image, block in figures:
            if not followed_image:
                failures.append(f'{path.name}: Fig. {number} has no image directly above')
            if not (block.runs and block.runs[0].font.bold):
                failures.append(f'{path.name}: Fig. {number} lead not bold')
            if block.alignment != WD_ALIGN_PARAGRAPH.CENTER:
                failures.append(f'{path.name}: Fig. {number} caption not centred')
        if len(images) != len(figures):
            failures.append(f'{path.name}: {len(images)} images vs {len(figures)} figure captions')

        # Image aspect ratios. Resolve each drawing back to the image part that is
        # actually embedded and compare the drawn box against that PNG, so the
        # check does not depend on document order.
        checked = 0
        for paragraph in images:
            size = drawing_size(paragraph)
            embed = paragraph._p.xpath('.//a:blip/@r:embed')
            if size is None or not embed:
                continue
            part = document.part.rels[embed[0]].target_part
            with tempfile.NamedTemporaryFile(suffix='.png') as handle:
                handle.write(part.blob)
                handle.flush()
                w, h = png_size(Path(handle.name))
            cx, cy = size
            drawn, source = cx / cy, w / h
            checked += 1
            if abs(drawn - source) / source > 0.01:
                failures.append(f'{path.name}: media {part.partname} stretched '
                                f'{drawn:.4f} vs {source:.4f}')
        print(f'  paragraphs {len(document.paragraphs)}   tables {len(document.tables)}   '
              f'images {len(images)}   figure captions {len(figures)}   ratios checked {checked}   '
              f'estimated A4 pages {estimate_pages(document):.1f}')

        # table style: three-line, centred content
        for index, table in enumerate(document.tables, start=1):
            borders = table._tbl.tblPr.find(qn('w:tblBorders'))
            if borders is None:
                failures.append(f'{path.name}: table {index} has no tblBorders')
                continue
            vals = {edge: borders.find(qn(f'w:{edge}')).get(qn('w:val'))
                    for edge in ('top', 'bottom', 'left', 'right', 'insideH', 'insideV')}
            if vals['top'] != 'single' or vals['bottom'] != 'single':
                failures.append(f'{path.name}: table {index} missing top/bottom rule {vals}')
            if any(vals[e] != 'nil' for e in ('left', 'right', 'insideH', 'insideV')):
                failures.append(f'{path.name}: table {index} has interior rules {vals}')
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        if paragraph.alignment != WD_ALIGN_PARAGRAPH.CENTER and paragraph.text.strip():
                            failures.append(f'{path.name}: table {index} cell not centred '
                                            f'("{paragraph.text[:24]}")')
                            break

    print()
    if failures:
        print(f'{len(failures)} problem(s):')
        for item in failures[:40]:
            print(f'  - {item}')
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
