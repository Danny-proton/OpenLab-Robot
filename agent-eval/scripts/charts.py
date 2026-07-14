#!/usr/bin/env python3
"""charts.py — 从 scores / traces / diagnosis 聚合出 charts.json。

v0.5 报告需要 8 类图的数据。本脚本读 scores/<run_id>.json + traces/<run_id>.jsonl
+ reports/<run_id>_diagnosis.json，输出 charts.json，供 HTML 报告渲染。

8 类图：
  1. overall_scorecard      指标卡片
  2. scenario_bar           场景柱状图
  3. case_metric_heatmap    case × metric 热力图
  4. failure_pareto         失败 Pareto
  5. trace_timeline         单 case trace 时间线（每 case 一条）
  6. tool_call_graph        工具调用图
  7. iteration_curve        迭代曲线（多 run 聚合）
  8. patch_impact_matrix    patch 影响矩阵（A/B 时用）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def build_overall_scorecard(score: dict, baseline_score: dict | None = None) -> list[dict]:
    """1. 总体评分卡：每个指标的 baseline / candidate / delta。"""
    metrics_keys = [
        ("task_success", "Task Success"),
        ("tool_correctness", "Tool Correctness"),
        ("business_rule_coverage", "Business Rule Coverage"),
        ("output_schema_validity", "Output Schema Validity"),
        ("efficiency", "Efficiency"),
    ]
    out = []
    agg = score.get("aggregate", {})
    b_agg = baseline_score.get("aggregate", {}) if baseline_score else {}

    # 汇总级
    for key, label in metrics_keys:
        c_val = _mean_metric(score, key)
        b_val = _mean_metric(baseline_score, key) if baseline_score else None
        delta = round(c_val - b_val, 3) if b_val is not None else None
        out.append({
            "metric": key,
            "label": label,
            "baseline": b_val,
            "candidate": c_val,
            "delta": delta,
        })

    # latency 和 token 单独处理
    c_lat = agg.get("latency_p50", 0)
    b_lat = b_agg.get("latency_p50", 0) if baseline_score else 0
    out.append({
        "metric": "latency_p50",
        "label": "Latency p50 (ms)",
        "baseline": b_lat if baseline_score else None,
        "candidate": c_lat,
        "delta": (c_lat - b_lat) if baseline_score else None,
    })

    # token cost
    c_tokens = _sum_tokens(score)
    b_tokens = _sum_tokens(baseline_score) if baseline_score else 0
    out.append({
        "metric": "token_cost",
        "label": "Token Cost",
        "baseline": b_tokens if baseline_score else None,
        "candidate": c_tokens,
        "delta": (c_tokens - b_tokens) if baseline_score else None,
    })

    return out


def _mean_metric(score: dict, key: str) -> float:
    """算某指标在所有 case 上的均值。"""
    vals = []
    for pc in score.get("per_case", []):
        m = pc.get("metrics", {}).get(key, {})
        v = m.get("score")
        if isinstance(v, (int, float)):
            vals.append(v)
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def _sum_tokens(score: dict) -> int:
    """算总 token 数（从 trace 统计，这里简化用 case 数 × 500）。"""
    # 实际从 trace 算更准，这里简化
    return sum(
        (pc.get("metrics", {}).get("efficiency", {}).get("detail", {}).get("actual_steps", 0) * 60)
        for pc in score.get("per_case", [])
    )


def build_scenario_bar(score: dict, cases: list[dict]) -> list[dict]:
    """2. 场景柱状图：每个场景的通过率。"""
    # 从 cases 里取 scenario（取 name 的第一个词作场景）
    case_scenario = {}
    for c in cases:
        cid = c.get("id", "")
        name = c.get("name", "")
        # 简单提取场景：name 的 "-" 前部分，或 id 的 "_" 前部分
        scenario = name.split("-")[0].strip() if name else cid.split("_")[0]
        case_scenario[cid] = scenario

    by_scenario: dict[str, list[float]] = defaultdict(list)
    for pc in score.get("per_case", []):
        cid = pc.get("case_id", "")
        scenario = case_scenario.get(cid, "other")
        ws = pc.get("weighted_score", 0)
        by_scenario[scenario].append(1.0 if not pc.get("is_hard_fail") and ws >= 0.6 else 0.0)

    out = []
    for scenario, vals in by_scenario.items():
        rate = round(sum(vals) / len(vals), 3) if vals else 0
        out.append({"scenario": scenario, "pass_rate": rate, "n_cases": len(vals)})
    out.sort(key=lambda x: x["pass_rate"])
    return out


def build_case_metric_heatmap(score: dict) -> dict:
    """3. case × metric 热力图。"""
    metrics_keys = [
        "task_success", "tool_correctness", "business_rule_coverage",
        "output_schema_validity", "efficiency",
    ]
    rows = []
    for pc in score.get("per_case", []):
        cid = pc.get("case_id", "")
        row = {"case_id": cid, "scores": {}}
        for k in metrics_keys:
            v = pc.get("metrics", {}).get(k, {}).get("score", 0)
            row["scores"][k] = round(v, 2) if isinstance(v, (int, float)) else 0
        row["weighted"] = pc.get("weighted_score", 0)
        row["is_hard_fail"] = pc.get("is_hard_fail", False)
        rows.append(row)
    return {"metrics": metrics_keys, "rows": rows}


def build_failure_pareto(diagnosis: dict) -> list[dict]:
    """4. 失败 Pareto：按失败类型数量降序。"""
    by_type: dict[str, int] = diagnosis.get("by_failure_type", {}) or {}
    items = [{"failure_type": k, "count": v} for k, v in by_type.items()]
    items.sort(key=lambda x: x["count"], reverse=True)
    total = sum(it["count"] for it in items) or 1
    cum = 0
    for it in items:
        cum += it["count"]
        it["cumulative_pct"] = round(cum / total * 100, 1)
    return items


def build_trace_timeline(cfg: C.EvalConfig, run_id: str) -> list[dict]:
    """5. trace 时间线：每 case 一条。"""
    trace_path = cfg.traces_dir / f"{run_id}.jsonl"
    events = C.load_jsonl(trace_path)
    by_case: dict[str, list[dict]] = defaultdict(list)
    for ev in events:
        crid = ev.get("case_run_id") or ev.get("case_run_id", "")
        cid = ev.get("case_id", "")
        if cid:
            by_case[cid].append(ev)

    timelines = []
    for cid, evs in by_case.items():
        evs.sort(key=lambda e: e.get("step", 0)
                 or int((e.get("span_id") or "span_0000").split("_")[-1])
                 if e.get("span_id") else 0)
        steps = []
        for ev in evs:
            attrs = ev.get("attributes") or {}
            out = ev.get("output") or {}
            metrics = ev.get("metrics") or {}
            step_info = {
                "step": ev.get("step", 0) or int((ev.get("span_id") or "span_0000").split("_")[-1] or 0),
                "event_type": ev.get("event_type") or ev.get("event", ""),
                "tool": (ev.get("component") or {}).get("name", "") or ev.get("tool", ""),
                "status": ev.get("status", "success"),
                "latency_ms": metrics.get("latency_ms", 0) or ev.get("latency_ms", 0),
                "arguments": attrs.get("tool.arguments", "") or ev.get("arguments", ""),
                "result": out.get("summary", "") or out.get("final_answer", "") or str(ev.get("result", ""))[:200],
                "timestamp": ev.get("timestamp", "") or ev.get("ts", ""),
                "span_id": ev.get("span_id", ""),
                "parent_span_id": ev.get("parent_span_id", ""),
            }
            # 清理空值
            step_info = {k: v for k, v in step_info.items() if v not in ("", None, 0) or k in ("step","event_type","tool","status")}
            steps.append(step_info)
        timelines.append({"case_id": cid, "steps": steps})
    return timelines


def build_tool_call_graph(cfg: C.EvalConfig, run_id: str) -> dict:
    """6. 工具调用图：节点 + 边。"""
    trace_path = cfg.traces_dir / f"{run_id}.jsonl"
    events = C.load_jsonl(trace_path)
    # 按 case 收集工具调用序列
    by_case: dict[str, list[str]] = defaultdict(list)
    tool_counter: Counter = Counter()
    for ev in events:
        if (ev.get("event_type") == "tool.call.start") or (ev.get("event") == "tool_call"):
            tool = (ev.get("component") or {}).get("name", "") or ev.get("tool", "")
            if tool:
                cid = ev.get("case_id", "")
                by_case[cid].append(tool)
                tool_counter[tool] += 1

    # 边：相邻工具调用
    edge_counter: Counter = Counter()
    for cid, tools in by_case.items():
        for i in range(len(tools) - 1):
            edge_counter[(tools[i], tools[i + 1])] += 1

    nodes = [{"id": t, "count": c} for t, c in tool_counter.most_common()]
    edges = [{"from": a, "to": b, "count": c} for (a, b), c in edge_counter.most_common()]
    return {"nodes": nodes, "edges": edges}


def build_iteration_curve(cfg: C.EvalConfig, current_run_id: str) -> list[dict]:
    """7. 迭代曲线：从所有 run 的 scores 聚合。"""
    runs = sorted((cfg.scores_dir).glob("*.json"))
    curve = []
    for p in runs:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
            agg = s.get("aggregate", {})
            curve.append({
                "run_id": s.get("run_id", p.stem),
                "weighted_score": agg.get("weighted_score", 0),
                "n_hard_fail": agg.get("n_hard_fail", 0),
                "n_success": agg.get("n_success", 0),
                "latency_p50": agg.get("latency_p50", 0),
            })
        except Exception:
            continue
    return curve


def build_patch_impact_matrix(cfg: C.EvalConfig, abtest_reports: list[dict] | None = None) -> list[dict]:
    """8. patch 影响矩阵：从 abtest 报告聚合。"""
    matrix = []
    if not abtest_reports:
        # 从 reports 目录扫
        for p in sorted((cfg.reports_dir).glob("abtest_*.md")):
            # 简化：从文件名提取，实际应该读 verdict.json
            matrix.append({
                "patch_id": p.stem,
                "recommendation": "unknown",
                "note": "see report file",
            })
    return matrix


def build_charts(
    cfg: C.EvalConfig,
    run_id: str,
    score: dict,
    diagnosis: dict | None = None,
    baseline_score: dict | None = None,
    cases: list[dict] | None = None,
) -> dict:
    """聚合 8 类图数据。"""
    if cases is None:
        cases = []
    if diagnosis is None:
        diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
        if diag_path.exists():
            diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))
        else:
            diagnosis = {"by_failure_type": {}, "diagnoses": []}

    return {
        "run_id": run_id,
        "overall_scorecard": build_overall_scorecard(score, baseline_score),
        "scenario_bar": build_scenario_bar(score, cases),
        "case_metric_heatmap": build_case_metric_heatmap(score),
        "failure_pareto": build_failure_pareto(diagnosis),
        "trace_timeline": build_trace_timeline(cfg, run_id),
        "tool_call_graph": build_tool_call_graph(cfg, run_id),
        "iteration_curve": build_iteration_curve(cfg, run_id),
        "patch_impact_matrix": build_patch_impact_matrix(cfg),
    }


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

    charts = build_charts(cfg, args.run, score, None, baseline_score, cases)

    out = cfg.scores_dir / f"{args.run}.charts.json"
    C.write_json(out, charts)
    print(f"charts: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
