#!/usr/bin/env python3
"""dashboard.py — v1 交互式 Dashboard 生成器。

生成单文件 HTML Dashboard，10 个页面可切换：
1. Overview       总览
2. Scenario       场景覆盖
3. Failures       失败探索
4. TraceViewer    Trace 查看器
5. ToolGraph      工具调用图
6. Optimization   优化历史
7. PatchCompare   Patch 对比
8. Regression     回归监控
9. Judges         Judge 分歧
10. CostLatency  成本/延迟分析

所有数据内联为 JS 对象，无外部依赖，可本地打开。

用法:
  python dashboard.py --config .agent-eval/config.yaml
  # 会聚合所有 run 的数据，生成 .agent-eval/reports/dashboard.html
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


def _h(s) -> str:
    return html.escape(str(s) if s is not None else "")


def collect_all_data(cfg: C.EvalConfig) -> dict:
    """聚合所有 run 的数据。"""
    runs_data = []
    for p in sorted((cfg.scores_dir).glob("*.json")):
        if p.name.endswith(".charts.json") or p.name.endswith(".deepeval.json") or ".opik_" in p.name or p.name.endswith(".candidates.json"):
            continue
        try:
            score = json.loads(p.read_text(encoding="utf-8"))
            run_id = score.get("run_id", p.stem)
            agg = score.get("aggregate", {})

            # 加载 charts
            charts_path = cfg.scores_dir / f"{run_id}.charts.json"
            charts_data = {}
            if charts_path.exists():
                charts_data = json.loads(charts_path.read_text(encoding="utf-8"))

            # 加载 diagnosis
            diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
            diag = {}
            if diag_path.exists():
                diag = json.loads(diag_path.read_text(encoding="utf-8"))

            # 加载 judges
            judges_path = cfg.reports_dir / f"{run_id}_judges.json"
            judges = {}
            if judges_path.exists():
                judges = json.loads(judges_path.read_text(encoding="utf-8"))

            runs_data.append({
                "run_id": run_id,
                "aggregate": agg,
                "per_case": score.get("per_case", []),
                "charts": charts_data,
                "diagnosis": diag,
                "judges": judges,
            })
        except Exception as e:
            sys.stderr.write(f"[dashboard] skip {p}: {e}\n")
            continue

    # 加载 regression trend
    trend_path = cfg.root / "regression_trend.jsonl"
    trend = C.load_jsonl(trend_path) if trend_path.exists() else []

    # 加载 accepted patches
    accepted_path = cfg.reports_dir / "accepted_patches.md"
    accepted_count = 0
    if accepted_path.exists():
        accepted_count = accepted_path.read_text(encoding="utf-8").count("## ")

    return {
        "runs": runs_data,
        "regression_trend": trend,
        "accepted_patch_count": accepted_count,
        "n_runs": len(runs_data),
    }


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
       background: #0f172a; color: #e2e8f0; }
.app { display: flex; min-height: 100vh; }
.sidebar { width: 220px; background: #1e293b; padding: 20px 0; flex-shrink: 0;
           border-right: 1px solid #334155; position: fixed; height: 100vh; overflow-y: auto; }
.sidebar h1 { font-size: 16px; padding: 0 20px 20px; color: #60a5fa; border-bottom: 1px solid #334155; }
.nav-item { padding: 12px 20px; cursor: pointer; color: #94a3b8; font-size: 14px;
            border-left: 3px solid transparent; transition: all 0.15s; }
.nav-item:hover { background: #334155; color: #e2e8f0; }
.nav-item.active { background: #1e3a5f; color: #60a5fa; border-left-color: #60a5fa; }
.main { margin-left: 220px; padding: 32px; flex: 1; }
.page { display: none; }
.page.active { display: block; }
.page h2 { font-size: 24px; margin-bottom: 20px; color: #f1f5f9; }
.card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px;
        margin-bottom: 16px; }
.card h3 { font-size: 14px; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase;
           letter-spacing: 0.5px; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
.stat { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; }
.stat .label { font-size: 12px; color: #94a3b8; text-transform: uppercase; }
.stat .value { font-size: 28px; font-weight: 700; color: #f1f5f9; margin: 4px 0; }
.stat .sub { font-size: 12px; color: #64748b; }
.stat.good .value { color: #4ade80; }
.stat.bad .value { color: #f87171; }
.stat.warn .value { color: #fbbf24; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid #334155; }
th { color: #94a3b8; font-weight: 600; font-size: 12px; text-transform: uppercase; }
td { color: #e2e8f0; }
.badge { padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge.pass { background: #166534; color: #4ade80; }
.badge.fail { background: #7f1d1d; color: #f87171; }
.badge.warn { background: #78350f; color: #fbbf24; }
.badge.accept { background: #166534; color: #4ade80; }
.badge.reject { background: #7f1d1d; color: #f87171; }
select, button { background: #334155; color: #e2e8f0; border: 1px solid #475569;
                 padding: 6px 12px; border-radius: 4px; font-size: 13px; cursor: pointer; }
select:hover, button:hover { background: #475569; }
.chart-container { background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 16px; }
.heatmap-cell { display: inline-block; width: 40px; height: 40px; margin: 2px;
                border-radius: 4px; text-align: center; line-height: 40px; font-size: 11px;
                font-weight: 600; cursor: pointer; }
.timeline-step { display: inline-block; width: 32px; height: 32px; margin: 1px;
                 border-radius: 4px; text-align: center; line-height: 32px; font-size: 9px;
                 font-weight: 600; color: white; cursor: pointer; }
.judge-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.judge-bar .name { width: 160px; font-size: 13px; }
.judge-bar .track { flex: 1; height: 20px; background: #334155; border-radius: 4px; overflow: hidden; }
.judge-bar .fill { height: 100%; border-radius: 4px; }
"""


