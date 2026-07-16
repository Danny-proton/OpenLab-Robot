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
# HTML 报告
# ---------------------------------------------------------------------------

HTML_STYLE = """
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 1100px; margin: 0 auto; padding: 24px; color: #1f2937; background: #f9fafb; }
  h1 { color: #111827; border-bottom: 3px solid #6366f1; padding-bottom: 8px; }
  h2 { color: #374151; margin-top: 32px; border-left: 4px solid #6366f1; padding-left: 12px; }
  h3 { color: #4b5563; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  th { background: #6366f1; color: white; padding: 10px 12px; text-align: left; font-weight: 600; }
  td { padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }
  tr:hover { background: #f3f4f6; }
  .metric-card { display: inline-block; background: white; padding: 16px 24px; margin: 8px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; min-width: 140px; }
  .metric-value { font-size: 28px; font-weight: 700; color: #6366f1; }
  .metric-label { font-size: 12px; color: #6b7280; margin-top: 4px; }
  .summary { background: #eef2ff; padding: 16px; border-radius: 8px; margin: 16px 0; border-left: 4px solid #6366f1; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .badge-red { background: #fee2e2; color: #991b1b; }
  .badge-yellow { background: #fef3c7; color: #92400e; }
  .badge-green { background: #d1fae5; color: #065f46; }
  .delta-up { color: #059669; font-weight: 600; }
  .delta-down { color: #dc2626; font-weight: 600; }
  code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
  .footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px; text-align: center; }
</style>
"""


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
    html.append(f"<title>用例自优化迭代报告 — {pid}</title>")
    html.append(HTML_STYLE)
    html.append("</head><body>")

    html.append(f"<h1>🔬 用例自优化迭代报告</h1>")
    html.append(f"<div class='summary'>")
    html.append(f"<p><strong>proposal_id</strong>: <code>{pid}</code> | ")
    html.append(f"<strong>run_id</strong>: <code>{run_id}</code> | ")
    html.append(f"<strong>split</strong>: {split} | ")
    html.append(f"<strong>触发</strong>: {proposal.get('trigger', '?')}</p>")
    html.append(f"<p>{proposal.get('summary', '')}</p>")
    html.append("</div>")

    # 指标卡片
    html.append("<div>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{ed.get('total_diagnoses', 0)}</div><div class='metric-label'>诊断总数</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{len(ed.get('concentrated_types', []))}</div><div class='metric-label'>集中失败类型</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{len(analysis.get('spec_gaps', []))}</div><div class='metric-label'>Spec 缺口</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{qb:.3f}</div><div class='metric-label'>质量分(前)</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{qa:.3f}</div><div class='metric-label'>质量分(后)</div></div>")
    html.append(f"<div class='metric-card'><div class='metric-value'>{mk.get('kill_rate', 0):.0%}</div><div class='metric-label'>Mutation 检出率</div></div>")
    html.append("</div>")

    # 错误分布
    html.append("<h2>1. 错误分布分析</h2>")
    by_ft = ed.get("by_failure_type", {})
    if by_ft:
        html.append("<table><tr><th>失败类型</th><th>数量</th><th>占比</th><th>集中</th></tr>")
        for ft, d in sorted(by_ft.items()):
            badge = "<span class='badge badge-red'>⚠️ 集中</span>" if d["concentrated"] else "<span class='badge badge-green'>正常</span>"
            html.append(f"<tr><td><code>{ft}</code></td><td>{d['count']}</td><td>{d['ratio']:.1%}</td><td>{badge}</td></tr>")
        html.append("</table>")
    else:
        html.append("<p>无诊断记录。</p>")

    # spec 缺口
    html.append("<h2>2. Spec 缺口</h2>")
    gaps = analysis.get("spec_gaps", [])
    if gaps:
        html.append("<table><tr><th>类型</th><th>描述</th><th>严重度</th></tr>")
        for g in gaps:
            sev = g.get("severity", "?")
            badge = f"<span class='badge badge-red'>{sev}</span>" if sev == "high" else (f"<span class='badge badge-yellow'>{sev}</span>" if sev == "medium" else f"<span class='badge badge-green'>{sev}</span>")
            html.append(f"<tr><td>{g.get('type', '?')}</td><td>{g.get('reason', '')}</td><td>{badge}</td></tr>")
        html.append("</table>")
    else:
        html.append("<p>✅ 无 spec 缺口。</p>")

    # 质量分
    html.append("<h2>3. 用例质量评分（12 维）</h2>")
    qs = analysis.get("quality_scores", {})
    low_dims = analysis.get("quality_low_score_dimensions", [])
    html.append(f"<p><strong>加权总分</strong>: {qb:.4f} ")
    if delta > 0:
        html.append(f"<span class='delta-up'>📈 +{delta:.4f} → {qa:.4f}</span>")
    elif delta < 0:
        html.append(f"<span class='delta-down'>📉 {delta:.4f} → {qa:.4f}</span>")
    html.append(f"</p>")
    if low_dims:
        html.append(f"<p>低分维度: {', '.join(f'<code>{d}</code>' for d in low_dims)}</p>")
    if qs:
        html.append("<table><tr><th>维度</th><th>名称</th><th>权重</th><th>得分</th><th>状态</th></tr>")
        for dim_id, d in qs.items():
            score = d.get("score", 0)
            if score >= 0.8:
                badge = "<span class='badge badge-green'>良好</span>"
            elif score >= 0.6:
                badge = "<span class='badge badge-yellow'>一般</span>"
            else:
                badge = "<span class='badge badge-red'>低分</span>"
            html.append(f"<tr><td><code>{dim_id}</code></td><td>{d.get('name', '')}</td><td>{d.get('weight', 0)}</td><td>{score:.3f}</td><td>{badge}</td></tr>")
        html.append("</table>")

    # mutation
    html.append("<h2>4. Mutation Kill Matrix</h2>")
    html.append(f"<p><strong>变异总数</strong>: {mk.get('total_mutations', 0)} | ")
    html.append(f"<strong>killed</strong>: {mk.get('killed', 0)} | ")
    html.append(f"<strong>survived</strong>: {mk.get('survived', 0)} | ")
    html.append(f"<strong>检出率</strong>: {mk.get('kill_rate', 0):.1%}</p>")
    survived = mk.get("survived_mutations", [])
    if survived:
        html.append("<table><tr><th>用例</th><th>变异</th><th>目标失败</th><th>原因</th></tr>")
        for sm in survived:
            html.append(f"<tr><td><code>{sm['case_id']}</code></td><td>{sm['mutation']}</td><td>{sm['target_failure_type']}</td><td>{sm['reason']}</td></tr>")
        html.append("</table>")

    # 优化建议
    html.append("<h2>5. 优化建议</h2>")
    add_cases = proposal.get("add_cases", [])
    modify_cases = proposal.get("modify_cases", [])
    deprecate_cases = proposal.get("deprecate_cases", [])
    spec_changes = proposal.get("spec_changes", [])

    html.append(f"<h3>5.1 新增用例（{len(add_cases)}）</h3>")
    if add_cases:
        html.append("<table><tr><th>ID</th><th>名称</th><th>原因</th><th>触发失败</th><th>类别</th></tr>")
        for ac in add_cases:
            c = ac.get("case", {})
            html.append(f"<tr><td><code>{ac.get('suggested_id', c.get('id', '?'))}</code></td><td>{c.get('name', '?')}</td><td>{ac.get('reason', '?')}</td><td>{ac.get('trigger_failure_type', '?')}</td><td>{c.get('category', '?')}</td></tr>")
        html.append("</table>")

    html.append(f"<h3>5.2 修改用例（{len(modify_cases)}）</h3>")
    if modify_cases:
        html.append("<table><tr><th>用例</th><th>字段</th><th>原值</th><th>新值</th><th>原因</th></tr>")
        for mc in modify_cases:
            old = str(mc.get("old_value", ""))[:40]
            new = str(mc.get("new_value", ""))[:40]
            html.append(f"<tr><td><code>{mc.get('case_id', '?')}</code></td><td>{mc.get('field', '?')}</td><td>{old}</td><td>{new}</td><td>{mc.get('reason', '?')[:50]}</td></tr>")
        html.append("</table>")

    html.append(f"<h3>5.3 废弃用例（{len(deprecate_cases)}）</h3>")
    if deprecate_cases:
        html.append("<table><tr><th>用例</th><th>原因</th></tr>")
        for dc in deprecate_cases:
            html.append(f"<tr><td><code>{dc.get('case_id', '?')}</code></td><td>{dc.get('reason', '?')}</td></tr>")
        html.append("</table>")

    html.append(f"<h3>5.4 Spec 变更（{len(spec_changes)}）</h3>")
    if spec_changes:
        html.append("<table><tr><th>规则ID</th><th>类型</th><th>描述</th><th>原因</th></tr>")
        for sc in spec_changes:
            html.append(f"<tr><td><code>{sc.get('rule_id', '?')}</code></td><td>{sc.get('type', '?')}</td><td>{sc.get('description', '?')}</td><td>{sc.get('reason', '?')}</td></tr>")
        html.append("</table>")

    # 迭代历史
    html.append("<h2>6. 迭代历史</h2>")
    if iterations:
        html.append("<table><tr><th>时间</th><th>proposal_id</th><th>run_id</th><th>质量分(前→后)</th><th>新增/修改/废弃</th></tr>")
        for it in iterations[-5:]:
            qb = it.get("quality_before", {}).get("weighted_total", 0)
            qa = it.get("quality_after_estimated", {}).get("weighted_total", 0)
            summary = it.get("apply_summary", {}).get("counts", {})
            counts = f"{summary.get('added', 0)}/{summary.get('modified', 0)}/{summary.get('deprecated', 0)}"
            html.append(f"<tr><td>{it.get('timestamp', '?')[:19]}</td><td><code>{it.get('proposal_id', '?')}</code></td><td>{it.get('run_id', '?')}</td><td>{qb:.3f}→{qa:.3f}</td><td>{counts}</td></tr>")
        html.append("</table>")
    else:
        html.append("<p>无历史迭代记录。</p>")

    html.append("<div class='footer'>本报告由 agent-eval-v1.1 case_iteration_report.py 自动生成。</div>")
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
