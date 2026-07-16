#!/usr/bin/env python3
"""scorer.py — 对一次 run 的所有 case 算分。

被 eval_runner.py 进程内调用，也提供 CLI 单独重算某次 run：
  python scorer.py --config .agent-eval/config.yaml --run <run_id>

不依赖第三方库（除 PyYAML）。jsonschema 验证是 best-effort：如果没装 jsonschema，
output_schema_validity 退化成"能否 json.loads"。
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

try:
    import jsonschema  # type: ignore
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


DEFAULT_WEIGHTS = {
    "task_success": 0.35,
    "tool_correctness": 0.20,
    "business_rule_coverage": 0.20,
    "output_schema_validity": 0.15,
    "efficiency": 0.10,
}
HARD_FAIL_PENALTY = 1.0


# ---------------------------------------------------------------------------
# 工具调用提取
# ---------------------------------------------------------------------------

def extract_tool_calls(events: list[dict]) -> list[dict]:
    """返回所有 tool_call 事件，按 step 排序。"""
    return sorted(
        [e for e in events if e.get("event") == "tool_call"],
        key=lambda e: e.get("step", 0),
    )


def extract_tool_results(events: list[dict]) -> list[dict]:
    return sorted(
        [e for e in events if e.get("event") == "tool_result"],
        key=lambda e: e.get("step", 0),
    )


def extract_final(events: list[dict]) -> str:
    for e in events:
        if e.get("event") == "agent_final":
            return e.get("final_answer", "") or ""
    return ""


# ---------------------------------------------------------------------------
# 指标实现
# ---------------------------------------------------------------------------

def metric_task_success(case: dict, events: list[dict], final: str) -> tuple[float, list[str]]:
    """task_success: 最终答案是否满足 expected.final_decision 约束。"""
    expected = (case.get("expected") or {}).get("final_decision") or {}
    contains: list[str] = expected.get("contains", []) or []
    regexes: list[str] = expected.get("regex", []) or []

    misses: list[str] = []
    for kw in contains:
        if kw not in final:
            misses.append(f"missing keyword: {kw!r}")
    for rx in regexes:
        if not re.search(rx, final):
            misses.append(f"regex not matched: {rx!r}")

    if misses:
        return 0.0, misses
    return 1.0, []


def metric_tool_correctness(case: dict, events: list[dict], final: str) -> tuple[float, dict, list[str]]:
    """tool_correctness: required recall / forbidden violation / soft order。"""
    expected_tools = case.get("expected_tools") or {}
    required: list[str] = expected_tools.get("required", []) or []
    forbidden: list[str] = expected_tools.get("forbidden", []) or []
    soft_order: list[str] = (expected_tools.get("order") or {}).get("soft", []) or []

    tool_calls = extract_tool_calls(events)
    actual_tools = [tc.get("tool", "") for tc in tool_calls]
    actual_set = set(actual_tools)

    required_hit = sum(1 for t in required if t in actual_set)
    recall = required_hit / len(required) if required else 1.0

    forbidden_violations = [t for t in actual_tools if t in forbidden]

    # LCS ratio for soft order
    order_score = 1.0
    if soft_order:
        order_score = _lcs_ratio(soft_order, actual_tools)

    hard_fails: list[str] = []
    if forbidden_violations:
        hard_fails.append(f"forbidden_tool_called: {forbidden_violations}")

    # tool_correctness 公式: 0.5*recall + 0.3*order + 0.2*(1 - min(forbidden_count,1))
    score = (
        0.5 * recall
        + 0.3 * order_score
        + 0.2 * (1.0 - min(len(forbidden_violations), 1))
    )
    detail = {
        "required": required,
        "forbidden": forbidden,
        "actual": actual_tools,
        "required_recall": round(recall, 3),
        "forbidden_violations": forbidden_violations,
        "order_soft_score": round(order_score, 3),
    }
    return round(score, 3), detail, hard_fails


def _lcs_ratio(a: list[str], b: list[str]) -> float:
    """最长公共子序列长度 / max(len(a), len(b))。"""
    if not a or not b:
        return 0.0
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[m][n]
    return lcs / max(m, n)


def metric_business_rule_coverage(
    case: dict, events: list[dict], final: str
) -> tuple[float, dict, list[str]]:
    """business_rule_coverage: must_satisfy 规则覆盖比例。"""
    rules = (case.get("business_rules") or {}).get("must_satisfy") or []
    if not rules:
        return 1.0, {"rules": [], "satisfied": [], "unsatisfied": []}, []

    tool_results = extract_tool_results(events)
    satisfied: list[str] = []
    unsatisfied: list[dict] = []

    for r in rules:
        rid = r.get("id", "?")
        ok = False
        # trace_event_contains
        tec = r.get("trace_event_contains")
        if tec:
            # 简化实现：tec 是一个 dict，如 {event: tool_result, field: result.volatility, equals: high}
            target_event = tec.get("event")
            target_field = tec.get("field", "")
            target_value = tec.get("equals")
            for e in events:
                if e.get("event") != target_event:
                    continue
                val = _dotpath(e, target_field)
                if target_value is None:
                    if val is not None and val != "":
                        ok = True
                        break
                else:
                    if val == target_value:
                        ok = True
                        break
        # final_answer_contains
        fac = r.get("final_answer_contains")
        if not ok and fac:
            kws = fac if isinstance(fac, list) else [fac]
            ok = all(kw in final for kw in kws)
        # 默认：如果规则没指定判定方式，看 final 里是否包含规则 description 的关键词
        if not ok and not tec and not fac:
            desc = r.get("description", "")
            # 取 description 里的关键词（前 4 个字）
            kw = desc[:4] if desc else ""
            if kw and kw in final:
                ok = True

        if ok:
            satisfied.append(rid)
        else:
            unsatisfied.append(r)

    coverage = len(satisfied) / len(rules) if rules else 1.0
    hard_fails: list[str] = []
    # hard_fail_if: missing_required_business_rule
    hfail = (case.get("scoring") or {}).get("hard_fail_if") or []
    if "missing_required_business_rule" in hfail and unsatisfied:
        hard_fails.append(f"missing_required_business_rule: {[r.get('id') for r in unsatisfied]}")

    detail = {
        "rules": [r.get("id") for r in rules],
        "satisfied": satisfied,
        "unsatisfied": [r.get("id") for r in unsatisfied],
        "coverage": round(coverage, 3),
    }
    return round(coverage, 3), detail, hard_fails


def _dotpath(obj: dict, path: str):
    cur = obj
    for p in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
    return cur


def metric_output_schema_validity(
    case: dict, events: list[dict], final: str
) -> tuple[float, dict, list[str]]:
    """output_schema_validity: 最终答案能否解析并符合 schema。"""
    schema_path = (case.get("expected") or {}).get("structured_output_schema")
    if not schema_path:
        # 这条 case 没要求结构化输出
        return 1.0, {"schema": None, "note": "no schema required"}, []

    # 从 final 里抽 JSON
    obj, parse_err = _extract_json(final)
    if obj is None:
        hard_fails: list[str] = []
        hfail = (case.get("scoring") or {}).get("hard_fail_if") or []
        if "invalid_json_schema" in hfail:
            hard_fails.append(f"invalid_json_schema: {parse_err}")
        return 0.0, {"schema": schema_path, "parse_error": parse_err}, hard_fails

    # 加载 schema
    schema_file = Path(schema_path)
    if not schema_file.is_absolute():
        # 相对路径相对 .agent-eval/ 解析
        from common import find_agent_eval_dir  # noqa: F811
        try:
            base = find_agent_eval_dir()
            schema_file = base / schema_path
        except FileNotFoundError:
            pass
    if not schema_file.exists():
        return 0.5, {"schema": schema_path, "note": "schema file not found, partial credit"}, []

    try:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except Exception as e:
        return 0.5, {"schema": schema_path, "note": f"schema parse error: {e}"}, []

    if HAS_JSONSCHEMA:
        try:
            jsonschema.validate(obj, schema)
            return 1.0, {"schema": schema_path, "valid": True}, []
        except jsonschema.ValidationError as e:
            hfail = (case.get("scoring") or {}).get("hard_fail_if") or []
            hard_fails = []
            if "invalid_json_schema" in hfail:
                hard_fails.append(f"invalid_json_schema: {e.message}")
            return 0.5, {"schema": schema_path, "valid": False, "error": e.message}, hard_fails
    else:
        # 无 jsonschema 库：只检查 required 字段是否存在
        missing = []
        for r in schema.get("required", []):
            if r not in obj:
                missing.append(r)
        if missing:
            return 0.5, {"schema": schema_path, "valid": False, "missing_required": missing}, []
        return 1.0, {"schema": schema_path, "valid": True, "note": "checked required only"}, []


def _extract_json(text: str) -> tuple[object, str | None]:
    """从 text 里抽 JSON 对象。支持纯 JSON / ```json fence / <json> tag。"""
    text = text.strip()
    # 直接 parse
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass
    # ```json ... ```
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip()), None
        except json.JSONDecodeError as e:
            return None, f"fence json parse error: {e}"
    # <json>...</json>
    m = re.search(r"<json>(.*?)</json>", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip()), None
        except json.JSONDecodeError as e:
            return None, f"tag json parse error: {e}"
    # 第一个 { 到最后一个 }
    i, j = text.find("{"), text.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(text[i : j + 1]), None
        except json.JSONDecodeError as e:
            return None, f"brace json parse error: {e}"
    return None, "no json found"


def metric_efficiency(
    case: dict, events: list[dict], final: str, all_steps: list[int] | None = None
) -> tuple[float, dict]:
    """efficiency: step count / repeat / error recovery。"""
    tool_calls = extract_tool_calls(events)
    actual_steps = max([e.get("step", 0) for e in events], default=0)
    expected_steps = case.get("expected_steps") or 8

    step_score = min(expected_steps, actual_steps) / max(expected_steps, actual_steps) if max(expected_steps, actual_steps) > 0 else 1.0

    # repeat penalty
    seen: dict[str, int] = {}
    repeats = 0
    for tc in tool_calls:
        key = tc.get("tool", "") + "::" + C.hash_arguments(tc.get("arguments") or {})
        seen[key] = seen.get(key, 0) + 1
        if seen[key] >= 3:
            repeats += 1
    repeat_penalty = min(repeats / max(len(tool_calls), 1), 0.5)

    # error recovery
    has_error = any(e.get("event") == "error" for e in events)
    has_final = any(e.get("event") == "agent_final" for e in events)
    if has_error:
        error_recovery = 1.0 if has_final else 0.0
    else:
        error_recovery = 1.0

    score = (
        0.4 * step_score
        + 0.3 * (1.0 - repeat_penalty)
        + 0.3 * error_recovery
    )
    detail = {
        "expected_steps": expected_steps,
        "actual_steps": actual_steps,
        "step_count_score": round(step_score, 3),
        "repeat_tool_calls": repeats,
        "repeat_penalty": round(repeat_penalty, 3),
        "error_recovery": round(error_recovery, 3),
    }
    return round(score, 3), detail


# ---------------------------------------------------------------------------
# 单 case 打分
# ---------------------------------------------------------------------------

def score_case(case: dict, events: list[dict], weights: dict[str, float]) -> dict:
    final = extract_final(events)

    ts_score, ts_misses = metric_task_success(case, events, final)
    tc_score, tc_detail, tc_hard = metric_tool_correctness(case, events, final)
    br_score, br_detail, br_hard = metric_business_rule_coverage(case, events, final)
    os_score, os_detail, os_hard = metric_output_schema_validity(case, events, final)
    ef_score, ef_detail = metric_efficiency(case, events, final)

    # 软指标占位
    ar_score = 1.0
    evf_score = 1.0
    sef_score = 1.0

    hard_fails = tc_hard + br_hard + os_hard
    # case.scoring.hard_fail_if 里的 forbidden_tool_called 已在 tc_hard 里
    is_hard_fail = len(hard_fails) > 0

    w = {**DEFAULT_WEIGHTS, **weights}
    weighted = (
        w["task_success"] * ts_score
        + w["tool_correctness"] * tc_score
        + w["business_rule_coverage"] * br_score
        + w["output_schema_validity"] * os_score
        + w["efficiency"] * ef_score
    )
    if is_hard_fail:
        weighted -= HARD_FAIL_PENALTY

    # TRACE 五维评分（如果 tracer_scorer 可用）
    trace_scores = None
    try:
        from tracer_scorer import score_trace_dimensions
        trace_scores = score_trace_dimensions(case, events, {
            "case_id": case.get("id"),
            "is_hard_fail": is_hard_fail,
            "hard_fails": hard_fails,
            "metrics": {
                "task_success": {"score": ts_score, "misses": ts_misses},
                "tool_correctness": {"score": tc_score, "detail": tc_detail},
                "business_rule_coverage": {"score": br_score, "detail": br_detail},
                "output_schema_validity": {"score": os_score, "detail": os_detail},
                "efficiency": {"score": ef_score, "detail": ef_detail},
                "answer_relevance": {"score": ar_score, "note": "placeholder"},
                "evidence_faithfulness": {"score": evf_score, "note": "placeholder"},
                "step_efficiency": {"score": sef_score, "note": "placeholder"},
            },
        })
    except Exception:
        trace_scores = None

    return {
        "case_id": case.get("id"),
        "is_hard_fail": is_hard_fail,
        "hard_fails": hard_fails,
        "trace_scores": trace_scores,
        "metrics": {
            "task_success": {"score": ts_score, "misses": ts_misses},
            "tool_correctness": {"score": tc_score, "detail": tc_detail},
            "business_rule_coverage": {"score": br_score, "detail": br_detail},
            "output_schema_validity": {"score": os_score, "detail": os_detail},
            "efficiency": {"score": ef_score, "detail": ef_detail},
            "answer_relevance": {"score": ar_score, "note": "placeholder"},
            "evidence_faithfulness": {"score": evf_score, "note": "placeholder"},
            "step_efficiency": {"score": sef_score, "note": "placeholder"},
        },
        "weighted_score": round(weighted, 3),
        "final_answer": final,
    }


# ---------------------------------------------------------------------------
# 一次 run 打分
# ---------------------------------------------------------------------------

def score_run(cfg: C.EvalConfig, run_id: str, cases: list[dict]) -> dict:
    runs = C.load_jsonl(cfg.runs_dir / f"{run_id}.jsonl")
    runs_by_case = {r["case_id"]: r for r in runs}
    # 加载 trace：注意 trace 文件是整 run 一个 jsonl，需要按 case_run_id 过滤
    trace_path = cfg.traces_dir / f"{run_id}.jsonl"
    all_events = C.load_jsonl(trace_path)

    per_case: list[dict] = []
    for case in cases:
        cid = case.get("id")
        run_record = runs_by_case.get(cid)
        if not run_record:
            per_case.append({
                "case_id": cid,
                "status": "missing_run_record",
                "weighted_score": 0.0,
                "is_hard_fail": True,
                "hard_fails": ["missing_run_record"],
            })
            continue
        case_run_id = run_record["case_run_id"]
        events = [e for e in all_events if e.get("case_run_id") == case_run_id]
        if run_record.get("status") != "success":
            per_case.append({
                "case_id": cid,
                "case_run_id": case_run_id,
                "status": run_record["status"],
                "weighted_score": 0.0,
                "is_hard_fail": True,
                "hard_fails": [f"runner_status:{run_record['status']}"],
                "error": run_record.get("error"),
            })
            continue
        s = score_case(case, events, cfg.weights)
        s["case_run_id"] = case_run_id
        s["status"] = "scored"
        per_case.append(s)

    # 汇总
    scores = [c.get("weighted_score", 0.0) for c in per_case]
    latencies = [r.get("latency_ms", 0) for r in runs]
    aggregate = {
        "run_id": run_id,
        "n_cases": len(per_case),
        "n_hard_fail": sum(1 for c in per_case if c.get("is_hard_fail")),
        "n_success": sum(1 for c in per_case if not c.get("is_hard_fail")),
        "weighted_score": round(statistics.mean(scores), 3) if scores else 0.0,
        "score_min": round(min(scores), 3) if scores else 0.0,
        "score_max": round(max(scores), 3) if scores else 0.0,
        "score_stdev": round(statistics.stdev(scores), 3) if len(scores) > 1 else 0.0,
        "latency_p50": int(statistics.median(latencies)) if latencies else 0,
        "latency_mean": int(statistics.mean(latencies)) if latencies else 0,
    }

    result = {
        "run_id": run_id,
        "aggregate": aggregate,
        "per_case": per_case,
        "weights": {**DEFAULT_WEIGHTS, **cfg.weights},
    }
    C.write_json(cfg.scores_dir / f"{run_id}.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])
    result = score_run(cfg, args.run, cases)
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