JS_TEMPLATE = """
const DATA = __DATA_PLACEHOLDER__;

function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + id).classList.add('active');
  document.querySelector(`.nav-item[data-page="${id}"]`).classList.add('active');
}

function colorFor(score) {
  if (score >= 0.9) return '#4ade80';
  if (score >= 0.7) return '#a7f3d0';
  if (score >= 0.5) return '#fbbf24';
  if (score >= 0.3) return '#fb923c';
  return '#f87171';
}

function renderOverview() {
  const runs = DATA.runs;
  const latest = runs[runs.length - 1] || {};
  const agg = latest.aggregate || {};
  const html = `
    <div class="stat-grid">
      <div class="stat"><div class="label">总 Run 数</div><div class="value">${DATA.n_runs}</div><div class="sub">历史评测次数</div></div>
      <div class="stat ${agg.n_hard_fail ? 'bad' : 'good'}"><div class="label">最新硬失败</div><div class="value">${agg.n_hard_fail || 0}</div><div class="sub">${agg.n_cases || 0} cases</div></div>
      <div class="stat"><div class="label">最新总分</div><div class="value">${(agg.weighted_score || 0).toFixed(3)}</div><div class="sub">满分 1.000</div></div>
      <div class="stat"><div class="label">已接受 Patch</div><div class="value">${DATA.accepted_patch_count}</div><div class="sub">累计</div></div>
      <div class="stat"><div class="label">回归测试</div><div class="value">${DATA.regression_trend.length}</div><div class="sub">次数</div></div>
      <div class="stat"><div class="label">最新 Latency</div><div class="value">${agg.latency_p50 || 0}<span style="font-size:14px">ms</span></div><div class="sub">p50</div></div>
    </div>
    <div class="card"><h3>最近 Runs</h3>
      <table><thead><tr><th>run_id</th><th>分数</th><th>硬失败</th><th>latency p50</th></tr></thead><tbody>
        ${runs.slice(-10).reverse().map(r => `
          <tr><td><code>${r.run_id}</code></td>
              <td>${(r.aggregate?.weighted_score || 0).toFixed(3)}</td>
              <td><span class="badge ${r.aggregate?.n_hard_fail ? 'fail' : 'pass'}">${r.aggregate?.n_hard_fail || 0}</span></td>
              <td>${r.aggregate?.latency_p50 || 0}ms</td></tr>
        `).join('')}
      </tbody></table>
    </div>`;
  document.getElementById('page-overview').innerHTML = html;
}

function renderScenario() {
  const runs = DATA.runs;
  const options = runs.map(r => `<option value="${r.run_id}">${r.run_id}</option>`).join('');
  const html = `
    <div class="card"><h3>选择 Run</h3>
      <select id="scenario-select" onchange="updateScenario()">${options}</select>
    </div>
    <div id="scenario-content"></div>`;
  document.getElementById('page-scenario').innerHTML = html;
  if (DATA.runs.length > 0) updateScenario();
}

function updateScenario() {
  const runId = document.getElementById('scenario-select').value;
  const run = DATA.runs.find(r => r.run_id === runId);
  const sb = (run?.charts?.scenario_bar) || [];
  const html = `
    <div class="card"><h3>场景通过率</h3>
      ${sb.map(s => `
        <div class="judge-bar">
          <div class="name">${s.scenario}</div>
          <div class="track"><div class="fill" style="width:${s.pass_rate*100}%;background:${colorFor(s.pass_rate)}"></div></div>
          <div style="width:80px;text-align:right">${(s.pass_rate*100).toFixed(1)}%</div>
        </div>
      `).join('')}
    </div>`;
  document.getElementById('scenario-content').innerHTML = html;
}

function renderFailures() {
  const runs = DATA.runs;
  const options = runs.map(r => `<option value="${r.run_id}">${r.run_id}</option>`).join('');
  const html = `
    <div class="card"><h3>选择 Run</h3>
      <select id="failures-select" onchange="updateFailures()">${options}</select>
    </div>
    <div id="failures-content"></div>`;
  document.getElementById('page-failures').innerHTML = html;
  if (DATA.runs.length > 0) updateFailures();
}

function updateFailures() {
  const runId = document.getElementById('failures-select').value;
  const run = DATA.runs.find(r => r.run_id === runId);
  const diag = run?.diagnosis || {};
  const byType = diag.by_failure_type || {};
  const diags = diag.diagnoses || [];
  const total = Object.values(byType).reduce((a,b) => a+b, 0) || 1;
  const html = `
    <div class="card"><h3>失败 Pareto</h3>
      ${Object.entries(byType).sort((a,b) => b[1]-a[1]).map(([t,n]) => `
        <div class="judge-bar">
          <div class="name">${t}</div>
          <div class="track"><div class="fill" style="width:${(n/total*100)}%;background:#f87171"></div></div>
          <div style="width:80px;text-align:right">${n} (${(n/total*100).toFixed(1)}%)</div>
        </div>
      `).join('')}
    </div>
    <div class="card"><h3>失败详情 (${diags.length})</h3>
      <table><thead><tr><th>case_id</th><th>类型</th><th>建议修改</th><th>mutation</th></tr></thead><tbody>
        ${diags.map(d => `
          <tr><td><code>${d.case_id}</code></td>
              <td><span class="badge warn">${d.failure_type}</span></td>
              <td>${d.suggested_mutation_target}</td>
              <td><code>${d.suggested_mutation_rule}</code></td></tr>
        `).join('')}
      </tbody></table>
    </div>`;
  document.getElementById('failures-content').innerHTML = html;
}

function renderTraceViewer() {
  const runs = DATA.runs;
  const options = runs.map(r => `<option value="${r.run_id}">${r.run_id}</option>`).join('');
  const html = `
    <div class="card"><h3>选择 Run 和 Case</h3>
      <select id="trace-run" onchange="updateTraceCases()">${options}</select>
      <select id="trace-case" onchange="renderTrace()"></select>
    </div>
    <div id="trace-content"></div>`;
  document.getElementById('page-trace').innerHTML = html;
  // 关键修复：填充 case 下拉框并渲染默认 trace
  if (runs.length > 0) updateTraceCases();
}

function updateTraceCases() {
  const runId = document.getElementById('trace-run').value;
  const run = DATA.runs.find(r => r.run_id === runId);
  const timelines = run?.charts?.trace_timeline || [];
  document.getElementById('trace-case').innerHTML = timelines.map(t =>
    `<option value="${t.case_id}">${t.case_id}</option>`).join('');
  renderTrace();
}

function renderTrace() {
  const runId = document.getElementById('trace-run').value;
  const caseId = document.getElementById('trace-case').value;
  const run = DATA.runs.find(r => r.run_id === runId);
  const timelines = run?.charts?.trace_timeline || [];
  const tl = timelines.find(t => t.case_id === caseId);
  if (!tl) { document.getElementById('trace-content').innerHTML = '<div class="card">无数据</div>'; return; }
  const colors = {
    'agent.run.start': '#3b82f6', 'agent.run.end': '#22c55e',
    'model.call.start': '#a855f7', 'model.call.end': '#c084fc',
    'tool.call.start': '#06b6d4', 'tool.call.end': '#0ea5e9',
    'tool.call.error': '#ef4444', 'planner.step': '#64748b',
  };
  const iconFor = (et) => et.includes('tool') ? '🔧' : et.includes('model') ? '🧠' : et.includes('agent') ? '🔄' : '📋';

  const html = `
    <div class="card"><h3>${caseId} (${tl.steps.length} steps)</h3>
      <div>${tl.steps.map((s, i) => {
        const c = colors[s.event_type] || '#64748b';
        const label = (s.tool || s.event_type.split('.').pop()).slice(0,3);
        return `<span class="timeline-step" style="background:${c};${s.status==='error'?'outline:2px solid #ef4444':''}" title="step ${s.step}: ${s.event_type} ${s.tool||''} (${s.latency_ms||0}ms)">${label}</span>`;
      }).join('')}</div>
    </div>
    <div class="card"><h3>🌳 调用结构</h3>
      <div style="font-family:monospace;font-size:13px;line-height:1.8">
        ${tl.steps.map(s => {
          const c = colors[s.event_type] || '#64748b';
          const icon = iconFor(s.event_type);
          const label = s.tool || s.event_type.split('.').pop();
          const st = s.status === 'success' ? '✅' : '❌';
          return `<div>${icon} <span style="color:${c};font-weight:600">${label}</span> <span style="color:#64748b;font-size:11px">${s.event_type}</span> ${st} <span style="color:#64748b;font-size:11px">${s.latency_ms||0}ms</span></div>`;
        }).join('')}
      </div>
    </div>
    <div class="card"><h3>📋 调用链详情（含参数/结果）</h3>
      <div style="overflow-x:auto">
        <table><thead><tr><th>step</th><th>event</th><th>tool</th><th>arguments</th><th>result</th><th>status</th><th>latency</th></tr></thead><tbody>
          ${tl.steps.map(s => {
            const args = s.arguments ? JSON.stringify(s.arguments).slice(0,80) : '-';
            const result = s.result ? String(s.result).slice(0,80) : '-';
            return `<tr><td>${s.step}</td><td><code>${s.event_type}</code></td><td>${s.tool||'-'}</td><td style="font-size:11px;color:#94a3b8;max-width:200px;overflow:hidden;text-overflow:ellipsis">${args}</td><td style="font-size:11px;color:#94a3b8;max-width:200px;overflow:hidden;text-overflow:ellipsis">${result}</td><td><span class="badge ${s.status==='error'?'fail':'pass'}">${s.status}</span></td><td>${s.latency_ms||0}ms</td></tr>`;
          }).join('')}
        </tbody></table>
      </div>
    </div>`;
  document.getElementById('trace-content').innerHTML = html;
}

function renderToolGraph() {
  const runs = DATA.runs;
  const options = runs.map(r => `<option value="${r.run_id}">${r.run_id}</option>`).join('');
  const html = `
    <div class="card"><h3>选择 Run</h3>
      <select id="toolgraph-select" onchange="updateToolGraph()">${options}</select>
    </div>
    <div id="toolgraph-content"></div>`;
  document.getElementById('page-toolgraph').innerHTML = html;
  if (DATA.runs.length > 0) updateToolGraph();
}

function updateToolGraph() {
  const runId = document.getElementById('toolgraph-select').value;
  const run = DATA.runs.find(r => r.run_id === runId);
  const graph = run?.charts?.tool_call_graph || {};
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const maxCount = Math.max(...nodes.map(n => n.count), 1);
  const html = `
    <div class="card"><h3>工具调用频次 (${nodes.length} 个工具)</h3>
      ${nodes.map(n => `
        <div class="judge-bar">
          <div class="name"><code>${n.id}</code></div>
          <div class="track"><div class="fill" style="width:${(n.count/maxCount*100)}%;background:#3b82f6"></div></div>
          <div style="width:60px;text-align:right">${n.count}</div>
        </div>
      `).join('')}
    </div>
    <div class="card"><h3>调用顺序 (${edges.length} 条边)</h3>
      <table><thead><tr><th>从</th><th>到</th><th>次数</th></tr></thead><tbody>
        ${edges.map(e => `<tr><td><code>${e.from}</code></td><td><code>${e.to}</code></td><td>${e.count}</td></tr>`).join('')}
      </tbody></table>
    </div>`;
  document.getElementById('toolgraph-content').innerHTML = html;
}

function renderOptimization() {
  const curve = [];
  DATA.runs.forEach(r => {
    curve.push({run_id: r.run_id, score: r.aggregate?.weighted_score || 0,
                hard_fail: r.aggregate?.n_hard_fail || 0});
  });
  const html = `
    <div class="card"><h3>迭代曲线</h3>
      <div>分数趋势: ${curve.map((c,i) => {
        const h = c.score * 200;
        return `<span class="timeline-step" style="background:${colorFor(c.score)};width:40px;height:${h}px;vertical-align:bottom;writing-mode:vertical-lr" title="${c.run_id}: ${c.score.toFixed(3)}">${c.score.toFixed(2)}</span>`;
      }).join('')}</div>
    </div>
    <div class="card"><h3>已接受 Patch: ${DATA.accepted_patch_count}</h3></div>`;
  document.getElementById('page-optimization').innerHTML = html;
}

function renderPatchCompare() {
  // 找所有 abtest verdict
  const verdicts = [];
  DATA.runs.forEach(r => {
    if (r.judges?.gatekeeper) {
      verdicts.push({run_id: r.run_id, verdict: r.judges.gatekeeper.verdict,
                     rationale: r.judges.gatekeeper.decision_rationale});
    }
  });
  const html = `
    <div class="card"><h3>Patch 决策历史</h3>
      <table><thead><tr><th>run_id</th><th>verdict</th><th>理由</th></tr></thead><tbody>
        ${verdicts.map(v => `<tr><td><code>${v.run_id}</code></td>
          <td><span class="badge ${v.verdict==='ACCEPT'?'accept':'reject'}">${v.verdict}</span></td>
          <td>${v.rationale}</td></tr>`).join('')}
      </tbody></table>
    </div>`;
  document.getElementById('page-patchcompare').innerHTML = html;
}

function renderRegression() {
  const trend = DATA.regression_trend || [];
  const html = `
    <div class="card"><h3>回归测试历史 (${trend.length})</h3>
      <table><thead><tr><th>时间</th><th>run_id</th><th>分数</th><th>硬失败</th><th>结果</th></tr></thead><tbody>
        ${trend.map(t => `<tr><td>${t.ts}</td><td><code>${t.current_run_id}</code></td>
          <td>${(t.weighted_score||0).toFixed(3)}</td><td>${t.n_hard_fail||0}</td>
          <td><span class="badge ${t.passed?'pass':'fail'}">${t.passed?'PASS':'FAIL'}</span></td></tr>`).join('')}
      </tbody></table>
    </div>`;
  document.getElementById('page-regression').innerHTML = html;
}

function renderJudges() {
  const runs = DATA.runs;
  const options = runs.map(r => `<option value="${r.run_id}">${r.run_id}</option>`).join('');
  const html = `
    <div class="card"><h3>选择 Run</h3>
      <select id="judges-select" onchange="updateJudges()">${options}</select>
    </div>
    <div id="judges-content"></div>`;
  document.getElementById('page-judges').innerHTML = html;
  if (DATA.runs.length > 0) updateJudges();
}

function updateJudges() {
  const runId = document.getElementById('judges-select').value;
  const run = DATA.runs.find(r => r.run_id === runId);
  const judges = run?.judges || {};
  const all = judges.all_judges || [];
  // 按 judge 名聚合
  const byJudge = {};
  all.forEach(j => { byJudge[j.judge] = byJudge[j.judge] || []; byJudge[j.judge].push(j); });
  const am = judges.agreement_matrix || {};
  const html = `
    <div class="card"><h3>Judge 平均分</h3>
      ${Object.entries(byJudge).map(([name, js]) => {
        const avg = js.reduce((a,j) => a + (j.score||0), 0) / js.length;
        return `<div class="judge-bar">
          <div class="name">${name}</div>
          <div class="track"><div class="fill" style="width:${avg*100}%;background:${colorFor(avg)}"></div></div>
          <div style="width:60px;text-align:right">${avg.toFixed(2)}</div>
        </div>`;
      }).join('')}
    </div>
    <div class="card"><h3>Judge Agreement Matrix (avg: ${am.avg_agreement || 1.0})</h3>
      <table><thead><tr><th>Judge 对</th><th>一致率</th></tr></thead><tbody>
        ${Object.entries(am.matrix || {}).map(([k,v]) => `<tr><td>${k}</td><td><span class="badge ${v>=0.7?'pass':v>=0.5?'warn':'fail'}">${v}</span></td></tr>`).join('')}
      </tbody></table>
    </div>
    <div class="card"><h3>Gatekeeper: <span class="badge ${judges.gatekeeper?.verdict==='ACCEPT'?'accept':'reject'}">${judges.gatekeeper?.verdict || '?'}</span></h3>
      <p>${judges.gatekeeper?.decision_rationale || ''}</p></div>`;
  document.getElementById('judges-content').innerHTML = html;
}

function renderCostLatency() {
  const runs = DATA.runs;
  const html = `
    <div class="card"><h3>Latency 趋势</h3>
      <table><thead><tr><th>run_id</th><th>latency p50</th><th>latency mean</th></tr></thead><tbody>
        ${runs.map(r => `<tr><td><code>${r.run_id}</code></td>
          <td>${r.aggregate?.latency_p50 || 0}ms</td>
          <td>${r.aggregate?.latency_mean || 0}ms</td></tr>`).join('')}
      </tbody></table>
    </div>`;
  document.getElementById('page-costlatency').innerHTML = html;
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
  renderOverview();
  renderScenario();
  renderFailures();
  renderTraceViewer();
  renderToolGraph();
  renderOptimization();
  renderPatchCompare();
  renderRegression();
  renderJudges();
  renderCostLatency();
  // 关键修复：显示默认页面（否则所有 page 都是 display:none）
  showPage('overview');
});
"""


