"""
mobileAgentTest - 测试报告生成
读取需求分析、测试用例、执行结果，生成 Markdown 和 HTML 格式的测试报告。

Usage:
    python generate_report.py --requirements path/to/requirements_analysis.xlsx
                              --testcases path/to/test_cases.xlsx
                              --results path/to/execution_results.xlsx
                              --output path/to/report(.md|.html)
"""
import sys
import json
import os
import re
import argparse
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", default=None, help="需求分析 Excel 文件路径")
    parser.add_argument("--testcases", default=None, help="测试用例 Excel 文件路径")
    parser.add_argument("--results", default=None, help="执行结果 Excel 文件路径")
    parser.add_argument("--output", default=None, help="输出报告文件路径（.md 或 .html）")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "..", "data")

    req_path = _resolve_path(args.requirements or os.path.join(data_dir, "requirements_analysis.xlsx"))
    tc_path = _resolve_path(args.testcases or os.path.join(data_dir, "test_cases.xlsx"))
    res_path = _resolve_path(args.results or os.path.join(data_dir, "execution_results.xlsx"))
    output_base = args.output or os.path.join(data_dir, "test_report.md")

    for p, name in [(req_path, "需求分析"), (tc_path, "测试用例"), (res_path, "执行结果")]:
        if not os.path.exists(p):
            print(f"[ERROR] {name} 文件不存在: {p}", file=sys.stderr)
            print(f"      尝试路径: {p}", file=sys.stderr)
            sys.exit(1)

    dims, scenarios, dim_scenario_map = _read_requirements(req_path)
    test_cases = _read_excel_rows(tc_path)
    results = _read_excel_rows(res_path)

    if not results:
        print("[ERROR] 执行结果为空", file=sys.stderr)
        sys.exit(1)

    report_data = _build_report_data(dims, scenarios, dim_scenario_map, test_cases, results)

    md = _render_markdown(report_data)
    html = _render_html(report_data)

    ext = os.path.splitext(output_base)[1].lower()
    base_no_ext = os.path.splitext(output_base)[0]

    if ext == ".html":
        _save_output(output_base, html, "html")
        _save_output(base_no_ext + ".md", md, "md")
    else:
        _save_output(output_base, md, "md")
        _save_output(base_no_ext + ".html", html, "html")

    print(f"[阶段 4/4] 测试报告生成完成")
    print(f"产出文件：data/{os.path.basename(output_path)}")
    print(f"")
    print(f"共 {report_data['total']} 个用例，通过 {report_data['passed']}，失败 {report_data['failed']}，阻塞 {report_data['blocked']}")
    print(f"通过率：{report_data['pass_rate']:.1f}%")
    print(f"覆盖 {len(report_data['dimensions'])} 个测试维度")


def _resolve_path(path):
    path = os.path.abspath(path)
    if os.path.exists(path):
        return path
    sess_out = os.getenv("SESSION_OUTPUT_DIR", "")
    if sess_out:
        alt = os.path.join(sess_out, "dataset", os.path.basename(path))
        if os.path.exists(alt):
            return alt
    return path


def _read_excel_rows(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h or "") for h in rows[0]]
    data = []
    for row in rows[1:]:
        r = {}
        for i, v in enumerate(row):
            if i < len(headers):
                r[headers[i]] = str(v or "")
        if r.get(headers[0], ""):
            data.append(r)
    return data


def _read_requirements(path):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    dims = []
    scenarios = []
    dim_scenario_map = {}

    for name in wb.sheetnames:
        if "维度" in name:
            ws = wb[name]
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                h = [str(x or "") for x in rows[0]]
                for row in rows[1:]:
                    if row and row[0]:
                        dims.append({h[i]: str(row[i] or "") for i in range(len(h)) if i < len(row)})
        if "场景" in name:
            ws = wb[name]
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                h = [str(x or "") for x in rows[0]]
                for row in rows[1:]:
                    if row and row[0]:
                        s = {h[i]: str(row[i] or "") for i in range(len(h)) if i < len(row)}
                        scenarios.append(s)
                        dim_id = s.get(h[1], "") if len(h) > 1 else ""
                        dim_scenario_map.setdefault(dim_id, []).append(s[list(s.keys())[0]])

    return dims, scenarios, dim_scenario_map


