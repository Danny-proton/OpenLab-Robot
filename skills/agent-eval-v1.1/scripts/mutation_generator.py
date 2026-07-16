#!/usr/bin/env python3
"""mutation_generator.py — 变异生成 + kill matrix（参考 Meta ACH arXiv 2501.12862）。

V1.1 用例自优化的分析模块之一。思路：
1. 取每条 case 的"正常 trace"（来自 run，或从 expected_tools 合成）
2. 注入 6 类变异（漏调工具/重复调用/参数错/空结果/幻觉/冗余步）
3. 用 diagnoser 的归因逻辑检查变异 trace
4. 产出诊断 = killed；未产出 = survived
5. survived 的变异 → 用例需增强

零 LLM。复用 diagnoser 的确定性逻辑。

用法:
  python mutation_generator.py --config .agent-eval/config.yaml --run <run_id> --split train
  python mutation_generator.py --config .agent-eval/config.yaml --latest --split train
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import case_io as CIO  # noqa: E402
import diagnoser as D  # noqa: E402
import scorer as S  # noqa: E402


# ---------------------------------------------------------------------------
# 6 类变异定义
# ---------------------------------------------------------------------------

MUTATIONS = [
    # (id, name, target_failure_type, description)
    ("mut_skip_tool",      "漏调一个 required 工具",      "F3.1", "删除一个 tool.call 事件"),
    ("mut_repeat_tool",    "同工具重复调用 3 次",          "F3.3", "复制一个 tool.call 事件 3 次"),
    ("mut_wrong_param",    "工具参数传错",                 "F4.4", "篡改 tool.arguments 的 id_card 字段"),
    ("mut_empty_result",   "工具返回空结果",               "F5.3", "把 tool.call.end 的 output.summary 改成空"),
    ("mut_hallucinate",    "final 编造 trace 没有的数字",  "F7.4", "在 final_answer 注入 '850' 数字"),
    ("mut_redundant_steps","插入多余 model_call",          "F8.2", "在工具间插入 4 次 model.call"),
]


# ---------------------------------------------------------------------------
# 变异操作（对 trace 事件列表做修改）
# ---------------------------------------------------------------------------

def mutate_skip_tool(events: list[dict], case: dict) -> list[dict]:
    """删除第一个 required 工具的 tool.call 事件对。"""
    required = (case.get("expected_tools") or {}).get("required", []) or []
    if not required:
        return events
    target_tool = required[0]
    new_events = []
    removed = False
    for ev in events:
        et = ev.get("event_type") or ev.get("event", "")
        comp = ev.get("component") or {}
        name = comp.get("name") or ev.get("tool", "")
        if not removed and et.startswith("tool.call") and name == target_tool:
            continue  # 跳过这个工具的所有事件
        new_events.append(ev)
    if not removed and len(new_events) == len(events):
        # 没找到目标工具，删第一个 tool.call
        new_events = [e for e in events if not (e.get("event_type", "").startswith("tool.call") or e.get("event") == "tool_call")][:0] or events
        # 简化：删前两个 tool.call 事件
        tool_indices = [i for i, e in enumerate(events) if e.get("event_type", "").startswith("tool.call") or e.get("event") == "tool_call"]
        if tool_indices:
            del_idx = tool_indices[0]
            new_events = events[:del_idx] + events[del_idx+1:]
    return new_events


def mutate_repeat_tool(events: list[dict], case: dict) -> list[dict]:
    """把第一个 tool.call 事件复制 3 次（重复调用）。"""
    new_events = []
    repeated = False
    for ev in events:
        new_events.append(ev)
        et = ev.get("event_type") or ev.get("event", "")
        if not repeated and et == "tool.call.end":
            # 复制这个 tool.call.end + 对应的 start
            for _ in range(2):
                new_events.append(copy.deepcopy(ev))
            repeated = True
    return new_events


def mutate_wrong_param(events: list[dict], case: dict) -> list[dict]:
    """篡改 tool.call.start 的 arguments.id_card 字段。"""
    new_events = []
    modified = False
    for ev in events:
        ev2 = copy.deepcopy(ev)
        et = ev.get("event_type") or ev.get("event", "")
        if not modified and et == "tool.call.start":
            attrs = ev2.get("attributes") or {}
            args = attrs.get("tool.arguments")
            if isinstance(args, dict):
                if "id_card" in args:
                    args["id_card"] = "WRONG_VALUE"
                    modified = True
                elif "application_id" in args:
                    args["application_id"] = "INVALID"
                    modified = True
            # 也尝试 v0 格式
            if not modified and "arguments" in ev2:
                ev2["arguments"] = {"id_card": "WRONG_VALUE"}
                modified = True
        new_events.append(ev2)
    return new_events


def mutate_empty_result(events: list[dict], case: dict) -> list[dict]:
    """把 tool.call.end 的 output.summary 改成空 + status=error。"""
    new_events = []
    modified = False
    for ev in events:
        ev2 = copy.deepcopy(ev)
        et = ev.get("event_type") or ev.get("event", "")
        if not modified and et == "tool.call.end":
            ev2["output"] = {"summary": ""}
            ev2["status"] = "error"
            # v0 兼容
            if "result" in ev2:
                ev2["result"] = ""
            modified = True
        new_events.append(ev2)
    return new_events


def mutate_hallucinate(events: list[dict], case: dict) -> list[dict]:
    """在 final_answer 注入 '850' 数字（trace 里没有的）。"""
    new_events = []
    for ev in events:
        ev2 = copy.deepcopy(ev)
        et = ev.get("event_type") or ev.get("event", "")
        out = ev2.get("output") or {}
        fa = out.get("final_answer") or ev2.get("final_answer")
        if fa and et in ("agent.run.end", "agent_final"):
            # 注入幻觉数字
            new_fa = fa + " 征信评分 850 分，建议通过。"
            if "output" in ev2:
                ev2["output"]["final_answer"] = new_fa
            else:
                ev2["final_answer"] = new_fa
        new_events.append(ev2)
    return new_events


def mutate_redundant_steps(events: list[dict], case: dict) -> list[dict]:
    """在第一个 tool.call 前插入 4 次 model.call（笨模式）。"""
    new_events: list[dict] = []
    inserted = False
    # 找第一个 tool.call.start 的位置
    first_tool_idx = None
    for i, ev in enumerate(events):
        et = ev.get("event_type") or ev.get("event", "")
        if et == "tool.call.start" or et == "tool_call":
            first_tool_idx = i
            break

    for i, ev in enumerate(events):
        if first_tool_idx is not None and i == first_tool_idx and not inserted:
            # 插入 4 对 model.call
            for j in range(4):
                new_events.append({
                    "schema_version": "uatr-0.5",
                    "run_id": ev.get("run_id", ""),
                    "case_id": ev.get("case_id", ""),
                    "case_run_id": ev.get("case_run_id", ""),
                    "timestamp": ev.get("timestamp", C.now_iso()),
                    "framework": "mutant",
                    "event_type": "model.call.start",
                    "component": {"type": "model", "name": "mutant-llm"},
                    "status": "success",
                    "attributes": {"note": f"redundant think {j+1}"},
                    "step": 100 + j * 2,
                })
                new_events.append({
                    "schema_version": "uatr-0.5",
                    "run_id": ev.get("run_id", ""),
                    "case_id": ev.get("case_id", ""),
                    "case_run_id": ev.get("case_run_id", ""),
                    "timestamp": ev.get("timestamp", C.now_iso()),
                    "framework": "mutant",
                    "event_type": "model.call.end",
                    "component": {"type": "model", "name": "mutant-llm"},
                    "status": "success",
                    "metrics": {"input_tokens": 300, "output_tokens": 20, "latency_ms": 150},
                    "output": {"summary": f"redundant thinking {j+1}"},
                    "step": 101 + j * 2,
                })
            inserted = True
        new_events.append(ev)
    return new_events


MUTATORS = {
    "mut_skip_tool": mutate_skip_tool,
    "mut_repeat_tool": mutate_repeat_tool,
    "mut_wrong_param": mutate_wrong_param,
    "mut_empty_result": mutate_empty_result,
    "mut_hallucinate": mutate_hallucinate,
    "mut_redundant_steps": mutate_redundant_steps,
}


# ---------------------------------------------------------------------------
# 合成"正常 trace"（无 run 时从 case 合成）
# ---------------------------------------------------------------------------

def synthesize_normal_trace(case: dict, run_id: str, case_run_id: str) -> list[dict]:
    """从 case.expected_tools 合成一条"正确"的 trace。"""
    events: list[dict] = []
    step = 1
    case_id = case.get("id", "synth")
    agent = case.get("agent", "synth-agent")
    ts = C.now_iso()

    def add(et: str, **kw):
        nonlocal step
        ev = {
            "schema_version": "uatr-0.5",
            "run_id": run_id,
            "case_id": case_id,
            "case_run_id": case_run_id,
            "trace_id": f"trace-{case_run_id}",
            "span_id": f"span_{step:04d}",
            "timestamp": ts,
            "framework": "synth",
            "source": "synth",
            "event_type": et,
            "actor": {"type": "agent", "name": agent, "role": "executor"},
            "status": "success",
            "step": step,
        }
        ev.update(kw)
        events.append(ev)
        step += 1

    add("agent.run.start", component={"type": "agent", "name": agent})
    add("model.call.start", component={"type": "model", "name": "synth-llm"},
        attributes={"prompt_hash": C.hash_prompt(f"synth-{case_id}")})
    add("model.call.end", component={"type": "model", "name": "synth-llm"},
        metrics={"input_tokens": 500, "output_tokens": 30, "latency_ms": 200},
        output={"summary": "decided to call tools"})

    et = case.get("expected_tools") or {}
    required = et.get("required", []) or []
    app_id = (case.get("input") or {}).get("application_id", "A001")
    for t in required:
        add("tool.call.start", component={"type": "tool", "name": t},
            attributes={"tool.arguments": {"application_id": app_id}})
        add("tool.call.end", component={"type": "tool", "name": t},
            metrics={"latency_ms": 100}, output={"summary": f"result of {t}"})

    # final
    exp = case.get("expected") or {}
    fd = exp.get("final_decision") or {}
    contains = fd.get("contains", []) or []
    final = "、".join(contains) if contains else "分析完成"
    add("agent.run.end", component={"type": "agent", "name": agent},
        metrics={"latency_ms": 1500}, output={"final_answer": final})

    return events


# ---------------------------------------------------------------------------
# kill matrix 核心
# ---------------------------------------------------------------------------

def _make_failed_score(case: dict, case_run_id: str) -> dict:
    """构造一个标记为 hard_fail 的 score，让 diagnoser 跑全 F1-F8 检查。"""
    return {
        "case_id": case.get("id"),
        "case_run_id": case_run_id,
        "weighted_score": 0.0,
        "is_hard_fail": True,
        "hard_fails": ["mutant_injected"],
        "metrics": {
            "task_success": {"score": 0.0},
            "tool_correctness": {"score": 0.0},
            "business_rule_coverage": {"score": 0.0, "detail": {"unsatisfied": []}},
            "output_schema_validity": {"score": 1.0, "detail": {}},
            "efficiency": {"score": 0.0},
        },
    }


def run_kill_matrix(
    cases: list[dict],
    traces_by_case: dict[str, list[dict]],
    run_id: str,
) -> dict[str, Any]:
    """跑 kill matrix。

    traces_by_case: {case_id: [events]}（来自 run 或合成）
    返回 kill matrix + survived 变异列表。
    """
    matrix: list[dict] = []  # 每行一个 case × mutation
    survived_mutations: list[dict] = []
    mutation_stats: dict[str, dict] = {m[0]: {"killed": 0, "survived": 0, "survived_cases": []} for m in MUTATIONS}

    for case in cases:
        cid = case.get("id", "?")
        case_run_id = f"{run_id}-{cid}-mutant"
        base_events = traces_by_case.get(cid)
        if base_events is None:
            base_events = synthesize_normal_trace(case, run_id, case_run_id)

        row = {"case_id": cid, "mutations": {}}

        for mut_id, mut_name, target_ft, mut_desc in MUTATIONS:
            mutator = MUTATORS[mut_id]
            mutated_events = mutator(base_events, case)

            # 用 diagnoser 检查
            score = _make_failed_score(case, case_run_id)
            try:
                diags = D.diagnose_case(case, mutated_events, score)
            except Exception as e:
                diags = []

            produced_fts = {d["failure_type"] for d in diags}
            # killed = 产出了目标 F 类型（或其父类）
            killed = any(
                ft == target_ft or ft.startswith(target_ft.split(".")[0])
                for ft in produced_fts
            )

            row["mutations"][mut_id] = {
                "killed": killed,
                "target_failure_type": target_ft,
                "produced_failure_types": sorted(produced_fts),
            }

            if killed:
                mutation_stats[mut_id]["killed"] += 1
            else:
                mutation_stats[mut_id]["survived"] += 1
                mutation_stats[mut_id]["survived_cases"].append(cid)
                survived_mutations.append({
                    "case_id": cid,
                    "mutation": mut_id,
                    "mutation_name": mut_name,
                    "target_failure_type": target_ft,
                    "reason": f"用例 {cid} 未能检出 {mut_name}（期望产出 {target_ft}，实际产出 {sorted(produced_fts)}）",
                    "suggestion": "增强用例断言，使其能检出该变异",
                })

        matrix.append(row)

    total = sum(s["killed"] + s["survived"] for s in mutation_stats.values())
    killed = sum(s["killed"] for s in mutation_stats.values())
    survived = sum(s["survived"] for s in mutation_stats.values())

    return {
        "run_id": run_id,
        "n_cases": len(cases),
        "total_mutations": total,
        "killed": killed,
        "survived": survived,
        "kill_rate": round(killed / total, 4) if total > 0 else 0.0,
        "mutation_stats": mutation_stats,
        "matrix": matrix,
        "survived_mutations": survived_mutations,
    }


# ---------------------------------------------------------------------------
# 加载 traces
# ---------------------------------------------------------------------------

def load_traces_by_case(cfg: C.EvalConfig, run_id: str) -> dict[str, list[dict]]:
    """从 traces/<run_id>.jsonl 加载，按 case_id 分组。"""
    path = cfg.traces_dir / f"{run_id}.jsonl"
    if not path.exists():
        return {}
    events = C.load_jsonl(path)
    by_case: dict[str, list[dict]] = {}
    for ev in events:
        cid = ev.get("case_id")
        if cid:
            by_case.setdefault(cid, []).append(ev)
    return by_case


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="变异生成 + kill matrix")
    ap.add_argument("--config", required=True)
    ap.add_argument("--run")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--split", default="train")
    ap.add_argument("--out", help="输出 JSON 路径")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = CIO.load_cases(cfg, args.split)

    run_id = args.run
    if args.latest or not run_id:
        run_id = D.find_latest_run(cfg)
        if not run_id:
            # 无 run，用合成 trace
            run_id = "synthetic-mutation"
            print(f"[mutation_generator] 无历史 run，使用合成 trace")
        else:
            print(f"[mutation_generator] latest run_id={run_id}")

    # 加载 traces（无则合成）
    traces_by_case = load_traces_by_case(cfg, run_id) if run_id != "synthetic-mutation" else {}

    result = run_kill_matrix(cases, traces_by_case, run_id)

    # 输出 JSON
    out_path = Path(args.out) if args.out else (cfg.reports_dir / f"case_mutation_{run_id}.json")
    C.write_json(out_path, result)

    # 输出 MD
    md_path = cfg.reports_dir / f"case_mutation_{run_id}.md"
    _render_md(result, md_path)

    print(f"[mutation_generator] 变异总数: {result['total_mutations']}")
    print(f"[mutation_generator] killed: {result['killed']} / survived: {result['survived']}")
    print(f"[mutation_generator] kill_rate: {result['kill_rate']:.2%}")
    print(f"[mutation_generator] survived 变异: {len(result['survived_mutations'])}")
    print(f"[mutation_generator] 报告: {out_path}")
    print(f"[mutation_generator] MD: {md_path}")
    return 0


def _render_md(result: dict, path: Path) -> None:
    lines: list[str] = []
    lines.append(f"# Mutation Kill Matrix — {result['run_id']}\n")
    lines.append(f"- 变异总数: {result['total_mutations']}")
    lines.append(f"- killed: {result['killed']} / survived: {result['survived']}")
    lines.append(f"- kill_rate: {result['kill_rate']:.2%}\n")

    lines.append("## 各变异类型统计\n")
    lines.append("| 变异 | 目标失败 | killed | survived | survived cases |")
    lines.append("|------|---------|--------|----------|---------------|")
    for mut_id, mut_name, target_ft, _ in MUTATIONS:
        s = result["mutation_stats"][mut_id]
        lines.append(f"| {mut_id} ({mut_name}) | {target_ft} | {s['killed']} | {s['survived']} | {', '.join(s['survived_cases']) or '-'} |")
    lines.append("")

    lines.append("## Kill Matrix\n")
    header = ["case_id"] + [m[0] for m in MUTATIONS]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for row in result["matrix"]:
        cells = [row["case_id"]]
        for mut_id, _, _, _ in MUTATIONS:
            m = row["mutations"][mut_id]
            cells.append("✅" if m["killed"] else "❌")
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    if result["survived_mutations"]:
        lines.append("## 未检出变异（需增强用例）\n")
        for sm in result["survived_mutations"]:
            lines.append(f"- **{sm['case_id']}** × {sm['mutation']} ({sm['mutation_name']})")
            lines.append(f"  - {sm['reason']}")
            lines.append(f"  - 建议: {sm['suggestion']}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
