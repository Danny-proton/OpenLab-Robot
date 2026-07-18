#!/usr/bin/env python3
"""case_iteration_report.py — 用例自优化迭代报告（MD + HTML）。

V1.1 用例自优化的报告模块。消费 case_optimizer 产出的 proposal + 完整质量/mutation 结果，
生成人读的迭代报告，含：
- 错误分布（F1-F8 集中度）
- spec 缺口清单
- 12 维质量分（前后对比）
- mutation kill matrix
- 优化建议清单（add/modify/deprecate/spec_changes）
- 度量指标（覆盖率/质量分/mutation 检出率变化）

零 LLM。纯模板渲染。

用法:
  python case_iteration_report.py --config .agent-eval/config.yaml --proposal <proposal_id>
  python case_iteration_report.py --config .agent-eval/config.yaml --latest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import case_io as CIO  # noqa: E402
import html as _html_lib  # noqa: E402

try:
    # 复用 report_portal.py 的 PORTAL_CSS（深色玻璃态设计语言），保证视觉一致
    from report_portal import PORTAL_CSS as _PORTAL_CSS  # type: ignore
except Exception:  # pragma: no cover
    _PORTAL_CSS = None  # 退化时由 HTML_STYLE 兜底


def _h(s) -> str:
    """HTML escape。"""
    return _html_lib.escape(str(s) if s is not None else "")


# ---------------------------------------------------------------------------
# 加载 proposal
# ---------------------------------------------------------------------------

def load_proposal(cfg: C.EvalConfig, proposal_id: str) -> dict[str, Any]:
    """加载完整 proposal（含 _full_quality/_full_mutation）。"""
    path = CIO.data_dir(cfg) / f"{proposal_id}.full.json"
    if not path.exists():
        # 退化到 clean 版本
        path = CIO.data_dir(cfg) / f"{proposal_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"proposal 不存在: {proposal_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def find_latest_proposal(cfg: C.EvalConfig) -> str | None:
    """找最新的 proposal id。"""
    proposals = sorted((CIO.data_dir(cfg)).glob("prop-*.full.json"))
    if not proposals:
        proposals = sorted((CIO.data_dir(cfg)).glob("prop-*.json"))
    if not proposals:
        return None
    return proposals[-1].stem.replace(".full", "")


# ---------------------------------------------------------------------------
# MD 报告
# ---------------------------------------------------------------------------

def render_md(proposal: dict, iterations: list[dict]) -> str:
    lines: list[str] = []
    pid = proposal.get("proposal_id", "?")
    run_id = proposal.get("run_id", "?")
    split = proposal.get("split", "?")

    lines.append(f"# 用例自优化迭代报告\n")
    lines.append(f"- **proposal_id**: `{pid}`")
    lines.append(f"- **run_id**: `{run_id}`")
    lines.append(f"- **split**: `{split}`")
    lines.append(f"- **生成时间**: {proposal.get('generated_at', '?')}")
    lines.append(f"- **触发原因**: {proposal.get('trigger', '?')}")
    lines.append(f"- **摘要**: {proposal.get('summary', '')}\n")

    analysis = proposal.get("analysis", {})

    # 1. 错误分布
    lines.append("## 1. 错误分布分析\n")
    ed = analysis.get("error_distribution", {})
    lines.append(f"- 诊断总数: {ed.get('total_diagnoses', 0)}")
    lines.append(f"- 集中类型: {ed.get('concentrated_types') or '无'}\n")
    by_ft = ed.get("by_failure_type", {})
    if by_ft:
        lines.append("| 失败类型 | 数量 | 占比 | 集中 |")
        lines.append("|---------|------|------|------|")
        for ft, d in sorted(by_ft.items()):
            lines.append(f"| {ft} | {d['count']} | {d['ratio']:.1%} | {'⚠️ 是' if d['concentrated'] else '否'} |")
        lines.append("")

    # 2. spec 缺口
    lines.append("## 2. Spec 缺口\n")
    gaps = analysis.get("spec_gaps", [])
    if gaps:
        lines.append("| 类型 | 描述 | 严重度 |")
        lines.append("|------|------|--------|")
        for g in gaps:
            desc = g.get("reason", "")
            lines.append(f"| {g.get('type', '?')} | {desc} | {g.get('severity', '?')} |")
        lines.append("")
    else:
        lines.append("无 spec 缺口。\n")

    # 3. 质量分
    lines.append("## 3. 用例质量评分（12 维）\n")
    qs = analysis.get("quality_scores", {})
    qtotal = analysis.get("quality_weighted_total", 0)
    low_dims = analysis.get("quality_low_score_dimensions", [])
    lines.append(f"- **加权总分**: {qtotal:.4f}")
    lines.append(f"- 低分维度（<0.6）: {low_dims or '无'}\n")
    if qs:
        lines.append("| 维度 | 权重 | 得分 |")
        lines.append("|------|------|------|")
        for dim_id, d in qs.items():
            score = d.get("score", 0)
            bar = "🟢" if score >= 0.8 else ("🟡" if score >= 0.6 else "🔴")
            lines.append(f"| {dim_id} ({d.get('name', '')}) | {d.get('weight', 0)} | {bar} {score:.3f} |")
        lines.append("")

    # 4. mutation kill matrix
    lines.append("## 4. Mutation Kill Matrix\n")
    mk = analysis.get("mutation_kills", {})
    lines.append(f"- 变异总数: {mk.get('total_mutations', 0)}")
    lines.append(f"- killed: {mk.get('killed', 0)} / survived: {mk.get('survived', 0)}")
    lines.append(f"- **检出率**: {mk.get('kill_rate', 0):.1%}\n")
    survived = mk.get("survived_mutations", [])
    if survived:
        lines.append("### 未检出变异（需增强用例）\n")
        for sm in survived:
            lines.append(f"- **{sm['case_id']}** × `{sm['mutation']}` ({sm['mutation_name']})")
            lines.append(f"  - {sm['reason']}")
        lines.append("")

    # 5. 优化建议
    lines.append("## 5. 优化建议\n")
    add_cases = proposal.get("add_cases", [])
    modify_cases = proposal.get("modify_cases", [])
    deprecate_cases = proposal.get("deprecate_cases", [])
    spec_changes = proposal.get("spec_changes", [])

    lines.append(f"### 5.1 新增用例（{len(add_cases)}）\n")
    if add_cases:
        for ac in add_cases:
            c = ac.get("case", {})
            lines.append(f"- **{ac.get('suggested_id', c.get('id', '?'))}** — {c.get('name', '?')}")
            lines.append(f"  - 原因: {ac.get('reason', '?')}")
            lines.append(f"  - 触发失败: {ac.get('trigger_failure_type', '?')}")
            lines.append(f"  - 类别: {c.get('category', '?')} | 生命周期: {c.get('lifecycle', '?')}")
        lines.append("")
    else:
        lines.append("无新增建议。\n")

    lines.append(f"### 5.2 修改用例（{len(modify_cases)}）\n")
    if modify_cases:
        lines.append("| 用例 | 字段 | 原值 | 新值 | 原因 |")
        lines.append("|------|------|------|------|------|")
        for mc in modify_cases:
            old = str(mc.get("old_value", ""))[:30]
            new = str(mc.get("new_value", ""))[:30]
            lines.append(f"| {mc.get('case_id', '?')} | {mc.get('field', '?')} | {old} | {new} | {mc.get('reason', '?')[:40]} |")
        lines.append("")
    else:
        lines.append("无修改建议。\n")

    lines.append(f"### 5.3 废弃用例（{len(deprecate_cases)}）\n")
    if deprecate_cases:
        for dc in deprecate_cases:
            lines.append(f"- **{dc.get('case_id', '?')}** — {dc.get('reason', '?')}")
        lines.append("")
    else:
        lines.append("无废弃建议。\n")

    lines.append(f"### 5.4 Spec 变更（{len(spec_changes)}）\n")
    if spec_changes:
        for sc in spec_changes:
            lines.append(f"- **{sc.get('rule_id', '?')}** ({sc.get('type', '?')})")
            lines.append(f"  - 描述: {sc.get('description', '?')}")
            lines.append(f"  - 适用: {sc.get('applies_to', '?')}")
            lines.append(f"  - 原因: {sc.get('reason', '?')}")
        lines.append("")
    else:
        lines.append("无 spec 变更。\n")

    # 6. 质量分预估变化
    lines.append("## 6. 质量分预估变化\n")
    qb = proposal.get("quality_before", {}).get("weighted_total", 0)
    qa = proposal.get("quality_after_estimated", {}).get("weighted_total", 0)
    delta = qa - qb
    arrow = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
    lines.append(f"- 优化前: {qb:.4f}")
    lines.append(f"- 优化后（预估）: {qa:.4f}")
    lines.append(f"- 变化: {arrow} {delta:+.4f}\n")

    # 7. 迭代历史
    lines.append("## 7. 迭代历史\n")
    if iterations:
        lines.append("| 时间 | proposal_id | run_id | 质量分(前→后) | 新增/修改/废弃 |")
        lines.append("|------|------------|--------|--------------|---------------|")
        for it in iterations[-5:]:  # 最近5条
            qb = it.get("quality_before", {}).get("weighted_total", 0)
            qa = it.get("quality_after_estimated", {}).get("weighted_total", 0)
            summary = it.get("apply_summary", {}).get("counts", {})
            counts = f"{summary.get('added', 0)}/{summary.get('modified', 0)}/{summary.get('deprecated', 0)}"
            lines.append(f"| {it.get('timestamp', '?')[:19]} | {it.get('proposal_id', '?')} | {it.get('run_id', '?')} | {qb:.3f}→{qa:.3f} | {counts} |")
        lines.append("")
    else:
        lines.append("无历史迭代记录。\n")

    lines.append("---")
    lines.append("*本报告由 agent-eval-v1.1 case_iteration_report.py 自动生成。*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML 报告（深色玻璃态 + 渐变 + 微动效，与 report_portal.py 设计语言一致）
# ---------------------------------------------------------------------------

HTML_STYLE = """
<style>
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    max-width: 1240px; margin: 0 auto; padding: 24px;
    color: #f1f5f9;
    background: #0f172a;
    background-image:
      radial-gradient(at 20% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%),
      radial-gradient(at 80% 100%, rgba(139, 92, 246, 0.06) 0px, transparent 50%);
    background-attachment: fixed;
    line-height: 1.6; font-size: 14px;
  }
  h1 {
    font-size: 28px; font-weight: 700;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px; letter-spacing: -0.5px;
  }
  h2 {
    color: #f1f5f9; margin-top: 36px;
    border-left: 4px solid; border-image: linear-gradient(180deg, #6366f1, #8b5cf6) 1;
    padding-left: 14px; font-size: 19px; font-weight: 700;
    display: flex; align-items: center; gap: 8px;
  }
  h3 { color: #cbd5e1; font-size: 15px; margin: 16px 0 10px; font-weight: 600; }
  .summary {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    padding: 18px 22px; border-radius: 12px; margin: 16px 0 24px;
    border: 1px solid rgba(99, 102, 241, 0.18);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }
  .summary p { color: #cbd5e1; font-size: 13px; margin: 4px 0; }
  .summary code, code {
    background: rgba(15, 23, 42, 0.6); padding: 2px 7px;
    border-radius: 4px; font-size: 0.88em; color: #c7d2fe;
    font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
  }
  strong { color: #f1f5f9; font-weight: 600; }
  .metric-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 14px; margin: 20px 0;
  }
  .metric-card {
    background: rgba(30, 41, 59, 0.7);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    padding: 18px 20px; border-radius: 12px; text-align: center;
    border: 1px solid rgba(99, 102, 241, 0.15);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative; overflow: hidden;
  }
  .metric-card::before {
    content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
    background: linear-gradient(180deg, #6366f1, #8b5cf6);
    opacity: 0.4; transition: all 0.2s;
  }
  .metric-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 12px 32px rgba(99, 102, 241, 0.25);
    border-color: rgba(99, 102, 241, 0.45);
  }
  .metric-card:hover::before { opacity: 1; width: 4px; }
  .metric-value {
    font-size: 30px; font-weight: 700;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    font-variant-numeric: tabular-nums;
  }
  .metric-value.success {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .metric-value.danger {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .metric-label { font-size: 11px; color: #64748b; margin-top: 4px;
    text-transform: uppercase; letter-spacing: 0.5px; }
  table {
    border-collapse: collapse; width: 100%; margin: 12px 0;
    background: rgba(30, 41, 59, 0.6);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border-radius: 10px; overflow: hidden;
    border: 1px solid rgba(99, 102, 241, 0.15);
  }
  th {
    background: rgba(15, 23, 42, 0.6); color: #94a3b8;
    padding: 10px 12px; text-align: left; font-weight: 600;
    font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
  }
  td { padding: 10px 12px; border-bottom: 1px solid rgba(99, 102, 241, 0.1);
    color: #cbd5e1; font-size: 13px; }
  tbody tr { transition: all 0.15s; }
  tbody tr:hover {
    background: rgba(99, 102, 241, 0.08);
    box-shadow: inset 2px 0 0 #6366f1;
  }
  tbody tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.3px; }
  .badge-red { background: rgba(239, 68, 68, 0.15); color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3); }
  .badge-yellow { background: rgba(251, 191, 36, 0.15); color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3); }
  .badge-green { background: rgba(34, 197, 94, 0.15); color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3); }
  .badge-violet { background: rgba(139, 92, 246, 0.15); color: #8b5cf6;
    border: 1px solid rgba(139, 92, 246, 0.3); }
  .delta-up { color: #22c55e; font-weight: 600; font-size: 14px; }
  .delta-down { color: #ef4444; font-weight: 600; font-size: 14px; }
  .delta-neutral { color: #94a3b8; font-weight: 600; font-size: 14px; }
  .chart-section {
    background: rgba(30, 41, 59, 0.6);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 12px; padding: 20px 24px; margin: 16px 0;
  }
  .chart-title { font-size: 13px; color: #cbd5e1; font-weight: 600; margin-bottom: 12px; }
  .chart-hint { font-size: 11px; color: #64748b; margin-top: 8px; text-align: center; }
  .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 820px) { .two-col { grid-template-columns: 1fr; } }
  .footer {
    margin-top: 40px; padding-top: 16px;
    border-top: 1px solid rgba(99, 102, 241, 0.15);
    color: #64748b; font-size: 12px; text-align: center;
  }
  .stat-row {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: 10px; margin: 10px 0;
  }
  .stat-cell {
    background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(99, 102, 241, 0.15);
    border-radius: 8px; padding: 8px 10px; text-align: center;
    transition: all 0.2s;
  }
  .stat-cell:hover { transform: translateY(-2px); border-color: rgba(99, 102, 241, 0.4); }
  .stat-cell .lbl { font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px; }
  .stat-cell .val { font-size: 18px; font-weight: 700; color: #f1f5f9; margin-top: 2px; }
  .stat-cell .val.up { color: #22c55e; }
  .stat-cell .val.down { color: #ef4444; }
</style>
"""


# ---------------------------------------------------------------------------
# SVG 图表片段
# ---------------------------------------------------------------------------

def _svg_quality_compare(qb: float, qa: float, dims_before: dict | None = None,
                         dims_after: dict | None = None) -> str:
    """质量分前后对比柱状图。

    若提供 dims_before/dims_after（12 维明细），同时渲染每维对比；
    否则只渲染总分对比。
    """
    width = 540
    pad_l, pad_r, pad_t, pad_b = 60, 30, 30, 50
    if dims_before and dims_after:
        keys = list(dims_before.keys())
        n = len(keys)
        bar_w = 14
        gap_dim = 28
        chart_w = n * gap_dim
        width = pad_l + chart_w + pad_r
        height = 280
        chart_h = height - pad_t - pad_b
        max_v = 1.0
        # 网格
        grid = ""
        for i in range(5):
            v = i * 0.25
            y = pad_t + chart_h - v * chart_h
            grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="rgba(99,102,241,0.08)" stroke-width="1"/>'
            grid += f'<text x="{pad_l - 8}" y="{y + 3:.1f}" text-anchor="end" font-size="9" fill="#64748b">{v:.2f}</text>'
        # 柱
        bars = ""
        labels = ""
        for i, k in enumerate(keys):
            x = pad_l + i * gap_dim + (gap_dim - bar_w * 2 - 2) / 2
            vb = (dims_before[k].get("score", 0) or 0)
            va = (dims_after.get(k, {}).get("score", 0) or 0)
            hb = vb * chart_h
            ha = va * chart_h
            yb = pad_t + chart_h - hb
            ya = pad_t + chart_h - ha
            bars += (f'<rect x="{x:.1f}" y="{yb:.1f}" width="{bar_w}" height="{hb:.1f}" '
                     f'fill="#6366f1" rx="2" style="transition:all .3s" opacity="0.85">'
                     f'<title>前: {k} = {vb:.3f}</title></rect>')
            bars += (f'<rect x="{x + bar_w + 2:.1f}" y="{ya:.1f}" width="{bar_w}" height="{ha:.1f}" '
                     f'fill="#22c55e" rx="2" style="transition:all .3s" opacity="0.85">'
                     f'<title>后: {k} = {va:.3f}</title></rect>')
            short_name = (dims_before[k].get("name", k))[:6]
            labels += f'<text x="{x + bar_w + 1:.1f}" y="{height - pad_b + 14}" text-anchor="middle" font-size="9" fill="#64748b" transform="rotate(-25 {x + bar_w + 1:.1f},{height - pad_b + 14})">{_h(short_name)}</text>'
        # 图例
        legend = f"""
<rect x="{pad_l}" y="6" width="10" height="10" fill="#6366f1" rx="2"/>
<text x="{pad_l + 14}" y="14" font-size="10" fill="#cbd5e1">优化前</text>
<rect x="{pad_l + 60}" y="6" width="10" height="10" fill="#22c55e" rx="2"/>
<text x="{pad_l + 74}" y="14" font-size="10" fill="#cbd5e1">优化后</text>"""
        return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%;">
  {legend}
  {grid}
  <line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{width - pad_r}" y2="{pad_t + chart_h}" stroke="rgba(99,102,241,0.3)" stroke-width="1"/>
  {bars}
  {labels}
</svg>"""
    # 仅总分对比
    height = 200
    chart_h = height - pad_t - pad_b
    bar_w = 60
    gap = 80
    width = pad_l + 2 * (bar_w + gap) + pad_r
    bars = ""
    for i, (label, v, color) in enumerate([("优化前", qb, "#6366f1"), ("优化后(预估)", qa, "#22c55e")]):
        x = pad_l + i * (bar_w + gap)
        h = v * chart_h
        y = pad_t + chart_h - h
        bars += (f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{h:.1f}" '
                 f'fill="{color}" rx="4" style="transition:all .3s">'
                 f'<title>{label}: {v:.3f}</title></rect>')
        bars += f'<text x="{x + bar_w / 2}" y="{y - 6:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="{color}">{v:.3f}</text>'
        bars += f'<text x="{x + bar_w / 2}" y="{pad_t + chart_h + 16}" text-anchor="middle" font-size="11" fill="#94a3b8">{label}</text>'
    delta = qa - qb
    delta_color = "#22c55e" if delta >= 0 else "#ef4444"
    delta_str = f"+{delta:.3f}" if delta >= 0 else f"{delta:.3f}"
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%;">
  <line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{width - pad_r}" y2="{pad_t + chart_h}" stroke="rgba(99,102,241,0.3)"/>
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="rgba(99,102,241,0.15)"/>
  {bars}
  <text x="{width - pad_r}" y="20" text-anchor="end" font-size="13" font-weight="700" fill="{delta_color}">Δ {delta_str}</text>
</svg>"""


def _svg_pareto(by_ft: dict[str, dict]) -> str:
    """错误分布 Pareto 图：按数量降序 + 累计百分比折线。"""
    if not by_ft:
        return '<div style="text-align:center;color:#64748b;font-size:12px;padding:20px;">无诊断数据</div>'
    items = sorted(by_ft.items(), key=lambda x: x[1].get("count", 0), reverse=True)
    total = sum(d.get("count", 0) for _, d in items) or 1
    width = 600
    height = 240
    pad_l, pad_r, pad_t, pad_b = 60, 50, 30, 50
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b
    max_count = max(d.get("count", 0) for _, d in items) or 1
    n = len(items)
    bar_w = chart_w / n * 0.7
    gap = chart_w / n
    # 网格
    grid = ""
    for i in range(5):
        v = i * max_count / 4
        y = pad_t + chart_h - (v / max_count) * chart_h
        grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" stroke="rgba(99,102,241,0.08)"/>'
        grid += f'<text x="{pad_l - 6}" y="{y + 3:.1f}" text-anchor="end" font-size="9" fill="#64748b">{int(v)}</text>'
    # 累计%
    cum = 0
    cum_pts = []
    bars = ""
    labels = ""
    for i, (ft, d) in enumerate(items):
        cnt = d.get("count", 0)
        ratio = d.get("ratio", 0)
        cum += cnt
        cum_pct = cum / total * 100
        x = pad_l + i * gap + (gap - bar_w) / 2
        h = (cnt / max_count) * chart_h
        y = pad_t + chart_h - h
        concentrated = d.get("concentrated", False)
        color = "#ef4444" if concentrated else "#6366f1"
        bars += (f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                 f'fill="{color}" rx="3" opacity="0.85" style="transition:all .2s">'
                 f'<title>{ft} | 数量: {cnt} | 占比: {ratio:.1%} | 累计: {cum_pct:.1f}% | {"集中" if concentrated else "正常"}</title></rect>')
        labels += (f'<text x="{x + bar_w / 2:.1f}" y="{height - pad_b + 14}" text-anchor="middle" '
                   f'font-size="10" fill="#94a3b8" transform="rotate(-20 {x + bar_w / 2:.1f},{height - pad_b + 14})">{_h(ft)}</text>')
        cum_x = x + bar_w / 2
        cum_y = pad_t + chart_h - (cum_pct / 100) * chart_h
        cum_pts.append((cum_x, cum_y))
    # 累计折线
    line_path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in cum_pts)
    cum_dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#fbbf24" '
        f'onmouseenter="this.setAttribute(\'r\',5)" onmouseleave="this.setAttribute(\'r\',3.5)">'
        f'<title>累计 {i+1}/{n}: {((i+1)/n*100):.0f}% 项 / {sum(items[j][1].get("count",0) for j in range(i+1))} 条</title></circle>'
        for i, (x, y) in enumerate(cum_pts)
    )
    # 右侧 %
    for i in range(6):
        v = i * 20
        y = pad_t + chart_h - (v / 100) * chart_h
        grid += f'<text x="{width - pad_r + 6}" y="{y + 3:.1f}" font-size="9" fill="#64748b">{v}%</text>'
    grid += f'<line x1="{width - pad_r}" y1="{pad_t}" x2="{width - pad_r}" y2="{pad_t + chart_h}" stroke="rgba(251,191,36,0.3)" stroke-dasharray="3,3"/>'
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%;">
  {grid}
  <line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{width - pad_r}" y2="{pad_t + chart_h}" stroke="rgba(99,102,241,0.3)"/>
  {bars}
  <path d="{line_path}" fill="none" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
  {cum_dots}
  {labels}
</svg>"""


def _svg_mutation_heatmap(survived: list[dict], total_killed: int,
                          total_survived: int) -> str:
    """Mutation kill matrix 热力图：行=case_id，列=mutation 类型，cell=是否 killed。"""
    if not survived:
        return ('<div style="text-align:center;padding:30px;color:#22c55e;font-size:13px;">'
                '✅ 所有变异均被检出，无 survived 项</div>')
    # 收集 case_id 与 mutation 类型
    case_ids = sorted({s.get("case_id", "?") for s in survived})
    mut_types = sorted({s.get("mutation", "?") for s in survived})
    n_c = len(case_ids)
    n_m = len(mut_types)
    cell = 38
    pad_l, pad_t = 140, 60
    width = pad_l + n_m * cell + 30
    height = pad_t + n_c * cell + 30
    # 头部
    headers = ""
    for j, m in enumerate(mut_types):
        x = pad_l + j * cell + cell / 2
        headers += (f'<text x="{x:.1f}" y="{pad_t - 14}" text-anchor="middle" font-size="10" '
                    f'fill="#cbd5e1" transform="rotate(-30 {x:.1f},{pad_t - 14})">{_h(m[:14])}</text>')
    rows = ""
    for i, cid in enumerate(case_ids):
        y = pad_t + i * cell + cell / 2
        rows += f'<text x="{pad_l - 8}" y="{y + 3:.1f}" text-anchor="end" font-size="10" fill="#cbd5e1" font-family="monospace">{_h(cid[:18])}</text>'
        for j, m in enumerate(mut_types):
            x = pad_l + j * cell
            survived_match = next((s for s in survived
                                  if s.get("case_id") == cid and s.get("mutation") == m), None)
            if survived_match:
                # 红色：未检出
                sev = "高" if survived_match.get("target_failure_type", "").startswith("F8") else "中"
                rows += (f'<rect x="{x + 1}" y="{pad_t + i * cell + 1}" width="{cell - 2}" height="{cell - 2}" '
                         f'fill="rgba(239,68,68,0.7)" stroke="rgba(239,68,68,0.9)" rx="4" '
                         f'style="transition:all .2s">'
                         f'<title>{cid} × {m}\n目标: {survived_match.get("target_failure_type", "?")}\n原因: {survived_match.get("reason", "")}</title></rect>')
                rows += f'<text x="{x + cell / 2:.1f}" y="{y + 3:.1f}" text-anchor="middle" font-size="11" fill="white" font-weight="600">S</text>'
            else:
                # 绿色：已检出
                rows += (f'<rect x="{x + 1}" y="{pad_t + i * cell + 1}" width="{cell - 2}" height="{cell - 2}" '
                         f'fill="rgba(34,197,94,0.5)" stroke="rgba(34,197,94,0.7)" rx="4" '
                         f'style="transition:all .2s" opacity="0.5">'
                         f'<title>{cid} × {m} — 已检出</title></rect>')
                rows += f'<text x="{x + cell / 2:.1f}" y="{y + 3:.1f}" text-anchor="middle" font-size="11" fill="#cbd5e1">K</text>'
    # 图例
    legend = f"""
<rect x="{pad_l}" y="{height - 14}" width="14" height="14" fill="rgba(239,68,68,0.7)" rx="3"/>
<text x="{pad_l + 18}" y="{height - 3}" font-size="10" fill="#cbd5e1">S = Survived (未检出，需增强)</text>
<rect x="{pad_l + 240}" y="{height - 14}" width="14" height="14" fill="rgba(34,197,94,0.5)" rx="3"/>
<text x="{pad_l + 258}" y="{height - 3}" font-size="10" fill="#cbd5e1">K = Killed (已检出)</text>"""
    return f"""
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%;">
  {headers}
  {rows}
  {legend}
</svg>"""


def render_html(proposal: dict, iterations: list[dict]) -> str:
    pid = proposal.get("proposal_id", "?")
    run_id = proposal.get("run_id", "?")
    split = proposal.get("split", "?")
    analysis = proposal.get("analysis", {})
    ed = analysis.get("error_distribution", {})
    mk = analysis.get("mutation_kills", {})
    qb = proposal.get("quality_before", {}).get("weighted_total", 0)
    qa = proposal.get("quality_after_estimated", {}).get("weighted_total", 0)
    delta = qa - qb

    html: list[str] = []
    html.append("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>")
    html.append(f"<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    html.append(f"<title>用例自优化迭代报告 — {_h(pid)}</title>")
    html.append(HTML_STYLE)
    html.append("</head><body>")

    html.append(f"<h1>🔬 用例自优化迭代报告</h1>")
    html.append(f"<div class='summary'>")
    html.append(f"<p><strong>proposal_id</strong>: <code>{_h(pid)}</code> &nbsp;|&nbsp; ")
    html.append(f"<strong>run_id</strong>: <code>{_h(run_id)}</code> &nbsp;|&nbsp; ")
    html.append(f"<strong>split</strong>: {_h(split)} &nbsp;|&nbsp; ")
    html.append(f"<strong>触发</strong>: {_h(proposal.get('trigger', '?'))}</p>")
    html.append(f"<p>{_h(proposal.get('summary', ''))}</p>")
    html.append("</div>")

    # 指标卡片
    kill_rate = mk.get("kill_rate", 0)
    kill_cls = "success" if kill_rate >= 0.7 else ("danger" if kill_rate < 0.4 else "")
    delta_cls = "success" if delta > 0 else ("danger" if delta < 0 else "")
    html.append("<div class='metric-grid'>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{ed.get('total_diagnoses', 0)}</div><div class='metric-label'>诊断总数</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value danger'>{len(ed.get('concentrated_types', []))}</div><div class='metric-label'>集中失败类型</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value danger'>{len(analysis.get('spec_gaps', []))}</div><div class='metric-label'>Spec 缺口</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{qb:.3f}</div><div class='metric-label'>质量分(前)</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value {delta_cls}'>{qa:.3f}</div><div class='metric-label'>质量分(后预估)</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value {kill_cls}'>{kill_rate:.0%}</div><div class='metric-label'>Mutation 检出率</div></div>")
    html.append("</div>")

    # 错误分布 + Pareto
    html.append("<h2>1. 错误分布分析</h2>")
    by_ft = ed.get("by_failure_type", {})
    pareto_svg = _svg_pareto(by_ft)
    html.append(f"<div class='chart-section'>")
    html.append(f"<div class='chart-title'>Pareto 图（按数量降序 + 累计百分比折线，hover 柱/点查看详情）</div>")
    html.append(f"<div style='display:flex;justify-content:center;overflow-x:auto;'>{pareto_svg}</div>")
    html.append(f"<div class='chart-hint'>红色柱=集中失败，蓝色柱=正常；黄线=累计占比</div>")
    html.append("</div>")
    if by_ft:
        html.append("<table><thead><tr><th>失败类型</th><th>数量</th><th>占比</th><th>集中</th></tr></thead><tbody>")
        for ft, d in sorted(by_ft.items(), key=lambda x: x[1].get("count", 0), reverse=True):
            badge = "<span class='badge badge-red'>⚠️ 集中</span>" if d.get("concentrated") else "<span class='badge badge-green'>正常</span>"
            html.append(f"<tr><td><code>{_h(ft)}</code></td><td>{d.get('count', 0)}</td><td>{d.get('ratio', 0):.1%}</td><td>{badge}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p style='color:#64748b;'>无诊断记录。</p>")

    # spec 缺口
    html.append("<h2>2. Spec 缺口</h2>")
    gaps = analysis.get("spec_gaps", [])
    if gaps:
        html.append("<table><thead><tr><th>类型</th><th>描述</th><th>严重度</th></tr></thead><tbody>")
        for g in gaps:
            sev = g.get("severity", "?")
            badge = f"<span class='badge badge-red'>{_h(sev)}</span>" if sev == "high" else (f"<span class='badge badge-yellow'>{_h(sev)}</span>" if sev == "medium" else f"<span class='badge badge-green'>{_h(sev)}</span>")
            html.append(f"<tr><td>{_h(g.get('type', '?'))}</td><td>{_h(g.get('reason', ''))}</td><td>{badge}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p style='color:#22c55e;'>✅ 无 spec 缺口。</p>")

    # 质量分 + 前后对比柱状图
    html.append("<h2>3. 用例质量评分（12 维）</h2>")
    qs_before = analysis.get("quality_scores", {})
    qs_after = proposal.get("quality_after_estimated", {}).get("dimensions")
    # 如果 proposal 提供 after 维度详情，渲染 12 维对比；否则只渲染总分对比
    if qs_after and isinstance(qs_after, dict):
        compare_svg = _svg_quality_compare(qb, qa, qs_before, qs_after)
    else:
        compare_svg = _svg_quality_compare(qb, qa)
    html.append(f"<div class='chart-section'>")
    html.append(f"<div class='chart-title'>质量分前后对比（hover 柱查看具体维度得分）</div>")
    html.append(f"<div style='display:flex;justify-content:center;overflow-x:auto;'>{compare_svg}</div>")
    html.append(f"<div class='chart-hint'>前(蓝) → 后(绿)，绿色增量代表质量提升</div>")
    html.append("</div>")

    low_dims = analysis.get("quality_low_score_dimensions", [])
    delta_arrow = "📈" if delta > 0 else ("📉" if delta < 0 else "➡️")
    delta_cls_text = "delta-up" if delta > 0 else ("delta-down" if delta < 0 else "delta-neutral")
    html.append(f"<p style='font-size:14px;margin:12px 0;'><strong>加权总分</strong>: {qb:.4f} "
                f"<span class='{delta_cls_text}'>{delta_arrow} {delta:+.4f} → {qa:.4f}</span></p>")
    if low_dims:
        html.append(f"<p style='color:#ef4444;font-size:13px;'>低分维度: {', '.join(f'<code>{_h(d)}</code>' for d in low_dims)}</p>")
    if qs_before:
        html.append("<table><thead><tr><th>维度</th><th>名称</th><th>权重</th><th>得分</th><th>状态</th></tr></thead><tbody>")
        for dim_id, d in sorted(qs_before.items(), key=lambda x: x[1].get("score", 1)):
            score = d.get("score", 0)
            if score >= 0.8:
                badge = "<span class='badge badge-green'>良好</span>"
            elif score >= 0.6:
                badge = "<span class='badge badge-yellow'>一般</span>"
            else:
                badge = "<span class='badge badge-red'>低分</span>"
            agent_tag = ' <span class="badge badge-violet" style="font-size:9px;padding:1px 6px;">agent</span>' if d.get("agent_specific") else ''
            html.append(f"<tr><td><code>{_h(dim_id)}</code></td><td>{_h(d.get('name', ''))}{agent_tag}</td><td>{d.get('weight', 0):.2f}</td><td>{score:.3f}</td><td>{badge}</td></tr>")
        html.append("</tbody></table>")

    # mutation + 热力图
    html.append("<h2>4. Mutation Kill Matrix</h2>")
    total_mut = mk.get("total_mutations", 0)
    killed = mk.get("killed", 0)
    survived_n = mk.get("survived", 0)
    survived_list = mk.get("survived_mutations", [])
    heatmap_svg = _svg_mutation_heatmap(survived_list, killed, survived_n)
    html.append(f"<div class='chart-section'>")
    html.append(f"<div class='chart-title'>Kill Matrix 热力图（行=用例，列=变异类型；hover 单元格查看详情）</div>")
    html.append(f"<div style='display:flex;justify-content:center;overflow-x:auto;'>{heatmap_svg}</div>")
    html.append("</div>")
    html.append(f"<div class='stat-row'>")
    html.append(f"<div class='stat-cell'><div class='lbl'>变异总数</div><div class='val'>{total_mut}</div></div>")
    html.append(f"<div class='stat-cell'><div class='lbl'>Killed</div><div class='val up'>{killed}</div></div>")
    html.append(f"<div class='stat-cell'><div class='lbl'>Survived</div><div class='val down'>{survived_n}</div></div>")
    html.append(f"<div class='stat-cell'><div class='lbl'>检出率</div><div class='val'>{kill_rate:.1%}</div></div>")
    html.append("</div>")
    if survived_list:
        html.append("<table><thead><tr><th>用例</th><th>变异</th><th>目标失败</th><th>原因</th></tr></thead><tbody>")
        for sm in survived_list:
            html.append(f"<tr><td><code>{_h(sm.get('case_id', '?'))}</code></td><td>{_h(sm.get('mutation', '?'))}</td><td>{_h(sm.get('target_failure_type', '?'))}</td><td>{_h(sm.get('reason', ''))}</td></tr>")
        html.append("</tbody></table>")

    # 优化建议
    html.append("<h2>5. 优化建议</h2>")
    add_cases = proposal.get("add_cases", [])
    modify_cases = proposal.get("modify_cases", [])
    deprecate_cases = proposal.get("deprecate_cases", [])
    spec_changes = proposal.get("spec_changes", [])

    html.append(f"<h3>5.1 新增用例（{len(add_cases)}）</h3>")
    if add_cases:
        html.append("<table><thead><tr><th>ID</th><th>名称</th><th>原因</th><th>触发失败</th><th>类别</th></tr></thead><tbody>")
        for ac in add_cases:
            c = ac.get("case", {})
            html.append(f"<tr><td><code>{_h(ac.get('suggested_id', c.get('id', '?')))}</code></td><td>{_h(c.get('name', '?'))}</td><td>{_h(ac.get('reason', '?'))}</td><td><span class='badge badge-red'>{_h(ac.get('trigger_failure_type', '?'))}</span></td><td>{_h(c.get('category', '?'))}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p style='color:#64748b;'>无新增建议。</p>")

    html.append(f"<h3>5.2 修改用例（{len(modify_cases)}）</h3>")
    if modify_cases:
        html.append("<table><thead><tr><th>用例</th><th>字段</th><th>原值</th><th>新值</th><th>原因</th></tr></thead><tbody>")
        for mc in modify_cases:
            old = str(mc.get("old_value", ""))[:40]
            new = str(mc.get("new_value", ""))[:40]
            html.append(f"<tr><td><code>{_h(mc.get('case_id', '?'))}</code></td><td>{_h(mc.get('field', '?'))}</td><td><code>{_h(old)}</code></td><td><code>{_h(new)}</code></td><td>{_h(mc.get('reason', '?')[:50])}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p style='color:#64748b;'>无修改建议。</p>")

    html.append(f"<h3>5.3 废弃用例（{len(deprecate_cases)}）</h3>")
    if deprecate_cases:
        html.append("<table><thead><tr><th>用例</th><th>原因</th></tr></thead><tbody>")
        for dc in deprecate_cases:
            html.append(f"<tr><td><code>{_h(dc.get('case_id', '?'))}</code></td><td>{_h(dc.get('reason', '?'))}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p style='color:#64748b;'>无废弃建议。</p>")

    html.append(f"<h3>5.4 Spec 变更（{len(spec_changes)}）</h3>")
    if spec_changes:
        html.append("<table><thead><tr><th>规则ID</th><th>类型</th><th>描述</th><th>原因</th></tr></thead><tbody>")
        for sc in spec_changes:
            html.append(f"<tr><td><code>{_h(sc.get('rule_id', '?'))}</code></td><td><span class='badge badge-violet'>{_h(sc.get('type', '?'))}</span></td><td>{_h(sc.get('description', '?'))}</td><td>{_h(sc.get('reason', '?'))}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p style='color:#64748b;'>无 spec 变更。</p>")

    # 迭代历史
    html.append("<h2>6. 迭代历史</h2>")
    if iterations:
        html.append("<table><thead><tr><th>时间</th><th>proposal_id</th><th>run_id</th><th>质量分(前→后)</th><th>新增/修改/废弃</th></tr></thead><tbody>")
        for it in iterations[-5:]:
            it_qb = it.get("quality_before", {}).get("weighted_total", 0)
            it_qa = it.get("quality_after_estimated", {}).get("weighted_total", 0)
            summary = it.get("apply_summary", {}).get("counts", {})
            counts = f"{summary.get('added', 0)}/{summary.get('modified', 0)}/{summary.get('deprecated', 0)}"
            it_delta = it_qa - it_qb
            it_cls = "up" if it_delta > 0 else ("down" if it_delta < 0 else "")
            html.append(f"<tr><td>{_h(it.get('timestamp', '?')[:19])}</td><td><code>{_h(it.get('proposal_id', '?'))}</code></td><td><code>{_h(it.get('run_id', '?'))}</code></td><td><span class='{it_cls}' style='font-weight:600;'>{it_qb:.3f} → {it_qa:.3f}</span></td><td>{counts}</td></tr>")
        html.append("</tbody></table>")
    else:
        html.append("<p style='color:#64748b;'>无历史迭代记录。</p>")

    html.append("<div class='footer'>本报告由 agent-eval-v1.1.1 case_iteration_report.py 自动生成 · 深色玻璃态可视化</div>")
    html.append("</body></html>")
    return "\n".join(html)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="用例自优化迭代报告 MD + HTML")
    ap.add_argument("--config", required=True)
    ap.add_argument("--proposal", help="proposal_id")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--out-dir", help="输出目录（默认 reports/）")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())

    proposal_id = args.proposal
    if args.latest or not proposal_id:
        proposal_id = find_latest_proposal(cfg)
        if not proposal_id:
            sys.stderr.write("[case_iteration_report] 无 proposal，请先运行 case_optimizer.py\n")
            return 2
        print(f"[case_iteration_report] latest proposal_id={proposal_id}")

    proposal = load_proposal(cfg, proposal_id)
    iterations = CIO.load_iterations(cfg)

    out_dir = Path(args.out_dir) if args.out_dir else cfg.reports_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # MD
    md = render_md(proposal, iterations)
    md_path = out_dir / f"case_iteration_{proposal_id}.md"
    md_path.write_text(md, encoding="utf-8")

    # HTML
    html = render_html(proposal, iterations)
    html_path = out_dir / f"case_iteration_{proposal_id}.html"
    html_path.write_text(html, encoding="utf-8")

    print(f"[case_iteration_report] MD: {md_path}")
    print(f"[case_iteration_report] HTML: {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