def _build_report_data(dims, scenarios, dim_scenario_map, test_cases, results):
    tc_map = {}
    for tc in test_cases:
        keys = list(tc.keys())
        if keys:
            tc_map[tc[keys[0]]] = tc

    scenario_map = {}
    for s in scenarios:
        keys = list(s.keys())
        if keys:
            scenario_map[s[keys[0]]] = s

    total = len(results)
    passed = sum(1 for r in results if r.get(list(r.keys())[-1], "") == "通过")
    failed = sum(1 for r in results if r.get(list(r.keys())[-1], "") == "失败")
    blocked = total - passed - failed

    total_ms = 0
    count_ms = 0
    for r in results:
        rt = r.get("响应时间", "0ms")
        digits = re.sub(r"[^\d]", "", rt)
        if digits:
            total_ms += int(digits)
            count_ms += 1
    avg_ms = total_ms / count_ms if count_ms else 0

    dim_results = {}
    for d in dims:
        d_id = d.get(list(d.keys())[0], "")
        dim_results[d_id] = {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "cases": []}

    for r in results:
        keys = list(r.keys())
        tc_id = r[keys[0]]
        scenario_id = r[keys[1]] if len(keys) > 1 else ""

        sc = scenario_map.get(scenario_id, {})
        sc_keys = list(sc.keys())
        dim_id = sc[sc_keys[1]] if len(sc_keys) > 1 else ""

        tc = tc_map.get(tc_id, {})
        status = r[keys[-1]]

        rt = r.get("响应时间", "0ms")
        digits = re.sub(r"[^\d]", "", rt)

        case_info = {
            "tc_id": tc_id,
            "scenario_id": scenario_id,
            "title": r.get(keys[2], "") if len(keys) > 2 else "",
            "user_input": tc.get("用户输入", ""),
            "priority": tc.get("优先级", ""),
            "status": status,
            "response_time": rt,
            "status_code": r.get("状态码", ""),
            "expected": tc.get("预期结果", ""),
            "actual": r.get(list(r.keys())[-1], ""),
        }

        if dim_id in dim_results:
            dim_results[dim_id]["total"] += 1
            dim_results[dim_id]["cases"].append(case_info)
            if status == "通过":
                dim_results[dim_id]["passed"] += 1
            elif status == "失败":
                dim_results[dim_id]["failed"] += 1
            else:
                dim_results[dim_id]["blocked"] += 1
        else:
            dim_results.setdefault("未归类", {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "cases": []})
            dim_results["未归类"]["total"] += 1
            dim_results["未归类"]["cases"].append(case_info)
            if status == "通过":
                dim_results["未归类"]["passed"] += 1
            elif status == "失败":
                dim_results["未归类"]["failed"] += 1
            else:
                dim_results["未归类"]["blocked"] += 1

    dim_list = []
    for d in dims:
        d_id = d.get(list(d.keys())[0], "")
        dr = dim_results.get(d_id, {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "cases": []})
        dr["dim_id"] = d_id
        dr["dim_name"] = d.get(list(d.keys())[1] if len(list(d.keys())) > 1 else "", d_id)
        dim_list.append(dr)

    if "未归类" in dim_results:
        dim_list.append({
            "dim_id": "-",
            "dim_name": "未归类",
            "total": dim_results["未归类"]["total"],
            "passed": dim_results["未归类"]["passed"],
            "failed": dim_results["未归类"]["failed"],
            "blocked": dim_results["未归类"]["blocked"],
            "cases": dim_results["未归类"]["cases"],
        })

    pass_rate = (passed / total * 100) if total else 0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "pass_rate": pass_rate,
        "avg_response_ms": avg_ms,
        "dimensions": dim_list,
    }


