#!/usr/bin/env python3
"""report_portal.py — 统一报告门户 + 进度管理（V1.1.1 新增）。

聚合 `.agent-eval/` 下的报告索引、进度埋点、用例迭代历史、质量分，
渲染为单文件 `reports/portal.html`，5 个页面：
  ① Overview  ② Reports  ③ Progress  ④ Iterations  ⑤ Quality

设计语言：深色玻璃态 + 渐变描边 + 微动效（hover 上浮 + 发光）。
零外部依赖：CSS/JS/数据全内联，本地双击可打开。

用法:
  python report_portal.py --config .agent-eval/config.yaml
  # → reports/portal.html，并自动 register_report
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import report_manager as RM  # noqa: E402
import progress_tracker as PT  # noqa: E402
import case_io as CIO  # noqa: E402


# ---------------------------------------------------------------------------
# 共享 CSS（深色玻璃态 + 渐变描边 + 微动效）
# ---------------------------------------------------------------------------

PORTAL_CSS = r"""
:root {
  --bg-base: #0f172a;
  --bg-card: rgba(30, 41, 59, 0.7);
  --bg-card-hover: rgba(30, 41, 59, 0.88);
  --border-soft: rgba(99, 102, 241, 0.15);
  --border-strong: rgba(99, 102, 241, 0.45);
  --text-primary: #f1f5f9;
  --text-secondary: #cbd5e1;
  --text-muted: #64748b;
  --indigo: #6366f1;
  --violet: #8b5cf6;
  --success: #22c55e;
  --danger: #ef4444;
  --warning: #fbbf24;
  --info: #3b82f6;
  --gradient-main: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  --gradient-success: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  --gradient-danger: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
  --shadow-glow: 0 12px 32px rgba(99, 102, 241, 0.25);
  --shadow-soft: 0 4px 12px rgba(0, 0, 0, 0.3);
  --transition-base: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
               "Microsoft YaHei", sans-serif;
  background: var(--bg-base);
  background-image:
    radial-gradient(at 20% 0%, rgba(99, 102, 241, 0.08) 0px, transparent 50%),
    radial-gradient(at 80% 100%, rgba(139, 92, 246, 0.06) 0px, transparent 50%);
  background-attachment: fixed;
  color: var(--text-primary);
  line-height: 1.6;
  font-size: 14px;
  min-height: 100vh;
}
.container { max-width: 1320px; margin: 0 auto; padding: 24px; }

/* Header */
.portal-header {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft);
  border-radius: 16px;
  padding: 28px 32px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-soft);
  position: relative;
  overflow: hidden;
}
.portal-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 2px;
  background: var(--gradient-main);
  opacity: 0.8;
}
.portal-header h1 {
  font-size: 26px;
  font-weight: 700;
  background: var(--gradient-main);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
}
.portal-header .subtitle {
  color: var(--text-secondary);
  font-size: 13px;
  margin-top: 4px;
}
.portal-header .meta {
  display: flex; flex-wrap: wrap; gap: 16px;
  margin-top: 14px;
  font-size: 12px;
  color: var(--text-muted);
}
.portal-header .meta span {
  display: inline-flex; align-items: center; gap: 6px;
}
.portal-header .meta strong { color: var(--text-secondary); font-weight: 600; }

/* Tabs */
.tabs {
  display: flex; gap: 4px; margin-bottom: 20px;
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 6px;
  box-shadow: var(--shadow-soft);
  overflow-x: auto;
}
.tab {
  padding: 10px 18px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: var(--transition-base);
  white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px;
}
.tab:hover {
  background: rgba(99, 102, 241, 0.12);
  color: var(--text-primary);
  transform: translateY(-1px);
}
.tab.active {
  background: var(--gradient-main);
  color: white;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}
.tab .count {
  display: inline-block;
  background: rgba(255, 255, 255, 0.18);
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.tab:not(.active) .count {
  background: rgba(99, 102, 241, 0.15);
  color: var(--indigo);
}

/* Page wrapper */
.page { display: none; animation: fadeIn 0.3s ease; }
.page.active { display: block; }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Card */
.card {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 20px 24px;
  box-shadow: var(--shadow-soft);
  transition: var(--transition-base);
  position: relative;
}
.card:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-strong);
  transform: translateY(-4px);
  box-shadow: var(--shadow-glow);
}
.card h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 14px;
  display: flex; align-items: center; gap: 8px;
}
.card h3 .icon {
  width: 6px; height: 18px;
  background: var(--gradient-main);
  border-radius: 3px;
}

/* KPI grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.kpi-card {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft);
  border-radius: 14px;
  padding: 18px 20px;
  cursor: pointer;
  transition: var(--transition-base);
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0; width: 3px;
  background: var(--gradient-main);
  opacity: 0.4;
  transition: var(--transition-base);
}
.kpi-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-glow);
  border-color: var(--border-strong);
}
.kpi-card:hover::before { opacity: 1; width: 4px; }
.kpi-card .label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 500;
}
.kpi-card .value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  margin-top: 6px;
  font-variant-numeric: tabular-nums;
  background: var(--gradient-main);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.kpi-card .sub {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* Section grid */
.section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.3px;
  background: rgba(99, 102, 241, 0.15);
  color: var(--indigo);
  border: 1px solid rgba(99, 102, 241, 0.2);
}
.badge.success { background: rgba(34, 197, 94, 0.15); color: var(--success); border-color: rgba(34, 197, 94, 0.3); }
.badge.danger { background: rgba(239, 68, 68, 0.15); color: var(--danger); border-color: rgba(239, 68, 68, 0.3); }
.badge.warning { background: rgba(251, 191, 36, 0.15); color: var(--warning); border-color: rgba(251, 191, 36, 0.3); }
.badge.info { background: rgba(59, 130, 246, 0.15); color: var(--info); border-color: rgba(59, 130, 246, 0.3); }
.badge.violet { background: rgba(139, 92, 246, 0.15); color: var(--violet); border-color: rgba(139, 92, 246, 0.3); }

/* Search bar */
.search-bar {
  display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px;
}
.search-bar input, .search-bar select {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 10px 14px;
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  transition: var(--transition-base);
  outline: none;
}
.search-bar input { flex: 1; min-width: 220px; }
.search-bar input:hover, .search-bar select:hover { border-color: var(--border-strong); }
.search-bar input:focus, .search-bar select:focus {
  border-color: var(--indigo);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.18);
}
.search-bar select option { background: var(--bg-base); color: var(--text-primary); }

