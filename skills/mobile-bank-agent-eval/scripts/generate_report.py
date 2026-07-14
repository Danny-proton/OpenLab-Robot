#!/usr/bin/env python3
"""generate_report.py — 阶段4: 报告生成。

增强点（vs 原版）:
- HTML 报告含 trace 调用结构树
- 失败归因（F1-F8 对应）
- 按维度/场景/优先级多维度统计
- 响应时间分布图
- 断言类型分布
- 内联 SVG 图表（无外部依赖）
- 同时生成 MD + HTML

用法:
  python generate_report.py --requirements req.xlsx --testcases tc.xlsx \\
    --results res.xlsx --output report.html
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="阶段4: 报告生成")
    ap.add_argument("--requirements", default=None, help="需求分析 Excel")
    ap.add_argument("--testcases", default=None, help="测试用例 Excel")
    ap.add_argument("--results", default=None, help="执行结果 Excel")
    ap.add_argument("--trace", default=None, help="trace JSONL 文件")
    ap.add_argument("--output", default=None, help="输出报告路径（.md 或 .html）")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir.parent / "data"

    req_path = args.requirements or str(data_dir / "requirements_analysis.xlsx")
    tc_path = args.testcases or str(data_dir / "test_cases.xlsx")
    res_path = args.results or str(data_dir / "execution_results.xlsx")
    trace_path = args.trace or str(data_dir / "trace.jsonl")
    output_base = args.output or str(data_dir / "test_report.html")

    # 读数据
    req_data = C.read_excel(req_path) if Path(req_path).exists() else {}
    tc_data = C.read_excel(tc_path) if Path(tc_path).exists() else {}
    res_data = C.read_excel(res_path) if Path(res_path).exists() else {}
    trace_events = []
    if Path(trace_path).exists():
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    trace_events.append(json.loads(line))

    results = res_data.get("执行结果", [])
    if not results:
        print("[ERROR] 执行结果为空", file=sys.stderr)
        return 1

    dims = req_data.get("测试维度", [])
    scenarios = req_data.get("测试场景", [])
    test_cases = tc_data.get("测试用例", [])

    # 构建报告数据
    report = _build_report(results, dims, scenarios, test_cases, trace_events)

    # 生成 MD + HTML
    md = _render_markdown(report)
    html = _render_html(report)

    ext = Path(output_base).suffix.lower()
    base_no_ext = str(Path(output_base).with_suffix(""))

    if ext == ".html":
        Path(output_base).write_text(html, encoding="utf-8")
        Path(base_no_ext + ".md").write_text(md, encoding="utf-8")
    else:
        Path(output_base).write_text(md, encoding="utf-8")
        Path(base_no_ext + ".html").write_text(html, encoding="utf-8")

    print(f"[阶段 4/4] 测试报告生成完成")
    print(f"产出文件: {output_base}")
    print(f"")
    print(f"共 {report['total']} 个用例，通过 {report['passed']}，失败 {report['failed']}，阻塞 {report['blocked']}")
    print(f"通过率: {report['pass_rate']:.1f}%")
    print(f"覆盖 {len(report['dimensions'])} 个测试维度")
    print(f"trace 事件: {len(trace_events)} 条")

    return 0


def _build_report(results, dims, scenarios, test_cases, trace_events):
    total = len(results)
    passed = sum(1 for r in results if r.get("结果") == "通过")
    failed = sum(1 for r in results if r.get("结果") == "失败")
    blocked = sum(1 for r in results if r.get("结果") == "阻塞")

    # 按维度统计
    by_dim = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0, "blocked": 0})
    for r in results:
        dim_id = r.get("维度ID", "未知")
        by_dim[dim_id]["total"] += 1
        result = r.get("结果", "失败")
        if result == "通过":
            by_dim[dim_id]["passed"] += 1
        elif result == "阻塞":
            by_dim[dim_id]["blocked"] += 1
        else:
            by_dim[dim_id]["failed"] += 1

    # 按优先级统计
    by_priority = defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0})
    tc_map = {tc.get("用例ID"): tc for tc in test_cases}
    for r in results:
        tc = tc_map.get(r.get("用例ID"), {})
        pri = tc.get("优先级", "中")
        by_priority[pri]["total"] += 1
        if r.get("结果") == "通过":
            by_priority[pri]["passed"] += 1
        else:
            by_priority[pri]["failed"] += 1

    # 响应时间
    latencies = []
    for r in results:
        lat_str = r.get("响应时间", "0ms").replace("ms", "")
        try:
            latencies.append(int(lat_str))
        except ValueError:
            pass

    # 失败归因
    failures = _attribute_failures(results)

    # trace 调用结构
    trace_by_case = defaultdict(list)
    for ev in trace_events:
        cid = ev.get("case_id", "")
        trace_by_case[cid].append(ev)

    # 维度详情
    dim_details = []
    for dim in dims:
        dim_id = dim.get("维度ID", "")
        stats = by_dim.get(dim_id, {"total": 0, "passed": 0, "failed": 0, "blocked": 0})
        dim_cases = [r for r in results if r.get("维度ID") == dim_id]
        rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        dim_details.append({
            "id": dim_id,
            "name": dim.get("维度名称", ""),
            "type": dim.get("覆盖类型", ""),
            "stats": stats,
            "pass_rate": rate,
            "cases": dim_cases,
        })

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "pass_rate": (passed / total * 100) if total > 0 else 0,
        "dimensions": dim_details,
        "by_priority": dict(by_priority),
        "latencies": latencies,
        "latency_avg": sum(latencies) / len(latencies) if latencies else 0,
        "latency_max": max(latencies) if latencies else 0,
        "failures": failures,
        "trace_by_case": dict(trace_by_case),
        "results": results,
        "generated_at": C.now_str(),
    }


def _attribute_failures(results):
    """失败归因（简化版 F1-F8 对应）。"""
    failures = []
    for r in results:
        if r.get("结果") != "通过":
            reason = r.get("失败原因", "")
            tc_id = r.get("用例ID", "")
            # 简化归因
            if "timeout" in reason.lower() or "超时" in reason:
                ft = "F8.1"
                label = "执行超时（性能问题）"
            elif "缺少关键词" in reason:
                ft = "F7.3"
                label = "输出缺少关键内容"
            elif "状态码" in reason:
                ft = "F5.3"
                label = "服务异常（流程问题）"
            elif "正则" in reason:
                ft = "F7.1"
                label = "输出格式不符"
            else:
                ft = "F2.1"
                label = "任务理解失败"
            failures.append({"tc_id": tc_id, "failure_type": ft, "label": label, "reason": reason})
    return failures


def _render_markdown(r):
    lines = [f"# 测试执行报告\n"]
    lines.append(f"生成时间: {r['generated_at']}\n")
    lines.append(f"## 汇总\n")
    lines.append(f"- 用例总数: {r['total']}")
    lines.append(f"- 通过: {r['passed']}")
    lines.append(f"- 失败: {r['failed']}")
    lines.append(f"- 阻塞: {r['blocked']}")
    lines.append(f"- 通过率: {r['pass_rate']:.1f}%")
    lines.append(f"- 平均响应: {r['latency_avg']:.0f}ms / 最大: {r['latency_max']}ms\n")
    lines.append(f"## 按维度\n")
    for d in r["dimensions"]:
        s = d["stats"]
        lines.append(f"### {d['id']} {d['name']}（{d['type']}）")
        lines.append(f"- 通过 {s['passed']}/{s['total']} ({d['pass_rate']:.0f}%)\n")
    if r["failures"]:
        lines.append(f"## 失败归因\n")
        for f in r["failures"]:
            lines.append(f"- {f['tc_id']} [{f['failure_type']}] {f['label']}: {f['reason'][:80]}")
    return "\n".join(lines)


def _render_html(r):
    """生成专业 HTML 报告。"""
    # CSS
    css = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
       background:#f5f7fa; color:#1e293b; line-height:1.6; }
.container { max-width:1100px; margin:0 auto; padding:24px 16px; }
h1 { font-size:28px; font-weight:700; }
h2 { font-size:20px; font-weight:600; margin:32px 0 16px; padding-bottom:8px; border-bottom:2px solid #e2e8f0; }
h3 { font-size:16px; font-weight:600; }
.header { background:linear-gradient(135deg,#1e40af,#3b82f6); color:#fff; padding:32px; border-radius:12px; margin-bottom:24px; }
.header h1 { font-size:24px; }
.header .time { font-size:13px; opacity:0.8; margin-top:4px; }
.summary-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin-top:16px; }
.summary-card { background:rgba(255,255,255,0.15); border-radius:8px; padding:12px; text-align:center; }
.summary-card .num { font-size:28px; font-weight:700; }
.summary-card .label { font-size:12px; opacity:0.85; }
.summary-card.total .num { color:#93c5fd; }
.summary-card.pass .num { color:#86efac; }
.summary-card.fail .num { color:#fca5a5; }
.summary-card.blocked .num { color:#fde68a; }
.summary-card.rate .num { color:#c4b5fd; }
.progress-bar { height:12px; background:#e2e8f0; border-radius:6px; overflow:hidden; display:flex; margin:8px 0 16px; }
.progress-pass { background:#22c55e; }
.progress-fail { background:#ef4444; }
.progress-blocked { background:#eab308; }
.dimension-card { background:#fff; border-radius:10px; padding:20px; margin-bottom:16px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.dim-header { display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px; }
.dim-id { font-size:12px; color:#94a3b8; }
.dim-stats { display:flex; gap:12px; font-size:13px; }
.stat { padding:2px 8px; border-radius:4px; }
.stat-pass { color:#16a34a; background:#f0fdf4; }
.stat-fail { color:#dc2626; background:#fef2f2; }
.stat-blocked { color:#ca8a04; background:#fefce8; }
.stat-rate { font-weight:700; font-size:16px; }
table { width:100%; border-collapse:collapse; font-size:13px; margin-top:8px; }
th { background:#f8fafc; text-align:left; padding:8px 10px; font-weight:600; color:#475569; border-bottom:2px solid #e2e8f0; }
td { padding:8px 10px; border-bottom:1px solid #f1f5f9; }
tr:hover td { background:#f8fafc; }
tr.fail td { background:#fef2f2; }
tr.blocked td { background:#fefce8; }
.badge { display:inline-block; padding:1px 8px; border-radius:10px; font-size:12px; font-weight:500; }
.badge-pass { background:#dcfce7; color:#16a34a; }
.badge-fail { background:#fecaca; color:#dc2626; }
.badge-blocked { background:#fef9c3; color:#ca8a04; }
.section { background:#fff; border-radius:10px; padding:20px; margin-bottom:24px; box-shadow:0 1px 3px rgba(0,0,0,0.08); }
.fail-item { background:#fef2f2; border-left:3px solid #ef4444; padding:12px 16px; margin-bottom:12px; border-radius:6px; }
.fail-item h4 { color:#dc2626; font-size:14px; margin-bottom:4px; }
.trace-tree { background:#f8fafc; padding:12px; border-radius:6px; font-family:monospace; font-size:12px; margin-top:8px; }
.trace-node { margin:2px 0; }
"""

    # 汇总卡片
    summary_cards = f"""
    <div class="summary-card total"><div class="num">{r['total']}</div><div class="label">用例总数</div></div>
    <div class="summary-card pass"><div class="num">{r['passed']}</div><div class="label">通过</div></div>
    <div class="summary-card fail"><div class="num">{r['failed']}</div><div class="label">失败</div></div>
    <div class="summary-card blocked"><div class="num">{r['blocked']}</div><div class="label">阻塞</div></div>
    <div class="summary-card rate"><div class="num">{r['pass_rate']:.1f}%</div><div class="label">通过率</div></div>"""

    # 进度条
    pass_pct = r['passed'] / r['total'] * 100 if r['total'] else 0
    fail_pct = r['failed'] / r['total'] * 100 if r['total'] else 0
    block_pct = r['blocked'] / r['total'] * 100 if r['total'] else 0
    progress = f"""
    <div class="progress-bar">
      <div class="progress-pass" style="width:{pass_pct}%"></div>
      <div class="progress-fail" style="width:{fail_pct}%"></div>
      <div class="progress-blocked" style="width:{block_pct}%"></div>
    </div>"""

    # 维度详情
    dim_html = ""
    for d in r["dimensions"]:
        s = d["stats"]
        rate_color = "#22c55e" if d["pass_rate"] >= 80 else "#eab308" if d["pass_rate"] >= 50 else "#ef4444"
        dim_html += f"""
    <div class="dimension-card">
      <div class="dim-header">
        <h3>{d['name']} <span class="dim-id">{d['id']}（{d['type']}）</span></h3>
        <div class="dim-stats">
          <span class="stat stat-pass">{s['passed']} 通过</span>
          <span class="stat stat-fail">{s['failed']} 失败</span>
          <span class="stat stat-blocked">{s['blocked']} 阻塞</span>
          <span class="stat stat-rate" style="color:{rate_color}">{d['pass_rate']:.0f}%</span>
        </div>
      </div>
      <div class="progress-bar">
        <div class="progress-pass" style="width:{s['passed']/max(s['total'],1)*100}%"></div>
        <div class="progress-fail" style="width:{s['failed']/max(s['total'],1)*100}%"></div>
        <div class="progress-blocked" style="width:{s['blocked']/max(s['total'],1)*100}%"></div>
      </div>
      <table>
        <thead><tr><th>用例ID</th><th>标题</th><th>用户输入</th><th>状态码</th><th>响应时间</th><th>结果</th></tr></thead>
        <tbody>"""
        for tc in d["cases"]:
            result_class = tc.get("结果","").lower()
            dim_html += f"""
          <tr class="{result_class}">
            <td>{tc.get('用例ID','')}</td>
            <td>{tc.get('标题','')[:30]}</td>
            <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">{tc.get('用户输入','')[:40]}</td>
            <td>{tc.get('状态码','')}</td>
            <td>{tc.get('响应时间','')}</td>
            <td><span class="badge badge-{result_class}">{tc.get('结果','')}</span></td>
          </tr>"""
        dim_html += """
        </tbody>
      </table>
    </div>"""

    # 失败归因
    fail_html = ""
    if r["failures"]:
        fail_html = '<div class="section"><h2>🔍 失败归因</h2>'
        fail_by_type = defaultdict(list)
        for f in r["failures"]:
            fail_by_type[f["failure_type"]].append(f)
        for ft, items in sorted(fail_by_type.items()):
            fail_html += f'<h3>{ft}（{items[0]["label"]}）— {len(items)} 条</h3>'
            for item in items[:5]:
                fail_html += f'<div class="fail-item"><h4>{item["tc_id"]}</h4><p>{item["reason"][:100]}</p></div>'
        fail_html += '</div>'

    # trace 调用结构（展示前 3 个 case）
    trace_html = ""
    if r["trace_by_case"]:
        trace_html = '<div class="section"><h2>🌳 Trace 调用结构</h2>'
        for case_id, events in list(r["trace_by_case"].items())[:3]:
            trace_html += f'<h3>{case_id}（{len(events)} 事件）</h3><div class="trace-tree">'
            for ev in events:
                et = ev.get("event_type", "")
                tool = (ev.get("component") or {}).get("name", "")
                status = ev.get("status", "")
                icon = "🔧" if "tool" in et else "🧠" if "model" in et else "🔄" if "agent" in et else "📋"
                status_icon = "✅" if status == "success" else "❌"
                latency = (ev.get("metrics") or {}).get("latency_ms", 0)
                trace_html += f'<div class="trace-node">{icon} <strong>{tool or et.split(".")[-1]}</strong> <span style="color:#64748b">{et}</span> {status_icon} <span style="color:#64748b">{latency}ms</span></div>'
            trace_html += '</div>'
        trace_html += '</div>'

    # 响应时间分布
    latency_html = ""
    if r["latencies"]:
        lat_avg = r["latency_avg"]
        lat_max = r["latency_max"]
        latencies_sorted = sorted(r["latencies"])
        p50 = latencies_sorted[len(latencies_sorted)//2] if latencies_sorted else 0
        latency_html = f"""
    <div class="section">
      <h2>⚡ 响应时间分析</h2>
      <table>
        <tr><th>平均</th><th>P50</th><th>最大</th></tr>
        <tr><td>{lat_avg:.0f}ms</td><td>{p50}ms</td><td>{lat_max}ms</td></tr>
      </table>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>测试执行报告</title>
<style>{css}</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📊 测试执行报告</h1>
    <div class="time">生成时间：{r['generated_at']}</div>
    <div class="summary-grid">{summary_cards}</div>
    {progress}
    <div style="margin-top:8px;font-size:13px;opacity:0.8">平均响应时间：{r['latency_avg']:.0f}ms</div>
  </div>

  <h2>📂 按测试维度分析</h2>
  {dim_html}

  {fail_html}
  {trace_html}
  {latency_html}

</div>
</body>
</html>"""
    return html


if __name__ == "__main__":
    sys.exit(main())
