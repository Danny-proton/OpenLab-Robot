#!/usr/bin/env python3
"""html_report.py — 生成专业美观的单文件 HTML 评测报告。

v0.5 的核心交付之一。所有 CSS / SVG 内联，无外部依赖，可邮件分享。

用法:
  python html_report.py --config .agent-eval/config.yaml --run <run_id>
  python html_report.py --config .agent-eval/config.yaml --run <run_id> --baseline-run <baseline_id>

被 eval_runner.py / report.py 进程内调用。
"""

from __future__ import annotations

import argparse
import json
import sys
import html
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import charts as CH  # noqa: E402


# ---------------------------------------------------------------------------
# 配色与样式
# ---------------------------------------------------------------------------

# 专业蓝灰主色 + 语义色
COLORS = {
    "primary": "#2563eb",       # 蓝
    "primary_dark": "#1e40af",
    "primary_light": "#dbeafe",
    "secondary": "#64748b",     # 灰
    "success": "#16a34a",       # 绿
    "success_light": "#dcfce7",
    "warning": "#d97706",       # 橙
    "warning_light": "#fef3c7",
    "danger": "#dc2626",        # 红
    "danger_light": "#fee2e2",
    "neutral": "#f1f5f9",
    "text": "#0f172a",
    "text_muted": "#64748b",
    "border": "#e2e8f0",
    "bg": "#ffffff",
    "bg_alt": "#f8fafc",
}

# 场景通过率阈值
SCENARIO_PASS_THRESHOLD = 0.8
SCENARIO_WARN_THRESHOLD = 0.5

# SVG 图表配色（用于热力图、时间线等）
HEATMAP_COLORS = ["#fee2e2", "#fecaca", "#fde68a", "#fef3c7",
                  "#d9f99d", "#a7f3d0", "#6ee7b7", "#34d399", "#10b981"]
TIMELINE_COLORS = {
    "agent.run.start": "#2563eb",
    "agent.run.end": "#16a34a",
    "model.call.start": "#8b5cf6",
    "model.call.end": "#a78bfa",
    "tool.call.start": "#0891b2",
    "tool.call.end": "#06b6d4",
    "tool.call.error": "#dc2626",
    "memory.retrieve.start": "#d97706",
    "memory.retrieve.end": "#f59e0b",
    "planner.step": "#64748b",
    "skill.select": "#db2777",
    "skill.load": "#ec4899",
}


def _h(s) -> str:
    """HTML escape。"""
    return html.escape(str(s) if s is not None else "")


