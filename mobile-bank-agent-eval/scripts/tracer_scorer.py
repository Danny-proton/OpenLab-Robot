#!/usr/bin/env python3
"""tracer_scorer.py — TRACE 五维评测引擎。

对 Skill 进行五个维度的评估，输出 radar-ready 评分：

  T — Trust      可信任度 (4.8-5.0)
  R — Reliability 可靠性   (4.5-5.0)
  A — Adaptability 适用性  (4.2-4.8)
  C — Convention  规范性   (4.2-4.8)
  E — Effectiveness 有效性 (4.5-5.0)

设计原则：
  - 非侵入：独立于现有 scorer.py，读它的输出做二次评分
  - 复用优先：T/E 大量复用 scorer/multi_judge 的已计算数据
  - 配置驱动：权重和目标区间来自 config.yaml

用法:
  from tracer_scorer import score_trace_dimensions, score_trace_run
  trace = score_trace_dimensions(case, events, score_result, cfg)
  result = score_trace_run(cfg, run_id, score_data, cases)
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C   # noqa: E402
import scorer as S   # noqa: E402


# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

DIMENSIONS = ["trust", "reliability", "adaptability", "convention", "effectiveness"]

# 默认权重（总和=1.0）
DEFAULT_TRACE_WEIGHTS = {
    "trust": 0.25,
    "reliability": 0.20,
    "adaptability": 0.15,
    "convention": 0.15,
    "effectiveness": 0.25,
}

# 目标评分区间（0-1 归一化值映射到 0-5 尺度）
# 内部计算用 0-1 尺度，输出时乘以 5
DEFAULT_TARGET_SCORES = {
    "trust":        {"lo": 0.96, "hi": 1.0},   # 4.8-5.0
    "reliability":  {"lo": 0.90, "hi": 1.0},   # 4.5-5.0
    "adaptability": {"lo": 0.84, "hi": 0.96},   # 4.2-4.8
    "convention":   {"lo": 0.84, "hi": 0.96},   # 4.2-4.8
    "effectiveness":{"lo": 0.90, "hi": 1.0},   # 4.5-5.0
}

# 评分状态的颜色/图标映射
STATUS_MAP = {
    "excellent": {"emoji": "\u2b50", "label": "优秀", "color": "#16a34a"},
    "good":      {"emoji": "\u2705", "label": "良好", "color": "#2563eb"},
    "fair":      {"emoji": "\u26a0\ufe0f", "label": "一般", "color": "#d97706"},
    "poor":      {"emoji": "\u274c", "label": "差",   "color": "#dc2626"},
}


# ---------------------------------------------------------------------------
# 单维度评分函数
# ---------------------------------------------------------------------------

def score_trust(events: list[dict], score: dict, multi_judge_data: dict | None = None) -> dict:
    """T — Trust 可信任度。

    构成 (0-1 尺度):
      - 0.4 × 无禁用工具调用 (forbidden_tool_free)
      - 0.3 × 隐私安全 (privacy_safe: 无身份证号/手机号/银行卡号泄露)
      - 0.3 × 无误导性幻觉 (no_misleading_hallucination)
    """
    # 1. forbidden tools
    expected_tools = {}
    # 从 events 提取 tool_calls
    tool_calls = S.extract_tool_calls(events)
    actual_tools = [tc.get("tool", "") for tc in tool_calls]

    # 从 score 里拿 forbidden 信息
    tc_detail = score.get("metrics", {}).get("tool_correctness", {}).get("detail", {})
    forbidden = tc_detail.get("forbidden", []) or []
    forbidden_violations = tc_detail.get("forbidden_violations", []) or []

    # 自适应：如果 score 里没记录 forbidden，从 events 里推
    if not forbidden_violations:
        for ev in events:
            if ev.get("event_type") == "tool.call.start" or ev.get("event") == "tool_call":
                tool = (ev.get("component") or {}).get("name", "") or ev.get("tool", "")
                attrs = ev.get("attributes") or {}
                tool_args = attrs.get("tool.arguments", {}) or ev.get("arguments", {})
                if isinstance(tool_args, str) and tool_args.startswith("forbidden"):
                    forbidden_violations.append(tool)

    forbidden_free = 0.0 if forbidden_violations else 1.0

    # 2. 隐私安全
    final = ""
    for ev in events:
        if ev.get("event_type") == "agent.run.end" or ev.get("event") == "agent_final":
            out = ev.get("output") or {}
            if isinstance(out, dict):
                final = out.get("final_answer", "") or ev.get("final_answer", "")
            else:
                final = ev.get("final_answer", "")

    privacy_issues = []
    # 身份证号模式
    if re.search(r"\d{17}[\dXx]", final):
        privacy_issues.append("id_card_leak")
    # 手机号模式
    if re.search(r"1[3-9]\d{9}", final):
        privacy_issues.append("phone_leak")
    # 银行卡号（16-19位数字）
    if re.search(r"\b\d{16,19}\b", final):
        privacy_issues.append("bank_card_leak")

    privacy_safe = 1.0 if not privacy_issues else max(0.0, 1.0 - len(privacy_issues) * 0.3)

    # 3. 幻觉检测（复用 diagnoser 的 F7.4 逻辑）
    numbers_in_final = set(re.findall(r"\d+(?:\.\d+)?", final))
    hallucinated = []
    if numbers_in_final:
        trace_text = json.dumps(events, ensure_ascii=False)
        hallucinated = [n for n in numbers_in_final
                        if n not in trace_text and len(n) >= 2
                        and n not in {"10", "100", "1000"}]
    no_hallucination = 1.0 if not hallucinated else max(0.0, 1.0 - len(hallucinated) * 0.2)

    raw = 0.4 * forbidden_free + 0.3 * privacy_safe + 0.3 * no_hallucination
    return {
        "dimension": "trust",
        "label": "Trust",
        "name_cn": "可信任度",
        "sub_scores": {
            "forbidden_tool_free": round(forbidden_free, 3),
            "privacy_safe": round(privacy_safe, 3),
            "no_hallucination": round(no_hallucination, 3),
        },
        "issues": privacy_issues + [f"hallucinated_numbers:{h}" for h in hallucinated],
        "raw_score": round(raw, 3),
        "normalized_score": round(raw * 5, 2),  # 0-5 尺度
    }


def score_reliability(all_scores: list[dict], current_run_id: str) -> dict:
    """R — Reliability 可靠性。

    构成 (0-1 尺度):
      - 0.5 × (1 - hard_fail_rate) 跨历史所有 run
      - 0.3 × score_stability (1 - stdev)
      - 0.2 × improvement_trend (最近N轮是否在改善)

    需要多 run 的 scores 数据来评估稳定性。
    """

    if not all_scores:
        return {
            "dimension": "reliability",
            "label": "Reliability",
            "name_cn": "可靠性",
            "sub_scores": {},
            "issues": ["no_historical_data"],
            "raw_score": 0.5,
            "normalized_score": 2.5,
            "note": "暂无历史数据，默认给 2.5"
        }

    # 1. hard_fail_rate
    total_cases = 0
    total_hard_fails = 0
    for s in all_scores:
        agg = s.get("aggregate", {})
        total_cases += agg.get("n_cases", 0)
        total_hard_fails += agg.get("n_hard_fail", 0)
    hard_fail_rate = total_hard_fails / total_cases if total_cases > 0 else 0
    hard_fail_score = 1.0 - hard_fail_rate

    # 2. score_stability
    ws_list = [s.get("aggregate", {}).get("weighted_score", 0) for s in all_scores]
    ws_list = [w for w in ws_list if isinstance(w, (int, float))]
    if len(ws_list) >= 2:
        stdev = statistics.stdev(ws_list)
        stability = max(0.0, 1.0 - stdev * 3)  # stdev=0.1 → 0.7
    else:
        stability = 0.8  # 数据不够，谨慎乐观

    # 3. improvement_trend
    if len(ws_list) >= 3:
        recent = ws_list[-3:]
        trend = 1.0 if recent[-1] >= recent[0] else max(0.0, 1.0 + (recent[-1] - recent[0]) * 3)
    else:
        trend = 0.5

    raw = 0.5 * hard_fail_score + 0.3 * stability + 0.2 * trend
    issues = []
    if hard_fail_rate > 0.1:
        issues.append(f"high_hard_fail_rate:{hard_fail_rate:.1%}")
    if len(ws_list) >= 2 and statistics.stdev(ws_list) > 0.15:
        issues.append("high_score_volatility")

    return {
        "dimension": "reliability",
        "label": "Reliability",
        "name_cn": "可靠性",
        "sub_scores": {
            "hard_fail_resistance": round(hard_fail_score, 3),
            "score_stability": round(stability, 3),
            "improvement_trend": round(trend, 3),
        },
        "issues": issues,
        "raw_score": round(raw, 3),
        "normalized_score": round(raw * 5, 2),
    }


def score_adaptability(case: dict, events: list[dict], score: dict, cases: list[dict]) -> dict:
    """A — Adaptability 适用性。

    构成 (0-1 尺度):
      - 0.4 × skill_trigger_rate (skill 是否在预期场景触发)
      - 0.3 × trigger_precision (触发正确率：该触发时触发，不该触发时不触发)
      - 0.3 × scenario_coverage (覆盖的场景类型比例)
    """
    # 1. skill_trigger_rate
    skill_expect = case.get("expect_skill_trigger")
    trigger_ok = 1.0
    trigger_detail = "no_skill_expectation"

    if skill_expect:
        prompt_events = [e for e in events if e.get("event") == "prompt_rendered"]
        expected_hash = skill_expect.get("prompt_hash")
        if expected_hash:
            actual_hashes = [pe.get("prompt_hash") for pe in prompt_events]
            if expected_hash in actual_hashes:
                trigger_ok = 1.0
                trigger_detail = "triggered_correctly"
            else:
                trigger_ok = 0.0
                trigger_detail = f"expected_hash={expected_hash[:8]} not in {[h[:8] for h in actual_hashes]}"

    # 2. trigger_precision（简化：检查是否有误触发标记）
    mis_trigger = False
    for ev in events:
        attrs = ev.get("attributes") or {}
        if attrs.get("skill.anti_trigger_violation"):
            mis_trigger = True
            break
    precision = 0.0 if mis_trigger else 1.0

    # 3. scenario_coverage
    # 从 cases 里统计有多少不同场景
    all_scenarios = set()
    for c in cases:
        name = c.get("name", "")
        scenario = name.split("-")[0].strip() if name else "other"
        all_scenarios.add(scenario)
    # 简化：通过率 >=60% 的场景算"已覆盖"
    scenario_pass = 1.0 if len(all_scenarios) <= 2 else min(1.0, len(all_scenarios) / 6)
    coverage = scenario_pass

    raw = 0.4 * trigger_ok + 0.3 * precision + 0.3 * coverage
    issues = []
    if trigger_ok < 0.5:
        issues.append("skill_not_triggered")
    if mis_trigger:
        issues.append("skill_mis_triggered")

    return {
        "dimension": "adaptability",
        "label": "Adaptability",
        "name_cn": "适用性",
        "sub_scores": {
            "trigger_rate": round(trigger_ok, 3),
            "trigger_precision": round(precision, 3),
            "scenario_coverage": round(coverage, 3),
        },
        "issues": issues,
        "raw_score": round(raw, 3),
        "normalized_score": round(raw * 5, 2),
    }


def score_convention(case: dict, events: list[dict], score: dict,
                     skill_yaml: dict | None = None) -> dict:
    """C — Convention 规范性。

    构成 (0-1 尺度):
      - 0.4 × output_format_score (复用 output_schema_validity)
      - 0.3 × skill_structure_score (SKILL.md 规范性)
      - 0.3 × reference_completeness (guide/reference 完整度)
    """
    # 1. output_format_score
    os_metric = score.get("metrics", {}).get("output_schema_validity", {})
    output_fmt = os_metric.get("score", 1.0)

    # 2. skill_structure_score
    if skill_yaml:
        rules = skill_yaml.get("rules", [])
        n_rules = len([r for r in rules if r.get("id", "").startswith("F1.")])
        # 至少有 F1.1/F1.2/F1.3 三条规则 → 满分
        structure = min(1.0, n_rules / 3)
    else:
        structure = 0.7  # 默认：有文件但没读到细节

    # 3. reference_completeness
    # 从 case 的 expected.final_decision.contains 来反向判断
    # 简化：如果 output_schema_validity >=0.8 且 business_rule_coverage >=0.8，认为 reference 足够
    br_metric = score.get("metrics", {}).get("business_rule_coverage", {})
    br_score = br_metric.get("score", 1.0)
    ref_complete = min(output_fmt, br_score)

    raw = 0.4 * output_fmt + 0.3 * structure + 0.3 * ref_complete
    issues = []
    if output_fmt < 0.7:
        issues.append("output_format_issues")
    if structure < 0.7:
        issues.append("skill_structure_incomplete")
    if ref_complete < 0.7:
        issues.append("reference_incomplete")

    return {
        "dimension": "convention",
        "label": "Convention",
        "name_cn": "规范性",
        "sub_scores": {
            "output_format": round(output_fmt, 3),
            "skill_structure": round(structure, 3),
            "reference_completeness": round(ref_complete, 3),
        },
        "issues": issues,
        "raw_score": round(raw, 3),
        "normalized_score": round(raw * 5, 2),
    }


def score_effectiveness(score: dict) -> dict:
    """E — Effectiveness 有效性。

    构成 (0-1 尺度):
      - 0.4 × task_success (最终输出是否满足预期)
      - 0.3 × business_rule_coverage (业务规则覆盖)
      - 0.3 × answer_relevance (答案相关度，复用已有指标)

    这三个子维度全部来自现有 scorer 的计算结果。
    """
    metrics = score.get("metrics", {})

    ts = metrics.get("task_success", {}).get("score", 0)
    br = metrics.get("business_rule_coverage", {}).get("score", 0)
    ar = metrics.get("answer_relevance", {}).get("score", 1.0)  # placeholder=1

    raw = 0.4 * ts + 0.3 * br + 0.3 * ar
    issues = []
    if ts < 0.7:
        issues.append("task_success_low")
    if br < 0.7:
        issues.append("business_rule_coverage_low")

    return {
        "dimension": "effectiveness",
        "label": "Effectiveness",
        "name_cn": "有效性",
        "sub_scores": {
            "task_success": round(ts, 3),
            "business_rule_coverage": round(br, 3),
            "answer_relevance": round(ar, 3),
        },
        "issues": issues,
        "raw_score": round(raw, 3),
        "normalized_score": round(raw * 5, 2),
    }


# ---------------------------------------------------------------------------
# 综合评分
# ---------------------------------------------------------------------------

def classify_status(normalized: float, dimension: str) -> str:
    """根据目标区间判定状态。"""
    target = DEFAULT_TARGET_SCORES.get(dimension, {"lo": 0, "hi": 1})
    # 归一化到 0-1
    norm_01 = normalized / 5.0
    if norm_01 >= target["hi"]:
        return "excellent"
    elif norm_01 >= target["lo"]:
        return "good"
    elif norm_01 >= target["lo"] - 0.15:
        return "fair"
    else:
        return "poor"


def score_trace_dimensions(
    case: dict,
    events: list[dict],
    score: dict,
    cfg: C.EvalConfig | None = None,
    *,
    all_historical_scores: list[dict] | None = None,
    cases: list[dict] | None = None,
    skill_yaml: dict | None = None,
    multi_judge_data: dict | None = None,
) -> dict:
    """对一个 case 计算五维评分。

    Returns:
      {
        "dimensions": {trust: {...}, reliability: {...}, ...},
        "trace_weighted_score": 0.85,  # 0-1
        "trace_normalized_score": 4.25,  # 0-5
        "radar": [...],
        "status": "good",
      }
    """
    if cases is None:
        cases = []

    # 尝试加载 skill_rules.yaml
    if skill_yaml is None:
        try:
            mut_dir = cfg.mutators_dir if cfg else None
            if mut_dir:
                skill_yaml_path = mut_dir / "skill_rules.yaml"
                if skill_yaml_path.exists():
                    skill_yaml = C.load_yaml(skill_yaml_path)
        except Exception:
            skill_yaml = None

    dims = {}
    dims["trust"] = score_trust(events, score, multi_judge_data)
    dims["reliability"] = score_reliability(all_historical_scores or [], score.get("case_run_id", ""))
    dims["adaptability"] = score_adaptability(case, events, score, cases)
    dims["convention"] = score_convention(case, events, score, skill_yaml)
    dims["effectiveness"] = score_effectiveness(score)

    # 加权总分
    weights = DEFAULT_TRACE_WEIGHTS
    if cfg and hasattr(cfg, "trace_weights") and cfg.trace_weights:
        weights = cfg.trace_weights

    weighted = sum(weights.get(d, 0.2) * dims[d]["raw_score"] for d in DIMENSIONS)

    # 雷达图数据（0-5 尺度）
    radar = [dims[d]["normalized_score"] for d in DIMENSIONS]

    # 综合状态
    norm_5 = weighted * 5
    if norm_5 >= 4.5:
        status = "excellent"
    elif norm_5 >= 4.0:
        status = "good"
    elif norm_5 >= 3.0:
        status = "fair"
    else:
        status = "poor"

    return {
        "case_id": case.get("id"),
        "dimensions": dims,
        "weights_used": weights,
        "trace_weighted_score": round(weighted, 3),
        "trace_normalized_score": round(norm_5, 2),
        "radar": radar,
        "radar_labels": ["Trust", "Reliability", "Adaptability", "Convention", "Effectiveness"],
        "target_zones": [DEFAULT_TARGET_SCORES[d] for d in DIMENSIONS],
        "status": status,
        "status_label": STATUS_MAP.get(status, {}).get("label", "?"),
    }


def score_trace_run(
    cfg: C.EvalConfig,
    run_id: str,
    score_data: dict,
    cases: list[dict],
    *,
    multi_judge_data: dict | None = None,
) -> dict:
    """对整次 run 做 TRACE 汇总评分。

    遍历 per_case，逐个计算五维，再聚合为 run 级分数。
    """
    # 加载历史所有 scores
    all_historical: list[dict] = []
    if cfg.scores_dir.exists():
        for p in sorted(cfg.scores_dir.glob("*.json")):
            try:
                all_historical.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue

    # 加载 skill_rules.yaml
    skill_yaml = None
    try:
        skill_yaml_path = cfg.mutators_dir / "skill_rules.yaml"
        if skill_yaml_path.exists():
            skill_yaml = C.load_yaml(skill_yaml_path)
    except Exception:
        pass

    # 逐 case 计算
    per_case_trace: list[dict] = []
    for case in cases:
        cid = case.get("id")
        # 找到这个 case 的 score 和 events
        pc_score = next((c for c in score_data.get("per_case", [])
                         if c.get("case_id") == cid), {})
        if not pc_score:
            continue

        # 加载 events
        trace_path = cfg.traces_dir / f"{run_id}.jsonl"
        all_events = C.load_jsonl(trace_path)
        case_run_id = pc_score.get("case_run_id", "")
        events = [e for e in all_events if e.get("case_run_id") == case_run_id]

        trace = score_trace_dimensions(
            case=case,
            events=events,
            score=pc_score,
            cfg=cfg,
            all_historical_scores=all_historical,
            cases=cases,
            skill_yaml=skill_yaml,
            multi_judge_data=multi_judge_data,
        )
        per_case_trace.append(trace)

    # 聚合
    if per_case_trace:
        avg_trace = round(statistics.mean(
            [t["trace_normalized_score"] for t in per_case_trace]
        ), 2)
        avg_weighted = round(statistics.mean(
            [t["trace_weighted_score"] for t in per_case_trace]
        ), 3)
        # 各维度均值
        dim_avgs = {}
        for d in DIMENSIONS:
            vals = [t["dimensions"][d]["normalized_score"] for t in per_case_trace
                    if d in t.get("dimensions", {})]
            dim_avgs[d] = round(statistics.mean(vals), 2) if vals else 0
    else:
        avg_trace = 0
        avg_weighted = 0
        dim_avgs = {d: 0 for d in DIMENSIONS}

    # 综合状态
    if avg_trace >= 4.5:
        status = "excellent"
    elif avg_trace >= 4.0:
        status = "good"
    elif avg_trace >= 3.0:
        status = "fair"
    else:
        status = "poor"

    result = {
        "run_id": run_id,
        "n_cases_evaluated": len(per_case_trace),
        "trace_weighted_score": avg_weighted,
        "trace_normalized_score": avg_trace,
        "dimension_averages": dim_avgs,
        "radar": [dim_avgs.get(d, 0) for d in DIMENSIONS],
        "radar_labels": ["Trust", "Reliability", "Adaptability", "Convention", "Effectiveness"],
        "target_zones": [
            {"dimension": d, "lo": DEFAULT_TARGET_SCORES[d]["lo"] * 5,
             "hi": DEFAULT_TARGET_SCORES[d]["hi"] * 5}
            for d in DIMENSIONS
        ],
        "status": status,
        "status_label": STATUS_MAP.get(status, {}).get("label", "?"),
        "per_case": per_case_trace,
    }

    # 写入文件
    out_path = cfg.scores_dir / f"{run_id}.trace.json"
    C.write_json(out_path, result)

    return result


# ---------------------------------------------------------------------------
# 独立 CLI
# ---------------------------------------------------------------------------

def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="TRACE 五维评测引擎")
    ap.add_argument("--config", required=True, help=".agent-eval/config.yaml 路径")
    ap.add_argument("--run", required=True, help="run_id")
    ap.add_argument("--split", default="train", help="case split")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])

    score_path = cfg.scores_dir / f"{args.run}.json"
    if not score_path.exists():
        print(f"[tracer_scorer] scores 文件不存在: {score_path}，请先跑 scorer")
        return 2

    score_data = json.loads(score_path.read_text(encoding="utf-8"))

    # 尝试加载 multi_judge
    multi_judge_data = None
    mj_path = cfg.reports_dir / f"{args.run}_judges.json"
    if mj_path.exists():
        try:
            multi_judge_data = json.loads(mj_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    result = score_trace_run(cfg, args.run, score_data, cases,
                             multi_judge_data=multi_judge_data)

    print(f"[tracer_scorer] TRACE 总分: {result['trace_normalized_score']:.2f}/5.0")
    print(f"[tracer_scorer] 综合状态: {result['status_label']}")
    for d in DIMENSIONS:
        s = result["dimension_averages"].get(d, 0)
        status = classify_status(s, d)
        status_label = STATUS_MAP.get(status, {}).get("label", "?")
        print(f"  {d:15s}: {s:.2f} [{status_label}]")
    print(f"[tracer_scorer] 输出: {cfg.scores_dir / (args.run + '.trace.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
