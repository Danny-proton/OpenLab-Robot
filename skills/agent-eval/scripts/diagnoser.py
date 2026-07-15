#!/usr/bin/env python3
"""diagnoser.py — 把失败 case 归因到 F1–F7。

被 eval_runner 在报告阶段调用，也可单独运行：
  python diagnoser.py --config .agent-eval/config.yaml --latest
  python diagnoser.py --config .agent-eval/config.yaml --run <run_id>

输出:
  .agent-eval/reports/<run_id>_diagnosis.md
  .agent-eval/reports/<run_id>_diagnosis.json  （供 mutator 读取）
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import scorer as S  # noqa: E402


# ---------------------------------------------------------------------------
# 归因逻辑：每个失败 case 走一遍 F1–F7 检查，命中的记录证据
# ---------------------------------------------------------------------------

def diagnose_case(
    case: dict,
    events: list[dict],
    score: dict,
) -> list[dict]:
    """对一条失败 case 输出 1..N 条诊断记录。"""
    diagnoses: list[dict] = []
    case_id = case.get("id")
    case_run_id = score.get("case_run_id", "")
    metrics = score.get("metrics", {})

    final = S.extract_final(events)
    tool_calls = S.extract_tool_calls(events)
    tool_results = S.extract_tool_results(events)
    actual_tools = [tc.get("tool", "") for tc in tool_calls]

    # ---- F3 工具选择 ----
    expected_tools = case.get("expected_tools") or {}
    required: list[str] = expected_tools.get("required", []) or []
    forbidden: list[str] = expected_tools.get("forbidden", []) or []

    missing_required = [t for t in required if t not in actual_tools]
    if missing_required:
        diagnoses.append({
            "failure_type": "F3.1",
            "failure_label": "工具选择失败-漏工具",
            "evidence": [
                {"event": "tool_call", "step": -1,
                 "reason": f"required tools not called: {missing_required}"},
            ],
            "suggested_mutation_target": "tool_schema",
            "suggested_mutation_rule": "F3.1_add_tool_description",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # F3.3 重复调用
    seen: dict[str, int] = {}
    repeats: list[dict] = []
    for tc in tool_calls:
        key = tc.get("tool", "") + "::" + C.hash_arguments(tc.get("arguments") or {})
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 3:
            repeats.append({"step": tc.get("step"), "tool": tc.get("tool")})
    if repeats:
        diagnoses.append({
            "failure_type": "F3.3",
            "failure_label": "工具选择失败-重复调用",
            "evidence": [{"event": "tool_call", "step": r["step"],
                          "reason": f"tool {r['tool']} called 3+ times with same args"} for r in repeats],
            "suggested_mutation_target": "tool_policy",
            "suggested_mutation_rule": "F3.3_dedup_policy",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # ---- F4 工具参数 ----
    # 检查 tool_result.status == error
    tool_errors = [tr for tr in tool_results if tr.get("status") == "error"]
    if tool_errors:
        diagnoses.append({
            "failure_type": "F4.4",
            "failure_label": "工具参数失败-ID或对象错误",
            "evidence": [
                {"event": "tool_result", "step": tr.get("step"),
                 "reason": f"tool {tr.get('tool')} returned error: {tr.get('result')}"}
                for tr in tool_errors
            ],
            "suggested_mutation_target": "tool_schema",
            "suggested_mutation_rule": "F4.4_id_validation",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # ---- F2 任务理解 ----
    # 判定：model_call 后没有 tool_call 直接 agent_final（没分析就给结论）
    has_model_call = any(e.get("event") == "model_call" for e in events)
    if has_model_call and not tool_calls and final:
        diagnoses.append({
            "failure_type": "F2.1",
            "failure_label": "任务理解失败-没识别任务类型",
            "evidence": [
                {"event": "model_call", "step": -1,
                 "reason": "model_call 后无 tool_call，直接 agent_final"},
            ],
            "suggested_mutation_target": "prompt",
            "suggested_mutation_rule": "F2.1_task_type_in_prompt",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # ---- F5 Workflow ----
    # 判定：有 tool_result.status=error 但后续没 advisor_enter 也没 fallback tool_call
    if tool_errors:
        last_err_step = max(tr.get("step", 0) for tr in tool_errors)
        after = [e for e in events if e.get("step", 0) > last_err_step]
        has_advisor_after = any(e.get("event") in ("advisor_enter", "advisor_exit") for e in after)
        has_fallback = any(e.get("event") == "tool_call" for e in after)
        if not has_advisor_after and not has_fallback:
            diagnoses.append({
                "failure_type": "F5.3",
                "failure_label": "Workflow失败-缺少fallback",
                "evidence": [
                    {"event": "tool_result", "step": last_err_step,
                     "reason": "tool error 后无 advisor 拦截，也无 fallback tool_call"},
                ],
                "suggested_mutation_target": "workflow",
                "suggested_mutation_rule": "F5.3_fallback_advisor",
                "case_id": case_id,
                "case_run_id": case_run_id,
            })

    # 判定：trace 开头没有 advisor_enter（缺前置检查）
    has_any_advisor = any(e.get("event") == "advisor_enter" for e in events)
    if not has_any_advisor and case.get("expect_preflight_advisor"):
        diagnoses.append({
            "failure_type": "F5.1",
            "failure_label": "Workflow失败-缺少前置检查",
            "evidence": [
                {"event": "agent_start", "step": 1,
                 "reason": "trace 中无 advisor_enter 事件，缺前置校验"},
            ],
            "suggested_mutation_target": "workflow",
            "suggested_mutation_rule": "F5.1_input_validation_advisor",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # ---- F6 Memory ----
    memory_events = [e for e in events if e.get("event") == "memory_retrieval"]
    if case.get("expect_memory_use"):
        if not memory_events:
            diagnoses.append({
                "failure_type": "F6.1",
                "failure_label": "Memory失败-没检索到",
                "evidence": [
                    {"event": "agent_start", "step": 1,
                     "reason": "case 期望 memory 使用但 trace 中无 memory_retrieval 事件"},
                ],
                "suggested_mutation_target": "memory",
                "suggested_mutation_rule": "F6.1_memory_trigger_in_prompt",
                "case_id": case_id,
                "case_run_id": case_run_id,
            })
        else:
            for me in memory_events:
                hits = me.get("memory_hits") or []
                if not hits:
                    diagnoses.append({
                        "failure_type": "F6.1",
                        "failure_label": "Memory失败-检索结果为空",
                        "evidence": [
                            {"event": "memory_retrieval", "step": me.get("step"),
                             "reason": f"memory_query={me.get('memory_query')!r} 但 hits 为空"},
                        ],
                        "suggested_mutation_target": "memory",
                        "suggested_mutation_rule": "F6.1_memory_index_expand",
                        "case_id": case_id,
                        "case_run_id": case_run_id,
                    })

    # ---- F7 输出 ----
    # F7.1 格式错
    os_metric = metrics.get("output_schema_validity", {})
    if os_metric.get("score", 1.0) < 1.0 and os_metric.get("detail", {}).get("schema"):
        diagnoses.append({
            "failure_type": "F7.1",
            "failure_label": "输出失败-格式错",
            "evidence": [
                {"event": "agent_final", "step": -1,
                 "reason": f"output_schema_validity={os_metric['score']}, "
                           f"detail={os_metric.get('detail')}"},
            ],
            "suggested_mutation_target": "prompt",
            "suggested_mutation_rule": "F7.1_output_format_in_prompt",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # F7.3 漏业务规则（且不是 F2/F5 导致）
    br_metric = metrics.get("business_rule_coverage", {})
    br_detail = br_metric.get("detail", {})
    unsatisfied = br_detail.get("unsatisfied", [])
    if unsatisfied:
        # 如果同时有 F2.1（没分析就给结论），就归到 F2，不再重复归 F7.3
        already_f2 = any(d["failure_type"].startswith("F2") for d in diagnoses)
        if not already_f2:
            diagnoses.append({
                "failure_type": "F7.3",
                "failure_label": "输出失败-漏业务规则",
                "evidence": [
                    {"event": "agent_final", "step": -1,
                     "reason": f"未覆盖业务规则: {unsatisfied}"},
                ],
                "suggested_mutation_target": "memory",
                "suggested_mutation_rule": "F7.3_rule_to_memory",
                "case_id": case_id,
                "case_run_id": case_run_id,
            })

    # F7.4 幻觉（粗检：final 里的数字没在 trace 里出现）
    numbers_in_final = set(_extract_numbers(final))
    if numbers_in_final:
        trace_text = json.dumps(events, ensure_ascii=False)
        hallucinated = [n for n in numbers_in_final if n not in trace_text]
        # 排除一些常见无意义数字
        hallucinated = [n for n in hallucinated if len(n) >= 2 and n not in {"10", "100", "1000"}]
        if hallucinated:
            diagnoses.append({
                "failure_type": "F7.4",
                "failure_label": "输出失败-幻觉补充事实",
                "evidence": [
                    {"event": "agent_final", "step": -1,
                     "reason": f"final 中出现 trace 中不存在的数字: {hallucinated}"},
                ],
                "suggested_mutation_target": "prompt",
                "suggested_mutation_rule": "F7.4_no_hallucination_in_prompt",
                "case_id": case_id,
                "case_run_id": case_run_id,
            })

    # ---- F1 Skill 触发（仅当 case 标了 expect_skill_trigger）----
    skill_expect = case.get("expect_skill_trigger")
    if skill_expect:
        prompt_events = [e for e in events if e.get("event") == "prompt_rendered"]
        expected_hash = skill_expect.get("prompt_hash")
        if expected_hash:
            actual_hashes = [pe.get("prompt_hash") for pe in prompt_events]
            if expected_hash not in actual_hashes:
                diagnoses.append({
                    "failure_type": "F1.1",
                    "failure_label": "Skill触发失败-没触发",
                    "evidence": [
                        {"event": "prompt_rendered", "step": -1,
                         "reason": f"期望 skill prompt_hash={expected_hash}，实际={actual_hashes}"},
                    ],
                    "suggested_mutation_target": "skill",
                    "suggested_mutation_rule": "F1.1_description_trigger_words",
                    "case_id": case_id,
                    "case_run_id": case_run_id,
                })

    # ---- F8 执行冗余失败（v1.1 新增：针对"轮数过多"）----
    # 即使 case 最终成功，如果步数远超 expected_steps，也归到 F8
    f8_diags = _diagnose_f8_redundancy(case, events, score, case_id, case_run_id)
    diagnoses.extend(f8_diags)

    # ---- 兜底：如果一条失败 case 没有任何诊断，标 UNKNOWN ----
    if not diagnoses and score.get("is_hard_fail"):
        diagnoses.append({
            "failure_type": "UNKNOWN",
            "failure_label": "未知失败",
            "evidence": [
                {"event": "agent_final", "step": -1,
                 "reason": f"hard_fails={score.get('hard_fails')}，但未能归因到 F1-F8"},
            ],
            "suggested_mutation_target": "unknown",
            "suggested_mutation_rule": "UNKNOWN_inspect_trace",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    return diagnoses


def _diagnose_f8_redundancy(
    case: dict,
    events: list[dict],
    score: dict,
    case_id: str,
    case_run_id: str,
) -> list[dict]:
    """F8: 执行冗余失败。检测轮数过多、重复规划、无效中间步。

    F8.1 轮数过多：actual_steps >> expected_steps
    F8.2 重复规划：planner.step / model.call 次数 > tool_call 次数（光想不干）
    F8.3 无效中间步：tool_call 后又 model_call 又 tool_call 同一工具（绕路）
    F8.4 探索式徘徊：连续 model_call 之间没有 tool_call（模型在想但没行动）
    """
    diags: list[dict] = []
    expected_steps = case.get("expected_steps", 8)

    # 实际步数（从 UATR span_id 提取，或从 v0 step 提取）
    actual_steps = 0
    for ev in events:
        s = ev.get("step", 0)
        if isinstance(s, int):
            actual_steps = max(actual_steps, s)
        elif isinstance(ev.get("span_id", ""), str) and ev["span_id"].startswith("span_"):
            try:
                n = int(ev["span_id"].split("_")[-1])
                actual_steps = max(actual_steps, n)
            except ValueError:
                pass

    # F8.1 轮数过多（actual > expected * 1.5）
    if actual_steps > expected_steps * 1.5:
        diags.append({
            "failure_type": "F8.1",
            "failure_label": f"执行冗余-轮数过多（{actual_steps}步 vs 期望{expected_steps}步）",
            "evidence": [
                {"event": "agent.run.end", "step": actual_steps,
                 "reason": f"实际 {actual_steps} 步，期望 {expected_steps} 步，超出 {(actual_steps/expected_steps - 1)*100:.0f}%。"
                           f"通常原因是 prompt 缺少明确执行路径，或缺少 reference 指引工具调用顺序。"},
            ],
            "suggested_mutation_target": "reference",
            "suggested_mutation_rule": "F8.1_inject_execution_path_reference",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # 统计各类事件
    model_calls = [e for e in events if e.get("event_type") == "model.call.end" or e.get("event") == "model_call"]
    tool_calls = [e for e in events if e.get("event_type") == "tool.call.start" or e.get("event") == "tool_call"]
    planner_steps = [e for e in events if e.get("event_type") == "planner.step" or e.get("event") == "advisor_enter"]

    # F8.2 重复规划：planner/model 次数 > tool 次数 * 1.5（光想不干）
    if (len(model_calls) + len(planner_steps)) > len(tool_calls) * 1.5 and len(tool_calls) > 0:
        diags.append({
            "failure_type": "F8.2",
            "failure_label": f"执行冗余-重复规划（model/planner {len(model_calls)+len(planner_steps)} vs tool {len(tool_calls)}）",
            "evidence": [
                {"event": "model.call.end", "step": -1,
                 "reason": f"模型调用 {len(model_calls)} 次 + planner {len(planner_steps)} 次，但工具只调了 {len(tool_calls)} 次。"
                           f"说明模型在反复思考但没有高效行动。建议在 reference 里给出'决策后立即执行'的约束。"},
            ],
            "suggested_mutation_target": "reference",
            "suggested_mutation_rule": "F8.2_inject_act_after_decide_reference",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # F8.3 无效中间步：同一工具被调用多次但中间夹着 model_call（绕路）
    tool_call_sequence = []
    for ev in events:
        if ev.get("event_type") == "tool.call.start" or ev.get("event") == "tool_call":
            tool = (ev.get("component") or {}).get("name", "") or ev.get("tool", "")
            tool_call_sequence.append(tool)
        elif ev.get("event_type") in ("model.call.end", "planner.step") or ev.get("event") in ("model_call", "advisor_enter"):
            tool_call_sequence.append("__think__")

    # 找模式：toolA → __think__ → toolA（同一工具反复调用中间夹思考）
    redundant_patterns = 0
    for i in range(len(tool_call_sequence) - 2):
        if (tool_call_sequence[i] != "__think__"
                and tool_call_sequence[i] == tool_call_sequence[i + 2]
                and tool_call_sequence[i + 1] == "__think__"):
            redundant_patterns += 1
    if redundant_patterns >= 2:
        diags.append({
            "failure_type": "F8.3",
            "failure_label": f"执行冗余-无效中间步（{redundant_patterns} 次工具-思考-同工具模式）",
            "evidence": [
                {"event": "tool.call.start", "step": -1,
                 "reason": f"检测到 {redundant_patterns} 次'调工具→思考→又调同工具'模式。"
                           f"说明第一次调用没拿到完整结果或没看懂结果。"
                           f"建议在 reference 里给出该工具的'参数校验清单'和'结果解读指南'。"},
            ],
            "suggested_mutation_target": "reference",
            "suggested_mutation_rule": "F8.3_inject_tool_usage_guide_reference",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    # F8.4 探索式徘徊：连续 >= 3 个 model_call 之间没有 tool_call
    consecutive_thinks = 0
    max_consecutive = 0
    for item in tool_call_sequence:
        if item == "__think__":
            consecutive_thinks += 1
            max_consecutive = max(max_consecutive, consecutive_thinks)
        else:
            consecutive_thinks = 0
    if max_consecutive >= 3:
        diags.append({
            "failure_type": "F8.4",
            "failure_label": f"执行冗余-探索式徘徊（连续 {max_consecutive} 次思考无行动）",
            "evidence": [
                {"event": "model.call.end", "step": -1,
                 "reason": f"检测到连续 {max_consecutive} 次模型调用之间没有工具调用。"
                           f"说明模型在'想'但不知道'做什么'。"
                           f"建议在 reference 里给出'每一步必须调用一个工具'的硬约束 + 工具选择决策树。"},
            ],
            "suggested_mutation_target": "reference",
            "suggested_mutation_rule": "F8.4_inject_tool_decision_tree_reference",
            "case_id": case_id,
            "case_run_id": case_run_id,
        })

    return diags


def _extract_numbers(text: str) -> list[str]:
    import re
    return re.findall(r"\d+(?:\.\d+)?", text)


# ---------------------------------------------------------------------------
# 一次 run 的诊断
# ---------------------------------------------------------------------------

def diagnose_run(cfg: C.EvalConfig, run_id: str, split: str = "train") -> dict:
    cases = C.load_yaml(cfg.cases_dir / f"{split}.yaml").get("cases", [])
    runs = C.load_jsonl(cfg.runs_dir / f"{run_id}.jsonl")
    runs_by_case = {r["case_id"]: r for r in runs}
    all_events = C.load_jsonl(cfg.traces_dir / f"{run_id}.jsonl")
    score_data = json.loads((cfg.scores_dir / f"{run_id}.json").read_text(encoding="utf-8"))
    per_case_scores = {c["case_id"]: c for c in score_data.get("per_case", [])}

    all_diagnoses: list[dict] = []
    for case in cases:
        cid = case.get("id")
        score = per_case_scores.get(cid, {})
        is_failed = score.get("is_hard_fail") or score.get("weighted_score", 0) < 0.6
        # v1.1: 即使成功的 case 也要跑 F8 冗余检查（轮数过多是效率问题不是正确性问题）
        if not is_failed:
            run_record = runs_by_case.get(cid)
            if not run_record:
                continue
            case_run_id = run_record["case_run_id"]
            events = [e for e in all_events if e.get("case_run_id") == case_run_id]
            # 只跑 F8，不跑其他（其他 F1-F7 是失败归因）
            f8_only = _diagnose_f8_redundancy(case, events, score, cid, case_run_id)
            all_diagnoses.extend(f8_only)
            continue
        run_record = runs_by_case.get(cid)
        if not run_record:
            continue
        case_run_id = run_record["case_run_id"]
        events = [e for e in all_events if e.get("case_run_id") == case_run_id]
        diags = diagnose_case(case, events, score)
        all_diagnoses.extend(diags)

    # 汇总
    by_type: dict[str, int] = {}
    for d in all_diagnoses:
        by_type[d["failure_type"]] = by_type.get(d["failure_type"], 0) + 1

    result = {
        "run_id": run_id,
        "split": split,
        "n_failed_cases": sum(1 for c in per_case_scores.values() if c.get("is_hard_fail") or c.get("weighted_score", 0) < 0.6),
        "n_diagnoses": len(all_diagnoses),
        "by_failure_type": by_type,
        "diagnoses": all_diagnoses,
    }
    return result


def render_diagnosis_report(cfg: C.EvalConfig, run_id: str, result: dict) -> Path:
    out = cfg.reports_dir / f"{run_id}_diagnosis.md"
    lines: list[str] = []
    lines.append(f"# 诊断报告 — {run_id}\n")
    lines.append(f"- 失败 case 数: {result['n_failed_cases']}")
    lines.append(f"- 诊断记录数: {result['n_diagnoses']}")
    lines.append(f"- 按失败类型分布:\n")
    for ft, n in sorted(result["by_failure_type"].items()):
        lines.append(f"  - `{ft}`: {n}")
    lines.append("\n## 逐条诊断\n")
    for d in result["diagnoses"]:
        lines.append(f"### {d['failure_type']} — {d['failure_label']}")
        lines.append(f"- case: `{d['case_id']}`")
        lines.append(f"- case_run_id: `{d['case_run_id']}`")
        lines.append(f"- 建议修改对象: `{d['suggested_mutation_target']}`")
        lines.append(f"- 建议 mutation 规则: `{d['suggested_mutation_rule']}`")
        lines.append("- 证据:")
        for ev in d["evidence"]:
            lines.append(f"  - event=`{ev['event']}` step={ev['step']}: {ev['reason']}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    try:
        import report_manager as RM
        RM.register_report(cfg, out, run_id=run_id, title=f"诊断报告 — {run_id}")
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
    return out


def find_latest_run(cfg: C.EvalConfig) -> str | None:
    runs = sorted((cfg.runs_dir).glob("*.jsonl"))
    if not runs:
        return None
    return runs[-1].stem


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    run_id = args.run
    if args.latest:
        run_id = find_latest_run(cfg)
        if not run_id:
            sys.stderr.write("没有找到任何 run\n")
            return 2
        print(f"[diagnoser] latest run_id={run_id}")

    result = diagnose_run(cfg, run_id, args.split)
    # 写 json
    json_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
    C.write_json(json_path, result)
    try:
        import report_manager as RM
        RM.register_report(cfg, json_path, run_id=run_id, title=f"诊断数据 — {run_id}")
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
    # 写 md
    out = render_diagnosis_report(cfg, run_id, result)
    print(f"[diagnoser] 诊断 {result['n_diagnoses']} 条")
    print(f"[diagnoser] 报告: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
