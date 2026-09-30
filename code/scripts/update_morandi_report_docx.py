"""Replace charts only; preserve experimental prose, tables, equation and flowchart."""
from pathlib import Path
import json
from docx import Document
from docx.oxml.ns import qn

PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT / 'output/docx/DASE7506_Project_1_TECH_Report_中文完整素材稿.docx'
TARGET = PROJECT / 'output/docx/DASE7506_Project_1_TECH_Report_莫兰迪图表版.docx'
PREVIEWS = PROJECT / 'tmp/morandi_charts'

def replace_text(paragraph, text):
    # Do not touch image-only runs. The original font/style stays on the first run.
    if paragraph.text == text:
        return
    if paragraph.runs:
        anchor = next((r for r in paragraph.runs if r.text), paragraph.runs[0])
        anchor.text = text
        for run in paragraph.runs:
            if run._r is not anchor._r and run.text:
                run.text = ''
    else:
        paragraph.add_run(text)

doc = Document(SOURCE)
assert len(doc.inline_shapes) == 25
image_ids = [
    None, None, '01_mainline', '03_lr_validation', '02_lr_loss',
    '04_regularization', '05_v1_curves', '06_test', '07_resources',
    '08_trainer', '09_factorial', '10_capacity', '11_representation',
    '12_rope_tying', '13_training_addons', '15_rope_three_seeds',
    '14_rope_initial', '17_rope_training', '16_paired_long',
    'wall_02_lr_loss_012', 'wall_02_lr_loss_345', 'wall_05_v1_curves',
    'wall_14_rope_initial', 'wall_15_rope_three_seeds', 'wall_17_rope_training',
]
for index, (shape, asset) in enumerate(zip(doc.inline_shapes, image_ids), 1):
    if asset is None:
        continue
    rel = shape._inline.xpath('.//a:blip')[0].get(qn('r:embed'))
    doc.part.related_parts[rel]._blob = (PREVIEWS / f'{asset}.png').read_bytes()
    shape.height = round(shape.width * 720 / 1280)
    props = shape._inline.docPr
    props.set('descr', props.get('descr', props.get('name', asset)) + '。莫兰迪半透明样式。可编辑源见附录 C。')

replace_text(doc.paragraphs[246], '以下为集中保留的曲线素材，不是额外实验。B1–B2 将正文六条学习率曲线拆为两组，其余图便于单独取用。深度仅区分系列，纵轴截断，填充不是误差带。末点表示最后一次观测，不表示最优值。精确比较请看数据表或 PPT 中的二维原生图表。')
replace_text(doc.paragraphs[262], '正文、表格和公式可在 Word 中编辑。实验图统一保存在“MP1_莫兰迪图表_可编辑.pptx”：第 1–23 页可改墙面、曲线、柱面、透明度和文字；第 24–40 页是带内嵌工作簿的二维原生图表，可右键“编辑数据”。两种版本不会自动同步。图 2 的合并流程图仍在独立 PPT 中。')
replace_text(doc.paragraphs[263], '扩展表 E20  Word 图与莫兰迪 PPT 页码对应')
replace_text(doc.paragraphs[265], '图 B1–B6 对应 PPT 第 18–23 页。Word 插图是预览，修改 PPT 后导出图片，再在 Word 中“更改图片”。墙形版不是 Excel 联动图表：若数值改变，应重跑绘图代码计算位置，不宜手拖顶点表示新结果。')
replace_text(doc.paragraphs[266], '数据源：output/figures/full_report/evidence.json。SVG、配色和页码索引：output/figures/morandi/。绘图与 Word 更新代码分别为 code/scripts/build_morandi_report_charts.mjs 和 update_morandi_report_docx.py。重建前请另存人工修改稿。')
# The taller, proportion-correct figure leaves one paragraph on the next page.
# Let the following subsection share that page rather than create an orphan page.
doc.paragraphs[153].paragraph_format.page_break_before = False

mapping = doc.tables[-1]
replace_text(mapping.cell(0, 2).paragraphs[0], '样式 / 数据页')
for row in mapping.rows[1:]:
    page = int(row.cells[2].text)
    replace_text(row.cells[2].paragraphs[0], f'{page} / {page + 23}')

assert len(doc.inline_shapes) == 25
assert len(doc.tables) == 31
assert len(doc._element.xpath('.//m:oMath')) == 1
doc.save(TARGET)
print(TARGET)