def generate_dashboard(cfg: C.EvalConfig) -> Path:
    """生成交互式 dashboard。"""
    data = collect_all_data(cfg)
    data_json = json.dumps(data, ensure_ascii=False)

    nav_items = [
        ("overview", "1. Overview"),
        ("scenario", "2. Scenario"),
        ("failures", "3. Failures"),
        ("trace", "4. Trace Viewer"),
        ("toolgraph", "5. Tool Graph"),
        ("optimization", "6. Optimization"),
        ("patchcompare", "7. Patch Compare"),
        ("regression", "8. Regression"),
        ("judges", "9. Judges"),
        ("costlatency", "10. Cost/Latency"),
    ]
    nav_html = "".join(
        f'<div class="nav-item" data-page="{pid}" onclick="showPage(\'{pid}\')">{label}</div>'
        for pid, label in nav_items
    )
    pages_html = "".join(f'<div class="page" id="page-{pid}"></div>' for pid, _ in nav_items)

    js = JS_TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Agent Eval Dashboard</title>
<style>{CSS}</style>
</head>
<body>
<div class="app">
  <div class="sidebar">
    <h1>📊 Agent Eval<br><span style="font-size:12px;color:#64748b">v1 Dashboard</span></h1>
    {nav_html}
  </div>
  <div class="main">
    {pages_html}
  </div>
</div>
<script>{js}</script>
</body>
</html>
"""
    out = cfg.reports_dir / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    try:
        import report_manager as RM
        RM.register_report(cfg, out, title="交互式 Dashboard")
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    out = generate_dashboard(cfg)
    print(f"[dashboard] 生成完成: {out}")
    print(f"[dashboard] 聚合了 {len(list((cfg.scores_dir).glob('*.json')))} 个 run 的数据")
    return 0


if __name__ == "__main__":
    sys.exit(main())