def _render_markdown(data):
    lines = []
    lines.append("# 测试执行报告")
    lines.append("")
    lines.append(f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 一、执行摘要")
    lines.append("")
    lines.append(f"- **用例总数**：{data['total']}")
    lines.append(f"- **通过**：{data['passed']} ({data['pass_rate']:.1f}%)")
    lines.append(f"- **失败**：{data['failed']} ({data['failed']/data['total']*100 if data['total'] else 0:.1f}%)")
    lines.append(f"- **阻塞**：{data['blocked']} ({data['blocked']/data['total']*100 if data['total'] else 0:.1f}%)")
    lines.append(f"- **通过率**：{data['pass_rate']:.1f}%")
    lines.append(f"- **平均响应时间**：{data['avg_response_ms']:.0f}ms")
    lines.append("")
    lines.append("```")
    bar_w = 30
    p = int(data['pass_rate'] / 100 * bar_w)
    f = int(data['failed'] / data['total'] * bar_w) if data['total'] else 0
    b = bar_w - p - f
    lines.append(f"通过:  {'█' * p}{'░' * (bar_w - p)}  {data['pass_rate']:.1f}% ({data['passed']}/{data['total']})")
    lines.append(f"失败:  {'█' * f}{'░' * (bar_w - f)}  {data['failed']/data['total']*100 if data['total'] else 0:.1f}% ({data['failed']}/{data['total']})")
    lines.append(f"阻塞:  {'█' * b}{'░' * (bar_w - b)}  {data['blocked']/data['total']*100 if data['total'] else 0:.1f}% ({data['blocked']}/{data['total']})")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 二、按测试维度分析")
    lines.append("")

    for dim in data['dimensions']:
        dim_rate = (dim['passed'] / dim['total'] * 100) if dim['total'] else 0
        lines.append(f"### {dim['dim_name']} ({dim['dim_id']})")
        lines.append("")
        lines.append(f"- 用例数：{dim['total']} | 通过：{dim['passed']} | 失败：{dim['failed']} | 阻塞：{dim['blocked']} | 通过率：{dim_rate:.1f}%")
        lines.append("")
        lines.append("| 用例 ID | 场景 | 标题 | 用户输入 | 优先级 | 状态码 | 响应时间 | 结果 |")
        lines.append("|---------|------|------|----------|--------|--------|----------|------|")
        for c in dim['cases']:
            status_icon = {"通过": "✅", "失败": "❌", "阻塞": "⏸️"}.get(c['status'], "❓")
            lines.append(f"| {c['tc_id']} | {c['scenario_id']} | {c['title'][:30]} | {c['user_input'][:25]} | {c['priority']} | {c['status_code']} | {c['response_time']} | {status_icon} {c['status']} |")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 三、详细测试日志")
    lines.append("")
    lines.append("| 用例 ID | 场景 | 标题 | 用户输入 | 状态码 | 响应时间 | 结果 |")
    lines.append("|---------|------|------|----------|--------|----------|------|")

    all_cases = []
    for dim in data['dimensions']:
        all_cases.extend(dim['cases'])
    for c in all_cases:
        status_icon = {"通过": "✅", "失败": "❌", "阻塞": "⏸️"}.get(c['status'], "❓")
        lines.append(f"| {c['tc_id']} | {c['scenario_id']} | {c['title'][:30]} | {c['user_input'][:25]} | {c['status_code']} | {c['response_time']} | {status_icon} {c['status']} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 四、失败分析")
    lines.append("")
    failed_cases = [c for dim in data['dimensions'] for c in dim['cases'] if c['status'] == "失败"]
    if failed_cases:
        for c in failed_cases:
            lines.append(f"### ❌ {c['tc_id']} - {c['title']}")
            lines.append(f"- **场景**：{c['scenario_id']}")
            lines.append(f"- **优先级**：{c['priority']}")
            lines.append(f"- **状态码**：{c['status_code']}")
            lines.append(f"- **响应时间**：{c['response_time']}")
            lines.append(f"- **预期结果**：{c['expected'][:100] if c.get('expected') else 'N/A'}")
            lines.append("")
    else:
        lines.append("✅ 全部通过，无失败用例。")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 五、建议")
    lines.append("")
    if data['failed'] > 0:
        lines.append(f"- 共 {data['failed']} 个失败用例，建议优先修复高优先级失败场景。")
    if data['blocked'] > 0:
        lines.append(f"- 共 {data['blocked']} 个阻塞用例，请检查环境配置或网络连通性。")
    if data['pass_rate'] >= 90:
        lines.append("- 通过率 ≥ 90%，产品质量达标，建议进行下一轮回归测试。")
    elif data['pass_rate'] >= 70:
        lines.append("- 通过率在 70%-90% 之间，存在一定风险，建议修复后再评估。")
    else:
        lines.append("- 通过率低于 70%，产品质量存在较大风险，强烈建议修复后重新测试。")
    lines.append(f"- 平均响应时间 {data['avg_response_ms']:.0f}ms，请根据业务需求评估是否需要优化。")

    return "\n".join(lines)


def _render_html(data):
    dim_rows = ""
    all_cases_html = ""
    failed_html = ""

    for dim in data['dimensions']:
        dim_rate = (dim['passed'] / dim['total'] * 100) if dim['total'] else 0
        dim_color = "#22c55e" if dim_rate >= 90 else "#eab308" if dim_rate >= 70 else "#ef4444"
        bar_p = int(dim_rate / 100 * 20)
        bar_f = int(dim['failed'] / dim['total'] * 20) if dim['total'] else 0
        bar_b = max(0, 20 - bar_p - bar_f)

        case_rows = ""
        for c in dim['cases']:
            status_cls = {"通过": "pass", "失败": "fail", "阻塞": "blocked"}.get(c['status'], "")
            case_rows += f"""<tr class="{status_cls}">
                <td>{c['tc_id']}</td>
                <td>{c['scenario_id']}</td>
                <td>{c['title'][:40]}</td>
                <td>{c['user_input'][:30]}</td>
                <td>{c['priority']}</td>
                <td>{c['status_code']}</td>
                <td>{c['response_time']}</td>
                <td><span class="badge badge-{status_cls}">{c['status']}</span></td>
            </tr>\n"""
            all_cases_html += f"""<tr class="{status_cls}">
                <td>{c['tc_id']}</td>
                <td>{c['scenario_id']}</td>
                <td>{c['title'][:40]}</td>
                <td>{c['user_input'][:30]}</td>
                <td>{c['status_code']}</td>
                <td>{c['response_time']}</td>
                <td><span class="badge badge-{status_cls}">{c['status']}</span></td>
            </tr>\n"""

        dim_rows += f"""
        <div class="dimension-card">
            <div class="dim-header">
                <h3>{dim['dim_name']} <span class="dim-id">{dim['dim_id']}</span></h3>
                <div class="dim-stats">
                    <span class="stat stat-pass">{dim['passed']} 通过</span>
                    <span class="stat stat-fail">{dim['failed']} 失败</span>
                    <span class="stat stat-blocked">{dim['blocked']} 阻塞</span>
                    <span class="stat stat-rate" style="color:{dim_color}">{dim_rate:.0f}%</span>
                </div>
            </div>
            <div class="progress-bar">
                <div class="progress-pass" style="width:{bar_p * 5}%"></div>
                <div class="progress-fail" style="width:{bar_f * 5}%"></div>
                <div class="progress-blocked" style="width:{bar_b * 5}%"></div>
            </div>
            <table>
                <thead><tr><th>用例 ID</th><th>场景</th><th>标题</th><th>用户输入</th><th>优先级</th><th>状态码</th><th>响应时间</th><th>结果</th></tr></thead>
                <tbody>{case_rows}</tbody>
            </table>
        </div>"""

    for dim in data['dimensions']:
        for c in dim['cases']:
            if c['status'] == "失败":
                failed_html += f"""<div class="fail-item">
                    <h4>❌ {c['tc_id']} - {c['title']}</h4>
                    <p><strong>场景</strong>：{c['scenario_id']} | <strong>优先级</strong>：{c['priority']}</p>
                    <p><strong>状态码</strong>：{c['status_code']} | <strong>响应时间</strong>：{c['response_time']}</p>
                    <p><strong>预期结果</strong>：{c.get('expected', 'N/A')[:200]}</p>
                </div>"""

    bar_w = 300
    p_w = int(data['pass_rate'] / 100 * bar_w)
    f_w = int(data['failed'] / max(data['total'], 1) * bar_w)
    b_w = max(0, bar_w - p_w - f_w)

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>测试执行报告</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif; background: #f5f7fa; color: #1e293b; line-height: 1.6; }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px; }}
h1 {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
h2 {{ font-size: 20px; font-weight: 600; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; }}
h3 {{ font-size: 16px; font-weight: 600; }}
.header {{ background: linear-gradient(135deg, #1e40af, #3b82f6); color: white; padding: 32px; border-radius: 12px; margin-bottom: 24px; }}
.header h1 {{ font-size: 24px; }}
.header .time {{ font-size: 13px; opacity: 0.8; margin-top: 4px; }}
.summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-top: 16px; }}
.summary-card {{ background: rgba(255,255,255,0.15); border-radius: 8px; padding: 12px; text-align: center; }}
.summary-card .num {{ font-size: 28px; font-weight: 700; }}
.summary-card .label {{ font-size: 12px; opacity: 0.85; }}
.summary-card.total .num {{ color: #93c5fd; }}
.summary-card.pass .num {{ color: #86efac; }}
.summary-card.fail .num {{ color: #fca5a5; }}
.summary-card.blocked .num {{ color: #fde68a; }}
.summary-card.rate .num {{ color: #c4b5fd; }}
.progress-bar {{ height: 12px; background: #e2e8f0; border-radius: 6px; overflow: hidden; display: flex; margin: 8px 0 16px; }}
.progress-pass {{ background: #22c55e; transition: width 0.5s; }}
.progress-fail {{ background: #ef4444; transition: width 0.5s; }}
.progress-blocked {{ background: #eab308; transition: width 0.5s; }}
.dimension-card {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
.dim-header {{ display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }}
.dim-id {{ font-size: 12px; color: #94a3b8; font-weight: 400; }}
.dim-stats {{ display: flex; gap: 12px; font-size: 13px; }}
.stat {{ padding: 2px 8px; border-radius: 4px; }}
.stat-pass {{ color: #16a34a; background: #f0fdf4; }}
.stat-fail {{ color: #dc2626; background: #fef2f2; }}
.stat-blocked {{ color: #ca8a04; background: #fefce8; }}
.stat-rate {{ font-weight: 700; font-size: 16px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }}
th {{ background: #f8fafc; text-align: left; padding: 8px 10px; font-weight: 600; color: #475569; border-bottom: 2px solid #e2e8f0; }}
td {{ padding: 8px 10px; border-bottom: 1px solid #f1f5f9; }}
tr:hover td {{ background: #f8fafc; }}
tr.fail td {{ background: #fef2f2; }}
tr.blocked td {{ background: #fefce8; }}
.badge {{ display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px; font-weight: 500; }}
.badge-pass {{ background: #dcfce7; color: #16a34a; }}
.badge-fail {{ background: #fecaca; color: #dc2626; }}
.badge-blocked {{ background: #fef9c3; color: #ca8a04; }}
.fail-item {{ background: #fef2f2; border-left: 3px solid #ef4444; padding: 12px 16px; margin-bottom: 12px; border-radius: 6px; }}
.fail-item h4 {{ color: #dc2626; font-size: 14px; margin-bottom: 4px; }}
.section {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>📊 测试执行报告</h1>
        <div class="time">生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}</div>
        <div class="summary-grid">
            <div class="summary-card total"><div class="num">{data['total']}</div><div class="label">用例总数</div></div>
            <div class="summary-card pass"><div class="num">{data['passed']}</div><div class="label">通过</div></div>
            <div class="summary-card fail"><div class="num">{data['failed']}</div><div class="label">失败</div></div>
            <div class="summary-card blocked"><div class="num">{data['blocked']}</div><div class="label">阻塞</div></div>
            <div class="summary-card rate"><div class="num">{data['pass_rate']:.1f}%</div><div class="label">通过率</div></div>
        </div>
        <div class="progress-bar" style="margin-top:16px;height:16px;background:rgba(255,255,255,0.3)">
            <div class="progress-pass" style="width:{p_w / bar_w * 100}%"></div>
            <div class="progress-fail" style="width:{f_w / bar_w * 100}%"></div>
            <div class="progress-blocked" style="width:{b_w / bar_w * 100}%"></div>
        </div>
        <div style="margin-top:8px;font-size:13px;opacity:0.8">平均响应时间：{data['avg_response_ms']:.0f}ms</div>
    </div>

    <h2>📂 按测试维度分析</h2>
    {dim_rows}

    <h2>📋 详细测试日志</h2>
    <div class="section">
    <table>
        <thead><tr><th>用例 ID</th><th>场景</th><th>标题</th><th>用户输入</th><th>状态码</th><th>响应时间</th><th>结果</th></tr></thead>
        <tbody>{all_cases_html}</tbody>
    </table>
    </div>

    <h2>🔍 失败分析</h2>
    <div class="section">
    {failed_html if failed_html else '<p style="padding:16px;text-align:center;color:#16a34a;font-size:16px">✅ 全部通过，无失败用例。</p>'}
    </div>

    <h2>💡 建议</h2>
    <div class="section">
    <ul style="padding-left:20px">
        {'<li>共 ' + str(data['failed']) + ' 个失败用例，建议优先修复高优先级失败场景。</li>' if data['failed'] > 0 else ''}
        {'<li>共 ' + str(data['blocked']) + ' 个阻塞用例，请检查环境配置或网络连通性。</li>' if data['blocked'] > 0 else ''}
        <li>{'✅ 通过率 ≥ 90%，产品质量达标，建议进行下一轮回归测试。' if data['pass_rate'] >= 90 else '⚠️ 通过率在 70%-90% 之间，存在一定风险，建议修复后再评估。' if data['pass_rate'] >= 70 else '❌ 通过率低于 70%，产品质量存在较大风险，强烈建议修复后重新测试。'}</li>
        <li>平均响应时间 {data['avg_response_ms']:.0f}ms，请根据业务需求评估是否需要优化。</li>
    </ul>
    </div>
</div>
</body>
</html>"""
    return html


def _save_output(path, content, mode):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] {mode.upper()} report saved: {path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