def _fmt_delta(delta) -> str:
    """安全格式化 delta 值。"""
    if delta is None:
        return "—"
    if delta > 0:
        return f"+{delta:.3f}"
    return f"{delta:.3f}"


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
               "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
  color: COLORS_TEXT;
  background: COLORS_BG_ALT;
  line-height: 1.6;
  font-size: 14px;
}
.container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }
@media print {
  @page { size: A4; margin: 15mm; }
  body { background: white !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .container { max-width: 100%; padding: 0; }
  .no-print { display: none !important; }
  .section { break-before: page; break-inside: avoid; box-shadow: none; border: 1px solid #ccc; }
  .section:first-of-type { break-before: avoid; }
  .report-header { break-after: avoid; }
  .page-break { page-break-before: always; }
  a { text-decoration: none; color: inherit; }
  .report-footer { page-break-inside: avoid; }
}

/* Header */
.report-header {
  background: linear-gradient(135deg, COLORS_PRIMARY 0%, COLORS_PRIMARY_DARK 100%);
  color: white; padding: 40px 32px; border-radius: 12px;
  margin-bottom: 32px; box-shadow: 0 4px 12px rgba(37,99,235,0.15);
}
.report-header h1 { font-size: 28px; margin-bottom: 8px; font-weight: 700; }
.report-header .subtitle { font-size: 15px; opacity: 0.9; margin-bottom: 16px; }
.report-header .meta {
  display: flex; flex-wrap: wrap; gap: 24px; font-size: 13px; opacity: 0.95;
}
.report-header .meta span { display: inline-flex; align-items: center; gap: 6px; }
.report-header .meta strong { font-weight: 600; }

/* Section */
.section { background: COLORS_BG; border-radius: 10px; padding: 28px;
           margin-bottom: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
           border: 1px solid COLORS_BORDER; }
.section h2 { font-size: 20px; color: COLORS_TEXT; margin-bottom: 4px;
              font-weight: 700; display: flex; align-items: center; gap: 8px; }
.section h2 .num {
  display: inline-block; width: 28px; height: 28px; background: COLORS_PRIMARY;
  color: white; border-radius: 50%; text-align: center; line-height: 28px;
  font-size: 14px; font-weight: 600;
}
.section h3 { font-size: 15px; color: COLORS_TEXT; margin: 20px 0 12px;
              font-weight: 600; }
.section .lead { color: COLORS_TEXT_MUTED; font-size: 13px; margin-bottom: 20px; }

/* Verdict banner */
.verdict {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px; border-radius: 8px; font-weight: 600; font-size: 15px;
  margin-bottom: 16px;
}
.verdict.accept { background: COLORS_SUCCESS_LIGHT; color: COLORS_SUCCESS;
                  border: 1px solid COLORS_SUCCESS; }
.verdict.reject { background: COLORS_DANGER_LIGHT; color: COLORS_DANGER;
                  border: 1px solid COLORS_DANGER; }
.verdict.inconclusive { background: COLORS_WARNING_LIGHT; color: COLORS_WARNING;
                        border: 1px solid COLORS_WARNING; }

/* Scorecards */
.scorecard-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px; margin-top: 16px;
}
.scorecard {
  background: COLORS_BG_ALT; border: 1px solid COLORS_BORDER;
  border-radius: 8px; padding: 16px; position: relative;
}
.scorecard .label { font-size: 12px; color: COLORS_TEXT_MUTED;
                    text-transform: uppercase; letter-spacing: 0.5px; }
.scorecard .value { font-size: 28px; font-weight: 700; color: COLORS_TEXT;
                    margin: 4px 0; }
.scorecard .delta { font-size: 13px; font-weight: 600; }
.scorecard .delta.up { color: COLORS_SUCCESS; }
.scorecard .delta.down { color: COLORS_DANGER; }
.scorecard .delta.neutral { color: COLORS_TEXT_MUTED; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid COLORS_BORDER; }
th { background: COLORS_NEUTRAL; font-weight: 600; color: COLORS_TEXT;
     font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
tr:hover { background: COLORS_BG_ALT; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
}
.badge.pass { background: COLORS_SUCCESS_LIGHT; color: COLORS_SUCCESS; }
.badge.fail { background: COLORS_DANGER_LIGHT; color: COLORS_DANGER; }
.badge.warn { background: COLORS_WARNING_LIGHT; color: COLORS_WARNING; }

/* Bar chart */
.bar-chart { margin: 16px 0; }
.bar-row { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
.bar-row .bar-label { width: 180px; font-size: 13px; color: COLORS_TEXT; }
.bar-row .bar-track {
  flex: 1; height: 24px; background: COLORS_NEUTRAL; border-radius: 4px;
  position: relative; overflow: hidden;
}
.bar-row .bar-fill {
  height: 100%; border-radius: 4px; transition: width 0.3s;
  display: flex; align-items: center; padding-left: 8px;
  color: white; font-size: 12px; font-weight: 600;
}
.bar-row .bar-value { width: 80px; font-size: 13px; font-weight: 600;
                      text-align: right; color: COLORS_TEXT; }

/* Heatmap */
.heatmap { overflow-x: auto; margin: 16px 0; }
.heatmap table { border-collapse: separate; border-spacing: 2px; }
.heatmap th, .heatmap td { padding: 6px 8px; text-align: center; font-size: 12px; }
.heatmap td.cell {
  min-width: 60px; height: 36px; border-radius: 4px;
  font-weight: 600; color: COLORS_TEXT;
}

/* Timeline */
.timeline { margin: 16px 0; }
.timeline-case {
  background: COLORS_BG_ALT; border: 1px solid COLORS_BORDER;
  border-radius: 8px; padding: 12px; margin-bottom: 12px;
}
.timeline-case .case-label { font-size: 13px; font-weight: 600;
                             margin-bottom: 8px; color: COLORS_TEXT; }
.timeline-steps {
  display: flex; align-items: center; gap: 2px; flex-wrap: wrap;
}
.timeline-step {
  min-width: 32px; height: 32px; border-radius: 4px;
  display: inline-flex; align-items: center; justify-content: center;
  color: white; font-size: 10px; font-weight: 600;
  position: relative; cursor: default;
}
.timeline-step.error { outline: 2px solid COLORS_DANGER; }
.timeline-step .tooltip {
  display: none; position: absolute; bottom: 100%; left: 50%;
  transform: translateX(-50%); background: COLORS_TEXT; color: white;
  padding: 6px 10px; border-radius: 4px; font-size: 11px; white-space: nowrap;
  z-index: 10; margin-bottom: 4px;
}
.timeline-step:hover .tooltip { display: block; }

/* Pareto */
.pareto-chart { margin: 16px 0; }

/* Recommendations */
.rec-list { list-style: none; }
.rec-item {
  background: COLORS_BG_ALT; border-left: 4px solid COLORS_PRIMARY;
  padding: 14px 18px; margin-bottom: 10px; border-radius: 0 8px 8px 0;
}
.rec-item .rec-title { font-weight: 600; color: COLORS_TEXT; margin-bottom: 4px; }
.rec-item .rec-desc { font-size: 13px; color: COLORS_TEXT_MUTED; }
.rec-item .rec-meta { font-size: 12px; color: COLORS_SECONDARY; margin-top: 6px; }
.rec-item.high { border-left-color: COLORS_DANGER; }
.rec-item.medium { border-left-color: COLORS_WARNING; }
.rec-item.low { border-left-color: COLORS_SUCCESS; }

/* Footer */
.report-footer {
  text-align: center; color: COLORS_TEXT_MUTED; font-size: 12px;
  padding: 24px; border-top: 1px solid COLORS_BORDER; margin-top: 32px;
}

/* Responsive */
@media (max-width: 768px) {
  .container { padding: 16px; }
  .report-header { padding: 24px 16px; }
  .section { padding: 16px; }
  .scorecard-grid { grid-template-columns: 1fr 1fr; }
  .bar-row .bar-label { width: 120px; }
}

/* Iteration curve */
.iteration-chart { margin: 16px 0; }

/* Tool graph */
.tool-graph { margin: 16px 0; }

/* Code blocks */
pre {
  background: COLORS_TEXT; color: #e2e8f0; padding: 14px;
  border-radius: 6px; overflow-x: auto; font-size: 12px;
  font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
}
code { font-family: "SF Mono", Monaco, "Cascadia Code", monospace;
       background: COLORS_NEUTRAL; padding: 1px 6px; border-radius: 3px;
       font-size: 12px; color: COLORS_PRIMARY_DARK; }
pre code { background: none; padding: 0; color: inherit; }
"""


def _css() -> str:
    """把 COLORS 占位符替换成实际颜色。

    按 key 长度降序替换，避免 COLORS_BG 把 COLORS_BG_ALT 部分替换掉。
    """
    css = CSS
    for k in sorted(COLORS.keys(), key=len, reverse=True):
        css = css.replace(f"COLORS_{k.upper()}", COLORS[k])
    return css


# ---------------------------------------------------------------------------
# SVG 图表生成
# ---------------------------------------------------------------------------

def svg_bar_chart(data: list[dict], value_key: str, label_key: str,
                  max_val: float = 1.0, color: str = None) -> str:
    """生成水平条形图 SVG。"""
    if not data:
        return '<p class="text-muted">暂无数据</p>'
    color = color or COLORS["primary"]
    row_height = 36
    label_width = 160
    chart_width = 500
    total_height = len(data) * (row_height + 8) + 20

    rows_svg = []
    for i, item in enumerate(data):
        y = i * (row_height + 8) + 10
        val = item.get(value_key, 0) or 0
        bar_w = max(2, (val / max_val) * chart_width) if max_val > 0 else 2
        label = _h(item.get(label_key, ""))
        rows_svg.append(f"""
        <g transform="translate(0,{y})">
          <text x="0" y="20" font-size="12" fill="{COLORS["text"]}" font-family="sans-serif">{label}</text>
          <rect x="{label_width}" y="6" width="{chart_width}" height="{row_height-12}" fill="{COLORS["neutral"]}" rx="4"/>
          <rect x="{label_width}" y="6" width="{bar_w:.1f}" height="{row_height-12}" fill="{color}" rx="4"/>
          <text x="{label_width + bar_w + 8:.1f}" y="22" font-size="12" font-weight="600" fill="{COLORS["text"]}" font-family="sans-serif">{val:.3f}</text>
        </g>""")

    return f"""
    <svg viewBox="0 0 {label_width + chart_width + 80} {total_height}" style="width:100%;max-width:{label_width + chart_width + 80}px;">
      {"".join(rows_svg)}
    </svg>
    """


def svg_scorecard_bars(scorecard: list[dict]) -> str:
    """scorecard 对比条形图：baseline vs candidate。"""
    if not scorecard:
        return '<p class="text-muted">暂无数据</p>'
    row_height = 44
    label_width = 180
    chart_width = 400
    total_height = len(scorecard) * (row_height + 6) + 20

    rows = []
    for i, item in enumerate(scorecard):
        y = i * (row_height + 6) + 10
        label = _h(item.get("label", item.get("metric", "")))
        baseline = item.get("baseline")
        candidate = item.get("candidate", 0) or 0
        # 归一化（如果是百分比用 1.0，如果是 latency 用 max）
        max_val = max(baseline or 0, candidate, 0.01)
        if "latency" in item.get("metric", "") or "token" in item.get("metric", ""):
            # 不归一化到 1，用实际值
            pass

        b_w = (baseline / max_val) * chart_width if baseline is not None else 0
        c_w = (candidate / max_val) * chart_width if candidate else 0
        delta = item.get("delta")
        delta_str = f"{'+' if delta and delta >= 0 else ''}{delta:.3f}" if delta is not None else "—"
        delta_color = COLORS["success"] if delta and delta > 0 else (COLORS["danger"] if delta and delta < 0 else COLORS["text_muted"])

        rows.append(f"""
        <g transform="translate(0,{y})">
          <text x="0" y="14" font-size="12" font-weight="600" fill="{COLORS["text"]}" font-family="sans-serif">{label}</text>
          <text x="0" y="32" font-size="11" fill="{COLORS["text_muted"]}" font-family="sans-serif">Δ {delta_str}</text>
          <rect x="{label_width}" y="6" width="{chart_width}" height="14" fill="{COLORS["neutral"]}" rx="3"/>
          <rect x="{label_width}" y="6" width="{b_w:.1f}" height="14" fill="{COLORS["secondary"]}" rx="3" opacity="0.5"/>
          <rect x="{label_width}" y="22" width="{chart_width}" height="14" fill="{COLORS["neutral"]}" rx="3"/>
          <rect x="{label_width}" y="22" width="{c_w:.1f}" height="14" fill="{COLORS["primary"]}" rx="3"/>
          <text x="{label_width + chart_width + 8}" y="18" font-size="11" fill="{COLORS["text_muted"]}" font-family="sans-serif">base: {baseline if baseline is not None else '—'}</text>
          <text x="{label_width + chart_width + 8}" y="34" font-size="11" font-weight="600" fill="{delta_color}" font-family="sans-serif">cand: {candidate}</text>
        </g>""")

    return f"""
    <svg viewBox="0 0 {label_width + chart_width + 100} {total_height}" style="width:100%;max-width:{label_width + chart_width + 100}px;">
      {"".join(rows)}
    </svg>
    """


def svg_pareto(items: list[dict]) -> str:
    """Pareto 图：柱状 + 累计折线。"""
    if not items:
        return '<p class="text-muted">暂无失败</p>'
    max_count = max(it["count"] for it in items) or 1
    chart_w = 600
    chart_h = 240
    bar_w = chart_w / len(items) * 0.7
    gap = chart_w / len(items) * 0.3
    y_scale = (chart_h - 40) / max_count

    bars = []
    points = []
    cum_pct_pts = []
    for i, item in enumerate(items):
        x = i * (bar_w + gap) + 20
        h = item["count"] * y_scale
        y = chart_h - 20 - h
        # 累计百分比折线点
        cum = item.get("cumulative_pct", 0)
        px = x + bar_w / 2
        py = chart_h - 20 - (cum / 100) * (chart_h - 40)
        points.append((px, py))

        label = _h(item["failure_type"])
        bars.append(f"""
        <rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{COLORS["primary"]}" rx="2"/>
        <text x="{x + bar_w/2:.1f}" y="{y - 6:.1f}" font-size="11" font-weight="600" text-anchor="middle" fill="{COLORS["text"]}" font-family="sans-serif">{item['count']}</text>
        <text x="{x + bar_w/2:.1f}" y="{chart_h - 4}" font-size="10" text-anchor="middle" fill="{COLORS["text_muted"]}" font-family="sans-serif" transform="rotate(-20 {x + bar_w/2} {chart_h - 4})">{label}</text>
        """)

    # 折线
    if len(points) >= 2:
        path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
        line = f'<path d="{path}" stroke="{COLORS["warning"]}" stroke-width="2" fill="none" marker-end="url(#arrow)"/>'
        dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{COLORS["warning"]}"/>'
                       for x, y in points)
    else:
        line = ""
        dots = ""

    return f"""
    <svg viewBox="0 0 {chart_w + 60} {chart_h + 20}" style="width:100%;max-width:{chart_w + 60}px;">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
          <polygon points="0 0, 8 4, 0 8" fill="{COLORS["warning"]}"/>
        </marker>
      </defs>
      <line x1="20" y1="{chart_h - 20}" x2="{chart_w + 20}" y2="{chart_h - 20}" stroke="{COLORS["border"]}" stroke-width="1"/>
      <line x1="20" y1="20" x2="20" y2="{chart_h - 20}" stroke="{COLORS["border"]}" stroke-width="1"/>
      {"".join(bars)}
      {line}
      {dots}
      <text x="10" y="15" font-size="10" fill="{COLORS["text_muted"]}" font-family="sans-serif">数量</text>
      <text x="{chart_w + 30}" y="15" font-size="10" fill="{COLORS["warning"]}" font-family="sans-serif">累计%</text>
    </svg>
    """


def svg_heatmap(heatmap_data: dict) -> str:
    """case × metric 热力图 SVG。"""
    metrics = heatmap_data.get("metrics", [])
    rows = heatmap_data.get("rows", [])
    if not rows:
        return '<p class="text-muted">暂无数据</p>'

    cell_w = 70
    cell_h = 36
    label_w = 140
    header_h = 40
    total_w = label_w + len(metrics) * cell_w + 80  # +weighted + status
    total_h = header_h + len(rows) * cell_h

    def color_for(score: float) -> str:
        if score >= 0.9: return "#10b981"
        if score >= 0.7: return "#6ee7b7"
        if score >= 0.5: return "#fde68a"
        if score >= 0.3: return "#fb923c"
        return "#f87171"

    # 表头
    headers = [f'<text x="{label_w + i * cell_w + cell_w/2}" y="20" font-size="11" font-weight="600" text-anchor="middle" fill="{COLORS["text"]}" font-family="sans-serif">{_h(m.replace("_"," ")[:12])}</text>'
               for i, m in enumerate(metrics)]
    headers.append(f'<text x="{label_w + len(metrics)*cell_w + cell_w/2}" y="20" font-size="11" font-weight="600" text-anchor="middle" fill="{COLORS["text"]}" font-family="sans-serif">总分</text>')
    headers.append(f'<text x="{label_w + (len(metrics)+1)*cell_w + cell_w/2}" y="20" font-size="11" font-weight="600" text-anchor="middle" fill="{COLORS["text"]}" font-family="sans-serif">状态</text>')

    # 行
    cells = []
    for ri, row in enumerate(rows):
        y = header_h + ri * cell_h
        cells.append(f'<text x="8" y="{y + cell_h/2 + 4}" font-size="11" fill="{COLORS["text"]}" font-family="sans-serif">{_h(row["case_id"])}</text>')
        for mi, m in enumerate(metrics):
            x = label_w + mi * cell_w
            v = row.get("scores", {}).get(m, 0)
            c = color_for(v)
            cells.append(f'<rect x="{x}" y="{y}" width="{cell_w-2}" height="{cell_h-2}" fill="{c}" rx="3"/>')
            cells.append(f'<text x="{x + cell_w/2}" y="{y + cell_h/2 + 4}" font-size="11" font-weight="600" text-anchor="middle" fill="white" font-family="sans-serif">{v:.2f}</text>')
        # weighted
        x = label_w + len(metrics) * cell_w
        w = row.get("weighted", 0)
        c = color_for(w)
        cells.append(f'<rect x="{x}" y="{y}" width="{cell_w-2}" height="{cell_h-2}" fill="{c}" rx="3"/>')
        cells.append(f'<text x="{x + cell_w/2}" y="{y + cell_h/2 + 4}" font-size="11" font-weight="600" text-anchor="middle" fill="white" font-family="sans-serif">{w:.2f}</text>')
        # status
        x2 = x + cell_w
        status = "FAIL" if row.get("is_hard_fail") else "PASS"
        sc = COLORS["danger"] if row.get("is_hard_fail") else COLORS["success"]
        cells.append(f'<rect x="{x2}" y="{y}" width="{cell_w-2}" height="{cell_h-2}" fill="{sc}" rx="3"/>')
        cells.append(f'<text x="{x2 + cell_w/2}" y="{y + cell_h/2 + 4}" font-size="11" font-weight="600" text-anchor="middle" fill="white" font-family="sans-serif">{status}</text>')

    return f"""
    <svg viewBox="0 0 {total_w} {total_h}" style="width:100%;max-width:{total_w}px;">
      {"".join(headers)}
      {"".join(cells)}
    </svg>
    """


def svg_timeline(timelines: list[dict]) -> str:
    """trace 时间线 + 调用结构详情（每 case 一条）。

    v2: 除了色块时间线，还加调用链详情表（step/event/tool/arguments/result/status/latency）
    和调用结构树（显示 parent → child span 关系）。
    """
    if not timelines:
        return '<p class="text-muted">暂无 trace</p>'

    parts = []
    for tl in timelines[:20]:
        cid = _h(tl.get("case_id", ""))
        steps = tl.get("steps", [])
        if not steps:
            continue

        # === 1. 色块时间线（总览）===
        step_size = 36
        gap = 2
        total_w = len(steps) * (step_size + gap)
        svg_steps = []
        for si, step in enumerate(steps):
            x = si * (step_size + gap)
            et = step.get("event_type", "")
            color = TIMELINE_COLORS.get(et, COLORS["secondary"])
            if step.get("status") == "error":
                color = COLORS["danger"]
            tool = step.get("tool", "")
            label = tool[:3] if tool else et.split(".")[-1][:3]
            tooltip_text = f"step {step.get('step', si+1)}: {et} {tool} ({step.get('latency_ms',0)}ms)"
            svg_steps.append(f"""
            <g>
              <rect x="{x}" y="0" width="{step_size}" height="{step_size}" fill="{color}" rx="4"/>
              <text x="{x + step_size/2}" y="{step_size/2 + 4}" font-size="10" font-weight="600" text-anchor="middle" fill="white" font-family="sans-serif">{_h(label)}</text>
              <title>{_h(tooltip_text)}</title>
            </g>""")

        # === 2. 调用链详情表 ===
        table_rows = []
        for step in steps:
            et = step.get("event_type", "")
            tool = step.get("tool", "")
            status = step.get("status", "success")
            latency = step.get("latency_ms", 0)
            args = step.get("arguments", "")
            result = step.get("result", "")
            args_str = _h(str(args)[:120] + ("..." if len(str(args)) > 120 else ""))
            result_str = _h(str(result)[:120] + ("..." if len(str(result)) > 120 else ""))
            status_badge = f'<span class="badge {"pass" if status=="success" else "fail"}">{_h(status)}</span>'
            table_rows.append(f"""
            <tr>
              <td class="num">{step.get('step', '')}</td>
              <td><code>{_h(et)}</code></td>
              <td>{_h(tool) if tool else '<span style="color:#94a3b8">—</span>'}</td>
              <td style="font-size:11px;color:#64748b;max-width:200px;overflow:hidden;text-overflow:ellipsis">{args_str}</td>
              <td style="font-size:11px;color:#64748b;max-width:200px;overflow:hidden;text-overflow:ellipsis">{result_str}</td>
              <td>{status_badge}</td>
              <td class="num">{latency}ms</td>
            </tr>""")

        # === 3. 调用结构树 ===
        tree_html = _build_call_tree(steps)

        parts.append(f"""
        <div class="timeline-case">
          <div class="case-label">{cid} <span style="color:{COLORS['text_muted']};font-weight:400;font-size:12px">({len(steps)} steps)</span></div>

          <h4 style="margin:12px 0 6px;color:{COLORS['text']};font-size:13px">📊 执行时间线</h4>
          <svg viewBox="0 0 {total_w} {step_size}" style="width:100%;max-width:{total_w}px;overflow:visible;">
            {"".join(svg_steps)}
          </svg>

          <h4 style="margin:16px 0 6px;color:{COLORS['text']};font-size:13px">🌳 调用结构</h4>
          {tree_html}

          <h4 style="margin:16px 0 6px;color:{COLORS['text']};font-size:13px">📋 调用链详情</h4>
          <div style="overflow-x:auto">
            <table style="font-size:12px">
              <thead><tr>
                <th class="num">step</th>
                <th>event_type</th>
                <th>tool</th>
                <th>arguments</th>
                <th>result</th>
                <th>status</th>
                <th class="num">latency</th>
              </tr></thead>
              <tbody>{"".join(table_rows)}</tbody>
            </table>
          </div>
        </div>""")

    return "".join(parts)


def _build_call_tree(steps: list[dict]) -> str:
    """构建调用结构树（基于 span_id / parent_span_id）。

    如果没有 parent_span_id，按线性顺序展示带缩进的事件序列。
    """
    if not steps:
        return '<p class="text-muted">无步骤</p>'

    has_span = any(s.get("span_id") for s in steps)
    if has_span:
        nodes = {s.get("span_id", f"span_{s.get('step',i)}"): s for i, s in enumerate(steps)}
        children = {}
        roots = []
        for s in steps:
            sid = s.get("span_id", f"span_{s.get('step',0)}")
            pid = s.get("parent_span_id", "")
            if pid and pid in nodes:
                children.setdefault(pid, []).append(s)
            else:
                roots.append(s)

        def render_node(node: dict, depth: int = 0) -> str:
            sid = node.get("span_id", f"span_{node.get('step',0)}")
            et = node.get("event_type", "")
            tool = node.get("tool", "")
            status = node.get("status", "success")
            color = TIMELINE_COLORS.get(et, COLORS["secondary"])
            if status == "error":
                color = COLORS["danger"]
            icon = "🔧" if "tool" in et else "🧠" if "model" in et else "🔄" if "agent" in et else "📋"
            label = tool if tool else et.split(".")[-1]
            status_icon = "✅" if status == "success" else "❌"
            indent = "  " * depth
            child_html = ""
            for c in children.get(sid, []):
                child_html += render_node(c, depth + 1)
            return f'<div style="margin:2px 0;font-size:12px;color:{COLORS["text"]}">{indent}{icon} <span style="color:{color};font-weight:600">{_h(label)}</span> <span style="color:#94a3b8;font-size:11px">{_h(et)}</span> {status_icon}{child_html}</div>'

        return '<div style="background:#f8fafc;padding:12px;border-radius:6px;font-family:monospace">' + "".join(render_node(r) for r in roots) + '</div>'
    else:
        lines = []
        for s in steps:
            et = s.get("event_type", "")
            tool = s.get("tool", "")
            status = s.get("status", "success")
            color = TIMELINE_COLORS.get(et, COLORS["secondary"])
            if status == "error":
                color = COLORS["danger"]
            icon = "🔧" if "tool" in et else "🧠" if "model" in et else "🔄" if "agent" in et else "📋"
            label = tool if tool else et.split(".")[-1]
            status_icon = "✅" if status == "success" else "❌"
            latency = s.get("latency_ms", 0)
            lines.append(f'<div style="margin:2px 0;font-size:12px;color:{COLORS["text"]}">{icon} <span style="color:{color};font-weight:600">{_h(label)}</span> <span style="color:#94a3b8;font-size:11px">{_h(et)}</span> {status_icon} <span style="color:#94a3b8;font-size:11px">{latency}ms</span></div>')
        return '<div style="background:#f8fafc;padding:12px;border-radius:6px;font-family:monospace">' + "".join(lines) + '</div>'


def svg_iteration_curve(curve: list[dict]) -> str:
    """迭代曲线 SVG。"""
    if not curve:
        return '<p class="text-muted">暂无历史 run</p>'
    chart_w = 700
    chart_h = 240
    padding = 40

    scores = [c.get("weighted_score", 0) for c in curve]
    if not scores:
        return '<p class="text-muted">无分数</p>'
    min_s = min(scores + [0])
    max_s = max(scores + [1])
    if max_s == min_s:
        max_s = min_s + 1

    points = []
    for i, c in enumerate(curve):
        x = padding + (i / max(len(curve) - 1, 1)) * (chart_w - 2 * padding)
        y = chart_h - padding - ((c.get("weighted_score", 0) - min_s) / (max_s - min_s)) * (chart_h - 2 * padding)
        points.append((x, y, c))

    # 折线
    if len(points) >= 2:
        path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y, _ in points)
        line = f'<path d="{path}" stroke="{COLORS["primary"]}" stroke-width="2" fill="none"/>'
    else:
        line = ""
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{COLORS["primary"]}"/><title>{_h(c.get("run_id",""))}: {c.get("weighted_score",0)}</title>'
                   for x, y, c in points)
    labels = "".join(f'<text x="{x:.1f}" y="{chart_h - padding + 16}" font-size="9" text-anchor="middle" fill="{COLORS["text_muted"]}" font-family="sans-serif">{_h(c.get("run_id","")[-12:])}</text>'
                     for x, y, c in points)
    values = "".join(f'<text x="{x:.1f}" y="{y - 10:.1f}" font-size="10" font-weight="600" text-anchor="middle" fill="{COLORS["text"]}" font-family="sans-serif">{c.get("weighted_score",0):.2f}</text>'
                     for x, y, c in points)

    return f"""
    <svg viewBox="0 0 {chart_w} {chart_h}" style="width:100%;max-width:{chart_w}px;">
      <line x1="{padding}" y1="{chart_h - padding}" x2="{chart_w - padding}" y2="{chart_h - padding}" stroke="{COLORS["border"]}"/>
      <line x1="{padding}" y1="{padding}" x2="{padding}" y2="{chart_h - padding}" stroke="{COLORS["border"]}"/>
      {line}
      {dots}
      {labels}
      {values}
      <text x="10" y="{chart_h/2}" font-size="11" fill="{COLORS["text_muted"]}" font-family="sans-serif" transform="rotate(-90 10 {chart_h/2})">加权总分</text>
    </svg>
    """


def svg_tool_graph(graph: dict) -> str:
    """工具调用图 SVG（简化版：节点圆 + 边）。"""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not nodes:
        return '<p class="text-muted">无工具调用</p>'

    # 简单布局：圆形排列
    import math
    cx, cy = 300, 200
    radius = 130
    n = len(nodes)
    node_pos = {}
    for i, node in enumerate(nodes):
        angle = 2 * math.pi * i / max(n, 1) - math.pi / 2
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        node_pos[node["id"]] = (x, y)

    max_count = max(n["count"] for n in nodes) or 1

    # 边
    edge_svg = []
    for e in edges:
        a, b = e["from"], e["to"]
        if a in node_pos and b in node_pos:
            x1, y1 = node_pos[a]
            x2, y2 = node_pos[b]
            w = max(1, e["count"])
            stroke_color = COLORS["secondary"]
            edge_svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke_color}" stroke-width="{w}" opacity="0.4"/>')

    # 节点
    node_svg = []
    for node in nodes:
        x, y = node_pos[node["id"]]
        r = 20 + (node["count"] / max_count) * 15
        node_svg.append(f"""
        <circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{COLORS["primary"]}" opacity="0.8"/>
        <text x="{x:.1f}" y="{y:.1f}" font-size="9" font-weight="600" text-anchor="middle" fill="white" font-family="sans-serif">{_h(node['id'][:8])}</text>
        <text x="{x:.1f}" y="{y + r + 12:.1f}" font-size="10" text-anchor="middle" fill="{COLORS["text_muted"]}" font-family="sans-serif">{node['count']}次</text>
        <title>{_h(node['id'])}: {node['count']} calls</title>
        """)

    return f"""
    <svg viewBox="0 0 600 400" style="width:100%;max-width:600px;">
      {"".join(edge_svg)}
      {"".join(node_svg)}
    </svg>
    """


# ---------------------------------------------------------------------------
# 报告各节
# ---------------------------------------------------------------------------

def section_executive_summary(score: dict, charts_data: dict, verdict: dict | None = None,
                              baseline_score: dict | None = None) -> str:
    agg = score.get("aggregate", {})
    b_agg = baseline_score.get("aggregate", {}) if baseline_score else {}
    n_cases = agg.get("n_cases", 0)
    n_success = agg.get("n_success", 0)
    n_hard = agg.get("n_hard_fail", 0)
    success_rate = (n_success / n_cases * 100) if n_cases else 0
    weighted = agg.get("weighted_score", 0)

    # 主要失败类型
    pareto = charts_data.get("failure_pareto", [])
    top_failure = pareto[0]["failure_type"] if pareto else "无"

    # 对比
    if baseline_score:
        b_rate = (b_agg.get("n_success", 0) / max(b_agg.get("n_cases", 1), 1)) * 100
        delta_rate = success_rate - b_rate
        direction = "提升" if delta_rate >= 0 else "下降"
        delta_str = f"较 baseline {direction} {abs(delta_rate):.1f} 个百分点"
    else:
        delta_str = "（无 baseline 对比）"

    verdict_html = ""
    if verdict:
        rec = verdict.get("recommendation", "")
        v_class = "accept" if rec == "ACCEPT" else ("reject" if rec == "REJECT" else "inconclusive")
        verdict_html = f'<div class="verdict {v_class}">建议: {rec}</div>'

    return f"""
    <div class="section" id="executive-summary">
      <h2><span class="num">1</span>执行摘要</h2>
      <p class="lead">本轮评测的总体结论。详细数据见后续各节。</p>
      {verdict_html}
      <div class="scorecard-grid">
        <div class="scorecard">
          <div class="label">Case 总数</div>
          <div class="value">{n_cases}</div>
          <div class="delta neutral">train / regression / adversarial</div>
        </div>
        <div class="scorecard">
          <div class="label">成功率</div>
          <div class="value">{success_rate:.1f}%</div>
          <div class="delta {'up' if baseline_score and delta_rate > 0 else 'neutral'}">{delta_str}</div>
        </div>
        <div class="scorecard">
          <div class="label">加权总分</div>
          <div class="value">{weighted:.3f}</div>
          <div class="delta neutral">满分 1.000</div>
        </div>
        <div class="scorecard">
          <div class="label">硬失败数</div>
          <div class="value" style="color:{COLORS['danger'] if n_hard else COLORS['success']}">{n_hard}</div>
          <div class="delta {'down' if n_hard else 'up'}">{'有硬失败' if n_hard else '无硬失败'}</div>
        </div>
        <div class="scorecard">
          <div class="label">Latency p50</div>
          <div class="value">{agg.get('latency_p50', 0)}<span style="font-size:14px;color:{COLORS['text_muted']}">ms</span></div>
          <div class="delta neutral">mean {agg.get('latency_mean', 0)}ms</div>
        </div>
        <div class="scorecard">
          <div class="label">主要失败类型</div>
          <div class="value" style="font-size:18px;">{_h(top_failure)}</div>
          <div class="delta neutral">见第 7 节失败归因</div>
        </div>
      </div>
    </div>
    """


def section_evaluation_setup(score: dict, cfg: C.EvalConfig, run_id: str) -> str:
    agg = score.get("aggregate", {})
    return f"""
    <div class="section" id="eval-setup">
      <h2><span class="num">2</span>评测配置</h2>
      <table>
        <tr><th>项目</th><th>值</th></tr>
        <tr><td>run_id</td><td><code>{_h(run_id)}</code></td></tr>
        <tr><td>评测时间</td><td>{_h(score.get('run_id', '').split('-')[0] if '-' in score.get('run_id','') else '')}</td></tr>
        <tr><td>adapter</td><td><code>{_h(cfg.adapter_name)}</code></td></tr>
        <tr><td>case 集合</td><td><code>{_h(cfg.cases_dir.name)}/</code></td></tr>
        <tr><td>case 数</td><td>{agg.get('n_cases', 0)}</td></tr>
        <tr><td>指标权重</td><td><code>{_h(json.dumps(score.get('weights', {}), ensure_ascii=False))}</code></td></tr>
        <tr><td>trace 格式</td><td><code>UATR-0.5</code></td></tr>
        <tr><td>报告生成器</td><td>agent-eval v0.5</td></tr>
      </table>
    </div>
    """


def section_overall_scorecard(charts_data: dict) -> str:
    sc = charts_data.get("overall_scorecard", [])
    return f"""
    <div class="section" id="scorecard">
      <h2><span class="num">3</span>总体评分卡</h2>
      <p class="lead">7 个核心指标的 baseline vs candidate 对比。蓝色条为 candidate，灰色条为 baseline。</p>
      {svg_scorecard_bars(sc)}
    </div>
    """


def section_scenario_results(charts_data: dict) -> str:
    sb = charts_data.get("scenario_bar", [])
    if not sb:
        return '<div class="section"><h2><span class="num">4</span>场景维度结果</h2><p class="lead">暂无场景数据</p></div>'
    max_rate = max((s.get("pass_rate", 0) for s in sb), default=1.0)
    rows = "".join(
        f"<tr><td>{_h(s['scenario'])}</td><td class='num'>{s['n_cases']}</td>"
        f"<td class='num'>{s['pass_rate']*100:.1f}%</td>"
        f"<td>{'✅' if s['pass_rate'] >= SCENARIO_PASS_THRESHOLD else '⚠️' if s['pass_rate'] >= SCENARIO_WARN_THRESHOLD else '❌'}</td></tr>"
        for s in sb
    )
    return f"""
    <div class="section" id="scenario">
      <h2><span class="num">4</span>场景维度结果</h2>
      <p class="lead">按 case 的 scenario 分组的通过率。识别 Agent 是全局不行还是某场景短板。</p>
      <table>
        <thead><tr><th>场景</th><th class="num">Case 数</th><th class="num">通过率</th><th>状态</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
      {svg_bar_chart(sb, "pass_rate", "scenario", max_val=1.0, color=COLORS['success'])}
    </div>
    """


def section_metric_results(charts_data: dict) -> str:
    sc = charts_data.get("overall_scorecard", [])
    rows = "".join(
        f"<tr><td>{_h(it.get('label',''))}</td>"
        f"<td class='num'>{it.get('baseline') if it.get('baseline') is not None else '—'}</td>"
        f"<td class='num'>{it.get('candidate') if it.get('candidate') is not None else '—'}</td>"
        f"<td class='num' style='color:{COLORS['success'] if (it.get('delta') or 0) > 0 else COLORS['danger'] if (it.get('delta') or 0) < 0 else COLORS['text_muted']}'>"
        + _fmt_delta(it.get('delta')) + "</td></tr>"
        for it in sc
    )
    return f"""
    <div class="section" id="metric-results">
      <h2><span class="num">5</span>指标维度结果</h2>
      <p class="lead">每个指标的 baseline / candidate / delta 明细。</p>
      <table>
        <thead><tr><th>指标</th><th class="num">Baseline</th><th class="num">Candidate</th><th class="num">Delta</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


def section_trace_analysis(charts_data: dict) -> str:
    graph = charts_data.get("tool_call_graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    nodes_rows = "".join(
        f"<tr><td><code>{_h(n['id'])}</code></td><td class='num'>{n['count']}</td></tr>"
        for n in nodes[:20]
    )
    edges_rows = "".join(
        f"<tr><td><code>{_h(e['from'])}</code> → <code>{_h(e['to'])}</code></td><td class='num'>{e['count']}</td></tr>"
        for e in edges[:20]
    )

    return f"""
    <div class="section" id="trace-analysis">
      <h2><span class="num">6</span>工具与流程分析</h2>
      <h3>工具调用图</h3>
      <p class="lead">节点大小 ∝ 调用次数，边粗细 ∝ 相邻调用次数。</p>
      {svg_tool_graph(graph)}

      <h3>工具调用频次</h3>
      <table>
        <thead><tr><th>工具</th><th class="num">调用次数</th></tr></thead>
        <tbody>{nodes_rows or '<tr><td colspan="2">无</td></tr>'}</tbody>
      </table>

      <h3>调用顺序（相邻工具）</h3>
      <table>
        <thead><tr><th>路径</th><th class="num">次数</th></tr></thead>
        <tbody>{edges_rows or '<tr><td colspan="2">无</td></tr>'}</tbody>
      </table>
    </div>
    """


def section_failure_taxonomy(charts_data: dict, diagnosis: dict | None) -> str:
    if not charts_data:
        return '<div class="section" id="failure-taxonomy"><h2><span class="num">7</span>失败归因</h2><p class="lead">失败归因数据不可用（charts_data 为空）。</p></div>'
    pareto = charts_data.get("failure_pareto", [])
    diags = (diagnosis or {}).get("diagnoses", []) if diagnosis else []

    # 按类型聚合代表 case
    by_type: dict[str, list[dict]] = {}
    for d in diags:
        ft = d.get("failure_type", "UNKNOWN")
        by_type.setdefault(ft, []).append(d)

    detail_parts = []
    for ft, ds in sorted(by_type.items()):
        sample = ds[0]
        detail_parts.append(f"""
        <div style="background:{COLORS['bg_alt']};padding:12px;border-radius:6px;margin-bottom:8px;border-left:3px solid {COLORS['warning']}">
          <strong>{_h(ft)}</strong> — {_h(sample.get('failure_label', ''))}
          <span style="color:{COLORS['text_muted']};font-size:12px">({len(ds)} 条诊断)</span><br>
          <span style="font-size:12px;color:{COLORS['text_muted']}">代表 case: <code>{_h(sample.get('case_id',''))}</code></span><br>
          <span style="font-size:12px">建议: 修改 <code>{_h(sample.get('suggested_mutation_target',''))}</code> via <code>{_h(sample.get('suggested_mutation_rule',''))}</code></span>
        </div>""")

    return f"""
    <div class="section" id="failure-taxonomy">
      <h2><span class="num">7</span>失败归因</h2>
      <p class="lead">按 F1-F7 taxonomy 分类的失败归因。优化不是瞎改 prompt，而是基于归因。</p>
      <h3>Pareto 图</h3>
      {svg_pareto(pareto)}
      <h3>分类详情</h3>
      {"".join(detail_parts) if detail_parts else '<p class="text-muted">无失败诊断</p>'}
    </div>
    """


def section_iteration_history(charts_data: dict) -> str:
    curve = charts_data.get("iteration_curve", [])
    matrix = charts_data.get("patch_impact_matrix", [])
    return f"""
    <div class="section" id="iteration">
      <h2><span class="num">8</span>迭代与 patch 历史</h2>
      <p class="lead">展示优化过程带来的收益趋势，证明不是单点偶然提升。</p>
      <h3>迭代曲线</h3>
      {svg_iteration_curve(curve)}
      <h3>Patch 影响矩阵</h3>
      <p class="text-muted" style="color:{COLORS['text_muted']};font-size:13px">{'共 '+str(len(matrix))+' 个 patch' if matrix else '本轮无 patch'}</p>
    </div>
    """


def section_case_heatmap(charts_data: dict) -> str:
    hm = charts_data.get("case_metric_heatmap", {})
    return f"""
    <div class="section" id="case-heatmap">
      <h2><span class="num">9</span>Case × Metric 热力图</h2>
      <p class="lead">每条 case 在每个 metric 上的得分。快速定位"哪几条 case 拉低整体分数"。</p>
      {svg_heatmap(hm)}
    </div>
    """


def section_trace_timeline(charts_data: dict) -> str:
    tls = charts_data.get("trace_timeline", [])
    return f"""
    <div class="section" id="trace-timeline">
      <h2><span class="num">10</span>Trace 时间线</h2>
      <p class="lead">单 case 的执行步骤序列。颜色按事件类型区分，红色表示 error。鼠标悬停查看详情。</p>
      {svg_timeline(tls)}
    </div>
    """


def _trace_radar_svg(radar: dict) -> str:
    """用纯 SVG 画五维雷达图，零外部依赖。"""
    labels = radar.get("labels", [])
    scores = radar.get("scores", [])
    if not labels or not scores:
        return '<div style="color:#64748b;padding:24px;text-align:center">暂无 TRACE 数据</div>'

    n = len(labels)
    cx, cy, R = 180, 180, 130
    angle_step = 2 * 3.14159265 / n

    # 点坐标
    pts = []
    for i, s in enumerate(scores):
        angle = angle_step * i - 3.14159265 / 2
        r = (s / 5.0) * R
        pts.append((cx + r * math.cos(angle), cy + r * r * 0.0 + r * math.sin(angle)))

    # 用简单三角函数
    pts = []
    for i, s in enumerate(scores):
        angle = angle_step * i - 3.14159265 / 2
        rr = (s / 5.0) * R
        pts.append((cx + rr * math.cos(angle), cy + rr * math.sin(angle)))

    # 网格层
    grid_lines = ""
    for level in [0.2, 0.4, 0.6, 0.8, 1.0]:
        gp = []
        for i in range(n):
            angle = angle_step * i - 3.14159265 / 2
            rr = R * level
            gp.append(f"{cx + rr * math.cos(angle)},{cy + rr * math.sin(angle)}")
        grid_lines += f'<polygon points="{" ".join(gp)}" fill="none" stroke="#e2e8f0" stroke-width="1"/>'

    # 数据多边形
    data_pts = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
    data_polygon = f'<polygon points="{data_pts}" fill="rgba(37,99,235,0.15)" stroke="#2563eb" stroke-width="2.5"/>'

    # 轴线 + 标签
    axes_and_labels = ""
    for i in range(n):
        angle = angle_step * i - 3.14159265 / 2
        ex = cx + R * math.cos(angle)
        ey = cy + R * math.sin(angle)
        axes_and_labels += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#cbd5e1" stroke-width="1"/>'

        # 标签偏移
        lx = cx + (R + 28) * math.cos(angle)
        ly = cy + (R + 28) * math.sin(angle)
        anchors = "middle"
        axes_and_labels += (f'<text x="{lx:.1f}" y="{ly:.1f}" '
                            f'text-anchor="middle" dominant-baseline="central" '
                            f'font-size="13" fill="#0f172a" font-weight="600">{_h(labels[i])}</text>')

    # 分数点
    dots = ""
    for i, p in enumerate(pts):
        dots += (f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="5" fill="#2563eb" stroke="#fff" stroke-width="2"/>'
                 f'<text x="{p[0]:.1f}" y="{p[1] - 12:.1f}" text-anchor="middle" '
                 f'font-size="12" fill="#2563eb" font-weight="700">{scores[i]:.1f}</text>')

    svg = f'''<svg viewBox="0 0 360 360" xmlns="http://www.w3.org/2000/svg">
      {grid_lines}
      {data_polygon}
      {axes_and_labels}
      {dots}
      <circle cx="{cx}" cy="{cy}" r="3" fill="#64748b"/>
    </svg>'''
    return svg


import math


def section_trace_dimensions(charts_data: dict) -> str:
    """第 12 节：TRACE 五维评测（雷达图）。"""
    radar = charts_data.get("trace_radar", {})
    if not radar or not radar.get("labels"):
        return """
    <div class="section" id="trace-dimensions">
      <h2><span class="num">12</span>TRACE 五维评测</h2>
      <p class="lead">五维能力雷达：Trust | Reliability | Adaptability | Convention | Effectiveness</p>
      <div style="color:#64748b;padding:32px;text-align:center;border:1px dashed #e2e8f0;border-radius:8px">
        <p>暂无 TRACE 数据。</p>
        <p style="font-size:13px;margin-top:8px">请在 <code>.agent-eval/config.yaml</code> 中配置 <code>trace</code> 段后重新运行评测。</p>
      </div>
    </div>
    """

    total = radar.get("total_score", 0)
    status = radar.get("status", "?")
    labels = radar.get("labels", [])
    scores = radar.get("scores", [])
    target_zones = radar.get("target_zones", [])

    status_colors = {"excellent": "#16a34a", "good": "#2563eb", "fair": "#d97706", "poor": "#dc2626"}
    status_labels = {"excellent": "优秀", "good": "良好", "fair": "一般", "poor": "差"}
    sc = status_colors.get(status, "#64748b")
    sl = status_labels.get(status, status)

    status_badge = f'<span style="background:{sc};color:#fff;padding:3px 12px;border-radius:99px;font-size:12px;font-weight:600">{sl}</span>'

    # 构建详情表格行
    rows_html = ""
    for i, (label, score) in enumerate(zip(labels, scores)):
        tz = target_zones[i] if i < len(target_zones) else {}
        tz_lo = tz.get("lo", 0)
        tz_hi = tz.get("hi", 0)
        if score >= tz_hi:
            st_emoji = "✅"
            st_color = "#16a34a"
        elif score >= tz_lo:
            st_emoji = "⬆"
            st_color = "#2563eb"
        elif score >= tz_lo - 0.5:
            st_emoji = "⚠️"
            st_color = "#d97706"
        else:
            st_emoji = "❌"
            st_color = "#dc2626"
        rows_html += f"""<tr>
          <td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;font-weight:600">{_h(label)}</td>
          <td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;text-align:center">
            <span style="font-size:20px;font-weight:700;color:{st_color}">{score:.2f}</span><span style="color:#94a3b8;font-size:13px">/5.0</span>
          </td>
          <td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;text-align:center;color:#64748b">{tz_lo:.1f}–{tz_hi:.1f}</td>
          <td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;text-align:center">{st_emoji}</td>
        </tr>"""

    return f"""
    <div class="section" id="trace-dimensions">
      <h2><span class="num">12</span>TRACE 五维评测</h2>
      <p class="lead">五维能力雷达：可信任度 | 可靠性 | 适用性 | 规范性 | 有效性</p>
      <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">
        <div style="flex-shrink:0">{_trace_radar_svg(radar)}</div>
        <div style="flex:1;min-width:300px">
          <div style="margin-bottom:16px">
            <span style="font-size:14px;color:#64748b">TRACE 综合评分</span>
            <span style="font-size:28px;font-weight:700;color:{sc};margin-left:8px">{total:.2f}/5.0</span>
            &nbsp;{status_badge}
          </div>
          <table style="width:100%;border-collapse:collapse">
            <thead><tr>
              <th style="padding:10px 16px;border-bottom:2px solid #e2e8f0;text-align:left;color:#64748b;font-size:12px;text-transform:uppercase">维度</th>
              <th style="padding:10px 16px;border-bottom:2px solid #e2e8f0;text-align:center;color:#64748b;font-size:12px;text-transform:uppercase">评分</th>
              <th style="padding:10px 16px;border-bottom:2px solid #e2e8f0;text-align:center;color:#64748b;font-size:12px;text-transform:uppercase">目标区间</th>
              <th style="padding:10px 16px;border-bottom:2px solid #e2e8f0;text-align:center;color:#64748b;font-size:12px;text-transform:uppercase">状态</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>
      </div>
    </div>
    """


def section_recommendations(score: dict, charts_data: dict, diagnosis: dict | None) -> str:
    """基于分析给出建议。"""
    recs = []
    agg = score.get("aggregate", {})
    pareto = charts_data.get("failure_pareto", [])

    if agg.get("n_hard_fail", 0) > 0:
        recs.append({
            "priority": "high",
            "title": "修复硬失败",
            "desc": f"本轮有 {agg['n_hard_fail']} 条硬失败。硬失败意味着违反业务规则或调用 forbidden 工具，必须优先修复。",
            "meta": "影响: 全部硬失败 case",
        })

    if pareto:
        top = pareto[0]
        recs.append({
            "priority": "high",
            "title": f"优先处理 {top['failure_type']} 失败",
            "desc": f"该类型失败 {top['count']} 次，占总失败的较大比例。参考失败归因第 7 节的 mutation 建议。",
            "meta": f"建议 mutation: 见诊断报告",
        })

    if agg.get("weighted_score", 0) < 0.5:
        recs.append({
            "priority": "high",
            "title": "整体分数偏低，建议系统性优化",
            "desc": "加权总分 < 0.5 说明 agent 整体能力不足，不是单点修复能解决。建议从 prompt 和 tool schema 两方面同时入手。",
            "meta": "当前分数: {:.3f}".format(agg.get("weighted_score", 0)),
        })
    elif agg.get("weighted_score", 0) < 0.8:
        recs.append({
            "priority": "medium",
            "title": "聚焦短板指标",
            "desc": "整体及格但有短板指标。参考评分卡第 3 节，优先提升分数最低的指标。",
            "meta": "当前分数: {:.3f}".format(agg.get("weighted_score", 0)),
        })
    else:
        recs.append({
            "priority": "low",
            "title": "维持当前水平",
            "desc": "整体表现良好。建议增加 adversarial case 覆盖边缘场景。",
            "meta": "当前分数: {:.3f}".format(agg.get("weighted_score", 0)),
        })

    rec_html = []
    for r in recs:
        rec_html.append(f"""
        <div class="rec-item {r['priority']}">
          <div class="rec-title">{_h(r['title'])}</div>
          <div class="rec-desc">{_h(r['desc'])}</div>
          <div class="rec-meta">优先级: {r['priority'].upper()} | {_h(r['meta'])}</div>
        </div>""")

    return f"""
    <div class="section" id="recommendations">
      <h2><span class="num">11</span>建议</h2>
      <p class="lead">基于以上分析的 3-5 条具体建议。</p>
      <div class="rec-list">{"".join(rec_html)}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# 主报告生成
# ---------------------------------------------------------------------------

def generate_html_report(
    cfg: C.EvalConfig,
    run_id: str,
    score: dict,
    charts_data: dict,
    diagnosis: dict | None = None,
    baseline_score: dict | None = None,
    verdict: dict | None = None,
) -> Path:
    """生成完整 HTML 报告。"""
    # 目录导航
    nav_items = [
        ("executive-summary", "1. 执行摘要"),
        ("eval-setup", "2. 评测配置"),
        ("scorecard", "3. 总体评分卡"),
        ("scenario", "4. 场景结果"),
        ("metric-results", "5. 指标结果"),
        ("trace-analysis", "6. 工具分析"),
        ("failure-taxonomy", "7. 失败归因"),
        ("iteration", "8. 迭代历史"),
        ("case-heatmap", "9. Case 热力图"),
        ("trace-timeline", "10. Trace 时间线"),
        ("trace-dimensions", "12. TRACE 五维评测"),
        ("recommendations", "11. 建议"),
    ]
    nav_html = '<div class="nav no-print" style="background:' + COLORS['bg'] + ';padding:12px 24px;border-radius:8px;margin-bottom:24px;border:1px solid ' + COLORS['border'] + ';position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,0.04)"><strong style="margin-right:16px;color:' + COLORS['text'] + '">目录:</strong>'
    for aid, label in nav_items:
        nav_html += f'<a href="#{aid}" style="color:{COLORS["primary"]};text-decoration:none;margin-right:16px;font-size:13px">{label}</a>'
    nav_html += '</div>'

    # header
    agg = score.get("aggregate", {})
    n_cases = agg.get("n_cases", 0)
    n_success = agg.get("n_success", 0)
    header = f"""
    <div class="report-header">
      <h1>Agent 评测报告</h1>
      <div class="subtitle">AgentEvalOps Lite v0.5 — Universal Agent Trace + Professional Report</div>
      <div class="meta">
        <span><strong>run_id:</strong> <code style="background:rgba(255,255,255,0.2);padding:2px 6px;border-radius:3px">{_h(run_id)}</code></span>
        <span><strong>case 数:</strong> {n_cases}</span>
        <span><strong>成功:</strong> {n_success}</span>
        <span><strong>生成时间:</strong> {_h(C.now_iso())}</span>
      </div>
    </div>
    """

    sections = [
        section_executive_summary(score, charts_data, verdict, baseline_score),
        section_evaluation_setup(score, cfg, run_id),
        section_overall_scorecard(charts_data),
        section_scenario_results(charts_data),
        section_metric_results(charts_data),
        section_trace_analysis(charts_data),
        section_failure_taxonomy(charts_data, diagnosis),
        section_iteration_history(charts_data),
        section_case_heatmap(charts_data),
        section_trace_timeline(charts_data),
        section_trace_dimensions(charts_data),
        section_recommendations(score, charts_data, diagnosis),
    ]

    footer = f"""
    <div class="report-footer">
      <p>本报告由 <strong>agent-eval v0.5</strong> 自动生成</p>
      <p style="margin-top:4px">UATR-0.5 trace 格式 | 12 节结构化报告（含 TRACE 五维评测）| 9 类可视化图表</p>
    </div>
    """

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent 评测报告 — {_h(run_id)}</title>
<style>{_css()}</style>
</head>
<body>
<div class="container">
{header}
<div class="no-print" style="text-align:right;margin-bottom:16px;">
  <button onclick="window.print()" style="
    background:#2563eb;color:white;border:none;padding:10px 24px;
    border-radius:6px;font-size:14px;font-weight:600;cursor:pointer;
  ">🖨️ 导出 PDF</button>
</div>
{nav_html}
{"".join(sections)}
{footer}
</div>
</body>
</html>
"""
    out = cfg.reports_dir / f"{run_id}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    try:
        import report_manager as RM
        RM.register_report(cfg, out, run_id=run_id, title=f"HTML 报告 — {run_id}")
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--baseline-run", help="baseline run_id（用于对比）")
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    score = json.loads((cfg.scores_dir / f"{args.run}.json").read_text(encoding="utf-8"))
    baseline_score = None
    if args.baseline_run:
        bp = cfg.scores_dir / f"{args.baseline_run}.json"
        if bp.exists():
            baseline_score = json.loads(bp.read_text(encoding="utf-8"))

    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])
    diagnosis = None
    diag_path = cfg.reports_dir / f"{args.run}_diagnosis.json"
    if diag_path.exists():
        diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))

    charts_data = CH.build_charts(cfg, args.run, score, diagnosis, baseline_score, cases)

    out = generate_html_report(cfg, args.run, score, charts_data, diagnosis, baseline_score)
    # 同时写 charts.json
    C.write_json(cfg.scores_dir / f"{args.run}.charts.json", charts_data)
    print(f"HTML report: {out}")
    print(f"charts.json: {cfg.scores_dir / (args.run + '.charts.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
