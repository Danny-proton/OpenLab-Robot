#!/usr/bin/env python3
"""report.py — 生成 markdown 报告。

被 eval_runner / abtest 进程内调用，也提供 CLI 单独生成：
  python report.py --config .agent-eval/config.yaml --run <run_id>
  python report.py --config .agent-eval/config.yaml --abtest <baseline_run_id> <candidate_run_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------------------------------------------------------------------
# 11 节辅助函数
# ---------------------------------------------------------------------------

TM = "|"  # table marker 简写


def _fmt_num(v, default="-") -> str:
    """安全格式化数字。"""
    if isinstance(v, (int, float)):
        return f"{v:.3f}" if isinstance(v, float) and v != int(v) else str(v)
    return str(default)


def _section_executive_summary(score: dict, charts_data: dict | None) -> list[str]:
    """第 1 节：执行摘要。"""
    agg = score.get("aggregate", {})
    n_cases = agg.get("n_cases", 0) or len(score.get("per_case", []))
    n_success = agg.get("n_success", 0)
    n_hard = agg.get("n_hard_fail", 0)
    success_rate = (n_success / n_cases * 100) if n_cases else 0
    weighted = agg.get("weighted_score", 0)

    pareto = (charts_data or {}).get("failure_pareto", [])
    top_failure = pareto[0]["failure_type"] if pareto else "无"

    bp = (charts_data or {}).get("overall_scorecard")
    baseline_note = "（无 baseline 对比）"
    if bp and any(it.get("baseline") is not None for it in bp):
        baseline_note = "（见第 3 节对比详情）"

    lines = [
        "## 1. 执行摘要\n",
        f"| 指标 | 值 |",
        f"{TM}------{TM}----{TM}",
        f"{TM} Case 总数 {TM} {n_cases} {TM}",
        f"{TM} 成功率 {TM} {success_rate:.1f}% {TM}",
        f"{TM} 加权总分 {TM} **{weighted:.3f}** (满分 1.000) {TM}",
        f"{TM} 硬失败数 {TM} {n_hard} {'⚠️ 有硬失败' if n_hard else '✅ 无硬失败'} {TM}",
        f"{TM} Latency p50 {TM} {agg.get('latency_p50', 0)}ms (mean: {agg.get('latency_mean', 0)}ms) {TM}",
        f"{TM} Latency p95 {TM} {agg.get('latency_p95', '-')}ms {TM}",
        f"{TM} 主要失败类型 {TM} {top_failure} {TM}",
        f"{TM} 对比备注 {TM} {baseline_note} {TM}",
        "",
    ]
    return lines


def _section_eval_setup(cfg: C.EvalConfig, run_id: str, score: dict) -> list[str]:
    """第 2 节：评测配置。"""
    agg = score.get("aggregate", {})
    n_cases = agg.get("n_cases", 0) or len(score.get("per_case", []))
    weights = score.get("weights", {})
    weights_str = ", ".join(f"{k}={v:.2f}" for k, v in weights.items()) if weights else "—"

    lines = [
        "## 2. 评测配置\n",
        f"{TM} 项目 {TM} 值 {TM}",
        f"{TM}------{TM}----{TM}",
        f"{TM} run_id {TM} `{run_id}` {TM}",
        f"{TM} adapter {TM} `{cfg.adapter_name}` {TM}",
        f"{TM} case 集合 {TM} `{cfg.cases_dir.name}/` {TM}",
        f"{TM} case 数 {TM} {n_cases} {TM}",
        f"{TM} 指标权重 {TM} {weights_str} {TM}",
        f"{TM} trace 格式 {TM} `UATR-0.5` {TM}",
        f"{TM} 报告生成器 {TM} agent-eval v0.5 {TM}",
        "",
    ]
    return lines


def _section_scorecard(charts_data: dict | None) -> list[str]:
    """第 3 节：总体评分卡。"""
    sc = (charts_data or {}).get("overall_scorecard", [])
    if not sc:
        return ["## 3. 总体评分卡\n\n> 暂无 charts.json 数据。请先运行评测或生成 charts 数据。\n"]

    has_baseline = any(it.get("baseline") is not None for it in sc)
    if has_baseline:
        lines = [
            "## 3. 总体评分卡\n",
            f"{TM} 指标 {TM} Baseline {TM} Candidate {TM} Delta {TM}",
            f"{TM}------{TM}----------{TM}-----------{TM}-------{TM}",
        ]
        for it in sc:
            b = _fmt_num(it.get("baseline"), "-")
            c = _fmt_num(it.get("candidate"), "-")
            d = it.get("delta")
            ds = f"{d:+.3f}" if isinstance(d, (int, float)) else "—"
            lines.append(f"{TM} {it.get('label', it.get('metric'))} {TM} {b} {TM} {c} {TM} {ds} {TM}")
    else:
        lines = [
            "## 3. 总体评分卡\n",
            f"{TM} 指标 {TM} 分数 {TM}",
            f"{TM}------{TM}------{TM}",
        ]
        for it in sc:
            c = _fmt_num(it.get("candidate"), "-")
            lines.append(f"{TM} {it.get('label', it.get('metric'))} {TM} {c} {TM}")

    lines.append("")
    return lines


def _section_scenarios(charts_data: dict | None) -> list[str]:
    """第 4 节：场景结果。"""
    sb = (charts_data or {}).get("scenario_bar", [])
    if not sb:
        return ["## 4. 场景结果\n\n> 暂无场景数据。\n"]

    lines = [
        "## 4. 场景结果\n",
        f"{TM} 场景 {TM} Case 数 {TM} 通过率 {TM} 状态 {TM}",
        f"{TM}------{TM}--------{TM}--------{TM}------{TM}",
    ]
    for s in sb:
        rate = s.get("pass_rate", 0) * 100
        if rate >= 80:
            status = "✅"
        elif rate >= 50:
            status = "⚠️"
        else:
            status = "❌"
        lines.append(
            f"{TM} {s.get('scenario')} {TM} {s.get('n_cases')} {TM} "
            f"{rate:.1f}% {TM} {status} {TM}"
        )
    lines.append("")
    return lines


def _section_metrics(charts_data: dict | None) -> list[str]:
    """第 5 节：指标结果。"""
    sc = (charts_data or {}).get("overall_scorecard", [])
    if not sc:
        return ["## 5. 指标结果\n\n> 暂无指标数据。\n"]

    lines = [
        "## 5. 指标结果\n",
        "各指标详细得分：\n",
        f"{TM} 指标 {TM} 得分 {TM} 说明 {TM}",
        f"{TM}------{TM}------{TM}------{TM}",
    ]
    descriptions = {
        "task_success": "任务是否完成",
        "tool_correctness": "工具调用正确性",
        "business_rule_coverage": "业务规则覆盖",
        "output_schema_validity": "输出格式合规",
        "efficiency": "执行效率（步骤/延迟）",
        "latency_p50": "延迟中位数",
        "token_cost": "Token 消耗",
    }
    for it in sc:
        metric = it.get("metric", "")
        c = _fmt_num(it.get("candidate"), "-")
        desc = descriptions.get(metric, "")
        lines.append(f"{TM} {it.get('label', metric)} {TM} {c} {TM} {desc} {TM}")
    lines.append("")
    return lines


def _section_tool_analysis(charts_data: dict | None) -> list[str]:
    """第 6 节：工具分析。"""
    graph = (charts_data or {}).get("tool_call_graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    lines = ["## 6. 工具分析\n"]
    if not nodes:
        lines.append("> 暂无工具调用数据。\n")
        return lines

    lines.append("### 工具调用频次\n")
    lines.append(f"{TM} 工具 {TM} 调用次数 {TM}")
    lines.append(f"{TM}------{TM}----------{TM}")
    for n in nodes[:20]:
        lines.append(f"{TM} `{n.get('id')}` {TM} {n.get('count')} {TM}")
    lines.append("")

    if edges:
        lines.append("### 调用路径（相邻工具）\n")
        lines.append(f"{TM} 路径 {TM} 次数 {TM}")
        lines.append(f"{TM}------{TM}------{TM}")
        for e in edges[:15]:
            lines.append(f"{TM} `{e.get('from')}` → `{e.get('to')}` {TM} {e.get('count')} {TM}")
        lines.append("")

    return lines


def _section_failure_taxonomy(charts_data: dict | None, diagnosis: dict | None) -> list[str]:
    """第 7 节：失败归因。"""
    pareto = (charts_data or {}).get("failure_pareto", [])
    diags = (diagnosis or {}).get("diagnoses", []) if diagnosis else []

    lines = ["## 7. 失败归因\n"]
    if not pareto and not diags:
        lines.append("> 暂无失败数据。\n")
        return lines

    if pareto:
        lines.append("### Pareto 分布\n")
        lines.append(f"{TM} 失败类型 {TM} 次数 {TM} 累计占比 {TM}")
        lines.append(f"{TM}------{TM}------{TM}----------{TM}")
        for it in pareto:
            lines.append(
                f"{TM} {it.get('failure_type')} {TM} {it.get('count')} {TM} "
                f"{it.get('cumulative_pct', 0):.1f}% {TM}"
            )
        lines.append("")

    if diags:
        by_type: dict[str, list[dict]] = {}
        for d in diags:
            ft = d.get("failure_type", "UNKNOWN")
            by_type.setdefault(ft, []).append(d)

        lines.append("### 分类详情\n")
        for ft, ds in sorted(by_type.items()):
            sample = ds[0]
            lines.append(f"- **{ft}** — {sample.get('failure_label', '')} ({len(ds)} 条)")
            lines.append(f"  - 代表 case: `{sample.get('case_id', '')}`")
            lines.append(f"  - 建议 mutation: `{sample.get('suggested_mutation_target', '')}` "
                        f"via `{sample.get('suggested_mutation_rule', '')}`")
        lines.append("")

    return lines


def _section_iteration_history(charts_data: dict | None) -> list[str]:
    """第 8 节：迭代历史。"""
    curve = (charts_data or {}).get("iteration_curve", [])
    matrix = (charts_data or {}).get("patch_impact_matrix", [])

    lines = ["## 8. 迭代历史\n"]
    if not curve:
        lines.append("> 暂无历史 run 数据。\n")
        return lines

    lines.append("### 迭代曲线\n")
    lines.append(f"{TM} 轮次 {TM} Run ID {TM} 加权总分 {TM} 硬失败 {TM} Latency p50 {TM}")
    lines.append(f"{TM}------{TM}--------{TM}----------{TM}--------{TM}-------------{TM}")
    for i, c in enumerate(curve, 1):
        rid = c.get("run_id", "-")
        if len(rid) > 20:
            rid = rid[-20:]
        lines.append(
            f"{TM} {i} {TM} `{rid}` {TM} {c.get('weighted_score', 0):.3f} {TM} "
            f"{c.get('n_hard_fail', 0)} {TM} {c.get('latency_p50', 0)}ms {TM}"
        )
    lines.append("")

    if matrix:
        lines.append("### Patch 影响矩阵\n")
        lines.append(f"共 {len(matrix)} 个 patch。\n")

    return lines


def _section_heatmap(score: dict, charts_data: dict | None) -> list[str]:
    """第 9 节：Case × Metric 热力图。"""
    hm = (charts_data or {}).get("case_metric_heatmap", {})
    if hm:
        metrics = hm.get("metrics", [])
        rows = hm.get("rows", [])
    else:
        metrics = ["task_success", "tool_correctness",
                    "business_rule_coverage", "output_schema_validity", "efficiency"]
        rows = []
        for pc in score.get("per_case", []):
            r = {"case_id": pc.get("case_id"), "scores": {}, "weighted": pc.get("weighted_score", 0),
                 "is_hard_fail": pc.get("is_hard_fail", False)}
            for k in metrics:
                r["scores"][k] = round(
                    pc.get("metrics", {}).get(k, {}).get("score", 0), 2
                )
            rows.append(r)

    lines = ["## 9. Case 热力图\n"]
    if not rows:
        lines.append("> 暂无 case 数据。\n")
        return lines

    metric_labels = (" " + TM + " ").join(m.replace("_", " ")[:12] for m in metrics)
    header = f"{TM} case_id {TM} 加权总分 {TM} {metric_labels} {TM} 状态 {TM}"
    sep = f"{TM}---------{TM}----------{TM}" + f"{TM}------{TM}" * len(metrics) + f"{TM}------{TM}"
    lines.append(header)
    lines.append(sep)
    for r in rows[:42]:
        cid = r.get("case_id", "")
        ws = r.get("weighted", 0)
        scores = (" " + TM + " ").join(f"{r['scores'].get(m, 0):.2f}" for m in metrics)
        status = "FAIL" if r.get("is_hard_fail") else "PASS"
        lines.append(f"{TM} `{cid}` {TM} {ws:.3f} {TM} {scores} {TM} {status} {TM}")
    lines.append("")
    return lines


def _section_trace_timeline(charts_data: dict | None) -> list[str]:
    """第 10 节：Trace 时间线。"""
    tls = (charts_data or {}).get("trace_timeline", [])
    lines = ["## 10. Trace 时间线\n"]
    if not tls:
        lines.append("> 暂无 trace 数据。\n")
        return lines

    for tl in tls[:20]:
        cid = tl.get("case_id", "")
        steps = tl.get("steps", [])
        n_steps = len(steps)
        n_errors = sum(1 for s in steps if s.get("status") == "error")
        tool_names = [s.get("tool", "") for s in steps if s.get("tool")]
        unique_tools = list(dict.fromkeys(tool_names))
        total_latency = sum(s.get("latency_ms", 0) for s in steps)

        lines.append(f"### `{cid}` ({n_steps} steps)\n")
        lines.append(f"- 工具: {', '.join(f'`{t}`' for t in unique_tools) if unique_tools else '—'}")
        lines.append(f"- 错误: {n_errors}")
        lines.append(f"- 总延迟: {total_latency}ms")
        lines.append(f"- 事件序列: {' → '.join(s.get('event_type','?').split('.')[-1][:4] for s in steps[:30])}")
        lines.append("")

        # 错误详情
        err_steps = [s for s in steps if s.get("status") == "error"]
        if err_steps:
            lines.append("错误步骤:\n")
            for s in err_steps:
                lines.append(f"- step {s.get('step')}: `{s.get('event_type')}` "
                            f"({s.get('tool', '')})")
            lines.append("")

    return lines


def _section_trace_dimensions(charts_data: dict | None) -> list[str]:
    """第 12 节：TRACE 五维评测。"""
    radar = (charts_data or {}).get("trace_radar", {})
    if not radar or not radar.get("labels"):
        return ["## 12. TRACE 五维评测\n\n> 暂无 TRACE 数据。请先运行 `tracer_scorer.py` 或配置 config.yaml 中的 `trace` 段。\n"]

    lines = [
        "## 12. TRACE 五维评测\n",
        "五维能力雷达：Trust（可信任度）| Reliability（可靠性）| Adaptability（适用性）| Convention（规范性）| Effectiveness（有效性）\n",
    ]

    total = radar.get("total_score", 0)
    status = radar.get("status", "?")
    lines.append(f"- **TRACE 综合评分**: {total:.2f}/5.0 ({status})\n")

    lines.append("### 逐维度详情\n")
    labels = radar.get("labels", [])
    scores = radar.get("scores", [])
    target_zones = radar.get("target_zones", [])

    lines.append(f"| 维度 | 评分 | 目标区间 | 状态 |")
    lines.append(f"|------|------|----------|------|")
    for i, (label, score) in enumerate(zip(labels, scores)):
        tz = target_zones[i] if i < len(target_zones) else {}
        tz_lo = tz.get("lo", 0)
        tz_hi = tz.get("hi", 0)
        if score >= tz_hi:
            st = "✅ 优秀"
        elif score >= tz_lo:
            st = "⬆ 达标"
        elif score >= tz_lo - 0.5:
            st = "⚠️ 接近"
        else:
            st = "❌ 需改善"
        lines.append(f"| {label} | {score:.2f}/5.0 | {tz_lo:.1f}-{tz_hi:.1f} | {st} |")
    lines.append("")

    return lines


def _section_recommendations(score: dict, charts_data: dict | None) -> list[str]:
    """第 11 节：建议。"""
    agg = score.get("aggregate", {})
    pareto = (charts_data or {}).get("failure_pareto", [])
    recs: list[dict] = []

    n_hard = agg.get("n_hard_fail", 0)
    if n_hard > 0:
        recs.append({
            "priority": "🔴 高",
            "text": f"修复 {n_hard} 条硬失败 — 硬失败违反业务规则或调用禁用工具，必须优先修复。",
        })

    if pareto:
        top = pareto[0]
        recs.append({
            "priority": "🔴 高",
            "text": f"优先处理 `{top['failure_type']}` 失败 — 该类型共 {top['count']} 次，占总失败较大比例。"
                    f"参考第 7 节失败归因的 mutation 建议。",
        })

    ws = agg.get("weighted_score", 0)
    if ws < 0.5:
        recs.append({
            "priority": "🔴 高",
            "text": f"整体分数偏低 (当前: {ws:.3f})，建议从 prompt 和 tool schema 两方面系统性优化。",
        })
    elif ws < 0.8:
        recs.append({
            "priority": "🟡 中",
            "text": f"聚焦短板指标 (当前: {ws:.3f})，参考第 3 节评分卡，优先提升分数最低的指标。",
        })
    else:
        recs.append({
            "priority": "🟢 低",
            "text": f"维持当前水平 (当前: {ws:.3f})，建议增加 adversarial case 覆盖边缘场景。",
        })

    lines = ["## 11. 建议\n"]
    for i, r in enumerate(recs, 1):
        lines.append(f"{i}. **[{r['priority']}]** {r['text']}")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# 主报告入口
# ---------------------------------------------------------------------------

def render_run_report(
    cfg: C.EvalConfig,
    run_id: str,
    score: dict,
    *,
    charts_data: dict | None = None,
    diagnosis: dict | None = None,
    cases: list[dict] | None = None,
    baseline_score: dict | None = None,
) -> Path:
    """生成 11 节 markdown 评测报告。

    参数:
        cfg: 评测配置
        run_id: 本轮 run id
        score: scorer 输出的 score dict
        charts_data: charts.py 输出的聚合图表数据（可选，缺失时节显示占位符）
        diagnosis: diagnoser 输出的诊断数据（可选）
        cases: 原始 case 列表（可选）
        baseline_score: baseline run 的 score dict（可选，用于对比）
    """
    out = cfg.reports_dir / f"{run_id}.md"
    agg = score.get("aggregate", {})
    n_cases = agg.get("n_cases", 0) or len(score.get("per_case", []))
    n_success = agg.get("n_success", 0)
    n_hard = agg.get("n_hard_fail", 0)

    # 如果提供了 charts_data 但没有 iteration_curve，尝试从 scores 目录构建
    if charts_data and not charts_data.get("iteration_curve") and cfg.scores_dir.exists():
        curve = []
        for p in sorted(cfg.scores_dir.glob("*.json")):
            try:
                s = json.loads(p.read_text(encoding="utf-8"))
                a_ = s.get("aggregate", {})
                curve.append({
                    "run_id": s.get("run_id", p.stem),
                    "weighted_score": a_.get("weighted_score", 0),
                    "n_hard_fail": a_.get("n_hard_fail", 0),
                    "latency_p50": a_.get("latency_p50", 0),
                })
            except Exception:
                continue
        charts_data = dict(charts_data)
        charts_data["iteration_curve"] = curve

    lines: list[str] = []
    lines.append(f"# 评测报告 — {run_id}\n")
    lines.append(f"> **生成时间**: {C.now_iso()} | **case 数**: {n_cases} | "
                 f"**成功**: {n_success} | **硬失败**: {n_hard}\n")

    # --- 1. 执行摘要 ---
    lines.extend(_section_executive_summary(score, charts_data))

    # --- 2. 评测配置 ---
    lines.extend(_section_eval_setup(cfg, run_id, score))

    # --- 3. 总体评分卡 ---
    lines.extend(_section_scorecard(charts_data))

    # --- 4. 场景结果 ---
    lines.extend(_section_scenarios(charts_data))

    # --- 5. 指标结果 ---
    lines.extend(_section_metrics(charts_data))

    # --- 6. 工具分析 ---
    lines.extend(_section_tool_analysis(charts_data))

    # --- 7. 失败归因 ---
    lines.extend(_section_failure_taxonomy(charts_data, diagnosis))

    # --- 8. 迭代历史 ---
    lines.extend(_section_iteration_history(charts_data))

    # --- 9. Case 热力图 ---
    lines.extend(_section_heatmap(score, charts_data))

    # --- 10. Trace 时间线 ---
    lines.extend(_section_trace_timeline(charts_data))

    # --- 12. TRACE 五维评测 ---
    lines.extend(_section_trace_dimensions(charts_data))

    # --- 11. 建议 ---
    lines.extend(_section_recommendations(score, charts_data))

    lines.append("---\n")
    lines.append(f"*本报告由 agent-eval v0.5 自动生成 | 12 节结构化报告（含 TRACE 五维评测）*")

    out.write_text("\n".join(lines), encoding="utf-8")
    try:
        import report_manager as RM
        RM.register_report(cfg, out, run_id=run_id, title=f"评测报告 — {run_id}")
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
    return out


def render_abtest_report(
    cfg: C.EvalConfig,
    baseline_run_id: str,
    candidate_run_id: str,
    patch_path: str,
    verdict: dict,
    baseline_score: dict,
    candidate_score: dict,
) -> Path:
    out = cfg.reports_dir / f"abtest_{baseline_run_id}_vs_{candidate_run_id}.md"
    lines: list[str] = []
    lines.append(f"# A/B 报告: {baseline_run_id} vs {candidate_run_id}\n")
    lines.append(f"- baseline: `{baseline_run_id}`")
    lines.append(f"- candidate: `{candidate_run_id}`")
    lines.append(f"- patch: `{patch_path}`")
    lines.append(f"- **建议: `{verdict['recommendation']}`**\n")

    lines.append("## 接受条件判定\n")
    lines.append("| # | 条件 | 结果 | 详情 |")
    lines.append("|---|------|------|------|")
    for d in verdict["decisions"]:
        status = "✅ PASS" if d["pass"] else "❌ FAIL"
        # 把 detail 字段拼成短字符串
        detail_parts = []
        for k, v in d.items():
            if k in ("id", "name", "pass"):
                continue
            detail_parts.append(f"{k}={v}")
        detail = ", ".join(detail_parts)
        lines.append(f"| {d['id']} | {d['name']} | {status} | {detail} |")
    lines.append("")

    b_agg = baseline_score.get("aggregate", {})
    c_agg = candidate_score.get("aggregate", {})
    lines.append("## 汇总对比\n")
    lines.append("| 指标 | baseline | candidate | delta |")
    lines.append("|------|----------|-----------|-------|")
    def row(name, key, fmt="{:.3f}"):
        b = b_agg.get(key, 0)
        c = c_agg.get(key, 0)
        try:
            delta = c - b
            return f"| {name} | {fmt.format(b)} | {fmt.format(c)} | {fmt.format(delta)} |"
        except (TypeError, ValueError):
            return f"| {name} | {b} | {c} | - |"
    lines.append(row("加权总分", "weighted_score"))
    lines.append(row("硬失败数", "n_hard_fail", "{:d}"))
    lines.append(row("成功数", "n_success", "{:d}"))
    lines.append(row("latency_p50", "latency_p50", "{:d}"))
    lines.append("")

    # 单 case 对比
    b_per = {pc["case_id"]: pc for pc in baseline_score.get("per_case", [])}
    c_per = {pc["case_id"]: pc for pc in candidate_score.get("per_case", [])}
    all_ids = sorted(set(b_per.keys()) | set(c_per.keys()))
    lines.append("## 单 case 对比\n")
    lines.append(f"> 注：baseline 和 candidate 可能跑在不同 split 上（baseline 通常在 train，candidate 在 {verdict.get('split', 'regression')}）。")
    lines.append(f"> 同 case_id 才能直接对比；只出现在一侧的 case 表示该 split 独有的 case。\n")
    lines.append("| case_id | baseline | candidate | delta | 状态 |")
    lines.append("|---------|----------|-----------|-------|------|")
    for cid in all_ids:
        b = b_per.get(cid, {}).get("weighted_score", "-")
        c = c_per.get(cid, {}).get("weighted_score", "-")
        try:
            d = c - b
            ds = f"{d:+.3f}"
        except TypeError:
            ds = "-"
        if isinstance(b, (int, float)) and isinstance(c, (int, float)):
            if c > b:
                status = "⬆ 改善"
            elif c < b:
                status = "⬇ 退化"
            else:
                status = "= 持平"
        else:
            status = "?"
        b_str = f"{b:.3f}" if isinstance(b, (int, float)) else b
        c_str = f"{c:.3f}" if isinstance(c, (int, float)) else c
        lines.append(f"| {cid} | {b_str} | {c_str} | {ds} | {status} |")
    lines.append("")

    # 建议
    lines.append("## 下一步\n")
    if verdict["recommendation"] == "ACCEPT":
        lines.append("1. `git add` 改动的文件并提交：")
        lines.append("   ```bash")
        lines.append(f'   git commit -m "agent-eval: accept {Path(patch_path).stem} ({candidate_run_id})"')
        lines.append("   ```")
        lines.append("2. 把这次 accept 记录追加到 `.agent-eval/reports/accepted_patches.md`")
        lines.append("3. 下一次 A/B 的 baseline 改为本次 candidate")
    elif verdict["recommendation"] == "REJECT":
        lines.append("1. **立即回滚** candidate 改动：")
        lines.append("   ```bash")
        lines.append("   git checkout -- <被改动的文件>")
        lines.append("   ```")
        lines.append("2. 检查上方 FAIL 的条件，重新看诊断是否归因正确")
        lines.append("3. 必要时重新跑 `diagnoser.py` 和 `mutator.py`")
    else:  # INCONCLUSIVE
        lines.append("1. patch 可能没生效——确认改动是否真的 apply 了")
        lines.append("2. 确认 adapter 配置是否正确")
        lines.append("3. 重新跑 candidate variant")

    out.write_text("\n".join(lines), encoding="utf-8")
    try:
        import report_manager as RM
        RM.register_report(
            cfg, out,
            run_id=candidate_run_id,
            related_run_ids=[baseline_run_id, candidate_run_id],
            title=f"A/B 报告: {baseline_run_id} vs {candidate_run_id}",
        )
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run")
    ap.add_argument("--abtest", nargs=2, metavar=("BASELINE", "CANDIDATE"))
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())

    if args.abtest:
        baseline_run_id, candidate_run_id = args.abtest
        # 简化：需要外部已生成 verdict.json
        # 这里只从 scores 读取并重新渲染
        b_score = json.loads((cfg.scores_dir / f"{baseline_run_id}.json").read_text(encoding="utf-8"))
        c_score = json.loads((cfg.scores_dir / f"{candidate_run_id}.json").read_text(encoding="utf-8"))
        # 找 patch path
        abtest_glob = list(cfg.reports_dir.glob(f"abtest_{baseline_run_id}_vs_{candidate_run_id}.md"))
        patch_path = abtest_glob[0].name if abtest_glob else "(unknown)"
        # 重新算 verdict
        import abtest as AB
        verdict = AB.evaluate_accept(b_score, c_score)
        out = render_abtest_report(cfg, baseline_run_id, candidate_run_id, patch_path, verdict, b_score, c_score)
        print(out)
        return 0

    if args.run:
        score = json.loads((cfg.scores_dir / f"{args.run}.json").read_text(encoding="utf-8"))
        out = render_run_report(cfg, args.run, score)
        print(out)
        return 0

    ap.error("需要 --run 或 --abtest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
