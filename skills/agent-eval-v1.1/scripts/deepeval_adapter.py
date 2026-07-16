#!/usr/bin/env python3
"""deepeval_adapter.py — DeepEval metric provider。

v1 把 DeepEval 作为可选 metric provider，不让它控制流程。
本脚本负责：
1. 把 UATR trace + cases 转成 DeepEval 的 test case 格式
2. 调用 DeepEval metrics（如果安装了）
3. 把结果回写到统一 report

如果没装 deepeval，提供 fallback 的纯 Python 实现（用规则模拟 G-Eval 的核心逻辑）。

用法:
  python deepeval_adapter.py --config .agent-eval/config.yaml --run <run_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

try:
    from deepeval import evaluate
    from deepeval.metrics import GEval, ToolCorrectnessMetric
    from deepeval.test_case import LLMTestCase, ConversationalTestCase
    HAS_DEEPEVAL = True
except ImportError:
    HAS_DEEPEVAL = False


def uatr_to_deepeval_cases(cases: list[dict], events_by_case: dict, scores_by_case: dict) -> list[dict]:
    """把 UATR trace + cases 转成 DeepEval test case 格式。"""
    out = []
    for case in cases:
        cid = case.get("id")
        events = events_by_case.get(cid, [])
        score = scores_by_case.get(cid, {})

        # 提取 final_answer
        final = ""
        for e in events:
            if e.get("event_type") == "agent.run.end":
                out_obj = e.get("output") or {}
                if isinstance(out_obj, dict):
                    final = out_obj.get("final_answer", "")
                break
            elif e.get("event") == "agent_final":
                final = e.get("final_answer", "")
                break

        # 提取工具调用
        tools_called = []
        for e in events:
            if e.get("event_type") == "tool.call.start" or e.get("event") == "tool_call":
                tool = (e.get("component") or {}).get("name", "") or e.get("tool", "")
                if tool:
                    tools_called.append(tool)

        expected_tools = case.get("expected_tools", {}) or {}
        out.append({
            "case_id": cid,
            "input": case.get("input", {}).get("user_message", ""),
            "actual_output": final,
            "expected_output": " ".join((case.get("expected", {}) or {}).get("final_decision", {}).get("contains", [])),
            "expected_tools": expected_tools.get("required", []),
            "actual_tools": tools_called,
            "context": [str(case.get("task", ""))],
        })
    return out


def run_deepeval_metrics(test_cases: list[dict]) -> dict:
    """运行 DeepEval metrics。如果没装 deepeval，用 fallback。"""
    if HAS_DEEPEVAL:
        return _run_real_deepeval(test_cases)
    else:
        return _run_fallback(test_cases)


def _run_real_deepeval(test_cases: list[dict]) -> dict:
    """真正的 DeepEval 调用。"""
    results = []
    for tc in test_cases:
        # G-Eval for task success
        g_eval = GEval(
            name="Task Success",
            criteria="Does the actual output contain all expected concepts and satisfy the task?",
            evaluation_params=["input", "actual_output", "expected_output"],
        )
        # Tool Correctness
        tool_metric = ToolCorrectnessMetric(
            name="Tool Correctness",
            expected_tools=tc["expected_tools"],
        )
        llm_tc = LLMTestCase(
            input=tc["input"],
            actual_output=tc["actual_output"],
            expected_output=tc["expected_output"],
            context=tc["context"],
        )
        # 注意：ToolCorrectnessMetric 需要 tools_called
        # 这里简化，实际 DeepEval API 可能略有不同
        try:
            g_eval.measure(llm_tc)
            g_score = g_eval.score
        except Exception:
            g_score = 0.0

        results.append({
            "case_id": tc["case_id"],
            "g_eval_score": g_score,
            "tool_correctness": 1.0 if set(tc["expected_tools"]).issubset(set(tc["actual_tools"])) else 0.0,
        })
    return {"provider": "deepeval", "results": results}


def _run_fallback(test_cases: list[dict]) -> dict:
    """没装 deepeval 时的 fallback：用规则模拟。"""
    results = []
    for tc in test_cases:
        # 模拟 G-Eval: 检查 expected_output 的关键词是否都在 actual_output
        expected_keywords = tc["expected_output"].split()
        hit = sum(1 for kw in expected_keywords if kw in tc["actual_output"])
        g_score = hit / len(expected_keywords) if expected_keywords else 1.0

        # tool correctness
        expected_set = set(tc["expected_tools"])
        actual_set = set(tc["actual_tools"])
        tool_score = len(expected_set & actual_set) / len(expected_set) if expected_set else 1.0

        results.append({
            "case_id": tc["case_id"],
            "g_eval_score": round(g_score, 3),
            "tool_correctness": round(tool_score, 3),
            "note": "fallback (deepeval not installed)",
        })
    return {"provider": "fallback", "results": results}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])
    score_data = json.loads((cfg.scores_dir / f"{args.run}.json").read_text(encoding="utf-8"))

    # 加载 trace
    events = C.load_jsonl(cfg.traces_dir / f"{args.run}.jsonl")
    events_by_case: dict[str, list] = {}
    for e in events:
        cid = e.get("case_id", "")
        events_by_case.setdefault(cid, []).append(e)

    scores_by_case = {c["case_id"]: c for c in score_data.get("per_case", [])}

    test_cases = uatr_to_deepeval_cases(cases, events_by_case, scores_by_case)
    print(f"[deepeval_adapter] 转换 {len(test_cases)} 个 test case")
    print(f"[deepeval_adapter] deepeval installed: {HAS_DEEPEVAL}")

    result = run_deepeval_metrics(test_cases)

    out = cfg.scores_dir / f"{args.run}.deepeval.json"
    C.write_json(out, result)
    print(f"[deepeval_adapter] output: {out}")
    print(f"[deepeval_adapter] provider: {result['provider']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