/* Report cards grid */
.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 14px;
}
.report-card {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 16px 18px;
  transition: var(--transition-base);
  cursor: pointer;
  position: relative;
  overflow: hidden;
}
.report-card::before {
  content: '';
  position: absolute;
  left: 0; top: 0; bottom: 0; width: 3px;
  background: var(--gradient-main);
  opacity: 0;
  transition: var(--transition-base);
}
.report-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-glow);
  border-color: var(--border-strong);
  background: var(--bg-card-hover);
}
.report-card:hover::before { opacity: 1; }
.report-card .title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.report-card .meta-row {
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.report-card .path {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(15, 23, 42, 0.6);
  padding: 4px 8px;
  border-radius: 6px;
  margin-top: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report-card .tags {
  display: flex; gap: 4px; flex-wrap: wrap; margin-top: 8px;
}
.report-card .missing {
  opacity: 0.55;
  border-color: rgba(239, 68, 68, 0.3);
}
.report-preview {
  margin-top: 12px;
  padding: 12px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 8px;
  border: 1px solid var(--border-soft);
  font-family: "SF Mono", Monaco, monospace;
  font-size: 11px;
  color: var(--text-secondary);
  max-height: 280px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.report-preview::-webkit-scrollbar { width: 6px; }
.report-preview::-webkit-scrollbar-thumb { background: var(--border-strong); border-radius: 3px; }

/* Empty state */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
}
.empty-state .icon { font-size: 48px; margin-bottom: 12px; opacity: 0.5; }
.empty-state .title { font-size: 16px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; }
.empty-state .hint { font-size: 13px; }

/* Progress ring */
.progress-ring-wrap {
  display: flex; align-items: center; gap: 24px; flex-wrap: wrap;
}
.progress-ring-wrap svg { flex-shrink: 0; }
.progress-ring-info { flex: 1; min-width: 200px; }
.progress-ring-info .pct {
  font-size: 36px; font-weight: 700;
  background: var(--gradient-main);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.progress-ring-info .step {
  font-size: 16px; color: var(--text-primary); font-weight: 600; margin-top: 4px;
}
.progress-ring-info .run-id {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 11px; color: var(--text-muted); margin-top: 6px;
}

/* Timeline (horizontal) */
.timeline-h {
  display: flex; align-items: center; gap: 0; margin: 16px 0; overflow-x: auto;
  padding: 20px 0;
}
.timeline-node {
  position: relative;
  display: flex; flex-direction: column; align-items: center;
  flex-shrink: 0;
  min-width: 96px;
}
.timeline-node .dot {
  width: 28px; height: 28px;
  border-radius: 50%;
  background: rgba(30, 41, 59, 0.8);
  border: 2px solid var(--text-muted);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
  color: var(--text-muted);
  transition: var(--transition-base);
  cursor: default;
  position: relative;
  z-index: 2;
}
.timeline-node.completed .dot {
  background: var(--gradient-success);
  border-color: var(--success);
  color: white;
}
.timeline-node.running .dot {
  background: var(--gradient-main);
  border-color: var(--indigo);
  color: white;
  animation: pulse 1.6s ease-in-out infinite;
}
.timeline-node.failed .dot {
  background: var(--gradient-danger);
  border-color: var(--danger);
  color: white;
}
.timeline-node.skipped .dot { opacity: 0.5; }
.timeline-node.pending .dot { opacity: 0.4; }
.timeline-node .dot:hover { transform: scale(1.15); }
.timeline-node .name {
  font-size: 11px; color: var(--text-secondary);
  margin-top: 8px; text-align: center;
  max-width: 88px;
  word-break: break-all;
}
.timeline-node .step-num {
  font-size: 10px; color: var(--text-muted); margin-top: 2px;
}
.timeline-line {
  flex: 1; height: 2px;
  background: var(--text-muted);
  opacity: 0.3;
  min-width: 16px;
  margin-top: -28px;
  position: relative;
  z-index: 1;
}
.timeline-line.done {
  background: var(--success);
  opacity: 0.6;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.6); }
  50% { box-shadow: 0 0 0 8px rgba(99, 102, 241, 0); }
}
.tooltip {
  position: absolute; bottom: calc(100% + 8px); left: 50%;
  transform: translateX(-50%);
  background: rgba(15, 23, 42, 0.96);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 11px; color: var(--text-primary);
  white-space: nowrap;
  z-index: 100;
  opacity: 0; pointer-events: none;
  transition: var(--transition-base);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
  max-width: 280px;
  white-space: normal;
  text-align: left;
}
.timeline-node:hover .tooltip, .dot:hover .tooltip, [data-tooltip]:hover::after {
  opacity: 1; transform: translateX(-50%) translateY(-2px);
}

/* Bar chart */
.bar-chart { margin: 8px 0; }
.bar-row {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 8px;
  padding: 4px 0;
  transition: var(--transition-base);
}
.bar-row:hover { transform: translateX(2px); }
.bar-row .bar-label {
  width: 140px; font-size: 12px; color: var(--text-secondary);
  flex-shrink: 0;
}
.bar-row .bar-track {
  flex: 1; height: 22px;
  background: rgba(15, 23, 42, 0.6);
  border-radius: 6px;
  position: relative;
  overflow: hidden;
}
.bar-row .bar-fill {
  height: 100%;
  background: var(--gradient-main);
  border-radius: 6px;
  transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
}
.bar-row .bar-fill.success { background: var(--gradient-success); }
.bar-row .bar-fill.danger { background: var(--gradient-danger); }
.bar-row .bar-fill.warning { background: linear-gradient(135deg, #fbbf24 0%, #d97706 100%); }
.bar-row .bar-value {
  width: 80px; font-size: 12px; font-weight: 600;
  text-align: right; color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

/* Tables */
.table-wrap { overflow-x: auto; border-radius: 10px; }
table {
  width: 100%; border-collapse: collapse; font-size: 12px;
}
th, td {
  padding: 10px 12px; text-align: left;
  border-bottom: 1px solid var(--border-soft);
}
th {
  background: rgba(15, 23, 42, 0.6);
  color: var(--text-muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}
tbody tr {
  transition: var(--transition-base);
  position: relative;
}
tbody tr:hover {
  background: rgba(99, 102, 241, 0.08);
  box-shadow: inset 2px 0 0 var(--indigo);
}
td { color: var(--text-secondary); }
td.num { text-align: right; font-variant-numeric: tabular-nums; }

/* Iteration card */
.iter-card {
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 12px;
  transition: var(--transition-base);
  cursor: default;
  position: relative;
}
.iter-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-soft);
}
.iter-card .head {
  display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 8px;
  margin-bottom: 10px;
}
.iter-card .prop-id {
  font-family: "SF Mono", Monaco, monospace;
  font-size: 12px; color: var(--text-secondary); font-weight: 600;
}
.iter-card .stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-top: 10px;
}
.iter-card .stat {
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  padding: 8px 10px;
  text-align: center;
}
.iter-card .stat .lbl {
  font-size: 10px; color: var(--text-muted); text-transform: uppercase;
  letter-spacing: 0.3px;
}
.iter-card .stat .val {
  font-size: 16px; font-weight: 700; color: var(--text-primary);
  margin-top: 2px;
}
.iter-card .stat .val.up { color: var(--success); }
.iter-card .stat .val.down { color: var(--danger); }

/* Radar chart */
.radar-wrap {
  display: flex; justify-content: center; align-items: center;
  padding: 16px;
}

/* Quality dim cards */
.dim-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.dim-card {
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid var(--border-soft);
  border-radius: 10px;
  padding: 12px 14px;
  transition: var(--transition-base);
  position: relative;
}
.dim-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-soft);
}
.dim-card.low { border-color: rgba(239, 68, 68, 0.4); background: rgba(239, 68, 68, 0.06); }
.dim-card .name { font-size: 12px; color: var(--text-secondary); font-weight: 500; }
.dim-card .score {
  font-size: 22px; font-weight: 700;
  margin-top: 4px;
  font-variant-numeric: tabular-nums;
}
.dim-card .score.good { color: var(--success); }
.dim-card .score.mid { color: var(--warning); }
.dim-card .score.low { color: var(--danger); }
.dim-card .weight {
  font-size: 10px; color: var(--text-muted); margin-top: 2px;
}

