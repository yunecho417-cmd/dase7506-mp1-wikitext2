"""Build the Chinese and English v3 reports.

Both editions are produced from one declarative block list, so the two documents
cannot drift structurally: only the strings differ.  Every number is read from
``output/figures/v3/data.json``, which ``collect_v3_evidence.py`` derives from the
frozen result files, and the appendix index is scanned from the run directories.

The section skeleton deliberately mirrors the v2 report pair
(DASE7506_Project_1_TECH_Report_中文期刊格式版 / _English_Journal_Style): the same
ten numbered sections and the same appendix grouping, so the v3 edition reads as
the next revision of the same document rather than a new one.

Outputs
-------
``output/docx/DASE7506_Project_1_TECH_Report_中文_v3版.docx``
``output/docx/DASE7506_Project_1_TECH_Report_English_v3版.docx``

Usage
-----
    <interpreter with python-docx> scripts/build_v3_reports.py [--compact]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt  # noqa: E402

from v3_report_layout import (  # noqa: E402
    EN_BODY, EN_HEAD, ZH_BODY, ZH_HEAD,
    caption, image, set_font, set_style_font, three_line_table,
)

PROJECT = Path(__file__).resolve().parents[2]
ROOT = PROJECT / 'code'
DATA = PROJECT / 'output/figures/v3/data.json'
FIGDIR = PROJECT / 'output/figures/v3'
OUT = PROJECT / 'output/docx'

ZH_OUT = OUT / 'DASE7506_Project_1_TECH_Report_中文_v3版.docx'
EN_OUT = OUT / 'DASE7506_Project_1_TECH_Report_English_v3版.docx'

PHASES = [
    ('2026-09-26_phase1', 'A.1', '训练预算与完整退火', 'Training budget and full anneal'),
    ('2026-09-26_phase2', 'A.2', '正则化消融', 'Regularisation ablation'),
    ('2026-09-26_phase3', 'A.3', '容量与批量（第一批）', 'Capacity and batch size, first batch'),
    ('2026-09-26_phase7', 'A.4', '批量（第二批）与配对复现', 'Batch size, second batch, and paired replications'),
    ('2026-09-26_phase8', 'A.5', '学习率重扫与批量边界', 'Learning-rate re-sweep and batch bounds'),
    ('2026-09-26_phase10', 'A.6', '学习率上探与批量复核', 'Learning-rate upper sweep and batch check'),
]


def f(value: float, digits: int = 6) -> str:
    return f'{value:.{digits}f}'


def scan_index() -> dict[str, list[list[str]]]:
    """Build the appendix run index straight from the run directories."""
    out: dict[str, list[list[str]]] = {}
    for phase, _, zh_title, _ in PHASES:
        rows = []
        for metrics in sorted((ROOT / 'runs' / phase).glob('*/metrics.json')):
            try:
                d = json.loads(metrics.read_text())
            except (OSError, ValueError):
                continue
            a = d['args']
            rows.append([
                metrics.parent.name, str(d.get('seed', a.get('seed', ''))),
                str(a['batch_size']), f"{a['lr']:g}",
                f"{d['processed_targets'] / 1e6:.2f}M",
                f"{d['validation']['bpb']:.6f}",
            ])
        if rows:
            out[phase] = rows
    return out


ARCHIVE_RUNS = [
    # trainer ladder on the supplied baseline model (width 128 / depth 4)
    'recipe_exact_baseline_s17', 'recipe_norepl_s17', 'recipe_norepl_beta095_s17',
    'recipe_full_student_s17',
    # normalisation x feed-forward 2x2 factorial at the same budget
    's0_lr1e3', 'ablation_ln_swiglu_s17', 'ablation_rms_gelu_s17', 's_lr1e3',
    # representation and weight sharing at width 320 / depth 8
    'lr1e3_a', 'ablation_untied_s17', 'ablation_rope_s17', 'ablation_rope_s137',
    'ablation_rope_untied_s17', 'ablation_rope_untied_s137',
    # training-only mechanisms that carry no inference-time state
    'ablation_rope_untied_ema099_s17', 'ablation_rope_untied_mtp1_s17',
    # regularisation and optimiser probes carried over from the earlier rounds
    'drop005_lr1e3_a', 'wd2e1_lr1e3_a',
    'lr5e4_a', 'lr7p5e4_a', 'lr1p25e3_a', 'lr2e3_a', 'lr4e3_a',
    'capacity_w320d10_s17', 'capacity_w384d8_s17',
]


def archive() -> dict[str, dict]:
    """Load the v1/v2-stage runs that decided the frozen block structure.

    These runs predate this round but they are the reason the final model uses
    RMSNorm + SwiGLU + RoPE + tied weights.  Reading them from ``metrics.json``
    keeps the reported numbers identical to whatever is on disk.
    """
    out: dict[str, dict] = {}
    for name in ARCHIVE_RUNS:
        path = ROOT / 'runs' / name / 'metrics.json'
        d = json.loads(path.read_text())
        out[name] = {
            'bpb': d['validation']['bpb'],
            'params': d['parameters'],
            'targets': d['processed_targets'],
            'seed': d.get('seed'),
            'config': d['config'],
        }
    return out


def archive_effects(a: dict[str, dict]) -> dict[str, float]:
    """Pairwise comparisons behind the structural choices of the frozen model."""
    c_ln_gelu = a['s0_lr1e3']['bpb']
    c_ln_swiglu = a['ablation_ln_swiglu_s17']['bpb']
    c_rms_gelu = a['ablation_rms_gelu_s17']['bpb']
    c_rms_swiglu = a['s_lr1e3']['bpb']
    learned_tied = a['lr1e3_a']['bpb']
    learned_untied = a['ablation_untied_s17']['bpb']
    rope_tied = a['ablation_rope_s17']['bpb']
    rope_tied_alt = a['ablation_rope_s137']['bpb']
    rope_untied = a['ablation_rope_untied_s17']['bpb']
    rope_untied_alt = a['ablation_rope_untied_s137']['bpb']
    base = a['ablation_rope_untied_s17']['bpb']
    return {
        'ffn_main': ((c_ln_swiglu - c_ln_gelu) + (c_rms_swiglu - c_rms_gelu)) / 2,
        'norm_main': ((c_rms_gelu - c_ln_gelu) + (c_rms_swiglu - c_ln_swiglu)) / 2,
        'norm_ffn_interaction': (c_ln_swiglu - c_ln_gelu) - (c_rms_swiglu - c_rms_gelu),
        'rope_gain': rope_tied - learned_tied,
        'untied_on_learned': learned_untied - learned_tied,
        'untied_on_rope_17': rope_untied - rope_tied,
        'untied_on_rope_137': rope_untied_alt - rope_tied_alt,
        'untied_on_rope_mean': ((rope_untied - rope_tied)
                                + (rope_untied_alt - rope_tied_alt)) / 2,
        'untied_interaction': (learned_untied - learned_tied)
                              - (((rope_untied - rope_tied)
                                  + (rope_untied_alt - rope_tied_alt)) / 2),
        'ema_gain': a['ablation_rope_untied_ema099_s17']['bpb'] - base,
        'mtp_gain': a['ablation_rope_untied_mtp1_s17']['bpb'] - base,
        'ladder_net': a['recipe_full_student_s17']['bpb']
                      - a['recipe_exact_baseline_s17']['bpb'],
        'ladder_norepl': a['recipe_norepl_s17']['bpb']
                         - a['recipe_exact_baseline_s17']['bpb'],
        'ladder_beta2': a['recipe_norepl_beta095_s17']['bpb']
                        - a['recipe_norepl_s17']['bpb'],
        'ladder_schedule': a['recipe_full_student_s17']['bpb']
                           - a['recipe_norepl_beta095_s17']['bpb'],
        'dropout_penalty': a['drop005_lr1e3_a']['bpb'] - learned_tied,
        'wd_penalty': a['wd2e1_lr1e3_a']['bpb'] - learned_tied,
        'capacity_d10': a['capacity_w320d10_s17']['bpb'] - learned_tied,
        'capacity_w384': a['capacity_w384d8_s17']['bpb'] - learned_tied,
    }


def blocks(d: dict, *, zh: bool, compact: bool) -> list[tuple]:
    t = d['temperature']
    noise = d['noise']
    ab = {r['label']: r for r in d['ablation']['rows']}
    res = {r['label']: r for r in d['resources']['rows']}
    freeze = d['freeze']
    search = d['search_accounting']
    live = d['search_live']
    v = {x['key']: x for x in d['versions']}
    delta_v3 = v['v2']['test'] - v['v3']['test']
    rel_v3 = (v['baseline']['test'] - v['v3']['test']) / v['baseline']['test'] * 100
    recipe = 1.5880948963549917 - v['v3']['validation']
    calib = v['v3']['validation'] - t['v3_headroom']['validation_bpb_after']
    arc = archive()
    fx = archive_effects(arc)
    if compact:
        return compact_blocks(d, zh=zh)

    if zh:
        B = [
            ('title', 'DASE7506 Project 1 语言模型 BPB 技术报告'),
            ('subtitle', f'冻结 v3：把完整 test BPB 从 {v["baseline"]["test"]:.6f} 降到 {v["v3"]["test"]:.6f}'),

            ('h1', '1 背景与任务目标'),
            ('p', '语言模型通过前文估计下一个 token 的概率。模型对正确 token 分配的概率越高，'
                  '编码同一段文本所需的信息量越少。因此本项目关注的不只是模型能否拟合训练文本，'
                  '还要检查它在未参与训练的数据上是否给出更准确、可复现的概率分布。'),
            ('p', '任务是在课程提供的 WikiText-2 文本上从随机初始化训练一个 decoder-only Transformer，'
                  '在固定的 BPE-2048 tokenizer、256 token 上下文与 CPU FP32 评测器下最小化完整 test split 的 '
                  'bits per byte（BPB）。训练只使用训练 split；模型结构、超参数、随机种子与 checkpoint '
                  '的选择全部只在 validation 上进行；test 只在方案冻结之后评测一次。'),
            ('p', '本轮工作在已冻结的 v2（test BPB 1.611178）之上继续，最终冻结的 v3 达到 '
                  f'{v["v3"]["test"]:.6f}，相对课程 baseline 降低 {rel_v3:.2f}%，'
                  f'相对 v2 再降低 {delta_v3:.6f}。'),
            ('table', ('Table 1', '作业的固定条件与硬性上限', ['项目', '固定设置', '作用或上限'], [
                ['数据', '课程提供的 WikiText-2', '训练、验证、测试 split 用途严格分开'],
                ['Tokenizer', 'BPE-2048', '词表与分词过程不可修改'],
                ['上下文', '256 tokens', '训练与评测使用相同最大上下文'],
                ['评测窗口', '独立且严格 causal', '禁止未来 token 与跨窗口状态'],
                ['模型选择', '仅使用 validation', 'test 不参与任何结构或超参数选择'],
                ['最终评测', 'CPU FP32，完整 test split', '报告可在 CPU 上复现的分数'],
                ['CPU 时间上限', '不超过 baseline 5 倍', '硬约束，不能用 BPB 抵消'],
                ['内存上限', '峰值 RSS 不超过 4 GiB', '硬约束'],
                ['资产上限', '未压缩推理资产不超过 64 MiB', '硬约束'],
            ], [1.30, 2.35, 2.80])),

            ('h1', '2 评价指标与选择协议'),
            ('p', '主指标是 bits per byte。设 B 为该 split 原始 UTF-8 文本的字节数，'
                  '总负对数似然除以 ln(2) 换算为比特数后再除以 B。BPB 越低越好。'
                  '计算完整 split 时应先累加所有 target 的负对数似然再统一除以字节数，'
                  '不能对各 batch 或各窗口的 BPB 简单平均。'),
            ('table', ('Table 2', '报告指标与判断方式', ['指标', '定义或测量方式', '报告作用', '方向或上限'], [
                ['BPB', '总 NLL ÷ ln(2) ÷ UTF-8 字节数', '主要质量指标', '越低越好'],
                ['Token PPL', 'exp（总 NLL ÷ target 数）', '辅助解释 token 级难度', '越低越好'],
                ['CPU 时间比', '候选评测时间 ÷ 同机同 split baseline 时间', '推理速度成本', '不超过 5 倍'],
                ['峰值 RSS', '评测进程最大常驻内存', '评测内存占用', '不超过 4 GiB'],
                ['推理资产', '推理所需未压缩资产总大小', 'checkpoint 与依赖资源', '不超过 64 MiB'],
            ], [1.05, 2.20, 1.47, 1.70])),
            ('p', 'BPB 是排序指标，三项资源上限是硬约束且互相独立；任何一项超限都不能用更低的 BPB 抵消。'
                  '因此本报告把质量结果与资源结果分开陈述，并在冻结前对资源做 median-of-5 复测。'),
            ('h2', '2.1 数据用途和冻结'),
            ('p', 'train 只用于更新参数；validation 用于选择结构、超参数、种子与 checkpoint；'
                  'test 在冻结清单写入之后评测一次。冻结清单记录 checkpoint、实现文件、评测器与 tokenizer '
                  '的 SHA-256，并把 test 结果字段留空，以证明冻结发生在任何 test 数值出现之前。'),
            ('p', '此外，任何方案比较都要在相同的评测器、上下文长度与已处理 targets 下进行。'
                  '当训练规模或训练时长变化时，报告分别说明质量变化与计算代价，'
                  '避免把"训练更多"或"模型更大"误写成单一机制改进。'),
            ('table', ('Table 3', '本轮实验的规模与训练预算', ['项', '数值', '说明'], [
                ['训练语料', '3,613,343 BPE tokens', '约 3.6M；这是本项目最主要的数据限制'],
                ['单次筛选预算', '9.83M ~ 28.9M processed targets', '约 2.7 ~ 8.0 个 epoch'],
                ['最终配方预算', '28,909,568 targets', '批量 4，共 28,232 个优化步'],
                ['本轮受控运行', f'{live["runs"]} 次', '另有 v1/v2 阶段 33 次运行'],
                ['本轮搜索成本', f'{live["total_processed_targets"]:,} targets', '训练时长与搜索规模不设上限，只需披露'],
                ['最终参数量', f'{freeze["parameters"]:,}', '与 v2 完全一致'],
            ], [1.55, 2.25, 2.65])),

            ('h1', '3 模型与训练方法'),
            ('p', '模型是 pre-norm decoder-only Transformer：宽度 320、深度 8、4 个注意力头（head dim 80），'
                  '使用 RMSNorm、SwiGLU 前馈（hidden 853，与 GELU 4 倍宽的 FLOPs 对齐）、RoPE 位置编码，'
                  '以及绑定的输入输出权重，参数量 10,488,640。'),
            ('p', '训练使用 AdamW（weight decay 0.1，betas 0.9/0.95）、梯度裁剪 1.0、'
                  '3% warmup 之后余弦退火、不带 replacement 的窗口采样（遍历全部合法窗口起点）。'
                  'v3 相对 v2 同时改变了随机种子、批量、峰值学习率、退火下限和 checkpoint 位置，'
                  '并在推理端对 logits 除以验证集拟合的温度 T = 1.075；报告只把温度前后的配对差值归因于校准，'
                  '其余差值统一称为联合训练与选点配方差异。'),
            ('fig', ('Fig. 1', '冻结 v3 的模型结构、训练数据流与评测流程。'
                               '标注的批量、学习率与退火下限均为 v3 的实际取值。', 'v13_architecture')),
            ('table', ('Table 4', '模型与训练配方：v2 与 v3 对比',
                       ['配置项', 'v2', 'v3', '对推理的影响'], [
                ['宽度 / 深度 / 头数', '320 / 8 / 4', '320 / 8 / 4', '无'],
                ['归一化 / 前馈 / 位置', 'RMSNorm / SwiGLU / RoPE', 'RMSNorm / SwiGLU / RoPE', '无'],
                ['权重绑定', '绑定', '绑定', '无'],
                ['参数量', '10,488,640', '10,488,640', '无'],
                ['批量（窗口数）', '32', '4', '无（仅训练）'],
                ['峰值学习率', '1e-3', '1.5e-3', '无（仅训练）'],
                ['退火下限', '0.1 × 峰值', '0', '无（仅训练）'],
                ['校准温度 T', '1.00', '1.075', '增加一次逐元素标量除法'],
                ['推理资产', '40.033 MiB', '40.034 MiB', '+1 KB'],
            ], [1.75, 1.80, 1.80, 1.60])),
            ('p', '批量、学习率和退火下限只作用于训练；温度缩放在推理图中增加一次逐元素标量除法，'
                  '但不增加可训练参数，资产只增加约 1 KB，相对于 Transformer 前向计算可以忽略。'),

            ('h1', '4 BPB 优化过程与判断方法'),
            ('p', 'v1 使用 learned positional embeddings，并把 RMSNorm、SwiGLU、绑定权重与训练器改动一起冻结；'
                  'v2 才加入 RoPE，并在较长训练中按预先声明的 validation 检查点选择规则冻结模型；'
                  'v3 在 28.9M targets 的固定预算内联合调整优化配方，再对输出置信度进行验证集温度校准。'),
            ('fig', ('Fig. 2', '四个版本的 validation 与官方 test BPB。各点来自独立运行；'
                               'v3 的 validation 一栏是未加温度校准的配方分数，'
                               '其冻结配置在此之上再施加 T = 1.075。', 'v01_versions')),
            ('h2', '4.1 优化路径的数值分解'),
            ('p', f'v3 相对 v2 的 test BPB 低 {delta_v3:.6f}。在 validation 上，v2 的冻结配置与 v3 的'
                  f'未校准配置相差 {recipe:.6f}，但两者同时改变了种子、批量、学习率、退火下限和 checkpoint，'
                  f'因此该数值只能描述联合训练与选点配方的差距；对同一个 v3 checkpoint 比较温度前后，'
                  f'校准带来的配对改善为 {calib:.6f}。validation 的两个差值不能与 test 差值相加后解释为因果分解。'
                  f'再往前看，v2 相对 v1 的改善为 {v["v1"]["test"] - v["v2"]["test"]:.6f}，'
                  f'v1 相对 baseline 为 {v["baseline"]["test"] - v["v1"]["test"]:.6f}。'),
            ('table', ('Table 5', '各阶段相邻差值及解释边界',
                       ['阶段', 'validation BPB', 'test BPB', '相邻差值', '解释边界'], [
                ['课程 baseline', f(v['baseline']['validation']), f(v['baseline']['test']), '—', '参考实现'],
                ['v1 结构 + 训练器', f(v['v1']['validation']), f(v['v1']['test']),
                 f"{v['baseline']['test'] - v['v1']['test']:.6f}", '结构、训练器与预算同时变化'],
                ['v2 长训练 + 选点', f(v['v2']['validation']), f(v['v2']['test']),
                 f"{v['v1']['test'] - v['v2']['test']:.6f}", '训练时长与 checkpoint 选择同时变化'],
                ['v3 联合配方 + 校准', f(v['v3']['validation']), f(v['v3']['test']),
                 f"{v['v2']['test'] - v['v3']['test']:.6f}", '种子、优化、选点与校准同时变化'],
            ], [1.55, 1.30, 1.24, 1.10, 1.90])),
            ('p', 'v2 的形成过程按证据逐步收缩候选空间：9.83M-target 的 2×2 因子实验显示 SwiGLU 的'
                  f'平均主效应为 {fx["ffn_main"]:+.6f}，RMSNorm 为 {fx["norm_main"]:+.6f}；随后宽度 320、深度 8'
                  '和 1e-3 学习率成为容量基准，而 dropout 0.05 与 weight decay 0.2 未产生可复现收益。'
                  '在 learned 位置编码的 v1 长训练之后，RoPE 的短预算对照在两个 seed 上方向一致，解绑权重、'
                  '更大容量、EMA 与多 token 预测则被资源或噪声证据排除；第一次 RoPE 长训练从 19.66M 到最终'
                  '检查点发生回退，因此三 seed 复现实验预先固定 9.83M、19.66M 和 28.91M 三个检查点，并按完整'
                  'validation 最低 BPB 选择 seed 137 的 19.66M checkpoint，最后一次性得到 v2 test BPB 1.611178。'),
            ('fig', ('Fig. 3', '三个冻结版本的"test BPB − validation BPB"偏移。'
                               '三次独立测量分别得到 +0.023711 / +0.023083 / +0.021850，'
                               '说明 validation 可以可靠地推知 test，无需反复评测 test。', 'v11_offset')),

            ('h1', '5 超参数与训练长度的决策依据'),
            ('p', '本节回答三个问题：训练预算应该停在多少、批量与学习率应该取多少、'
                  '以及这些选择在多大的噪声下才可判定。所有比较都在 seed 17、同一评测器下进行。'),
            ('fig', ('Fig. 4', '在固定 20M 左右预算下扫描训练总量。'
                               '20.0M / 24.0M / 28.9M 三点在噪声内持平，说明 horizon 在 20M 附近饱和；'
                               '16M 明显不足。', 'v02_horizon')),
            ('table', ('Table 6', '训练预算扫描（seed 17，批量 32，完整退火）',
                       ['processed targets', 'validation BPB', '相对 20M', '判定'], [
                [h['label'], f(h['value']),
                 f"{h['value'] - d['horizon'][1]['value']:+.6f}",
                 '不足' if i == 0 else ('饱和区' if i else '基准')]
                for i, h in enumerate(d['horizon'])
            ], [1.80, 1.55, 1.40, 1.40])),
            ('p', '这条结果关闭了"训练更久"这条常规路线：在完整退火条件下，'
                  '把预算从 20M 推到 28.9M 只换来噪声量级的差异，'
                  '因此后续改进必须来自同一 token 预算下更有效的优化。'),

            ('h2', '5.1 训练损失与 validation 为什么要同时看'),
            ('p', '本轮一开始就发现训练本身不可复现：MPS 的 bf16 矩阵乘与归约存在非确定性，'
                  '同一配置的两次运行训练损失从第 500 步就开始分叉。'
                  '因此我们先把同一配置重复三次，得到可用的噪声基线，之后所有比较都以此为尺度。'),
            ('fig', ('Fig. 5', '同一配置（seed 17、28.9M targets、批量 32、完整退火）三次独立运行的 '
                               'validation BPB。三者均值 ' + f(noise['mean']) +
                     '，标准差 ' + f(noise['stdev']) + '，极差 ' + f(noise['range']) +
                     '。图中最低的一次恰好是先前被选作基线的一次。', 'v07_noise')),
            ('table', ('Table 7', '噪声基线与其含义', ['量', '数值', '带来的判据'], [
                ['三次同配置均值', f(noise['mean']), '作为批量 32 的诚实基准'],
                ['运行间标准差 σ', f(noise['stdev']), '单次比较需大于约 2σ 才可解读'],
                ['三次极差', f(noise['range']), '约等于 2σ，符合预期'],
                ['本轮采纳门槛', '单调趋势 + 配对复现', '避免用单点差异下结论'],
            ], [1.55, 1.65, 3.25])),
            ('p', '这条基线直接改变了两条早期结论的判定：'
                  '先前认为 19.66M 处出现"过拟合拐点"，其回升幅度 +0.015 落在噪声内，'
                  '正确表述应是"horizon 在 20M 附近进入平台期"；'
                  '先前认为"1e-3 是最优学习率"，该结论只在批量 32 下成立（见 5.3）。'
                  '本报告据此对每一条被采纳的机制都给出了配对或单调证据。'),

            ('h2', '5.2 正则结果与学习率选择的适用范围'),
            ('p', '为了确认"改进来自配方而不是来自正则强度"，'
                  '我们在 20M targets、批量 32 的固定基准（1.605134）上测试了三种训练期正则化。'
                  '结果全部为负或未决：droppath 0.1 让 validation BPB 变差 0.045020，远超噪声；'
                  '整 token 丢弃与 embedding dropout 的改善分别只有 0.003067 与 0.000981，'
                  '不足噪声的三分之一。'),
            ('fig', ('Fig. 6', '加入训练期正则化后的 validation BPB，基准是批量 32 / 20M targets 的 1.605134。'
                               'droppath 0.1 明确有害；其余两项落在噪声内。', 'v08_ablation_regularisation')),
            ('table', ('Table 8', '正则化消融（seed 17，20M targets，批量 32）',
                       ['方向', 'validation BPB', '相对基准', '判定'], [
                ['基准（无正则）', f(d['ablation']['baseline']), '—', '基准'],
                ['droppath 0.1', f(ab['droppath 0.1']['value']),
                 f"{ab['droppath 0.1']['delta']:+.6f}", '有害'],
                ['token dropout 0.05', f(ab['token drop 0.05']['value']),
                 f"{ab['token drop 0.05']['delta']:+.6f}", '未决'],
                ['embedding dropout 0.1', f(ab['embed dropout 0.1']['value']),
                 f"{ab['embed dropout 0.1']['delta']:+.6f}", '未决'],
                ['EMA 0.999（权重平均）', f(ab['EMA 0.999']['value']),
                 f"{ab['EMA 0.999']['delta']:+.6f}", '有害'],
            ], [1.95, 1.50, 1.35, 1.65])),
            ('p', '把这一组与容量结果（5.4）合起来看，可以得到本报告的核心判断：'
                  '当前模型既不欠正则，也不欠容量，而是受限于 3.6M 个训练 token 中可学的信号量。'
                  '这解释了为什么继续加正则、加宽度都无效。'),

            ('h2', '5.3 学习率与批量的联合选择'),
            ('p', '这是本轮收益最大的一节，也是最容易被忽略的一节。'
                  '在固定 20M targets 下把批量从 32 降到 4，token 预算不变，'
                  '优化步数从 2,442 提升到 19,532，validation BPB 从 1.605134 降到 1.568646。'
                  '继续降到 2 与 1 则反弹到 1.622860 与 1.660514，说明甜点在 4 而不是越小越好。'),
            ('fig', ('Fig. 7', '批量大小对 validation BPB 的影响。'
                               '曲线在批量 4 处触底，两端变差：批量越小每步梯度噪声越大，'
                               '过小反而损害最终质量。', 'v03_batch')),
            ('fig', ('Fig. 8', '把同样的结果按优化步数重新排序。'
                               '步数越多，最终 validation BPB 越低，直到 19,532 步。', 'v10_ablation_steps')),
            ('table', ('Table 9', '批量与优化步数（seed 17，20M targets，完整退火）',
                       ['批量', '优化步数', 'validation BPB', '相对批量 32'], [
                [b['label'], f"{b['steps']:,}", f(b['value']),
                 f"{b['value'] - d['batch'][0]['value']:+.6f}"] for b in d['batch']
            ], [1.20, 1.65, 1.80, 1.80])),
            ('p', '在同一 20M-target、seed 17 与完整退火条件下，批量 32→8→4 的 validation BPB '
                  '依次为 1.605134、1.582448 和 1.568646，构成方向一致的单次扫描；批量 32 的三次复现'
                  '是在 28.91M targets 下测得，只能用于估计运行波动，不能与 20M-target 的批量 4 单点组成'
                  '有效显著性检验，因此本报告删除原先的 p 值，并把批量结论限定为需要同预算配对复现的趋势证据。'),
            ('p', '批量改变后必须重新扫描学习率——这一点是本轮最重要的可迁移经验。'
                  '1e-3 这个学习率是批量 32 时代（每步 8,192 token）调出来的；'
                  '批量降到 4 之后每步只有 1,024 token，梯度噪声大得多，最优学习率整体右移。'),
            ('fig', ('Fig. 9', '批量改为 4 之后重新扫描峰值学习率，六个点覆盖 7.5e-4 到 3e-3。'
                               '1.5e-3 与 2.5e-3 两个候选点相差 0.000259，但中间的 2e-3 较差，'
                               '两侧的 2e-3 与 3e-3 各差约 0.0075，降低学习率则明确有害。', 'v04_lr')),
            ('table', ('Table 10', '学习率重扫（seed 17，批量 4，28.9M targets）',
                       ['峰值学习率', 'validation BPB', '相对 1e-3', '判定'], [
                [r['label'], f(r['value']), f"{r['value'] - d['lr'][1]['value']:+.6f}",
                 '较优候选' if r['label'] in ('1.5e-3', '2.5e-3') else
                 ('过小' if r['label'] == '7.5e-4' else
                  ('单次较差' if r['label'] in ('2.0e-3', '3.0e-3') else '基准'))]
                for r in d['lr']
            ], [1.55, 1.60, 1.35, 1.40])),
            ('p', '结论有三条。第一，历史那次"1e-3 最优、2e-3 更差"的扫描只在批量 32 下成立，'
                  '不能外推到新批量——换批量必须重扫学习率，这是本轮最重要的可迁移经验。'
                  '第二，1.5e-3 与 2.5e-3 的单次结果接近，但夹在中间的 2e-3 较差，因此不能把区间写成连续平台；'
                  '在约 0.010 的运行间标准差下只能确认 1.5e-3 是已测候选中的稳妥选择，学习率最优点仍需配对复现。'),
            ('p', '进一步的交叉验证暴露了批量与学习率之间的耦合。在 lr 2e-3、28.9M targets 下，'
                  '批量 8 / 4 / 2 的 validation BPB 依次为 1.572065 / 1.564327 / 1.548231，'
                  '仍然是单调下降——也就是说前面得到的"批量在 4 触底"只在 lr 1e-3 下成立；'
                  '学习率提上去之后，更小的批量继续变好'
                  '（bs2 在 lr 1e-3 下曾测得 1.622860）。'),
            ('p', '但把两者放在同一校准口径下比较时，这个优势几乎消失。'
                  'bs2 + lr2e-3 的最优温度只有 1.025、校准收益仅 0.000065（模型本身已经很校准），'
                  '校准后为 1.548165；而 v3 的校准收益是 0.007392，校准后为 1.549498。'
                  '两者的差距从 0.008659 缩到 0.001333，约合 0.13 倍标准差。'),
            ('p', '随后对 bs2 + lr2e-3 做了完全同配置的配对复现：得到 1.555356，'
                  '与首次的 1.548231 相差 0.007125，约合 0.7 倍标准差，两样本均值为 1.551793。'
                  '这说明首次那 0.008659 的优势主要来自单点波动，'
                  '而两样本均值在统一校准口径下仍差于 v3（1.551793 对 1.549498）。'
                  '继续把批量压到 1 会急剧恶化（1.660200），bs2 配更高的 2.5e-3 也变差（1.560446），'
                  '因此小批量方向到此关闭。'),
            ('p', '本报告据此不发布新版本，并把这一组结果记为两条方法学结论：'
                  '其一，比较两个配方时必须各自先用自己的最优温度再比，'
                  '否则"更小批量 + 更高学习率"这类改动会因为校准余量的此消彼长而被系统性高估；'
                  '其二，任何量级接近噪声的单点差异都必须先做配对复现再下结论——'
                  '本例中单点看起来赢了 0.0087，复现后优势归零。'),

            ('h2', '5.4 归一化与前馈网络的 2×2 因子对照'),
            ('p-compact', '把归一化与前馈拆成 2×2 因子之后可以看到：收益几乎全部来自前馈网络，'
                          'RMSNorm 只有小幅额外改善，交互项可以忽略——两个选择近似可加，'
                          '可以分别解释、分别采纳。'),
            ('p-full', '前面几节讨论的都是"同一个 block 该怎么训练"。要说明这个 block 本身为什么是 '
                  'RMSNorm + SwiGLU，需要把归一化与前馈网络两个因素拆开而不是合并断言。'
                  '这组对照在 baseline 尺度（width 128 / depth 4，约 1.08M 参数）上完成：'
                  '四个格子共用 9,830,400 processed targets、批量 32、峰值学习率 1e-3、'
                  '3% warmup 之后余弦退火、seed 17，因此格子之间的差值只能来自所替换的那一个部件。'),
            ('table', ('D-1', '归一化 × 前馈网络的四格因子对照（9.83M targets，批量 32，'
                              '峰值学习率 1e-3，seed 17）',
                       ['归一化', '前馈网络', '参数量', 'validation BPB'], [
                ['LayerNorm', 'GELU（4× 宽）', f"{arc['s0_lr1e3']['params']:,}",
                 f(arc['s0_lr1e3']['bpb'])],
                ['LayerNorm', 'SwiGLU（2.667× 宽）', f"{arc['ablation_ln_swiglu_s17']['params']:,}",
                 f(arc['ablation_ln_swiglu_s17']['bpb'])],
                ['RMSNorm', 'GELU（4× 宽）', f"{arc['ablation_rms_gelu_s17']['params']:,}",
                 f(arc['ablation_rms_gelu_s17']['bpb'])],
                ['RMSNorm', 'SwiGLU（2.667× 宽）', f"{arc['s_lr1e3']['params']:,}",
                 f(arc['s_lr1e3']['bpb'])],
            ], [1.15, 1.85, 1.55, 1.85])),
            ('table', ('D-2', '同一因子的主效应与交互项', ['效应', '定义', '数值'], [
                ['前馈主效应', 'SwiGLU 2.667× 替换 GELU 4×（两行平均）', f"{fx['ffn_main']:+.6f}"],
                ['归一化主效应', 'RMSNorm 替换 LayerNorm（两行平均）', f"{fx['norm_main']:+.6f}"],
                ['交互项', '在两种归一化条件下，换前馈的收益之差',
                 f"{fx['norm_ffn_interaction']:+.6f}"],
            ], [1.45, 3.45, 1.55])),
            ('p-full', f'读数很直接：几乎全部收益来自前馈网络（{fx["ffn_main"]:+.6f}），'
                  f'RMSNorm 只有约十分之一的额外改善（{fx["norm_main"]:+.6f}），'
                  f'交互项（{fx["norm_ffn_interaction"]:+.6f}）远小于任一主效应。'
                  f'这意味着两个选择近似可加：可以分别解释、分别采纳，'
                  f'而不必把它们包装成一个只能整体存在的"组合机制"。'
                  f'四个格子参数量相差不到 0.16%，因此也不能用"参数变多了"来解释前馈主效应——'
                  f'SwiGLU 取 2.667 倍宽度本来就是为了与 GELU 4 倍宽对齐 FLOPs。'),
            ('p-full', '局限要说清楚：这组对照只在 baseline 尺度的小模型上做过，'
                  '没有在最终 width 320 / depth 8 上逐格重跑。它支撑"最终结构为什么选用 '
                  'RMSNorm + SwiGLU"，但不能给出该结论在最终尺度上的精确数值，'
                  '本报告只把它当作方向性证据使用。'),

            ('h2', '5.5 位置表示与权重共享'),
            ('p-compact', 'RoPE 在 seed 17 与 seed 137 上方向一致地被改善并被采纳；'
                          '而"解绑"表面上的收益大部分与 RoPE 混杂——在 RoPE 已经生效之后'
                          '只剩不到单轮噪声的量级，因此最终保留绑定权重。'),
            ('p-full', '第二组在接近最终尺度（width 320 / depth 8）上对照位置表示与输出/输入权重是否绑定。'
                  '条件统一为 9,830,400 targets、批量 32、峰值学习率 1e-3、3% warmup 与余弦退火；'
                  '两种位置表示各配对了 seed 17 与 seed 137，因此可以把单点噪声与结构性收益分开。'),
            ('table', ('D-3', '位置表示 × 权重共享（9.83M targets，批量 32，峰值学习率 1e-3）',
                       ['位置表示', '权重', '参数量', 'seed 17', 'seed 137'], [
                ['learned 位置嵌入', '绑定', f"{arc['lr1e3_a']['params']:,}",
                 f(arc['lr1e3_a']['bpb']), '—'],
                ['learned 位置嵌入', '解绑', f"{arc['ablation_untied_s17']['params']:,}",
                 f(arc['ablation_untied_s17']['bpb']), '—'],
                ['RoPE', '绑定', f"{arc['ablation_rope_s17']['params']:,}",
                 f(arc['ablation_rope_s17']['bpb']), f(arc['ablation_rope_s137']['bpb'])],
                ['RoPE', '解绑', f"{arc['ablation_rope_untied_s17']['params']:,}",
                 f(arc['ablation_rope_untied_s17']['bpb']),
                 f(arc['ablation_rope_untied_s137']['bpb'])],
            ], [1.70, 0.90, 1.40, 1.20, 1.20])),
            ('table', ('D-4', '把两个看似独立的收益拆开', ['对照', '差值', '说明'], [
                ['RoPE 替换 learned 位置（绑定，seed 17）', f"{fx['rope_gain']:+.6f}",
                 '同时省掉 81,920 个位置参数'],
                ['解绑，在 learned 位置条件下（seed 17）', f"{fx['untied_on_learned']:+.6f}",
                 '表面收益最大'],
                ['解绑，在 RoPE 条件下（seed 17）', f"{fx['untied_on_rope_17']:+.6f}",
                 '只剩前者的三分之一'],
                ['解绑，在 RoPE 条件下（seed 137）', f"{fx['untied_on_rope_137']:+.6f}",
                 '同方向但更小'],
                ['解绑，在 RoPE 条件下两 seed 平均', f"{fx['untied_on_rope_mean']:+.6f}",
                 '低于单轮噪声 σ≈0.0102'],
                ['交互项：两种位置条件下的解绑收益之差', f"{fx['untied_interaction']:+.6f}",
                 '解绑收益大部分与 RoPE 混杂'],
            ], [2.85, 1.25, 2.35])),
            ('p-full', f'这张表是本报告中最能说明"合并比较不等于因果"的一处：'
                  f'如果只看当时最好的那一个格子（RoPE + 解绑，{arc["ablation_rope_untied_s137"]["bpb"]:.6f}），'
                  f'很容易把 {fx["untied_on_learned"]:+.6f} 全部归给解绑；'
                  f'但把两行差分开之后，在 RoPE 已经生效的前提下，'
                  f'解绑只剩平均 {fx["untied_on_rope_mean"]:+.6f}，'
                  f'低于第 5.1 节测得的单轮训练噪声 σ ≈ 0.0102。'
                  f'再考虑到解绑要多花 655,360 个参数（约 2.6 MiB 推理资产），'
                  f'最终结构保留绑定权重。'
                  f'RoPE 则相反：它在 seed 17 与 seed 137 上分别给出 '
                  f'{fx["rope_gain"]:+.6f} 与 '
                  f"{arc['ablation_rope_s137']['bpb'] - arc['lr1e3_a']['bpb']:+.6f}，"
                  f'方向一致、量级远大于噪声，同时省掉 256 × 320 = 81,920 个位置嵌入参数，因此被采纳。'),

            ('h2', '5.6 训练期机制与训练器逐项对照'),
            ('p-compact', '尾部权重平均与多 token 预测的收益都落在噪声量级内；'
                          '把训练器逐项叠加到 baseline 模型上反而使其变差，'
                          '说明改善来自结构而不是采样、β2 或学习率调度；'
                          '学习率的最优值还会随批量移动。'),
            ('p-full', '这一小节回答两个常被混为一谈的问题：'
                  '其一是"不占推理预算的训练技巧有没有用"，其二是"改善会不会其实来自训练器而不是模型"。'),
            ('table', ('D-5', '两个不增加推理期状态的训练期机制（RoPE + 解绑，seed 17，9.83M targets）',
                       ['配置', 'validation BPB', '差值', '判定'], [
                ['对照（同一配置，无附加机制）', f(arc['ablation_rope_untied_s17']['bpb']), '—', '参考'],
                ['尾部权重平均 EMA 0.99（80% 之后起算）',
                 f(arc['ablation_rope_untied_ema099_s17']['bpb']), f"{fx['ema_gain']:+.6f}",
                 '单次结果，未达复现门槛'],
                ['多 token 预测 MTP k=1（辅助损失权重 0.15）',
                 f(arc['ablation_rope_untied_mtp1_s17']['bpb']), f"{fx['mtp_gain']:+.6f}",
                 '同上'],
            ], [2.45, 1.55, 1.25, 1.20])),
            ('p-full', f'EMA 与 MTP 都不增加推理期的模型状态与计算：EMA 只是取同一次优化轨迹上的尾部权重平均，'
                  f'MTP 只在训练时对额外未来位置加一个辅助监督。'
                  f'在作业"训练时长不受限"的前提下它们本可以自由添加，'
                  f'但两次改善（{fx["ema_gain"]:+.6f} 与 {fx["mtp_gain"]:+.6f}）都是单次运行结果，'
                  f'且都不超过第 5.1 节测得的单轮噪声 σ ≈ 0.0102，因此没有进入冻结配方。'
                  f'必须补充一条边界：这两个机制从未在 v3 配方（批量 4、峰值学习率 1.5e-3、'
                  f'28.9M targets）下重测过，本报告既不声称它们在最终配方上仍然成立，'
                  f'也不声称它们无效。'),
            ('table', ('D-6', '训练器逐项叠加对照（baseline 模型 width 128 / depth 4，'
                              'seed 17，9.83M targets，累积叠加）',
                       ['累积到第几项', 'validation BPB', '相邻差值'], [
                ['① 课程原始配方（有放回、β2=0.999、baseline LR 调度）',
                 f(arc['recipe_exact_baseline_s17']['bpb']), '—'],
                ['② 换成不带 replacement 的窗口采样',
                 f(arc['recipe_norepl_s17']['bpb']), f"{fx['ladder_norepl']:+.6f}"],
                ['③ 再把 AdamW β2 改为 0.95',
                 f(arc['recipe_norepl_beta095_s17']['bpb']), f"{fx['ladder_beta2']:+.6f}"],
                ['④ 再换成 3% warmup + 余弦退火',
                 f(arc['recipe_full_student_s17']['bpb']), f"{fx['ladder_schedule']:+.6f}"],
                ['① → ④ 净效果', '—', f"{fx['ladder_net']:+.6f}"],
            ], [3.55, 1.55, 1.35])),
            ('p-full', f'这组 ladder 正是为了排除"收益其实来自训练器"这一替代解释：'
                  f'把训练器逐项换成本项目使用的设置之后，同一个 baseline 模型的 validation BPB '
                  f'不但没有变好，反而变差 {fx["ladder_net"]:+.6f}。'
                  f'因此归因给模型的改善不可能来自采样、β2 或学习率调度本身，'
                  f'必须来自结构（第 3 节与 5.4 节）。'
                  f'这也是一处应当记录的负结果：β2 由 0.999 改到 0.95 在这一预算下单独是有害的'
                  f'（{fx["ladder_beta2"]:+.6f}）；它之所以仍被保留，'
                  f'是因为在更深更宽的模型与更长预算上它与 warmup、余弦退火组合后不再显出劣势。'
                  f'阶梯的每一行都与前面几行混杂，任何一行都不能当作单一机制的因果贡献。'),
            ('table', ('D-7', '早期学习率扫描（批量 32，seed 17，9.83M targets，learned 位置 + 绑定权重）',
                       ['峰值学习率', 'validation BPB', '相对 1e-3'], [
                [label, f(arc[name]['bpb']),
                 f"{arc[name]['bpb'] - arc['lr1e3_a']['bpb']:+.6f}"]
                for label, name in (('5.0e-4', 'lr5e4_a'), ('7.5e-4', 'lr7p5e4_a'),
                                    ('1.0e-3', 'lr1e3_a'), ('1.25e-3', 'lr1p25e3_a'),
                                    ('2.0e-3', 'lr2e3_a'), ('4.0e-3', 'lr4e3_a'))
            ], [1.65, 1.95, 1.75])),
            ('p-full', f'这张表是 5.3 节那条方法论结论的原始出处：当时在批量 32 下扫出的最优学习率是 1e-3，'
                  f'而 2e-3 明确崩溃（{arc["lr2e3_a"]["bpb"] - arc["lr1e3_a"]["bpb"]:+.6f}）。'
                  f'把批量降到 4 之后同一个"1e-3 最优"的结论不再成立，最优整体右移到 1.5e-3 以上。'
                  f'换句话说，学习率从来没有一个脱离批量的最优值——每一次改批量都必须重扫学习率。'),

            ('h2', '5.7 容量与形状为什么停在 width 320 / depth 8'),
            ('p', '在相同 token 预算下改变宽度或深度：宽度 256 与 288 分别比 320 差 '
                  '0.022691 与 0.011753；深度 9 名义上好 0.010936，但只有噪声的一半，属未决。'
                  '这说明"缩小模型可以减轻过拟合"的直觉在本任务上不成立，'
                  '宽度 320 / 深度 8 是当前预算下的甜点。'),
            ('fig', ('Fig. 10', '在相同 token 预算下改变宽度或深度。'
                                '向下缩小容量明确变差；向上加深的收益在噪声量级内。', 'v05_capacity')),
            ('fig', ('Fig. 11', '容量方向的配对结果。'
                                '宽度 288 与 256 分别比宽度 320 差 0.011753 与 0.022691 BPB。',
                     'v09_ablation_capacity')),
            ('table', ('Table 11', '容量、质量与训练成本（seed 17，20M targets，批量 32）',
                       ['配置', 'validation BPB', '相对宽 320', '参数量', '判定'], [
                ['宽度 256 / 深度 8', f(ab['width 256']['value']), f"{ab['width 256']['delta']:+.6f}",
                 '6,816,000', '有害'],
                ['宽度 288 / 深度 8', f(ab['width 288']['value']), f"{ab['width 288']['delta']:+.6f}",
                 '8,557,344', '有害'],
                ['宽度 320 / 深度 8（基准）', f(d['ablation']['baseline']), '—', '10,488,640', '基准'],
                ['宽度 320 / 深度 9', f(ab['depth 9']['value']), f"{ab['depth 9']['delta']:+.6f}",
                 '11,717,760', '未决'],
            ], [1.85, 1.40, 1.20, 1.25, 0.95])),
            ('p', '另有两个容量方向被资源上限而不是被实验排除：'
                  '宽度 384 会把 CPU 时间比推到 4.5 ~ 5.0 倍，逼近 5 倍上限而缺乏余量；'
                  '更早的一次短预算对照中宽度 384 与深度 10 都明显更差。'
                  '因此在当前评测预算下，容量方向的探索实际上是关闭的。'),

            ('h1', '6 冻结后的最终结果与资源'),
            ('p', 'v3 的冻结清单写于 test 之前，其 test 结果字段为空；'
                  '随后才对同一 checkpoint 评测一次。哈希逐一核对与清单一致。'),
            ('table', ('Table 12', '完整 test split 的最终结果',
                       ['版本', 'validation BPB', '完整 test BPB', 'token PPL', '相对 baseline'], [
                ['课程 baseline', f(v['baseline']['validation']), f(v['baseline']['test']), '80.848', '—'],
                ['冻结 v1', f(v['v1']['validation']), f(v['v1']['test']), '31.83',
                 f"{(v['v1']['test'] / v['baseline']['test'] - 1) * 100:.2f}%"],
                ['冻结 v2', f(v['v2']['validation']), f(v['v2']['test']), '29.023',
                 f"{(v['v2']['test'] / v['baseline']['test'] - 1) * 100:.2f}%"],
                ['冻结 v3（本轮）', f(v['v3']['validation']), f(v['v3']['test']), '26.704',
                 f"{(v['v3']['test'] / v['baseline']['test'] - 1) * 100:.2f}%"],
            ], [1.50, 1.35, 1.30, 1.05, 1.25])),
            ('h2', '6.1 训练和搜索成本'),
            ('p', f'本轮搜索合计 {live["runs"]} 次受控运行、'
                  f'{live["total_processed_targets"]:,} processed targets。'
                  f'冻结清单记录的是冻结时刻的快照（{search["runs_included"]} 次、'
                  f'{search["total_processed_targets"]:,} targets），'
                  f'此后为定位学习率峰顶又追加了若干次运行，一并计入披露。'
                  f'v1/v2 阶段的开发另有 33 次运行、429,047,808 targets。'
                  f'单次 20M target 训练在 MPS bf16 下约需 16 ~ 20 分钟，'
                  f'最终配方（28.9M targets，批量 4）耗时约 27 分钟。'
                  f'课程规则对训练时长与搜索规模不设上限，只需披露。'),
            ('p', '本轮把训练步数提高约八倍，而模型参数量保持不变；推理阶段新增的工作只有对 logits '
                  '执行一次温度除法，其计算与存储开销相对于 Transformer 前向传播可以忽略。'),
            ('h2', '6.2 正式 test 改善对应什么'),
            ('p', f'v3 的 test BPB 比 v2 低 {delta_v3:.6f}，但这不是可逐项相加的因果分解：'
                  f'未校准 validation 的 {recipe:.6f} 差距同时包含随机种子、批量、学习率、退火下限与 checkpoint '
                  f'位置的变化；只有在同一 v3 checkpoint 上测得的温度校准收益 {calib:.6f} 可以单独归因。'
                  '模型结构与参数量没有变化，推理图则增加了显式的温度除法。'),
            ('fig', ('Fig. 12', '两个 checkpoint 在应用温度前后的 validation BPB；v2 的 T = 1.10 '
                                '是冻结后的诊断结果，正式 v2 始终使用 T = 1.00，v3 则在冻结前选择 T = 1.075。',
                     'v06_temperature')),
            ('table', ('Table 13', '温度校准与半分位泛化检验',
                       ['项目', '数值', '说明'], [
                ['v2 诊断最优 T', f"{t['v2_temperature']:.3f}", '冻结后分析；正式 v2 仍为 T = 1.00'],
                ['v3 最优 T', f"{t['v3_temperature']:.3f}", 'validation BPB 1.556890 → 1.549498'],
                ['拟合半区收益', f"{t['holdout']['half_a_at_t1'] - t['holdout']['half_a_at_t_star']:.6f}",
                 'T 只用偶数半区拟合'],
                ['留出半区收益', f"{t['holdout']['half_b_at_t1'] - t['holdout']['half_b_at_t_star']:.6f}",
                 '在奇数半区评估，不小于拟合半区'],
                ['推理成本', '可忽略', '无额外参数；一次标量除法，资产 +1 KB'],
            ], [1.60, 1.40, 3.45])),
            ('p', '一个容易忽略的交互：批量越小、训练噪声越大，模型的校准余量就越小'
                  '（v2 为 0.013023，v3 只有 0.007392）。因此"批量 4"与"温度校准"两项收益'
                  '不能简单相加后再与批量 32 比较，必须放在同一校准口径下对比，本报告即按此处理。'),
            ('h2', '6.3 资源门槛与测量协议'),
            ('p', '资源测量使用 median-of-5：每次重复在独立进程中加载一个 checkpoint、'
                  '在 CPU FP32 下评测完整 test split，baseline 与候选在同一调用内测量，'
                  '避免采信陈旧的硬编码基准。'),
            ('fig', ('Fig. 13', 'v2 与 v3 在 test split 上的资源占用率；两套预测器的三项资源指标均低于上限，'
                                '资产占用几乎相同。', 'v12_resources')),
            ('table', ('Table 14', 'test 资源测量（median-of-5，FP32，4 线程）',
                       ['指标', 'v2 实测', 'v3 实测', '上限', '判定'], [
                ['CPU 时间比', f"{res['CPU time']['v2']:.3f}x", f"{res['CPU time']['v3']:.3f}x", '5x', '通过'],
                ['峰值 RSS', f"{res['Peak RSS']['v2']:.3f} GiB", f"{res['Peak RSS']['v3']:.3f} GiB",
                 '4 GiB', '通过'],
                ['推理资产', f"{res['Inference assets']['v2']:.3f} MiB",
                 f"{res['Inference assets']['v3']:.3f} MiB", '64 MiB', '通过'],
            ], [1.40, 1.35, 1.35, 1.10, 0.95])),
            ('p', '计算量上限之所以不是瓶颈，是因为固定开销与参考实现的低效率占比较高：'
                  '课程 baseline 只有 1.09M 参数，其小矩阵乘效率远低于宽度 320 的模型，'
                  '因此参数量放大近十倍后时间比只增加到 3 倍左右。'
                  '同时本报告也记录到该比值本身在会话间不稳定，'
                  '所以冻结前一律复测而不采信单次结果。'),

            ('h1', '7 补充消融如何改变后续方向'),
            ('p', '本节汇总本轮全部被否定或未决的方向。它们与正面结果同等重要：'
                  '正是这些负结果把"加正则、加容量、加训练时长"三条常规路线依次关闭，'
                  '才使批量与学习率这两个零推理成本的杠杆成为唯一剩下的方向。'),
            ('table', ('Table 15', '本轮全部消融的方向与判定',
                       ['方向', 'validation BPB', '相对基准', '判定', '后续影响'], [
                ['droppath 0.1', f(ab['droppath 0.1']['value']), f"{ab['droppath 0.1']['delta']:+.6f}",
                 '有害', '训练期正则化整体关闭'],
                ['EMA 0.999', f(ab['EMA 0.999']['value']), f"{ab['EMA 0.999']['delta']:+.6f}",
                 '有害', '权重平均不采用'],
                ['宽度 256', f(ab['width 256']['value']), f"{ab['width 256']['delta']:+.6f}",
                 '有害', '缩小容量不可行'],
                ['宽度 288', f(ab['width 288']['value']), f"{ab['width 288']['delta']:+.6f}",
                 '有害', '缩小容量不可行'],
                ['深度 9', f(ab['depth 9']['value']), f"{ab['depth 9']['delta']:+.6f}",
                 '未决', '需配对复现'],
                ['token dropout 0.05', f(ab['token drop 0.05']['value']),
                 f"{ab['token drop 0.05']['delta']:+.6f}", '未决', '收益不足噪声'],
                ['embedding dropout 0.1', f(ab['embed dropout 0.1']['value']),
                 f"{ab['embed dropout 0.1']['delta']:+.6f}", '未决', '收益不足噪声'],
            ], [1.75, 1.35, 1.15, 0.85, 1.85])),
            ('h2', '7.1 为什么正则化在这里失效'),
            ('p', '本轮的正则化全部为负或未决，这与"数据量小、应该加正则"的常识相反。'
                  '原因在于本项目的数据限制不是"模型见过太多遍训练集"，'
                  '而是"训练集本身只有 3.6M token"。在这个区间里模型的瓶颈是拟合能力尚未用尽，'
                  '任何形式的扰动（丢分支、丢 token、丢维度、平均权重）都会减少它本可学到的信号。'
                  '第 5 节的训练预算扫描也是同一现象的另一面：20M 之后没有观察到超出噪声的稳定收益。'),
            ('h2', '7.2 被资源上限排除的方向'),
            ('p', '宽度 384 / 深度 8 在参数量上仍能塞进 64 MiB 资产上限（约 57 MiB），'
                  '但把 CPU 时间比推到 4.5 ~ 5.0 倍，逼近 5 倍硬上限而缺乏复测余量；'
                  '考虑到本报告记录的比值不稳定幅度，这一方向被判定为不可行而非被实验否定。'
                  '把批量压到 1 已经实测反弹，无需继续。'),

            ('h1', '8 三个 seed 与最佳 checkpoint'),
            ('p', 'v2 是通过三个 seed 的 validation 结果选出的（seed 137 得分 1.588095、'
                  'seed 17 得分 1.600916、seed 233 得分 1.611337，均值 1.600116）。'
                  '本轮在建立噪声基线后发现，这个"三 seed 选优"的优势只有 0.012，'
                  '与运行间标准差 0.010 同量级，因此其中相当一部分可能来自选择噪声；这不会改变 v2 的冻结合法性，'
                  '但要求后续报告同时披露均值、离散程度与选点规则。'),
            ('table', ('Table 16', '同配置三样本与 v2 三 seed 的对比',
                       ['样本来源', '内容', '均值', '标准差'], [
                ['本轮配对复现', '同一配置三次运行（批量 32）', f(noise['mean']), f(noise['stdev'])],
                ['v2 三 seed', 'seed 137 / 17 / 233', '1.600116', '0.011642'],
            ], [1.60, 2.30, 1.25, 1.25])),
            ('h2', '8.1 训练不可复现如何改变判定规则'),
            ('p', '本轮据此确立了三条规则并贯彻到所有结论中：'
                  '其一，单次运行小于 0.02 的差异不解读；'
                  '其二，被采纳的机制必须有单调趋势或配对复现；'
                  '其三，选择 checkpoint 或 seed 时应报告均值与离散度，'
                  '而不是只报告最好的一次。'
                  '这也直接导致本报告下调了两条早期结论（过拟合拐点、最优学习率的适用范围）。'),
            ('h2', '8.2 温度校准的合法性边界与披露'),
            ('p', '温度校准很容易被误读成"调参刷分"，因此这里明确它的边界：'
                  '它不改变模型的判别能力，只改善输出分布的校准；'
                  '输出仍然归一化、严格因果、无跨窗口状态，评测器对归一化的校验依然通过；'
                  'T 是一个在 validation 上选择的超参数，与学习率、weight decay 同性质，'
                  '并未使用 test 信息；'
                  '并且它通过了半分位泛化检验——只用一半验证集拟合，在另一半上的收益不小于拟合集。'
                  '本报告与冻结清单都明确记录"温度在验证集上拟合"。'),

            ('h1', '9 正确性与提交要求'),
            ('h2', '9.1 复现材料'),
            ('p', '冻结清单记录 checkpoint、student.py、evaluate.py 与 tokenizer 的 SHA-256；'
                  '训练脚本为 train_student.py，评测器为课程提供的 evaluate.py（未修改）；'
                  '所有运行的 config、种子、耗时、参数量与 checkpoint 哈希保存在各 run 目录的 metrics.json，'
                  '并由 code/results/grid.tsv 汇总。'),
            ('table', ('Table 17', '冻结记录（v3）', ['项目', '值'], [
                ['冻结时间', freeze['timestamp']],
                ['checkpoint', freeze['checkpoint']],
                ['checkpoint SHA-256', freeze['checkpoint_sha256']],
                ['student.py SHA-256', freeze['implementation_sha256']],
                ['evaluate.py SHA-256', freeze['evaluator_sha256']],
                ['tokenizer SHA-256', freeze['tokenizer_sha256']],
                ['参数量', f"{freeze['parameters']:,}"],
                ['test BPB（冻结后单次评测）', f(v['v3']['test'])],
            ], [2.30, 4.30], 8.2)),
            ('h2', '9.2 作业要求覆盖'),
            ('table', ('Table 18', '课程要求与证据位置', ['课程要求', '本报告中的位置'], [
                ['初始 baseline', '第 4 节 Table 5、Fig. 2'],
                ['相同 processed targets 的比较', '第 5.3 节 Table 9（全部为 20M targets）'],
                ['关键机制的消融', '第 5.2 / 5.3 / 5.4 节与第 7 节'],
                ['基于 validation 的开发与选择', '第 2.1 节、第 8 节'],
                ['预测质量与计算代价的权衡', '第 5.3 节与第 6.3 节的资源表'],
                ['训练成本、seed 与 checkpoint 沿革', '第 6.1 节、第 8 节、附录 A'],
                ['5× CPU / 4 GiB / 64 MiB 限制', '第 6.3 节的资源表与资源图'],
                ['冻结后单次 test 评测', '第 6 节最终结果表与第 9.1 节冻结记录'],
            ], [2.60, 4.00])),

            ('h1', '10 结论与局限及 AI 披露'),
            ('h2', '10.1 结论'),
            ('p', f'在固定的 WikiText-2 文本、BPE-2048 tokenizer、256 token 上下文与 CPU FP32 评测器下，'
                  f'冻结 v3 取得完整 test BPB {v["v3"]["test"]:.6f}，'
                  f'相对课程 baseline 降低 {rel_v3:.2f}%，相对上一版冻结结果 v2 降低 {delta_v3:.6f}。'
                  f'三项评测资源上限全部通过；参数量与 v2 相同，温度缩放使推理图增加一次标量除法，'
                  f'推理资产仅增加约 1 KB。'),
            ('p', '本轮最可靠的方法学结论是：批量变化后必须重新扫描学习率，并且所有配方都应在统一的校准'
                  '口径下比较。v3 的未校准 validation BPB 比冻结 v2 低 0.031，但这个联合差值还包含种子、退火'
                  '下限与 checkpoint 的变化，不能只归因于批量和学习率；温度缩放另提供 0.007392 的同 checkpoint '
                  '配对收益，并以一次标量除法为代价。'),
            ('h2', '10.2 局限'),
            ('p', '第一，训练不可复现是本轮最大的方法学约束。'
                  '同配置三次运行的标准差为 0.010，使所有单次比较都必须在配对复现或单调趋势的支撑下成立。'
                  '本报告据此下调了两条早期结论。'),
            ('p', '第二，批量 4 在共同 20M-target 口径下只有一次扫描结果，28.91M-target 的批量 32 复现只能'
                  '估计噪声，不能替代同预算配对实验；后续应至少对批量 32、8、4 各做两次独立复现，并在每个批量'
                  '内部重新扫描学习率。现有学习率曲线的 1.5e-3 与 2.5e-3 单点相近，但 2e-3 较差，不能称为连续平台。'),
            ('p', '第三，模型结构与参数量保持不变，改善主要伴随训练与选点配方变化，并包含一次推理温度缩放。'
                  '下一轮实验应在冻结的 28.91M-target 预算下采用预注册的配对矩阵，统一报告未校准与各自最佳校准后的'
                  'validation BPB，再用均值和置信区间判断批量、学习率与退火下限的交互；只有超过运行波动且在复现中'
                  '保持方向一致的差值才应进入下一版本。'),
            ('p', '第四，温度校准改善的是校准而非判别能力，'
                  '虽然通过了半分位泛化检验，仍必须在报告与披露中明确其拟合来源，'
                  '不能与结构改进混为一谈。'),
            ('h2', '10.3 AI assistance disclosure'),
            ('p', '本项目的实验脚本、图表生成与报告排版在 AI 协助下完成，'
                  '包括三个训练期正则化旋钮（droppath / token dropout / embedding dropout）的实现、'
                  '温度校准与冻结清单工具、以及图表与 Word 文档的生成流程。'
                  '所有实验设计、指标判定与结论均由作者确认；'
                  'AI 未参与任何 test 上的选择行为，也未接触除课程提供文本以外的训练数据。'),
            ('fig', ('Fig. 14', '从 v1/v2 的结构、容量、位置表示和 checkpoint 选择，到 v3 的噪声、批量、'
                                '学习率与校准检查；每个实验现象都直接对应下一步策略。', 'v14_decision_flow')),
            ('h2', '参考资料'),
            ('p', '1. DASE7506 Project 1 课程指南（GUIDE.md）。'
                  '2. 课程提供的 baseline 实现与评测器（model.py / evaluate.py / common.py，未修改）。'
                  '3. Vaswani et al., “Attention Is All You Need,” NeurIPS, 2017。'
                  '4. Zhang and Sennrich, “Root Mean Square Layer Normalization,” NeurIPS, 2019。'
                  '5. Shazeer, “GLU Variants Improve Transformer,” arXiv:2002.05202, 2020。'
                  '6. Su et al., “RoFormer: Enhanced Transformer with Rotary Position Embedding,” Neurocomputing, 2024。'
                  '7. Loshchilov and Hutter, “Decoupled Weight Decay Regularization,” ICLR, 2019。'
                  '8. Merity et al., “Pointer Sentinel Mixture Models,” ICLR, 2017。'
                  '9. 本项目 v1、v2 阶段的技术报告与实验索引（code/results/ 与各 run 目录）。'),
        ]
        B += appendix_blocks(d, zh=True)
        return B

    B = [
        ('title', 'DASE7506 Project 1 Language Model BPB Technical Report'),
        ('subtitle', f'Frozen v3: driving the complete test BPB from '
                     f'{v["baseline"]["test"]:.6f} to {v["v3"]["test"]:.6f}'),

        ('h1', '1. Background and Mission Objectives'),
        ('p', 'A language model estimates the probability of the next token from the preceding context. '
              'The higher the probability it assigns to the correct token, the fewer bits are needed to '
              'encode the same text. This project therefore cares not only about whether the model fits the '
              'training text, but also about whether it produces accurate and reproducible probability '
              'distributions on text it has not been trained on.'),
        ('p', 'The task is to train a decoder-only Transformer from random initialisation on the supplied '
              'WikiText-2 text and to minimise bits per byte (BPB) on the complete test split under a fixed '
              'BPE-2048 tokenizer, a 256-token context and the supplied CPU FP32 scorer. Only the training '
              'split updates parameters; architecture, hyperparameters, seeds and checkpoint selection are '
              'decided on validation alone; the test split is scored once, after the method is frozen.'),
        ('p', f'This round builds on the frozen v2 predictor (test BPB 1.611178). The frozen v3 reaches '
              f'{v["v3"]["test"]:.6f}, {rel_v3:.2f}% below the course baseline and {delta_v3:.6f} below v2.'),
        ('table', ('Table 1', 'Fixed conditions and rigid limits', ['Item', 'Fixed setting', 'Role or limit'], [
            ['Data', 'Supplied WikiText-2', 'Train, validation and test splits strictly separated'],
            ['Tokenizer', 'BPE-2048', 'Vocabulary and segmentation are not modifiable'],
            ['Context', '256 tokens', 'Training and evaluation share the maximum context'],
            ['Windows', 'Independent, strictly causal', 'No future tokens and no cross-window state'],
            ['Model choice', 'Validation only', 'Test never selects structure or hyperparameters'],
            ['Final scoring', 'CPU FP32, complete test split', 'The reported score reproduces on a CPU'],
            ['CPU time limit', 'At most 5x the baseline', 'Hard limit; a lower BPB cannot offset it'],
            ['Memory limit', 'Peak RSS at most 4 GiB', 'Hard limit'],
            ['Asset limit', 'At most 64 MiB uncompressed', 'Hard limit'],
        ], [1.30, 2.35, 2.80])),

        ('h1', '2 Evaluation Indicators and Selection Agreement'),
        ('p', 'The headline metric is bits per byte. With B the raw UTF-8 byte count of the split, the total '
              'negative log-likelihood is converted to bits through ln(2) and divided by B. Lower is better. '
              'A complete split must accumulate all target NLL first and divide once, never averaging the BPB '
              'of individual batches or windows.'),
        ('table', ('Table 2', 'Reported metrics and assessment', ['Metric', 'Definition or measurement', 'Role', 'Direction or limit'], [
            ['BPB', 'total NLL / ln(2) / UTF-8 bytes', 'headline quality', 'lower better'],
            ['Token PPL', 'exp(total NLL / targets)', 'token-level difficulty', 'lower better'],
            ['CPU time ratio', 'candidate time / same-split baseline time', 'inference speed cost', 'at most 5x'],
            ['Peak RSS', 'maximum resident memory of the scorer', 'evaluation memory', 'at most 4 GiB'],
            ['Inference assets', 'uncompressed assets needed at inference', 'checkpoint and dependencies', 'at most 64 MiB'],
        ], [1.05, 2.30, 1.40, 1.55])),
        ('p', 'BPB is the ranking metric; the three resource limits are hard constraints that stand on their '
              'own and cannot be offset by a lower BPB. Quality and resources are therefore reported '
              'separately, and resources are re-measured with a median of five repetitions before freezing.'),
        ('h2', '2.1 Data usage and freezing'),
        ('p', 'Train updates parameters, validation selects structure, hyperparameters, seeds and checkpoints, '
              'and test is scored once after the freeze manifest has been written. The manifest records the '
              'SHA-256 of the checkpoint, the implementation files, the evaluator and the tokenizer, and it '
              'leaves the test-result field empty to show the freeze preceded any test number.'),
        ('p', 'Comparisons must also hold the scorer, the context length and the number of processed targets '
              'fixed. Where training scale or duration changes, quality and cost are reported separately, so '
              'that "trained more" or "model larger" is never written up as a single mechanism.'),
        ('table', ('Table 3', 'Scale and training budget of this round', ['Item', 'Value', 'Note'], [
            ['Training corpus', '3,613,343 BPE tokens', 'about 3.6M; the dominant data limit here'],
            ['Screening budget', '9.83M to 28.9M processed targets', 'about 2.7 to 8.0 epochs'],
            ['Final recipe budget', '28,909,568 targets', 'batch 4, 28,232 optimisation steps'],
            ['Controlled runs', f'{live["runs"]} runs this round', 'plus 33 runs during v1 and v2'],
            ['Search cost', f'{live["total_processed_targets"]:,} targets', 'training size is unlimited, only disclosed'],
            ['Final parameters', f'{freeze["parameters"]:,}', 'identical to v2'],
        ], [1.55, 2.45, 2.60])),

        ('h1', '3 Models and Training Methods'),
        ('p', 'The model is a pre-norm decoder-only Transformer: width 320, depth 8, four attention heads '
              '(head dimension 80), RMSNorm, a SwiGLU feed-forward with hidden size 853 (FLOP-matched to a '
              '4x GELU MLP), RoPE positional encoding, and tied input and output weights, for a total of '
              '10,488,640 parameters.'),
        ('p', 'Training uses AdamW (weight decay 0.1, betas 0.9/0.95), gradient clipping at 1.0, a three '
              'percent warmup followed by cosine decay, and without-replacement window sampling over every '
              'legal window start. Relative to v2, v3 changes the seed, batch size, peak learning rate, decay '
              'floor and checkpoint location together, then divides the logits by a validation-fitted '
              'temperature of 1.075; only the before-and-after temperature comparison is assigned a separate '
              'causal interpretation, while the other changes are reported as a joint recipe difference.'),
        ('fig', ('Fig. 1', 'Model structure, training data flow and evaluation path of frozen v3. The annotated '
                           'batch size, learning rate and decay floor are the v3 values.', 'v13_architecture')),
        ('table', ('Table 4', 'Model and training recipe: v2 against v3',
                   ['Setting', 'v2', 'v3', 'Effect on inference'], [
            ['Width / depth / heads', '320 / 8 / 4', '320 / 8 / 4', 'none'],
            ['Norm / FFN / positional', 'RMSNorm / SwiGLU / RoPE', 'RMSNorm / SwiGLU / RoPE', 'none'],
            ['Weight tying', 'tied', 'tied', 'none'],
            ['Parameters', '10,488,640', '10,488,640', 'none'],
            ['Batch (windows)', '32', '4', 'none, training only'],
            ['Peak learning rate', '1e-3', '1.5e-3', 'none, training only'],
            ['Decay floor', '0.1 x peak', '0', 'none, training only'],
            ['Calibration temperature', '1.00', '1.075', 'one elementwise scalar division'],
            ['Inference assets', '40.033 MiB', '40.034 MiB', '+1 KB'],
        ], [1.75, 1.80, 1.80, 1.60])),
        ('p', 'Batch size, learning rate and the decay floor affect training only, while temperature scaling '
              'adds one elementwise division to the inference graph without adding trainable parameters; the '
              'asset increase is about 1 KB and the operation is negligible beside the Transformer forward pass.'),

        ('h1', '4 BPB Optimization Process and Judgment Methods'),
        ('p', 'v1 used learned positional embeddings and froze RMSNorm, SwiGLU, tied weights and the trainer '
              'changes together; v2 introduced RoPE and selected among predeclared validation checkpoints '
              'during longer training; v3 keeps a 28.9M-target budget, changes the optimisation and checkpoint '
              'recipe jointly, and calibrates the output confidence on validation.'),
        ('fig', ('Fig. 2', 'Validation and official test BPB of the four versions. Points come from independent '
                           'runs; the v3 validation bar is the uncalibrated recipe score, and the frozen '
                           'configuration additionally applies T = 1.075.', 'v01_versions')),
        ('h2', '4.1 Numerical decomposition of the optimisation path'),
        ('p', f'v3 lowers test BPB by {delta_v3:.6f} relative to v2. On validation, the frozen v2 setting and '
              f'the uncalibrated v3 setting differ by {recipe:.6f}, but that contrast combines the seed, batch, '
              f'learning rate, decay floor and checkpoint location and is therefore a joint recipe gap rather '
              f'than a causal contribution; the paired temperature comparison on the same v3 checkpoint gives '
              f'a separately attributable calibration gain of {calib:.6f}. These validation differences '
              f'cannot be added and equated with the test delta. Earlier, v2 improved on v1 by '
              f'{v["v1"]["test"] - v["v2"]["test"]:.6f} and v1 on the '
              f'baseline by {v["baseline"]["test"] - v["v1"]["test"]:.6f}.'),
        ('table', ('Table 5', 'Stage-to-stage deltas and their interpretation limits',
                   ['Stage', 'Validation BPB', 'Test BPB', 'Delta', 'Interpretation limit'], [
            ['Course baseline', f(v['baseline']['validation']), f(v['baseline']['test']), '—', 'reference implementation'],
            ['v1 structure + trainer', f(v['v1']['validation']), f(v['v1']['test']),
             f"{v['baseline']['test'] - v['v1']['test']:.6f}", 'structure, trainer and budget all change'],
            ['v2 long run + selection', f(v['v2']['validation']), f(v['v2']['test']),
             f"{v['v1']['test'] - v['v2']['test']:.6f}", 'duration and checkpoint rule both change'],
            ['v3 joint recipe + calibration', f(v['v3']['validation']), f(v['v3']['test']),
             f"{v['v2']['test'] - v['v3']['test']:.6f}", 'seed, optimisation, selection and calibration change'],
        ], [1.70, 1.25, 1.20, 1.00, 1.95])),
        ('p', 'The path to v2 narrowed the search space in recorded steps. A 9.83M-target 2 by 2 factorial '
              f'gave a SwiGLU main effect of {fx["ffn_main"]:+.6f} and an RMSNorm main effect of '
              f'{fx["norm_main"]:+.6f}; width 320, depth 8 and a 1e-3 peak rate then became the capacity '
              'reference, while dropout 0.05 and weight decay 0.2 produced no reproducible gain. After the v1 '
              'long run with learned positions, short RoPE controls improved both tested seeds, whereas '
              'untying, larger capacity, EMA and multi-token prediction were rejected by resource or noise '
              'evidence. The first long RoPE run regressed after 19.66M targets, so three seed runs declared '
              'checkpoints at 9.83M, 19.66M and 28.91M in advance and selected the lowest complete-validation '
              'score; seed 137 at 19.66M was frozen and produced the one-shot v2 test BPB of 1.611178.'),
        ('fig', ('Fig. 3', 'The "test BPB minus validation BPB" offset for the three frozen versions. Three '
                           'independent measurements give +0.023711, +0.023083 and +0.021850, so validation '
                           'predicts test reliably and the test split never has to be scored repeatedly.',
                 'v11_offset')),

        ('h1', '5 Basis for Decisions on Hyperparameters and Training Length'),
        ('p', 'This section answers three questions: where the training budget should stop, what batch size '
              'and learning rate should be used, and how large the noise is before any of these choices can '
              'be judged. All comparisons use seed 17 and one scorer.'),
        ('fig', ('Fig. 4', 'Sweeping the training budget near 20M. The points at 20.0M, 24.0M and 28.9M are '
                           'indistinguishable within noise, so the horizon saturates around 20M, while 16M is '
                           'clearly short.', 'v02_horizon')),
        ('table', ('Table 6', 'Training-budget sweep (seed 17, batch 32, full anneal)',
                   ['Processed targets', 'Validation BPB', 'Relative to 20M', 'Verdict'], [
            [h['label'], f(h['value']),
             f"{h['value'] - d['horizon'][1]['value']:+.6f}",
             'insufficient' if i == 0 else ('saturated' if i else 'reference')]
            for i, h in enumerate(d['horizon'])
        ], [1.80, 1.55, 1.40, 1.40])),
        ('p', 'This closes the ordinary route of training longer. Under a full anneal, pushing the budget '
              'from 20M to 28.9M buys only a noise-level difference, so the remaining improvement had to come '
              'from spending the same token budget more effectively.'),

        ('h2', '5.1 Why training loss and validation must be read together'),
        ('p', 'Training turned out not to be reproducible. The MPS bf16 kernels used for multiplication and '
              'reduction are non-deterministic and two runs of an identical configuration diverge in training '
              'loss from step 500 onwards. We therefore replicated one configuration three times to obtain a '
              'usable noise floor, and graded every later comparison against it.'),
        ('fig', ('Fig. 5', 'Validation BPB of three independent runs of one configuration (seed 17, 28.9M '
                           'targets, batch 32, full anneal). Mean ' + f(noise['mean']) + ', standard deviation '
                 + f(noise['stdev']) + ', range ' + f(noise['range']) + '. The lowest run happens to be the one '
                 'previously used as the baseline.', 'v07_noise')),
        ('table', ('Table 7', 'Noise floor and what it implies', ['Quantity', 'Value', 'Consequence'], [
            ['Mean of three runs', f(noise['mean']), 'the honest baseline for batch 32'],
            ['Between-run standard deviation', f(noise['stdev']), 'a single comparison must exceed about 2 sigma'],
            ['Range of three runs', f(noise['range']), 'about 2 sigma, as expected'],
            ['Adoption criterion', 'monotone trend + paired replication', 'no conclusions from single points'],
        ], [1.95, 1.85, 2.85])),
        ('p', 'This floor changed two earlier conclusions. The claimed overfitting turning point at 19.66M '
              'rests on a +0.015 rebound that sits inside the noise; the correct statement is a plateau around '
              '20M. The claim that "1e-3 is the best learning rate" holds only at batch 32, as section 5.3 '
              'shows. Every mechanism adopted below is therefore supported by a paired comparison or a '
              'monotone trend.'),

        ('h2', '5.2 Scope of application for regularisation results'),
        ('p', 'To confirm that the gain comes from the recipe rather than from regularisation strength, three '
              'training-time regularisers were tested against the fixed batch-32 baseline of 1.605134 at 20M '
              'targets. All were negative or unresolved. Droppath 0.1 degrades validation BPB by 0.045020, far '
              'beyond noise; whole-token dropout and embedding dropout gain only 0.003067 and 0.000981, less '
              'than a third of the noise floor.'),
        ('fig', ('Fig. 6', 'Validation BPB after adding training-time regularisation, against the batch-32 '
                           'baseline of 1.605134 at 20M targets. Droppath 0.1 is clearly harmful; the other '
                           'two sit inside the noise.', 'v08_ablation_regularisation')),
        ('table', ('Table 8', 'Regularisation ablation (seed 17, 20M targets, batch 32)',
                   ['Direction', 'Validation BPB', 'Relative', 'Verdict'], [
            ['baseline, no regulariser', f(d['ablation']['baseline']), '—', 'reference'],
            ['droppath 0.1', f(ab['droppath 0.1']['value']), f"{ab['droppath 0.1']['delta']:+.6f}", 'harmful'],
            ['token dropout 0.05', f(ab['token drop 0.05']['value']),
             f"{ab['token drop 0.05']['delta']:+.6f}", 'unresolved'],
            ['embedding dropout 0.1', f(ab['embed dropout 0.1']['value']),
             f"{ab['embed dropout 0.1']['delta']:+.6f}", 'unresolved'],
            ['EMA 0.999 weight averaging', f(ab['EMA 0.999']['value']),
             f"{ab['EMA 0.999']['delta']:+.6f}", 'harmful'],
        ], [1.95, 1.50, 1.35, 1.65])),
        ('p', 'Read together with the capacity results in section 5.4, this gives the central judgement of '
              'the project: the model is neither under-regularised nor under-sized, but limited by the signal '
              'available in 3.6M training tokens. That is why adding regularisation and adding width both fail.'),

        ('h2', '5.3 Joint choice of learning rate and batch size'),
        ('p', 'This is the largest and most easily missed result of the round. At a fixed 20M targets, '
              'dropping the batch from 32 windows to 4 keeps the token budget and raises the number of '
              'optimisation steps from 2,442 to 19,532, moving validation BPB from 1.605134 to 1.568646. '
              'Continuing to 2 and 1 rebounds to 1.622860 and 1.660514, so the optimum is 4 rather than as '
              'small as possible.'),
        ('fig', ('Fig. 7', 'Validation BPB against batch size. The curve bottoms out at four windows and '
                           'degrades on both sides: smaller batches carry noisier gradients and going too far '
                           'hurts the final quality.', 'v03_batch')),
        ('fig', ('Fig. 8', 'The same results re-ordered by optimisation step count. More steps means lower '
                           'final validation BPB up to 19,532 steps.', 'v10_ablation_steps')),
        ('table', ('Table 9', 'Batch size and optimisation steps (seed 17, 20M targets, full anneal)',
                   ['Batch', 'Steps', 'Validation BPB', 'Relative to batch 32'], [
            [b['label'], f"{b['steps']:,}", f(b['value']),
             f"{b['value'] - d['batch'][0]['value']:+.6f}"] for b in d['batch']
        ], [1.20, 1.65, 1.80, 1.80])),
        ('p', 'At the common 20M-target budget, seed 17 and full anneal, validation BPB moves monotonically '
              'from 1.605134 to 1.582448 and 1.568646 as batch size falls from 32 to 8 and 4. The three '
              'batch-32 replications were run at 28.91M targets and can estimate run-to-run variability, but '
              'they cannot form a valid significance test against the single 20M-target batch-4 result; the '
              'earlier p-value is therefore removed, and the batch result is reported as a trend that still '
              'requires matched-budget replication.'),
        ('p', 'Changing the batch invalidates the learning-rate sweep, and that is the most transferable '
              'lesson of the round. The rate of 1e-3 had been tuned at batch 32, where a step processes 8,192 '
              'tokens. At batch 4 a step processes 1,024 tokens, the gradient noise per step is far larger, '
              'and the optimum shifts upward.'),
        ('fig', ('Fig. 9', 'Re-sweeping the peak learning rate after the batch was changed to 4; six points '
                           'span 7.5e-4 to 3e-3. The single runs at 1.5e-3 and 2.5e-3 differ by 0.000259, while '
                           'the intervening 2e-3 point and the 3e-3 point are about 0.0075 worse and lowering the rate is '
                           'clearly harmful.', 'v04_lr')),
        ('table', ('Table 10', 'Learning-rate re-sweep (seed 17, batch 4, 28.9M targets)',
                   ['Peak learning rate', 'Validation BPB', 'Relative to 1e-3', 'Verdict'], [
            [r['label'], f(r['value']), f"{r['value'] - d['lr'][1]['value']:+.6f}",
             'strong candidate' if r['label'] in ('1.5e-3', '2.5e-3') else
             ('too small' if r['label'] == '7.5e-4' else
              ('weaker single run' if r['label'] in ('2.0e-3', '3.0e-3') else 'reference'))]
            for r in d['lr']
        ], [1.55, 1.60, 1.35, 1.40])),
        ('p', 'Three conclusions follow. The earlier sweep stating that 1e-3 is best and 2e-3 clearly worse '
              'holds only at batch 32 and does not extrapolate; changing the batch invalidates the sweep, which '
              'is the most transferable lesson of the round. Second, extending the sweep to 3e-3 locates the '
              'two separated candidates at 1.5e-3 and 2.5e-3 differ by only 0.000259, but the worse 2e-3 '
              'result between them rules out describing the interval as a continuous plateau. With a '
              'run-to-run standard deviation near 0.010, the evidence supports 1.5e-3 as a sound frozen '
              'choice while leaving the precise learning-rate optimum unresolved pending paired replications.'),
        ('p', 'A further cross-check exposes the coupling between batch size and learning rate. At lr 2e-3 and '
              '28.9M targets, batches of 8, 4 and 2 give validation BPB of 1.572065, 1.564327 and 1.548231, '
              'still monotonically decreasing. In other words the "batch bottoms out at 4" result holds only at '
              'lr 1e-3; once the rate is raised, smaller batches keep improving, where batch 2 scored 1.622860 '
              'at lr 1e-3.'),
        ('p', 'Under a common calibration regime that advantage almost disappears. The optimal temperature for '
              'batch 2 with lr 2e-3 is only 1.025 with a calibration gain of 0.000065, because the model is '
              'already well calibrated, giving 1.548165; v3 gains 0.007392 from calibration and reaches '
              '1.549498. The gap shrinks from 0.008659 to 0.001333, about 0.13 standard deviations.'),
        ('p', 'A paired replication of batch 2 with lr 2e-3, using an identical configuration, then returned '
              '1.555356 against the original 1.548231, a spread of 0.007125 or about 0.7 standard deviations, '
              'for a two-sample mean of 1.551793. The original 0.008659 advantage was therefore mostly a single '
              'point fluctuation, and the two-sample mean is still worse than v3 under a common calibration '
              'regime (1.551793 against 1.549498). Pushing on to batch 1 degrades sharply to 1.660200, and '
              'batch 2 with a higher rate of 2.5e-3 is also worse at 1.560446, so the small-batch direction is '
              'closed.'),
        ('p', 'This report therefore does not issue a new version, and records two methodological rules instead. '
              'Two recipes must be compared after each has been given its own optimal temperature, otherwise '
              'changes of the "smaller batch and higher rate" kind are systematically overstated because '
              'calibration headroom moves the other way. And any single-point difference near the noise floor '
              'must be replicated before it is believed: here a single point appeared to win by 0.0087 and the '
              'advantage vanished on replication.'),

        ('h2', '5.4 Normalisation and feed-forward factorial'),
        ('p-compact', 'Once the two factors are separated, almost the entire gain sits in the '
                      'feed-forward network; RMSNorm adds only a small extra amount and the '
                      'interaction is negligible, so the two choices are close to additive and can '
                      'be explained separately.'),
        ('p-full', 'Everything above asks how this block should be trained. Explaining why the block itself is '
              'RMSNorm plus SwiGLU needs the two factors separated instead of asserted jointly. The '
              'factorial below runs on the baseline scale (width 128, depth 4, about 1.08M parameters). All '
              'four cells share 9,830,400 processed targets, batch 32, peak learning rate 1e-3, three percent '
              'warmup followed by cosine decay, and seed 17, so a difference between two cells can only come '
              'from the component that was swapped.'),
        ('table', ('D-1', 'Normalisation by feed-forward factorial: four cells at 9.83M targets, batch 32, '
                          'peak learning rate 1e-3, seed 17.',
                   ['Normalisation', 'Feed-forward', 'Parameters', 'Validation BPB'], [
            ['LayerNorm', 'GELU (4x wide)', f"{arc['s0_lr1e3']['params']:,}", f(arc['s0_lr1e3']['bpb'])],
            ['LayerNorm', 'SwiGLU (2.667x wide)', f"{arc['ablation_ln_swiglu_s17']['params']:,}",
             f(arc['ablation_ln_swiglu_s17']['bpb'])],
            ['RMSNorm', 'GELU (4x wide)', f"{arc['ablation_rms_gelu_s17']['params']:,}",
             f(arc['ablation_rms_gelu_s17']['bpb'])],
            ['RMSNorm', 'SwiGLU (2.667x wide)', f"{arc['s_lr1e3']['params']:,}",
             f(arc['s_lr1e3']['bpb'])],
        ], [1.35, 1.75, 1.35, 1.60])),
        ('table', ('D-2', 'Main effects and interaction of the same factorial',
                   ['Effect', 'Definition', 'Value'], [
            ['Feed-forward main effect', 'SwiGLU 2.667x replacing GELU 4x, averaged over both rows',
             f"{fx['ffn_main']:+.6f}"],
            ['Normalisation main effect', 'RMSNorm replacing LayerNorm, averaged over both rows',
             f"{fx['norm_main']:+.6f}"],
            ['Interaction', 'difference between the feed-forward gain under the two normalisations',
             f"{fx['norm_ffn_interaction']:+.6f}"],
        ], [1.70, 3.55, 1.25])),
        ('p-full', f'The reading is direct: almost the whole gain comes from the feed-forward network '
              f'({fx["ffn_main"]:+.6f}); RMSNorm adds roughly one tenth more ({fx["norm_main"]:+.6f}); the '
              f'interaction ({fx["norm_ffn_interaction"]:+.6f}) is far smaller than either main effect. The '
              f'two choices are therefore close to additive and can be explained and adopted separately, '
              f'instead of being presented as a single indivisible "combination mechanism". The four cells '
              f'differ in parameter count by less than 0.16 percent, so the feed-forward main effect cannot '
              f'be dismissed as extra parameters: the 2.667x width exists precisely to match the FLOPs of a '
              f'4x-wide GELU layer.'),
        ('p-full', 'The boundary of this evidence has to be stated: the factorial was run only at the baseline '
              'scale and was never repeated cell by cell at the final width 320 / depth 8. It supports the '
              'choice of RMSNorm plus SwiGLU, but it does not produce a number that transfers exactly to the '
              'final scale, and it is used here as directional evidence only.'),

        ('h2', '5.5 Position representation and weight sharing'),
        ('p-compact', 'RoPE improves both seeds by a consistent amount and is adopted. The apparent '
                      'gain from untying is largely confounded with RoPE: once RoPE is in place it '
                      'falls below the single-run noise level, so tied weights are kept.'),
        ('p-full', 'The second group compares position representation and tied output/input weights close to the '
              'final scale (width 320, depth 8). Conditions are again 9,830,400 targets, batch 32, peak '
              'learning rate 1e-3, three percent warmup and cosine decay; each position variant is paired '
              'across seed 17 and seed 137, so structural gains can be separated from single-run noise.'),
        ('table', ('D-3', 'Position representation by weight sharing: 9.83M targets, batch 32, peak learning '
                          'rate 1e-3.',
                   ['Position', 'Weights', 'Parameters', 'Seed 17', 'Seed 137'], [
            ['learned embeddings', 'tied', f"{arc['lr1e3_a']['params']:,}",
             f(arc['lr1e3_a']['bpb']), '-'],
            ['learned embeddings', 'untied', f"{arc['ablation_untied_s17']['params']:,}",
             f(arc['ablation_untied_s17']['bpb']), '-'],
            ['RoPE', 'tied', f"{arc['ablation_rope_s17']['params']:,}",
             f(arc['ablation_rope_s17']['bpb']), f(arc['ablation_rope_s137']['bpb'])],
            ['RoPE', 'untied', f"{arc['ablation_rope_untied_s17']['params']:,}",
             f(arc['ablation_rope_untied_s17']['bpb']),
             f(arc['ablation_rope_untied_s137']['bpb'])],
        ], [1.55, 0.95, 1.35, 1.15, 1.15])),
        ('table', ('D-4', 'Separating two apparently independent gains',
                   ['Comparison', 'Delta', 'Reading'], [
            ['RoPE replacing learned positions (tied, seed 17)', f"{fx['rope_gain']:+.6f}",
             'also removes 81,920 position parameters'],
            ['untied, under learned positions (seed 17)', f"{fx['untied_on_learned']:+.6f}",
             'the largest apparent gain'],
            ['untied, under RoPE (seed 17)', f"{fx['untied_on_rope_17']:+.6f}",
             'only a third of the previous row'],
            ['untied, under RoPE (seed 137)', f"{fx['untied_on_rope_137']:+.6f}",
             'same direction, smaller size'],
            ['untied, under RoPE, mean of two seeds', f"{fx['untied_on_rope_mean']:+.6f}",
             'below the single-run noise sigma of about 0.0102'],
            ['interaction: the untied gain under the two position choices',
             f"{fx['untied_interaction']:+.6f}", 'most of the untied gain is confounded with RoPE'],
        ], [2.80, 1.25, 2.40])),
        ('p-full', f'This is the clearest example in the report of why a combined comparison is not a causal '
              f'claim. Reading only the best cell (RoPE plus untied, '
              f'{arc["ablation_rope_untied_s137"]["bpb"]:.6f}) invites attributing '
              f'{fx["untied_on_learned"]:+.6f} to untying; once the two rows are differenced, untying on top '
              f'of RoPE is worth only {fx["untied_on_rope_mean"]:+.6f} on average, below the single-run noise '
              f'sigma of about 0.0102 measured in section 5.1. Untying also costs 655,360 extra parameters, '
              f'about 2.6 MiB of inference assets, so the final model keeps tied weights. RoPE goes the other '
              f'way: it gives {fx["rope_gain"]:+.6f} on seed 17 and '
              f"{arc['ablation_rope_s137']['bpb'] - arc['lr1e3_a']['bpb']:+.6f} on seed 137, consistent in "
              f'sign and far larger than the noise, while removing the 256 x 320 = 81,920 learned position '
              f'parameters, so it is adopted.'),

        ('h2', '5.6 Training-only mechanisms and the trainer ladder'),
        ('p-compact', 'Tail weight averaging and multi-token prediction both land inside the noise '
                      'band, and applying every trainer change to the baseline model degrades it, so '
                      'the gains are structural rather than from sampling, beta2 or the schedule; the '
                      'optimal learning rate also moves with batch size.'),
        ('p-full', 'This subsection answers two questions that are easily conflated: whether training tricks that '
              'cost nothing at inference time help, and whether the improvement could in fact come from the '
              'trainer rather than from the model.'),
        ('table', ('D-5', 'Two training-only mechanisms that add no inference-time state (RoPE plus untied, '
                          'seed 17, 9.83M targets)',
                   ['Configuration', 'Validation BPB', 'Delta', 'Verdict'], [
            ['control, same configuration, nothing added', f(arc['ablation_rope_untied_s17']['bpb']),
             '-', 'reference'],
            ['tail weight averaging, EMA 0.99 starting at 80 percent',
             f(arc['ablation_rope_untied_ema099_s17']['bpb']), f"{fx['ema_gain']:+.6f}",
             'single run, below the replication threshold'],
            ['multi-token prediction, MTP k=1 with auxiliary weight 0.15',
             f(arc['ablation_rope_untied_mtp1_s17']['bpb']), f"{fx['mtp_gain']:+.6f}",
             'same as above'],
        ], [2.55, 1.45, 1.20, 1.25])),
        ('p-full', f'Neither mechanism adds inference-time state or computation: EMA only averages tail weights '
              f'from one optimisation trajectory, and MTP only adds an auxiliary target during training. '
              f'Both could therefore be added freely under the rule that training duration is unrestricted, '
              f'but their gains ({fx["ema_gain"]:+.6f} and {fx["mtp_gain"]:+.6f}) come from single runs and '
              f'neither exceeds the single-run noise sigma of about 0.0102 measured in section 5.1, so they '
              f'did not enter the frozen recipe. One boundary has to be recorded: neither mechanism was ever '
              f're-measured under the v3 recipe (batch 4, peak learning rate 1.5e-3, 28.9M targets). This '
              f'report claims neither that they hold at that setting nor that they fail there.'),
        ('table', ('D-6', 'Trainer changes applied cumulatively to the supplied baseline model '
                          '(width 128, depth 4; seed 17; 9.83M targets)',
                   ['Cumulative step', 'Validation BPB', 'Delta from previous step'], [
            ['1. supplied recipe: with replacement, beta2 0.999, baseline LR schedule',
             f(arc['recipe_exact_baseline_s17']['bpb']), '-'],
            ['2. plus without-replacement window sampling',
             f(arc['recipe_norepl_s17']['bpb']), f"{fx['ladder_norepl']:+.6f}"],
            ['3. plus AdamW beta2 = 0.95',
             f(arc['recipe_norepl_beta095_s17']['bpb']), f"{fx['ladder_beta2']:+.6f}"],
            ['4. plus three percent warmup and cosine decay',
             f(arc['recipe_full_student_s17']['bpb']),              f"{fx['ladder_schedule']:+.6f}"],
            ['net effect of step 1 to step 4', '-', f"{fx['ladder_net']:+.6f}"],
        ], [3.75, 1.45, 1.35])),
        ('p-full', f'This ladder exists to close the alternative explanation that the improvement comes from the '
              f'trainer. After every trainer setting used in this project is applied to the same baseline '
              f'model, validation BPB does not improve: it gets worse by {fx["ladder_net"]:+.6f}. The gains '
              f'attributed to the model therefore cannot come from sampling, beta2 or the learning-rate '
              f'schedule; they have to come from the structure, discussed in section 3 and section 5.4. This '
              f'is also a negative result worth keeping: moving beta2 from 0.999 to 0.95 is harmful on its '
              f'own at this budget ({fx["ladder_beta2"]:+.6f}), and it is retained only because combined with '
              f'warmup and cosine decay on deeper, wider and longer-trained models it no longer shows a '
              f'penalty. Every row of the ladder is confounded with the rows above it, so no single row is a '
              f'causal contribution of one mechanism.'),
        ('table', ('D-7', 'The earlier learning-rate sweep: batch 32, seed 17, 9.83M targets, learned '
                          'positions with tied weights',
                   ['Peak learning rate', 'Validation BPB', 'Relative to 1e-3'], [
            [label, f(arc[name]['bpb']), f"{arc[name]['bpb'] - arc['lr1e3_a']['bpb']:+.6f}"]
            for label, name in (('5.0e-4', 'lr5e4_a'), ('7.5e-4', 'lr7p5e4_a'),
                                ('1.0e-3', 'lr1e3_a'), ('1.25e-3', 'lr1p25e3_a'),
                                ('2.0e-3', 'lr2e3_a'), ('4.0e-3', 'lr4e3_a'))
        ], [1.65, 1.75, 1.65])),
        ('p-full', f'This is the source of the methodological point made in section 5.3: at batch 32 the swept '
              f'optimum really was 1e-3, and 2e-3 collapsed '
              f'({arc["lr2e3_a"]["bpb"] - arc["lr1e3_a"]["bpb"]:+.6f}). Once the batch drops to 4 the same '
              f'conclusion stops holding and the optimum moves past 1.5e-3. A learning rate has no optimum '
              f'that is independent of batch size; every change of batch requires a fresh sweep.'),

        ('h2', '5.7 Why capacity stops at width 320 / depth 8'),
        ('p', 'Changing width or depth at a fixed token budget shows widths of 256 and 288 to be worse than '
              '320 by 0.022691 and 0.011753, while depth 9 is nominally better by 0.010936 but only half the '
              'noise floor and therefore unresolved. The intuition that a smaller model would overfit less '
              'does not hold here, and width 320 with depth 8 is the sweet spot for this budget.'),
        ('fig', ('Fig. 10', 'Changing width or depth at a fixed token budget. Shrinking the model clearly '
                            'hurts; deepening it gains nothing outside the noise band.', 'v05_capacity')),
        ('fig', ('Fig. 11', 'The paired capacity results: widths 288 and 256 are worse than width 320 by '
                            '0.011753 and 0.022691 BPB.', 'v09_ablation_capacity')),
        ('table', ('Table 11', 'Capacity, quality and training cost (seed 17, 20M targets, batch 32)',
                   ['Configuration', 'Validation BPB', 'Relative to w320', 'Parameters', 'Verdict'], [
            ['width 256 / depth 8', f(ab['width 256']['value']), f"{ab['width 256']['delta']:+.6f}",
             '6,816,000', 'harmful'],
            ['width 288 / depth 8', f(ab['width 288']['value']), f"{ab['width 288']['delta']:+.6f}",
             '8,557,344', 'harmful'],
            ['width 320 / depth 8 (reference)', f(d['ablation']['baseline']), '—', '10,488,640', 'reference'],
            ['width 320 / depth 9', f(ab['depth 9']['value']), f"{ab['depth 9']['delta']:+.6f}",
             '11,717,760', 'unresolved'],
        ], [1.90, 1.35, 1.15, 1.25, 0.95])),
        ('p', 'Two further capacity directions were excluded by the resource limits rather than by experiment. '
              'Width 384 would push the CPU time ratio to between 4.5 and 5.0x, too close to the hard limit to '
              'leave any re-measurement margin, and an earlier short-budget comparison found both width 384 and '
              'depth 10 clearly worse. Within this evaluation budget, capacity exploration is effectively closed.'),

        ('h1', '6 Final Results and Resources After Freezing'),
        ('p', 'The v3 freeze manifest was written before the test run with its test-result field empty; the '
              'same checkpoint was then scored once. Every hash was checked against the manifest.'),
        ('table', ('Table 12', 'Final results on the complete test split',
                   ['Version', 'Validation BPB', 'Complete test BPB', 'Token PPL', 'Relative to baseline'], [
            ['Course baseline', f(v['baseline']['validation']), f(v['baseline']['test']), '80.848', '—'],
            ['Frozen v1', f(v['v1']['validation']), f(v['v1']['test']), '31.83',
             f"{(v['v1']['test'] / v['baseline']['test'] - 1) * 100:.2f}%"],
            ['Frozen v2', f(v['v2']['validation']), f(v['v2']['test']), '29.023',
             f"{(v['v2']['test'] / v['baseline']['test'] - 1) * 100:.2f}%"],
            ['Frozen v3 (this round)', f(v['v3']['validation']), f(v['v3']['test']), '26.704',
             f"{(v['v3']['test'] / v['baseline']['test'] - 1) * 100:.2f}%"],
        ], [1.55, 1.35, 1.35, 1.05, 1.40])),
        ('h2', '6.1 Training and search costs'),
        ('p', f'The disclosed search totals {live["runs"]} controlled runs and '
              f'{live["total_processed_targets"]:,} processed targets this round. The freeze manifest records '
              f'the snapshot as it stood at freeze time ({search["runs_included"]} runs and '
              f'{search["total_processed_targets"]:,} targets); the later learning-rate runs are counted here '
              f'as well. On top of that, 33 runs and 429,047,808 targets went into v1 and v2 development. '
              f'A single 20M-target run takes about 16 to 20 minutes on '
              f'MPS bf16, and the final recipe (28.9M targets at batch 4) about 27 minutes. Training duration '
              f'and search size are unlimited under the course rules and only need disclosure.'),
        ('p', 'This round raises the optimisation-step count by about eightfold while leaving the parameter '
              'count unchanged; inference adds only one temperature division over the logits, whose compute '
              'and storage costs are negligible beside the Transformer forward pass.'),
        ('h2', '6.2 What the test improvement corresponds to'),
        ('p', f'v3 test BPB is {delta_v3:.6f} below v2, but the result is not an additive causal decomposition: '
              f'the {recipe:.6f} uncalibrated validation gap combines changes in seed, batch, learning rate, '
              f'decay floor and checkpoint location, whereas only the {calib:.6f} temperature gain is a paired '
              'comparison on the same v3 checkpoint. The architecture and parameter count are unchanged, and '
              'the inference graph explicitly adds the temperature division.'),
        ('fig', ('Fig. 12', 'Validation BPB before and after temperature scaling. The v2 value T = 1.10 is a '
                            'post-freeze diagnostic and official v2 remains at T = 1.00; v3 selected T = 1.075 '
                            'before its freeze.', 'v06_temperature')),
        ('table', ('Table 13', 'Calibration and the half-split generalisation check',
                   ['Item', 'Value', 'Note'], [
            ['Diagnostic optimum T for v2', f"{t['v2_temperature']:.3f}", 'post-freeze only; official v2 uses T = 1.00'],
            ['Optimal T for v3', f"{t['v3_temperature']:.3f}", 'validation BPB 1.556890 to 1.549498'],
            ['Gain on the fitting half', f"{t['holdout']['half_a_at_t1'] - t['holdout']['half_a_at_t_star']:.6f}",
             'T fitted on the even half only'],
            ['Gain on the held-out half', f"{t['holdout']['half_b_at_t1'] - t['holdout']['half_b_at_t_star']:.6f}",
             'scored on the odd half; no smaller than the fitting half'],
            ['Inference cost', 'negligible', 'no extra parameters; one scalar division, assets +1 KB'],
        ], [1.95, 1.35, 3.15])),
        ('p', 'One interaction is easy to miss: smaller batches carry more training noise and leave less '
              'calibration headroom (0.013023 for v2 against 0.007392 for v3). The batch-4 gain and the '
              'calibration gain therefore cannot be added and compared against batch 32; both must be compared '
              'under the same calibration regime, which is how this report treats them.'),
        ('h2', '6.3 Resource thresholds and measurement protocols'),
        ('p', 'Resource measurement uses a median of five repetitions. Each repetition loads one checkpoint in '
              'a fresh process and scores the complete test split in CPU FP32, with the baseline measured in '
              'the same invocation so the ratio never depends on a stale hard-coded number.'),
        ('fig', ('Fig. 13', 'Resource use of v2 and v3 on the test split, as a fraction of each limit. Both '
                            'predictors remain below all three bounds, with nearly identical asset use.',
                 'v12_resources')),
        ('table', ('Table 14', 'Test resource measurement (median of five, FP32, four threads)',
                   ['Metric', 'v2 measured', 'v3 measured', 'Limit', 'Verdict'], [
            ['CPU time ratio', f"{res['CPU time']['v2']:.3f}x", f"{res['CPU time']['v3']:.3f}x", '5x', 'pass'],
            ['Peak RSS', f"{res['Peak RSS']['v2']:.3f} GiB", f"{res['Peak RSS']['v3']:.3f} GiB",
             '4 GiB', 'pass'],
            ['Inference assets', f"{res['Inference assets']['v2']:.3f} MiB",
             f"{res['Inference assets']['v3']:.3f} MiB", '64 MiB', 'pass'],
        ], [1.45, 1.35, 1.35, 1.05, 0.95])),
        ('p', 'The compute limit is not the binding constraint because fixed overhead and the inefficiency of '
              'the reference implementation take a large share: the course baseline has only 1.09M parameters '
              'and its small matrix multiplications run far below the efficiency of a width-320 model, so '
              'scaling parameters by nearly ten raises the time ratio only to about three. This report also '
              'records that the ratio itself is unstable across sessions, so freezing always re-measures '
              'instead of trusting a single number.'),

        ('h1', '7. How the supplementary ablation changes the subsequent direction'),
        ('p', 'This section collects every direction that was rejected or left unresolved. They matter as much '
              'as the positive results: these negative results closed the three conventional routes of more '
              'regularisation, more capacity and more training, which left batch size and learning rate as the '
              'only remaining levers that cost nothing at inference.'),
        ('table', ('Table 15', 'Every ablation of this round and its verdict',
                   ['Direction', 'Validation BPB', 'Relative', 'Verdict', 'Consequence'], [
            ['droppath 0.1', f(ab['droppath 0.1']['value']), f"{ab['droppath 0.1']['delta']:+.6f}",
             'harmful', 'training-time regularisation closed'],
            ['EMA 0.999', f(ab['EMA 0.999']['value']), f"{ab['EMA 0.999']['delta']:+.6f}",
             'harmful', 'weight averaging not adopted'],
            ['width 256', f(ab['width 256']['value']), f"{ab['width 256']['delta']:+.6f}",
             'harmful', 'shrinking capacity is not viable'],
            ['width 288', f(ab['width 288']['value']), f"{ab['width 288']['delta']:+.6f}",
             'harmful', 'shrinking capacity is not viable'],
            ['depth 9', f(ab['depth 9']['value']), f"{ab['depth 9']['delta']:+.6f}",
             'unresolved', 'needs paired replication'],
            ['token dropout 0.05', f(ab['token drop 0.05']['value']),
             f"{ab['token drop 0.05']['delta']:+.6f}", 'unresolved', 'gain below the noise floor'],
            ['embedding dropout 0.1', f(ab['embed dropout 0.1']['value']),
             f"{ab['embed dropout 0.1']['delta']:+.6f}", 'unresolved', 'gain below the noise floor'],
        ], [1.75, 1.35, 1.15, 0.85, 1.85])),
        ('h2', '7.1 Why regularisation fails here'),
        ('p', 'Regularisation is negative or unresolved across the board, which runs against the common '
              'expectation that a small dataset wants more of it. The reason is that the limiting factor here '
              'is not how often the model has seen the training set, but that the training set itself holds '
              'only 3.6M tokens. In that regime the model has not exhausted its fitting capacity, and any '
              'perturbation, whether dropping branches, tokens, dimensions or averaging weights, removes '
              'signal it could otherwise have learned. The training-budget sweep in section 5 shows the '
              'same limit from another direction: beyond 20M targets no stable gain exceeds run variability.'),
        ('h2', '7.2 Directions excluded by the resource limits'),
        ('p', 'Width 384 with depth 8 still fits the 64 MiB asset limit (about 57 MiB) but pushes the CPU time '
              'ratio to between 4.5 and 5.0x, too close to the hard limit given the instability this report '
              'records. That direction is judged infeasible rather than refuted. Batches of 1 already rebounded '
              'in the measurement and need no further work.'),

        ('h1', '8 Three Seeds and Best-Checkpoint Selection'),
        ('p', 'v2 was selected from three seeds on validation (seed 137 scored 1.588095, seed 17 scored '
              '1.600916 and seed 233 scored 1.611337, mean 1.600116). After establishing the noise floor this '
              'round, that three-seed selection advantage turns out to be only 0.012, the same order as the '
              'between-run standard deviation of 0.010, so a substantial part of it was selecting noise.'),
        ('table', ('Table 16', 'Paired replications against the v2 three-seed spread',
                   ['Source', 'Content', 'Mean', 'Standard deviation'], [
            ['This round, paired', 'three runs of one configuration (batch 32)', f(noise['mean']), f(noise['stdev'])],
            ['v2 three seeds', 'seeds 137 / 17 / 233', '1.600116', '0.011642'],
        ], [1.75, 2.15, 1.35, 1.45])),
        ('h2', '8.1 How non-reproducible training changed the decision rules'),
        ('p', 'Three rules follow and were applied to every conclusion here. A single-run difference below '
              '0.02 is not interpreted. An adopted mechanism must show a monotone trend or a paired '
              'replication. And when selecting checkpoints or seeds, the mean and the spread are reported '
              'rather than only the best run. These rules are what forced the downgrade of the two earlier '
              'conclusions about the overfitting turning point and the scope of the learning-rate sweep.'),
        ('h2', '8.2 Legitimacy boundary of the calibration temperature'),
        ('p', 'Temperature calibration can be misread as tuning for a score, so its boundary is stated '
              'explicitly. It does not change the model\'s discriminative ability, only the calibration of '
              'its output distribution. The output stays normalised, strictly causal and stateless, and the '
              'scorer\'s normalization check still passes. T is a hyperparameter selected on validation, of '
              'the same nature as a learning rate or weight decay, and no test information was used. It also '
              'passed a half-split generalisation check, in which a temperature fitted on one half of '
              'validation gains no less on the other half. Both this report and the freeze manifest state '
              'plainly that the temperature was fitted on validation.'),

        ('h1', '9 Correctness and submission requirements'),
        ('h2', '9.1 Reproducing materials'),
        ('p', 'The freeze manifest records the SHA-256 of the checkpoint, student.py, evaluate.py and the '
              'tokenizer. Training uses train_student.py and scoring uses the supplied evaluate.py unmodified. '
              'Per-run configuration, seed, training seconds, parameter count and checkpoint hash live in each '
              'run directory\'s metrics.json and are summarised in code/results/grid.tsv.'),
        ('table', ('Table 17', 'Freeze record (v3)', ['Item', 'Value'], [
            ['Frozen at', freeze['timestamp']],
            ['Checkpoint', freeze['checkpoint']],
            ['Checkpoint SHA-256', freeze['checkpoint_sha256']],
            ['student.py SHA-256', freeze['implementation_sha256']],
            ['evaluate.py SHA-256', freeze['evaluator_sha256']],
            ['Tokenizer SHA-256', freeze['tokenizer_sha256']],
            ['Parameters', f"{freeze['parameters']:,}"],
            ['Test BPB (single run after freeze)', f(v['v3']['test'])],
        ], [2.30, 4.30], 8.2)),
        ('h2', '9.2 Assignment requirement coverage'),
        ('table', ('Table 18', 'Course requirements and where the evidence lives',
                   ['Course requirement', 'Where it is covered'], [
            ['Initial supplied baseline', 'section 4, Table 5 and Fig. 2'],
            ['Comparison at equal processed targets', 'section 5.3, Table 9 (all at 20M targets)'],
            ['Ablation of the key mechanism', 'sections 5.2, 5.3, 5.4 and section 7'],
            ['Validation-based development and selection', 'sections 2.1 and 8'],
            ['Prediction quality against computational cost', 'sections 5.3 and 6.3, including the resource table'],
            ['Training costs, seeds and checkpoint ancestry', 'section 6.1, section 8 and Appendix A'],
            ['The 5x CPU / 4 GiB / 64 MiB limits', 'section 6.3 resource table and figure'],
            ['One test evaluation after freezing', 'section 6 Table 12 and section 9.1 Table 17'],
        ], [2.60, 4.00])),

        ('h1', '10 Conclusions, Limitations, and AI Disclosure'),
        ('h2', '10.1 Conclusion'),
        ('p', f'Under the fixed WikiText-2 text, BPE-2048 tokenizer, 256-token context and CPU FP32 scorer, '
              f'frozen v3 reaches a complete test BPB of {v["v3"]["test"]:.6f}, {rel_v3:.2f}% below the course '
              f'baseline and {delta_v3:.6f} below the previously frozen v2. All three resource limits pass, '
              f'the three resource limits pass; the parameter count matches v2, while temperature scaling adds '
              f'one scalar division and about 1 KB to the inference assets.'),
        ('p', 'The strongest methodological conclusion is that a batch change requires a fresh learning-rate '
              'sweep and that recipes must be compared under a common calibration protocol. The uncalibrated '
              'v3 validation score is 0.031 below frozen v2, but this joint gap also includes the seed, decay '
              'floor and checkpoint change and cannot be assigned to batch size and learning rate alone; '
              'temperature scaling supplies a separate paired gain of 0.007392 at the cost of one scalar division.'),
        ('h2', '10.2 Limitations'),
        ('p', 'First, non-reproducible training is the dominant methodological constraint. Three runs of one '
              'configuration have a standard deviation of 0.010, so no single comparison counts unless it is '
              'backed by a paired replication or a monotone trend, and two earlier conclusions were downgraded '
              'on that basis.'),
        ('p', 'Second, batch 4 has one observation under the common 20M-target comparison, while the three '
              'batch-32 replications use 28.91M targets and estimate variability rather than a matched effect. '
              'A follow-up should repeat batches 32, 8 and 4 at least twice under the same budget and re-sweep '
              'the learning rate within each batch. The isolated 1.5e-3 and 2.5e-3 runs are close, but the '
              'weaker 2e-3 run between them prevents a continuous-plateau claim.'),
        ('p', 'Third, the architecture and parameter count remain fixed, while the result combines a training '
              'and checkpoint recipe change with inference-time temperature scaling. A stronger experiment '
              'would preregister a paired 28.91M-target matrix, report both uncalibrated and independently '
              'calibrated validation BPB, and use means with confidence intervals to resolve the interactions '
              'among batch size, learning rate and decay floor before freezing another version.'),
        ('p', 'Fourth, the calibration temperature improves calibration rather than discriminative ability. '
              'Although it passed the half-split check, its origin must be stated plainly and it must not be '
              'presented as an architectural improvement.'),
        ('h2', '10.3 AI assistance disclosure'),
        ('p', 'The experiment scripts, figure generation and report typesetting were produced with AI '
              'assistance, including the implementation of three training-only regularisation knobs '
              '(droppath, token dropout and embedding dropout), the calibration and freeze-manifest tooling, '
              'and the figure and Word generation pipeline. All experimental design, metric decisions and '
              'conclusions were confirmed by the author. No AI component took part in any selection on the '
              'test split, and no training data beyond the supplied text was used.'),
        ('fig', ('Fig. 14', 'The debugging path from v1/v2 structure, capacity, position and checkpoint '
                            'selection to the v3 noise, batch, learning-rate and calibration checks; each '
                            'observation directly determines the next experiment.', 'v14_decision_flow')),
        ('h2', 'References'),
        ('p', '1. DASE7506 Project 1 course guide (GUIDE.md). '
              '2. Supplied baseline implementation and scorer (model.py / evaluate.py / common.py, unmodified). '
              '3. Vaswani et al., “Attention Is All You Need,” NeurIPS, 2017. '
              '4. Zhang and Sennrich, “Root Mean Square Layer Normalization,” NeurIPS, 2019. '
              '5. Shazeer, “GLU Variants Improve Transformer,” arXiv:2002.05202, 2020. '
              '6. Su et al., “RoFormer: Enhanced Transformer with Rotary Position Embedding,” Neurocomputing, 2024. '
              '7. Loshchilov and Hutter, “Decoupled Weight Decay Regularization,” ICLR, 2019. '
              '8. Merity et al., “Pointer Sentinel Mixture Models,” ICLR, 2017. '
              '9. This project\'s v1 and v2 technical reports and experiment index (code/results/ and run directories).'),
    ]
    B += appendix_blocks(d, zh=False)
    return B


def appendix_blocks(d: dict, *, zh: bool) -> list[tuple]:
    """Appendix A: the full run index, scanned from the run directories."""
    index = scan_index()
    out: list[tuple] = []
    first = True

    # A.0 lists the earlier v1/v2-stage runs quoted in sections 5.4 to 5.6, so every
    # number in those tables can be traced back to a metrics.json on disk.
    archive_rows = []
    for name in ARCHIVE_RUNS:
        path = ROOT / 'runs' / name / 'metrics.json'
        if not path.exists():
            continue
        d_local = json.loads(path.read_text())
        a = d_local['args']
        archive_rows.append([
            name, str(d_local.get('seed', a.get('seed', ''))), str(a['batch_size']),
            f"{a['lr']:g}", f"{d_local['processed_targets'] / 1e6:.2f}M",
            f"{d_local['validation']['bpb']:.6f}",
        ])
    if archive_rows:
        out.append(('h1', '附录 A 全部已保存实验与来源索引' if zh
                    else 'Appendix A  Full index of saved experiments'))
        out.append(('p', '每一行来自对应 run 目录下的 metrics.json。' if zh else
                    'Each row comes from the metrics.json of that run directory.'))
        out.append(('h2', 'A.0 ' + ('早期结构与表示对照（v1 / v2 阶段）' if zh
                                    else 'Earlier structural and representation controls (v1 / v2 stage)')))
        headers = (['运行', 'seed', '批量', '峰值学习率', 'targets', 'validation BPB'] if zh
                   else ['Run', 'Seed', 'Batch', 'Peak LR', 'Targets', 'Validation BPB'])
        out.append(('table', ('A.0', 'v1 / v2 阶段的历史运行', headers, archive_rows,
                              [1.85, 0.75, 0.85, 1.35, 1.15, 1.50], 7.6)))
        first = False

    for phase, tag, zh_title, en_title in PHASES:
        rows = index.get(phase)
        if not rows:
            continue
        title = zh_title if zh else en_title
        if first:
            out.append(('h1', '附录 A 全部已保存实验与来源索引' if zh
                        else 'Appendix A  Full index of saved experiments'))
            out.append(('p', '每一行来自对应 run 目录下的 metrics.json。' if zh else
                        'Each row comes from the metrics.json of that run directory.'))
            first = False
        out.append(('h2', f'{tag} {title}'))
        headers = (['运行', 'seed', '批量', '峰值学习率', 'targets', 'validation BPB'] if zh
                   else ['Run', 'Seed', 'Batch', 'Peak LR', 'Targets', 'Validation BPB'])
        label = f'（{phase}）' if zh else f'  ({phase})'
        out.append(('table', (tag, title + label, headers, rows,
                              [1.55, 0.80, 0.85, 1.45, 1.20, 1.75], 8.1)))
    if not first:
        out.append(('p', '各 run 目录同时保存 config、种子、训练耗时、参数量与 checkpoint 的 SHA-256；'
                        'v1 与 v2 阶段的历史运行索引见 code/results/grid.tsv。' if zh else
                        'Each run directory also keeps the config, seed, training seconds, parameter '
                        'count and checkpoint SHA-256. Historical v1 and v2 runs are indexed in '
                        'code/results/grid.tsv.'))
    return out


def compact_blocks(d: dict, *, zh: bool) -> list[tuple]:
    """Ten-page submission variant.

    Same ten sections and the same narrative; the appendix index is dropped and
    only the headline figure of each theme is kept.  Captions are renumbered by
    ``renumber`` so the shorter edition has no gaps.
    """
    full = blocks(d, zh=zh, compact=False)
    for index, (kind, payload) in enumerate(full):
        if kind == 'h1' and ('附录 A' in payload or 'Appendix A' in payload):
            full = full[:index]
            break
    # Six figures: the ones whose message is not already carried by a table.
    # The horizon sweep is dropped because Table 6 states it in full.
    keep_fig = {'Fig. 1', 'Fig. 7', 'Fig. 9', 'Fig. 12', 'Fig. 13', 'Fig. 14'}
    arc = archive()
    fx = archive_effects(arc)
    out: list[tuple] = []
    for kind, payload in full:
        if kind == 'fig' and payload[0] not in keep_fig:
            continue
        if kind == 'table' and payload[0].startswith('D-'):
            continue
        if kind in ('p-full', 'p-compact'):
            continue
        if kind == 'h2' and (payload.startswith('5.5 ') or payload.startswith('5.6 ')):
            continue
        out.append((kind, payload))
        if kind == 'h2' and payload.startswith('5.4 '):
            out.append(('p', summary_intro(zh)))
            out.append(summary_table(fx, zh))
    return out


def summary_intro(zh: bool) -> str:
    """One paragraph replacing the dropped detail tables in the ten-page edition."""
    if zh:
        return ('冻结模型的结构本身来自一组更早的对照实验（均为 9,830,400 targets、批量 32、'
                '峰值学习率 1e-3）：归一化 × 前馈网络的 2×2 因子逐格对照、'
                '位置表示与权重共享的配对对照、两个不占推理预算的训练期机制，'
                '以及把训练器逐项叠加到 baseline 模型上的阶梯。'
                '下列差值即这四组实验的结论，逐格的原始数值见完整版第 5.4–5.6 节。')
    return ('The structure of the frozen model comes from an earlier set of controlled comparisons, all at '
            '9,830,400 processed targets, batch 32 and peak learning rate 1e-3: a cell-by-cell '
            'normalisation by feed-forward factorial, a paired comparison of position representation and '
            'weight sharing, two training-only mechanisms that cost nothing at inference, and a ladder that '
            'applies every trainer change to the supplied baseline model. The deltas below are what those '
            'four groups established; the full edition carries the per-cell values in sections 5.4 to 5.6.')


def summary_table(fx: dict[str, float], zh: bool) -> tuple:
    """The verdicts of the structural ablation, condensed to one table."""
    rows = [
        ('SwiGLU 2.667× 替换 GELU 4×（因子主效应）' if zh else
         'SwiGLU 2.667x replacing GELU 4x (factorial main effect)', fx['ffn_main'],
         '采纳' if zh else 'adopted'),
        ('RMSNorm 替换 LayerNorm（因子主效应）' if zh else
         'RMSNorm replacing LayerNorm (main effect)', fx['norm_main'],
         '采纳' if zh else 'adopted'),
        ('上述两者的交互项' if zh else 'interaction between the two',
         fx['norm_ffn_interaction'], '可忽略' if zh else 'negligible'),
        ('RoPE 替换 learned 位置（绑定，seed 17）' if zh else
         'RoPE replacing learned positions (tied, seed 17)', fx['rope_gain'],
         '采纳' if zh else 'adopted'),
        ('解绑，在 learned 位置条件下（seed 17）' if zh else
         'untied, under learned positions (seed 17)', fx['untied_on_learned'],
         '与 RoPE 混杂' if zh else 'confounded with RoPE'),
        ('解绑，在 RoPE 条件下（两个 seed 平均）' if zh else
         'untied, under RoPE (mean of two seeds)', fx['untied_on_rope_mean'],
         '低于噪声，未采纳' if zh else 'below noise, rejected'),
        ('尾部权重平均 EMA 0.99（单次）' if zh else 'tail weight averaging, EMA 0.99 (single run)',
         fx['ema_gain'], '低于噪声，未采纳' if zh else 'below noise, rejected'),
        ('多 token 预测 MTP k=1（单次）' if zh else
         'multi-token prediction, MTP k=1 (single run)', fx['mtp_gain'],
         '低于噪声，未采纳' if zh else 'below noise, rejected'),
        ('训练器逐项叠加的净效果（baseline 模型）' if zh else
         'net effect of applying every trainer change (baseline model)', fx['ladder_net'],
         '训练器不贡献收益' if zh else 'trainer contributes no gain'),
    ]
    return ('table', ('S', '结构与表示的对照汇总（9.83M targets，批量 32，峰值学习率 1e-3）' if zh else
                            'Summary of the structural comparisons: 9.83M targets, batch 32, peak learning '
                            'rate 1e-3.',
                      ['对照' if zh else 'Comparison', '差值' if zh else 'Delta',
                       '结论' if zh else 'Verdict'],
                      [[label, f'{value:+.6f}', verdict] for label, value, verdict in rows],
                      [3.30, 1.20, 1.95]))


def renumber(blocks_list: list[tuple]) -> list[tuple]:
    """Renumber Fig./Table. captions so the compact edition has no gaps."""
    fig = table = 0
    out = []
    for kind, payload in blocks_list:
        if kind == 'fig':
            fig += 1
            out.append((kind, (f'Fig. {fig}', payload[1], payload[2])))
        elif kind == 'table':
            table += 1
            out.append((kind, (f'Table {table}', *payload[1:])))
        else:
            out.append((kind, payload))
    return out


def relabel(flow: list[tuple]) -> list[tuple]:
    """Sequential body-table numbers; appendix tables keep their A.* labels.

    The full edition used to carry hard-coded "Table N" labels.  New tables are
    inserted with a "D-" placeholder so the numbering self-repairs instead of
    every later label having to be renumbered by hand.
    """
    counter = 0
    out: list[tuple] = []
    for kind, payload in flow:
        if kind == 'table' and (payload[0].startswith('Table')
                                or payload[0].startswith('D-')
                                or payload[0] == 'S'):
            counter += 1
            out.append((kind, (f'Table {counter}', *payload[1:])))
        else:
            out.append((kind, payload))
    return out


def render(d: dict, *, zh: bool, compact: bool) -> Path:
    body = ZH_BODY if zh else EN_BODY
    head = ZH_HEAD if zh else EN_HEAD
    document = Document()

    section = document.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = section.right_margin = Cm(2.3)
    section.top_margin = section.bottom_margin = Cm(2.0)

    body_size = 9.0 if compact else 10
    set_style_font(document.styles['Normal'], latin=body, east_asia=body, size=body_size)
    document.styles['Normal'].paragraph_format.line_spacing = 1.02 if compact else 1.15
    set_style_font(document.styles['Title'], latin=head, east_asia=head, size=17, bold=True)
    title_ppr = document.styles['Title'].element.get_or_add_pPr()
    for tag in ('pBdr', 'shd'):
        node = title_ppr.find(qn(f'w:{tag}'))
        if node is not None:
            title_ppr.remove(node)
    set_style_font(document.styles['Heading 1'], latin=head, east_asia=head,
                   size=12.5 if compact else 13.5, bold=True)
    set_style_font(document.styles['Heading 2'], latin=head, east_asia=head,
                   size=10.5 if compact else 11, bold=True)
    document.styles['Heading 1'].paragraph_format.space_before = Pt(10 if compact else 13)
    document.styles['Heading 1'].paragraph_format.space_after = Pt(4 if compact else 5)
    document.styles['Heading 2'].paragraph_format.space_before = Pt(7 if compact else 9)
    document.styles['Heading 2'].paragraph_format.space_after = Pt(3 if compact else 4)

    image_width = 3.8 if compact else 5.4
    indent = Pt(18 if compact else 21)
    table_size = 7.7 if compact else 8.5
    flow = blocks(d, zh=zh, compact=compact)
    flow = renumber(flow) if compact else relabel(flow)

    for kind, payload in flow:
        if kind == 'p-compact' and not compact:
            continue
        if kind == 'title':
            paragraph = document.add_paragraph(payload, style='Title')
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(4)
            ppr = paragraph._p.get_or_add_pPr()
            for tag in ('pBdr', 'shd'):
                node = ppr.find(qn(f'w:{tag}'))
                if node is not None:
                    ppr.remove(node)
        elif kind == 'subtitle':
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            paragraph.paragraph_format.space_after = Pt(10)
            run = paragraph.add_run(payload)
            set_font(run, latin=body, east_asia=body, size=9.5, italic=True, color='555555')
        elif kind in ('h1', 'h2'):
            paragraph = document.add_paragraph(payload, style='Heading 1' if kind == 'h1' else 'Heading 2')
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.keep_together = True
        elif kind in ('p', 'p-full'):
            paragraph = document.add_paragraph(payload, style='Normal')
            fmt = paragraph.paragraph_format
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            fmt.first_line_indent = indent
            fmt.space_after = Pt(4)
            fmt.widow_control = True
        elif kind == 'table':
            label, text, headers, rows, widths = payload[:5]
            size = payload[5] if len(payload) > 5 else table_size
            caption(document, label + '. ', text, font=body, east_asia=body)
            three_line_table(document, headers, rows, widths,
                             font=body, east_asia=body, size=size, header_size=size)
            document.add_paragraph().paragraph_format.space_after = Pt(2)
        elif kind == 'fig':
            label, text, figure_id = payload
            path = FIGDIR / f'{figure_id}.png'
            if not path.exists():
                raise SystemExit(f'missing figure {path}')
            image(document, path, image_width)
            caption(document, label + '. ', text, font=body, east_asia=body, keep_with_next=False)

    document.core_properties.title = (
        'DASE7506 Project 1 技术报告 v3' if zh else 'DASE7506 Project 1 Technical Report v3')
    document.core_properties.comments = (
        f'Frozen v3 test BPB {d["versions"][3]["test"]:.6f}; search '
        f'{d["search_accounting"]["total_processed_targets"]:,} processed targets')

    OUT.mkdir(parents=True, exist_ok=True)
    if compact:
        target = OUT / ('DASE7506_Project_1_TECH_Report_中文_v3_10页版.docx' if zh
                        else 'DASE7506_Project_1_TECH_Report_English_v3_Submission_10pg.docx')
    else:
        target = ZH_OUT if zh else EN_OUT
    document.save(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--compact', action='store_true',
                        help='also build the ten-page submission variants')
    args = parser.parse_args()
    d = json.loads(DATA.read_text(encoding='utf-8'))
    targets = [(d, zh, False) for zh in (True, False)]
    if args.compact:
        targets += [(d, zh, True) for zh in (True, False)]
    for payload, zh, compact in targets:
        target = render(payload, zh=zh, compact=compact)
        doc = Document(target)
        figures = sum(1 for p in doc.paragraphs if p._p.xpath('.//w:drawing'))
        print(f'{"中文" if zh else "English"}{"（10页版）" if compact else ""}: {target.name}  '
              f'{len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables, {figures} figures, '
              f'{target.stat().st_size / 1024:.0f} KB')


if __name__ == '__main__':
    main()