/* Footer */
.portal-footer {
  text-align: center;
  color: var(--text-muted);
  font-size: 11px;
  padding: 24px 16px;
  border-top: 1px solid var(--border-soft);
  margin-top: 32px;
}

/* Mini sparkline */
.sparkline { display: block; }

/* Status dot */
.status-dot {
  display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; margin-right: 6px;
  vertical-align: middle;
}
.status-dot.running { background: var(--indigo); animation: pulse 1.6s ease-in-out infinite; }
.status-dot.completed { background: var(--success); }
.status-dot.failed { background: var(--danger); }
.status-dot.pending { background: var(--text-muted); }

/* Responsive */
@media (max-width: 768px) {
  .container { padding: 12px; }
  .portal-header { padding: 20px; }
  .kpi-grid { grid-template-columns: 1fr 1fr; }
  .bar-row .bar-label { width: 100px; }
}
"""


# ---------------------------------------------------------------------------
# 数据聚合
# ---------------------------------------------------------------------------

def _load_latest_quality(cfg: C.EvalConfig) -> dict[str, Any] | None:
    """加载最近一次 case_quality_*.json。

    默认写在 reports/（case_quality_checker.py:391），兼容历史 data/ 路径。
    """
    candidates: list[Path] = []
    for d in (cfg.reports_dir, cfg.root / "data"):
        if d.exists():
            candidates.extend(d.glob("case_quality_*.json"))
    if not candidates:
        return None
    # 按修改时间取最新
    candidates.sort(key=lambda p: p.stat().st_mtime)
    try:
        return json.loads(candidates[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_runs_summary(cfg: C.EvalConfig) -> list[dict[str, Any]]:
    """读取 scores/*.json，提取 weighted_score 等关键字段。"""
    out: list[dict[str, Any]] = []
    if not cfg.scores_dir.exists():
        return out
    for p in sorted(cfg.scores_dir.glob("*.json")):
        # 跳过 charts/trace 类聚合文件
        if "charts" in p.name or "trace" in p.name:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        run_id = p.stem
        out.append({
            "run_id": run_id,
            "weighted_score": d.get("weighted_score") or d.get("weighted_total"),
            "n_hard_fail": d.get("n_hard_fail"),
            "n_cases": d.get("n_cases"),
            "verdict": d.get("verdict"),
            "timestamp": d.get("timestamp"),
        })
    return out


def aggregate(cfg: C.EvalConfig) -> dict[str, Any]:
    """聚合门户所需的全部数据。"""
    reports = RM.list_reports(cfg, missing=False)
    iterations = CIO.load_iterations(cfg)
    try:
        progress_timeline = PT.timeline(cfg)
        progress_summary = PT.summary(cfg)
    except Exception as e:
        sys.stderr.write(f"[report_portal] progress_tracker 读取失败: {e}\n")
        progress_timeline = {"sessions": [], "total_sessions": 0}
        progress_summary = {"total_events": 0, "total_sessions": 0, "latest": None,
                           "latest_session": None, "avg_step_ms": {}}
    latest_quality = _load_latest_quality(cfg)
    runs = _load_runs_summary(cfg)

    # KPI 统计
    html_reports = sum(1 for r in reports if r.get("format") == "html")
    md_reports = sum(1 for r in reports if r.get("format") == "md")
    run_count = len(runs)
    avg_score = None
    if runs:
        scores = [r["weighted_score"] for r in runs if r.get("weighted_score") is not None]
        if scores:
            avg_score = round(sum(scores) / len(scores), 4)

    # 当前进度
    latest_session = progress_summary.get("latest_session")
    current_progress = None
    if latest_session:
        current_progress = {
            "session_id": latest_session.get("session_id"),
            "run_id": latest_session.get("run_id"),
            "current_step": latest_session.get("current_step"),
            "current_step_name": latest_session.get("current_step_name"),
            "current_status": latest_session.get("current_status"),
            "progress_pct": latest_session.get("progress_pct"),
            "total_steps": latest_session.get("total_steps"),
        }

    return {
        "reports": reports,
        "reports_total": len(reports),
        "html_reports": html_reports,
        "md_reports": md_reports,
        "iterations": iterations,
        "iterations_total": len(iterations),
        "progress_timeline": progress_timeline,
        "progress_summary": progress_summary,
        "current_progress": current_progress,
        "latest_quality": latest_quality,
        "runs": runs,
        "run_count": run_count,
        "avg_score": avg_score,
        "generated_at": C.now_iso(),
    }


# ---------------------------------------------------------------------------
# HTML 渲染：SVG 图表片段
# ---------------------------------------------------------------------------

def _svg_progress_ring(pct: float, size: int = 132, stroke: int = 10) -> str:
    """环形进度条。"""
    r = (size - stroke) // 2
    cx = cy = size // 2
    circumference = 2 * 3.141592653589793 * r
    offset = circumference * (1 - max(0, min(1, pct / 100)))
    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
    stroke="rgba(99,102,241,0.15)" stroke-width="{stroke}"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none"
    stroke="url(#ringGrad)" stroke-width="{stroke}"
    stroke-linecap="round"
    stroke-dasharray="{circumference:.2f}"
    stroke-dashoffset="{offset:.2f}"
    transform="rotate(-90 {cx} {cy})"
    style="transition: stroke-dashoffset 0.8s cubic-bezier(0.4,0,0.2,1)">
    <title>{pct:.1f}%</title>
  </circle>
  <text x="{cx}" y="{cy - 2}" text-anchor="middle"
    font-size="22" font-weight="700" fill="#f1f5f9" font-family="sans-serif">{pct:.0f}%</text>
  <text x="{cx}" y="{cy + 18}" text-anchor="middle"
    font-size="11" fill="#64748b" font-family="sans-serif">进度</text>
</svg>
"""


def _svg_sparkline(values: list[float], width: int = 280, height: int = 60) -> str:
    """Mini 折线图（最近 N 次 run 分数趋势）。"""
    if not values:
        return '<div class="empty-state" style="padding:20px;font-size:12px;">暂无数据</div>'
    pts = values
    vmin, vmax = min(pts), max(pts)
    if vmax == vmin:
        vmax = vmin + 1
    n = len(pts)
    pad = 6
    w = width - pad * 2
    h = height - pad * 2 - 10
    coords = []
    for i, v in enumerate(pts):
        x = pad + (w / max(1, n - 1)) * i
        y = pad + h - (v - vmin) / (vmax - vmin) * h
        coords.append((x, y))
    path = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in coords)
    # 面积填充
    area = f"{path} L {coords[-1][0]:.1f} {pad + h} L {coords[0][0]:.1f} {pad + h} Z"
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="#8b5cf6" '
        f'style="transition: r .15s" onmouseenter="this.setAttribute(\'r\',5)" '
        f'onmouseleave="this.setAttribute(\'r\',3.5)"><title>Run {i+1}: {v:.3f}</title></circle>'
        for i, (x, y) in enumerate(coords)
    )
    return f"""
<svg class="sparkline" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="sparkArea" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="rgba(139,92,246,0.35)"/>
      <stop offset="100%" stop-color="rgba(139,92,246,0)"/>
    </linearGradient>
    <linearGradient id="sparkLine" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#6366f1"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>
  <path d="{area}" fill="url(#sparkArea)"/>
  <path d="{path}" fill="none" stroke="url(#sparkLine)" stroke-width="2"
    stroke-linecap="round" stroke-linejoin="round"/>
  {dots}
</svg>
"""


def _svg_radar(dims: list[dict[str, Any]], size: int = 380) -> str:
    """12 维雷达图。dims: [{name, score, weight}, ...]"""
    if not dims:
        return '<div class="empty-state" style="padding:20px;">暂无质量评分</div>'
    n = len(dims)
    cx = cy = size // 2
    r = size // 2 - 50
    # 网格层（5 层）
    grid_layers = 5
    grid = ""
    for layer in range(1, grid_layers + 1):
        rr = r * layer / grid_layers
        points = []
        for i in range(n):
            angle = -3.141592653589793 / 2 + 2 * 3.141592653589793 * i / n
            x = cx + rr * __import__("math").cos(angle)
            y = cy + rr * __import__("math").sin(angle)
            points.append(f"{x:.1f},{y:.1f}")
        grid += f'<polygon points="{" ".join(points)}" fill="none" stroke="rgba(99,102,241,0.12)" stroke-width="1"/>'

    # 轴线
    axes = ""
    labels = ""
    import math
    for i, d in enumerate(dims):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="rgba(99,102,241,0.15)" stroke-width="1"/>'
        lx = cx + (r + 18) * math.cos(angle)
        ly = cy + (r + 18) * math.sin(angle)
        score = d.get("score", 0)
        color = "#22c55e" if score >= 0.8 else "#fbbf24" if score >= 0.5 else "#ef4444"
        labels += (f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                   f'dominant-baseline="middle" font-size="10" fill="#cbd5e1" '
                   f'font-family="sans-serif">{d["name"][:8]}</text>')

    # 数据多边形
    data_pts = []
    import math
    for i, d in enumerate(dims):
        angle = -math.pi / 2 + 2 * math.pi * i / n
        rr = r * max(0, min(1, d.get("score", 0)))
        x = cx + rr * math.cos(angle)
        y = cy + rr * math.sin(angle)
        data_pts.append((x, y, d))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in data_pts)
    dots = ""
    for x, y, d in data_pts:
        score = d.get("score", 0)
        color = "#22c55e" if score >= 0.8 else "#fbbf24" if score >= 0.5 else "#ef4444"
        dots += (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" '
                 f'style="transition: r .15s" onmouseenter="this.setAttribute(\'r\',6)" '
                 f'onmouseleave="this.setAttribute(\'r\',4)">'
                 f'<title>{d["name"]} | 得分: {score:.3f} | 权重: {d.get("weight", 0):.2f}</title>'
                 f'</circle>')

    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <linearGradient id="radarFill" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="rgba(99,102,241,0.45)"/>
      <stop offset="100%" stop-color="rgba(139,92,246,0.35)"/>
    </linearGradient>
  </defs>
  {grid}
  {axes}
  <polygon points="{poly}" fill="url(#radarFill)" stroke="#8b5cf6" stroke-width="2"
    stroke-linejoin="round" style="transition: all .3s"/>
  {dots}
  {labels}
</svg>
"""


# ---------------------------------------------------------------------------
# HTML 渲染：5 个页面
# ---------------------------------------------------------------------------

def _fmt_ts(ts: str | None) -> str:
    if not ts:
        return "—"
    return ts.replace("T", " ").split("+")[0].split(".")[0]


def _render_overview(data: dict[str, Any]) -> str:
    runs = data.get("runs", [])
    recent_runs = runs[-5:]
    scores = [r["weighted_score"] for r in recent_runs if r.get("weighted_score") is not None]
    sparkline = _svg_sparkline(scores)
    recent_reports = data.get("reports", [])[:5]
    cp = data.get("current_progress")

    kpis = [
        {"label": "报告总数", "value": data.get("reports_total", 0),
         "sub": f"HTML {data.get('html_reports', 0)} · MD {data.get('md_reports', 0)}", "page": "Reports"},
        {"label": "评测 Run 数", "value": data.get("run_count", 0),
         "sub": f"平均分 {data.get('avg_score', '—')}", "page": "Reports"},
        {"label": "用例迭代次数", "value": data.get("iterations_total", 0),
         "sub": "自优化轮数", "page": "Iterations"},
        {"label": "进度事件数", "value": data.get("progress_summary", {}).get("total_events", 0),
         "sub": f"会话 {data.get('progress_summary', {}).get('total_sessions', 0)} 个", "page": "Progress"},
        {"label": "当前进度", "value": f"{cp['progress_pct']}%" if cp else "—",
         "sub": cp["current_step_name"] if cp else "无运行中会话", "page": "Progress"},
        {"label": "平均分", "value": f"{data.get('avg_score', 0) or 0:.3f}" if data.get("avg_score") else "—",
         "sub": f"基于 {len(scores)} 次 run", "page": "Quality"},
    ]
    kpi_html = "".join(
        f'<div class="kpi-card" onclick="switchPage(\'{k["page"]}\')">'
        f'<div class="label">{k["label"]}</div>'
        f'<div class="value">{k["value"]}</div>'
        f'<div class="sub">{k["sub"]}</div></div>'
        for k in kpis
    )

    recent_reports_html = ""
    if recent_reports:
        rows = "".join(
            f'<tr onclick="switchPage(\'Reports\')" style="cursor:pointer">'
            f'<td>{r.get("title", "")[:50]}</td>'
            f'<td><span class="badge">{r.get("format", "")}</span></td>'
            f'<td>{_fmt_ts(r.get("created_at"))}</td>'
            f'<td>{r.get("run_id") or "—"}</td></tr>'
            for r in recent_reports
        )
        recent_reports_html = f"""
<div class="card">
  <h3><span class="icon"></span>最近报告</h3>
  <div class="table-wrap">
    <table>
      <thead><tr><th>标题</th><th>格式</th><th>创建时间</th><th>Run ID</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>"""
    else:
        recent_reports_html = """
<div class="card">
  <h3><span class="icon"></span>最近报告</h3>
  <div class="empty-state"><div class="icon">📂</div><div class="title">暂无报告</div>
  <div class="hint">先运行 eval_runner / case_optimizer 生成报告</div></div>
</div>"""

    progress_card = ""
    if cp:
        ring = _svg_progress_ring(cp["progress_pct"])
        status_cls = {"completed": "success", "failed": "danger",
                     "running": "info", "pending": "", "skipped": "warning"}.get(cp["current_status"], "")
        progress_card = f"""
<div class="card">
  <h3><span class="icon"></span>当前运行</h3>
  <div class="progress-ring-wrap">
    {ring}
    <div class="progress-ring-info">
      <div class="pct">{cp['progress_pct']}%</div>
      <div class="step">{cp['current_step_name'] or '—'}</div>
      <div><span class="badge {status_cls}">{cp['current_status']}</span></div>
      <div class="run-id">{cp['run_id'] or '—'}</div>
    </div>
  </div>
</div>"""
    else:
        progress_card = """
<div class="card">
  <h3><span class="icon"></span>当前运行</h3>
  <div class="empty-state"><div class="icon">⏸️</div><div class="title">无运行中会话</div>
  <div class="hint">sidecar 落盘的进度事件会在此显示</div></div>
</div>"""

    return f"""
<div class="kpi-grid">{kpi_html}</div>
<div class="section-grid">
  <div class="card">
    <h3><span class="icon"></span>最近 5 次 Run 分数趋势</h3>
    <div style="display:flex;justify-content:center;">{sparkline}</div>
    <div style="font-size:11px;color:var(--text-muted);text-align:center;margin-top:8px;">
      鼠标悬浮圆点查看 run_id 与分数
    </div>
  </div>
  {progress_card}
</div>
{recent_reports_html}
"""


def _render_reports(data: dict[str, Any]) -> str:
    reports = data.get("reports", [])
    if not reports:
        return '<div class="empty-state"><div class="icon">📭</div><div class="title">暂无报告</div><div class="hint">先运行评测生成报告</div></div>'

    # 收集所有类型与格式
    types = sorted({r.get("report_type", "unknown") for r in reports})
    fmts = sorted({r.get("format", "") for r in reports})

    type_options = "".join(f'<option value="{t}">{t}</option>' for t in types)
    fmt_options = "".join(f'<option value="{f}">{f}</option>' for f in fmts)

    return f"""
<div class="search-bar">
  <input type="text" id="reportSearch" placeholder="🔍 搜索标题 / run_id / tags / 路径 / notes..."
    oninput="filterReports()">
  <select id="reportType" onchange="filterReports()">
    <option value="">全部类型</option>{type_options}
  </select>
  <select id="reportFmt" onchange="filterReports()">
    <option value="">全部格式</option>{fmt_options}
  </select>
</div>
<div class="report-grid" id="reportGrid"></div>
<div class="empty-state" id="reportEmpty" style="display:none;">
  <div class="icon">🔍</div>
  <div class="title">无匹配报告</div>
  <div class="hint">尝试更换关键词或清除过滤</div>
</div>
"""


def _render_progress(data: dict[str, Any]) -> str:
    timeline = data.get("progress_timeline", {})
    sessions = timeline.get("sessions", [])
    summary = data.get("progress_summary", {})

    if not sessions:
        return '<div class="empty-state"><div class="icon">⏱️</div><div class="title">暂无进度数据</div><div class="hint">运行 sidecar.py 或 eval_runner 后会自动落盘</div></div>'

    # 当前会话（取最后一个）
    latest = sessions[-1]
    ring = _svg_progress_ring(latest.get("progress_pct", 0))
    status_cls = {"completed": "success", "failed": "danger",
                 "running": "info", "pending": "", "skipped": "warning"}.get(
        latest.get("current_status"), "")

    # 时间线节点
    steps = latest.get("steps", [])
    total_steps = latest.get("total_steps", 9)
    nodes_html = ""
    for s in steps:
        st = s.get("status", "pending")
        dur = s.get("duration_ms")
        dur_str = f"{dur}ms" if dur is not None else "—"
        ts_s = _fmt_ts(s.get("started_at"))
        ts_e = _fmt_ts(s.get("ended_at"))
        err = s.get("error") or "无"
        tip = (f"<b>{s.get('name', '')}</b><br>状态: {st}<br>耗时: {dur_str}"
               f"<br>开始: {ts_s}<br>结束: {ts_e}<br>错误: {err}")
        nodes_html += f"""
<div class="timeline-node {st}">
  <div class="dot">{s.get('step', '?')}
    <div class="tooltip">{tip}</div>
  </div>
  <div class="name">{s.get('name', '')}</div>
  <div class="step-num">#{s.get('step', '?')}</div>
</div>"""
        if s.get("step", 0) < total_steps:
            done = "done" if st in ("completed", "skipped") else ""
            nodes_html += f'<div class="timeline-line {done}"></div>'

    # 阶段耗时条形图（基于 summary.avg_step_ms）
    avg_ms = summary.get("avg_step_ms", {})
    bars_html = ""
    if avg_ms:
        max_ms = max(avg_ms.values()) if avg_ms else 1
        for step in sorted(avg_ms.keys()):
            ms = avg_ms[step]
            name_map = {1: "启动前", 2: "跑基线", 3: "失败诊断", 4: "多 Judge",
                       5: "HRPO 分析", 6: "生成 reference", 7: "A/B + 自优化",
                       8: "生成报告", 9: "Dashboard"}
            name = name_map.get(int(step), f"步骤 {step}")
            pct = (ms / max_ms) * 100 if max_ms > 0 else 0
            sec = ms / 1000
            dur_label = f"{sec:.2f}s" if sec >= 1 else f"{ms}ms"
            bars_html += f"""
<div class="bar-row" data-tooltip="{name}: {dur_label} ({pct:.1f}%)">
  <div class="bar-label">{name}</div>
  <div class="bar-track">
    <div class="bar-fill" style="width:{pct:.1f}%"></div>
  </div>
  <div class="bar-value">{dur_label}</div>
</div>"""
    else:
        bars_html = '<div class="empty-state" style="padding:20px;">暂无耗时数据</div>'

    # 历史会话表
    sessions_rows = ""
    for s in sessions:
        status = s.get("current_status", "—")
        s_cls = {"completed": "success", "failed": "danger",
                "running": "info", "pending": "", "skipped": "warning"}.get(status, "")
        sessions_rows += f"""
<tr>
  <td><span class="status-dot {status}"></span>{s.get('session_id', '—')}</td>
  <td>{s.get('run_id') or '—'}</td>
  <td>{s.get('current_step', 0)}/{s.get('total_steps', 9)}</td>
  <td><span class="badge {s_cls}">{status}</span></td>
  <td>{_fmt_ts(s.get('started_at'))}</td>
  <td>{_fmt_ts(s.get('ended_at'))}</td>
  <td>{s.get('n_events', 0)}</td>
</tr>"""

    return f"""
<div class="card" style="margin-bottom:16px;">
  <h3><span class="icon"></span>当前运行进度</h3>
  <div class="progress-ring-wrap">
    {ring}
    <div class="progress-ring-info">
      <div class="pct">{latest.get('progress_pct', 0)}%</div>
      <div class="step">{latest.get('current_step_name') or '—'}</div>
      <div><span class="badge {status_cls}">{latest.get('current_status', '—')}</span></div>
      <div class="run-id">{latest.get('run_id') or '—'}</div>
      <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">
        会话: {latest.get('session_id', '—')}
      </div>
    </div>
  </div>
</div>

<div class="card" style="margin-bottom:16px;">
  <h3><span class="icon"></span>阶段时间线（hover 节点查看详情）</h3>
  <div class="timeline-h">{nodes_html}</div>
</div>

<div class="section-grid">
  <div class="card">
    <h3><span class="icon"></span>阶段平均耗时</h3>
    <div class="bar-chart">{bars_html}</div>
  </div>
  <div class="card">
    <h3><span class="icon"></span>进度总览</h3>
    <div class="bar-chart">
      <div class="bar-row">
        <div class="bar-label">总会话数</div>
        <div class="bar-track"><div class="bar-fill" style="width:100%"></div></div>
        <div class="bar-value">{summary.get('total_sessions', 0)}</div>
      </div>
      <div class="bar-row">
        <div class="bar-label">已完成</div>
        <div class="bar-track"><div class="bar-fill success" style="width:{(summary.get('completed_sessions', 0) / max(1, summary.get('total_sessions', 1))) * 100:.0f}%"></div></div>
        <div class="bar-value">{summary.get('completed_sessions', 0)}</div>
      </div>
      <div class="bar-row">
        <div class="bar-label">失败</div>
        <div class="bar-track"><div class="bar-fill danger" style="width:{(summary.get('failed_sessions', 0) / max(1, summary.get('total_sessions', 1))) * 100:.0f}%"></div></div>
        <div class="bar-value">{summary.get('failed_sessions', 0)}</div>
      </div>
      <div class="bar-row">
        <div class="bar-label">运行中</div>
        <div class="bar-track"><div class="bar-fill" style="width:{(summary.get('running_sessions', 0) / max(1, summary.get('total_sessions', 1))) * 100:.0f}%"></div></div>
        <div class="bar-value">{summary.get('running_sessions', 0)}</div>
      </div>
      <div class="bar-row">
        <div class="bar-label">总事件数</div>
        <div class="bar-track"><div class="bar-fill" style="width:100%"></div></div>
        <div class="bar-value">{summary.get('total_events', 0)}</div>
      </div>
    </div>
  </div>
</div>

<div class="card">
  <h3><span class="icon"></span>历史会话</h3>
  <div class="table-wrap">
    <table>
      <thead><tr><th>会话 ID</th><th>Run ID</th><th>步骤</th><th>状态</th>
        <th>开始</th><th>结束</th><th>事件数</th></tr></thead>
      <tbody>{sessions_rows}</tbody>
    </table>
  </div>
</div>
"""


def _render_iterations(data: dict[str, Any]) -> str:
    iters = data.get("iterations", [])
    if not iters:
        return '<div class="empty-state"><div class="icon">🔄</div><div class="title">暂无用例迭代</div><div class="hint">运行 case_optimizer apply 后会记录迭代历史</div></div>'

    # 质量分趋势
    scores = []
    for it in iters:
        before = (it.get("quality_before") or {}).get("weighted_total")
        after = (it.get("quality_after_estimated") or {}).get("weighted_total")
        if before is not None:
            scores.append(before)
        if after is not None:
            scores.append(after)
    # 去重连续相同
    dedup_scores = []
    for s in scores:
        if not dedup_scores or abs(dedup_scores[-1] - s) > 0.001:
            dedup_scores.append(s)
    sparkline = _svg_sparkline(dedup_scores[-8:]) if dedup_scores else ""

    cards = ""
    for it in iters:
        prop_id = it.get("proposal_id", "—")
        run_id = it.get("run_id", "—")
        ts = _fmt_ts(it.get("timestamp"))
        accepted = it.get("accepted")
        acc_badge = '<span class="badge success">已应用</span>' if accepted else '<span class="badge warning">未应用</span>'

        before = (it.get("quality_before") or {}).get("weighted_total")
        after = (it.get("quality_after_estimated") or {}).get("weighted_total")
        delta = (after - before) if (before is not None and after is not None) else None
        delta_str = f"+{delta:.3f}" if delta is not None else "—"
        delta_cls = "up" if delta and delta > 0 else ("down" if delta and delta < 0 else "")

        apply_summary = it.get("apply_summary") or {}
        counts = apply_summary.get("counts") or {}
        added = counts.get("added", 0)
        modified = counts.get("modified", 0)
        deprecated = counts.get("deprecated", 0)
        before_n = counts.get("before", 0)
        after_n = counts.get("after", 0)

        cards += f"""
<div class="iter-card">
  <div class="head">
    <div>
      <span class="prop-id">{prop_id}</span>
      <span style="margin-left:8px;font-size:11px;color:var(--text-muted);">{ts}</span>
    </div>
    <div>{acc_badge}</div>
  </div>
  <div style="font-size:11px;color:var(--text-muted);font-family:'SF Mono',Monaco,monospace;">
    run: {run_id} · split: {it.get('split', '—')}
  </div>
  <div class="stats-row">
    <div class="stat">
      <div class="lbl">质量分 前</div>
      <div class="val">{before if before is not None else '—'}</div>
    </div>
    <div class="stat">
      <div class="lbl">质量分 后</div>
      <div class="val {delta_cls}">{after if after is not None else '—'}</div>
    </div>
    <div class="stat">
      <div class="lbl">变化</div>
      <div class="val {delta_cls}">{delta_str}</div>
    </div>
    <div class="stat">
      <div class="lbl">用例 前→后</div>
      <div class="val">{before_n} → {after_n}</div>
    </div>
    <div class="stat">
      <div class="lbl">新增</div>
      <div class="val up">+{added}</div>
    </div>
    <div class="stat">
      <div class="lbl">修改</div>
      <div class="val">~{modified}</div>
    </div>
    <div class="stat">
      <div class="lbl">废弃</div>
      <div class="val down">-{deprecated}</div>
    </div>
  </div>
</div>"""

    return f"""
<div class="section-grid">
  <div class="card">
    <h3><span class="icon"></span>质量分趋势</h3>
    <div style="display:flex;justify-content:center;">{sparkline}</div>
    <div style="font-size:11px;color:var(--text-muted);text-align:center;margin-top:8px;">
      横轴为迭代序列（前/后），纵轴为 weighted_total
    </div>
  </div>
  <div class="card">
    <h3><span class="icon"></span>迭代概览</h3>
    <div class="bar-chart">
      <div class="bar-row"><div class="bar-label">迭代总数</div>
        <div class="bar-track"><div class="bar-fill" style="width:100%"></div></div>
        <div class="bar-value">{len(iters)}</div></div>
    </div>
  </div>
</div>
{cards}
"""


def _render_quality(data: dict[str, Any]) -> str:
    q = data.get("latest_quality")
    if not q:
        return '<div class="empty-state"><div class="icon">🎯</div><div class="title">暂无质量评分</div><div class="hint">运行 case_optimizer 后会生成 case_quality_*.json</div></div>'

    dims_dict = q.get("dimensions", {})
    dims_list = []
    for k, v in dims_dict.items():
        dims_list.append({
            "key": k,
            "name": v.get("name", k),
            "score": v.get("score", 0),
            "weight": v.get("weight", 0),
            "agent_specific": v.get("agent_specific", False),
            "detail": v.get("detail", {}),
        })
    # 按权重+得分排序
    dims_list.sort(key=lambda x: (x["weight"], x["score"]))

    radar = _svg_radar(dims_list)
    weighted = q.get("weighted_total", 0)
    passes = q.get("passes_threshold", False)
    threshold = q.get("total_threshold", 0.75)
    n_cases = q.get("n_cases", 0)
    low_dims = q.get("low_score_dimensions", [])

    verdict_badge = ('<span class="badge success">通过阈值</span>' if passes
                    else '<span class="badge danger">未通过</span>')

    # 维度卡片
    dim_cards = ""
    for d in dims_list:
        score = d["score"]
        cls = "good" if score >= 0.8 else ("mid" if score >= 0.5 else "low")
        card_cls = "low" if score < 0.5 else ""
        agent_tag = ' <span class="badge violet" style="font-size:9px;padding:1px 6px;">agent</span>' if d["agent_specific"] else ''
        dim_cards += f"""
<div class="dim-card {card_cls}" data-tooltip="{d['name']} | 得分: {score:.3f} | 权重: {d['weight']:.2f}">
  <div class="name">{d['name']}{agent_tag}</div>
  <div class="score {cls}">{score:.3f}</div>
  <div class="weight">权重 {d['weight']:.2f}</div>
</div>"""

    # 低分维度提示
    low_dim_html = ""
    if low_dims:
        low_names = [dims_dict[k].get("name", k) for k in low_dims if k in dims_dict]
        low_dim_html = f"""
<div class="card" style="border-color:rgba(239,68,68,0.3);">
  <h3><span class="icon" style="background:var(--gradient-danger)"></span>低分维度告警</h3>
  <div style="color:var(--text-secondary);font-size:13px;">
    以下维度得分低于阈值，建议在下一轮 case_optimizer 中重点补充用例：
  </div>
  <div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;">
    {"".join(f'<span class="badge danger">{n}</span>' for n in low_names)}
  </div>
</div>"""

    return f"""
<div class="section-grid">
  <div class="card">
    <h3><span class="icon"></span>12 维质量雷达</h3>
    <div class="radar-wrap">{radar}</div>
    <div style="font-size:11px;color:var(--text-muted);text-align:center;">
      hover 圆点查看权重 + 得分 + 状态
    </div>
  </div>
  <div class="card">
    <h3><span class="icon"></span>总览</h3>
    <div class="bar-chart">
      <div class="bar-row">
        <div class="bar-label">加权总分</div>
        <div class="bar-track">
          <div class="bar-fill {'success' if passes else 'danger'}" style="width:{weighted*100:.1f}%"></div>
        </div>
        <div class="bar-value">{weighted:.3f}</div>
      </div>
      <div class="bar-row">
        <div class="bar-label">通过阈值</div>
        <div class="bar-track">
          <div class="bar-fill" style="width:{threshold*100:.1f}%"></div>
        </div>
        <div class="bar-value">{threshold:.2f}</div>
      </div>
    </div>
    <div style="margin-top:14px;display:flex;gap:8px;align-items:center;">
      {verdict_badge}
      <span style="font-size:12px;color:var(--text-muted);">用例数 {n_cases}</span>
    </div>
  </div>
</div>
{low_dim_html}
<div class="card">
  <h3><span class="icon"></span>维度明细（hover 查看详情）</h3>
  <div class="dim-grid">{dim_cards}</div>
</div>
"""


# ---------------------------------------------------------------------------
# HTML 主框架
# ---------------------------------------------------------------------------

JS_TEMPLATE = r"""
const DATA = __DATA_JSON__;

function switchPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const page = document.getElementById('page-' + name);
  if (page) page.classList.add('active');
  const tab = document.querySelector(`.tab[data-page="${name}"]`);
  if (tab) tab.classList.add('active');
  window.scrollTo({top: 0, behavior: 'smooth'});
}

function fmtPath(p) {
  if (!p) return '';
  return p.length > 56 ? p.slice(0, 30) + '…' + p.slice(-24) : p;
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function renderReports() {
  const reports = DATA.reports || [];
  const grid = document.getElementById('reportGrid');
  const empty = document.getElementById('reportEmpty');
  const q = (document.getElementById('reportSearch').value || '').toLowerCase().trim();
  const typeF = document.getElementById('reportType').value;
  const fmtF = document.getElementById('reportFmt').value;

  const filtered = reports.filter(r => {
    if (typeF && r.report_type !== typeF) return false;
    if (fmtF && r.format !== fmtF) return false;
    if (!q) return true;
    const texts = [r.report_id, r.title, r.run_id, r.path,
                   (r.tags || []).join(' '), r.notes || ''].join(' ').toLowerCase();
    return texts.includes(q);
  });

  if (filtered.length === 0) {
    grid.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  grid.innerHTML = filtered.map(r => {
    const typeBadges = {
      run_report: 'info', abtest_report: 'violet', diagnosis: 'warning',
      diagnosis_data: 'warning', html_report: 'info', dashboard: 'violet',
      judges_report: 'success', judges_data: 'success', ci_verdict: 'success',
      pdf_report: 'info', patch_acceptance_log: '', unknown: ''
    };
    const tCls = typeBadges[r.report_type] || '';
    const fmtIcon = r.format === 'html' ? '🌐' : r.format === 'md' ? '📝' :
                   r.format === 'pdf' ? '📄' : '📄';
    const missing = r._exists === false;
    const tagsHtml = (r.tags || []).slice(0, 4)
      .map(t => `<span class="badge" style="font-size:9px;padding:1px 6px;">${escapeHtml(t)}</span>`).join('');
    const previewId = 'preview-' + r.report_id.replace(/[^a-zA-Z0-9_-]/g, '_');
    return `
<div class="report-card ${missing ? 'missing' : ''}" onclick="togglePreview('${previewId}', '${escapeHtml(r.path)}', ${r.format === 'md' ? true : false})">
  <div class="title">${escapeHtml(r.title || r.report_id)}</div>
  <div class="meta-row">
    <span class="badge ${tCls}">${escapeHtml(r.report_type || 'unknown')}</span>
    <span>${fmtIcon} ${escapeHtml(r.format || '')}</span>
    <span>${fmtTs(r.created_at)}</span>
  </div>
  <div class="path" title="${escapeHtml(r.path)}">${escapeHtml(r.path || '')}</div>
  ${tagsHtml ? `<div class="tags">${tagsHtml}</div>` : ''}
  ${r.run_id ? `<div style="font-size:10px;color:var(--text-muted);margin-top:6px;font-family:'SF Mono',Monaco,monospace;">run: ${escapeHtml(r.run_id)}</div>` : ''}
  <div id="${previewId}" style="display:none;"></div>
</div>`;
  }).join('');
}

function fmtTs(ts) {
  if (!ts) return '—';
  return ts.replace('T', ' ').split('+')[0].split('.')[0];
}

let _previewCache = {};
async function togglePreview(id, path, isMd) {
  const el = document.getElementById(id);
  if (el.style.display === 'none') {
    el.style.display = 'block';
    if (!_previewCache[path]) {
      el.innerHTML = '<div style="padding:8px;color:var(--text-muted);">加载中…</div>';
      try {
        // 单文件 portal 是快照模式，无法回读文件；这里给出路径与打开提示
        _previewCache[path] = `<div style="padding:10px;border-radius:6px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);color:var(--success);font-size:12px;margin-bottom:8px;">📂 文件路径：<code style="color:var(--text-primary);">${escapeHtml(path)}</code></div>` +
          (isMd
            ? '<div style="color:var(--text-muted);font-size:11px;">MD 报告：请用文件管理器打开此路径查看完整内容。</div>'
            : '<div style="color:var(--text-muted);font-size:11px;">HTML 报告：双击文件可在浏览器中查看完整交互。</div>');
      } catch (e) {
        _previewCache[path] = '<div style="color:var(--danger);font-size:11px;">读取失败: ' + e.message + '</div>';
      }
    }
    el.innerHTML = _previewCache[path];
  } else {
    el.style.display = 'none';
  }
}

function filterReports() { renderReports(); }

document.addEventListener('DOMContentLoaded', () => {
  renderReports();
});
"""


def render_html(data: dict[str, Any]) -> str:
    overview = _render_overview(data)
    reports = _render_reports(data)
    progress = _render_progress(data)
    iterations = _render_iterations(data)
    quality = _render_quality(data)

    n_reports = data.get("reports_total", 0)
    n_iters = data.get("iterations_total", 0)
    n_sessions = data.get("progress_summary", {}).get("total_sessions", 0)
    n_runs = data.get("run_count", 0)

    js = JS_TEMPLATE.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False, default=str))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Eval — 统一报告门户</title>
<style>{PORTAL_CSS}</style>
</head>
<body>
<div class="container">
  <div class="portal-header">
    <h1>Agent Eval — 统一报告门户</h1>
    <div class="subtitle">报告统一管理 · 进度可视化 · 用例自优化迭代 · 质量看板</div>
    <div class="meta">
      <span>📅 <strong>{_fmt_ts(data.get('generated_at'))}</strong></span>
      <span>📊 <strong>{n_reports}</strong> 报告</span>
      <span>⚡ <strong>{n_sessions}</strong> 进度会话</span>
      <span>🔄 <strong>{n_iters}</strong> 用例迭代</span>
      <span>🎯 <strong>{n_runs}</strong> 评测 Run</span>
    </div>
  </div>

  <div class="tabs">
    <button class="tab active" data-page="Overview" onclick="switchPage('Overview')">📋 Overview</button>
    <button class="tab" data-page="Reports" onclick="switchPage('Reports')">📂 Reports <span class="count">{n_reports}</span></button>
    <button class="tab" data-page="Progress" onclick="switchPage('Progress')">⚡ Progress <span class="count">{n_sessions}</span></button>
    <button class="tab" data-page="Iterations" onclick="switchPage('Iterations')">🔄 Iterations <span class="count">{n_iters}</span></button>
    <button class="tab" data-page="Quality" onclick="switchPage('Quality')">🎯 Quality</button>
  </div>

  <div id="page-Overview" class="page active">{overview}</div>
  <div id="page-Reports" class="page">{reports}</div>
  <div id="page-Progress" class="page">{progress}</div>
  <div id="page-Iterations" class="page">{iterations}</div>
  <div id="page-Quality" class="page">{quality}</div>

  <div class="portal-footer">
    Agent Eval v1.1.1 · 统一报告门户 · 单文件 HTML · 零外部依赖
  </div>
</div>
<script>{js}</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def generate(cfg: C.EvalConfig, output: Path | None = None) -> Path:
    """聚合数据 → 渲染 HTML → 写入 reports/portal.html → 注册到 report_manager。"""
    data = aggregate(cfg)
    html = render_html(data)

    out_path = output or (cfg.reports_dir / "portal.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    # 注册到报告索引
    try:
        RM.register_report(
            cfg,
            path=out_path,
            report_type="portal",
            title=f"统一报告门户 — {data.get('generated_at', '')[:19]}",
            tags=["portal", "v1.1.1"],
            notes="聚合报告索引 + 进度埋点 + 用例迭代 + 质量看板的单文件门户",
        )
    except Exception as e:
        sys.stderr.write(f"[report_portal] 注册到 report_manager 失败（不影响生成）: {e}\n")

    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="统一报告门户生成器")
    ap.add_argument("--config", required=True, help=".agent-eval/config.yaml 路径")
    ap.add_argument("--output", help="输出 HTML 路径（默认 reports/portal.html）")
    args = ap.parse_args()

    cfg_path = Path(args.config).resolve()
    if not cfg_path.exists():
        print(f"[ERROR] config 不存在: {cfg_path}", file=sys.stderr)
        return 1
    cfg = C.EvalConfig.load(cfg_path)

    out = generate(cfg, Path(args.output).resolve() if args.output else None)
    print(f"[report_portal] 门户已生成: {out}")
    print(f"  报告数: {len(RM.list_reports(cfg, missing=False))}")
    print(f"  进度会话: {PT.summary(cfg).get('total_sessions', 0)}")
    print(f"  用例迭代: {len(CIO.load_iterations(cfg))}")
    print(f"  质量文件: {'有' if _load_latest_quality(cfg) else '无'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
