#!/usr/bin/env python3
"""spring_ai_to_uatr.py — Spring AI observation → UATR 转换器。

Spring AI 端通过 EvalTraceAdvisor / EvalToolCallbackWrapper 吐出的事件
是 camelCase 字段（eventType / stepNumber / toolName 等）。本脚本把它们
转成 UATR snake_case + 结构化字段。

用法:
  python spring_ai_to_uatr.py --input raw_spring_ai.jsonl --out uatr.jsonl
  python spring_ai_to_uatr.py --input raw.jsonl --check

也可作为模块导入:
  from spring_ai_to_uatr import convert
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))  # 让 import common 能找到
import common as C  # noqa: E402
from trace_normalizer import DEFAULT_MAPPING  # noqa: E402


# Spring AI 事件类型 → UATR event_type
SPRING_AI_TO_UATR = {
    "agent_start": "agent.run.start",
    "agent_end": "agent.run.end",
    "prompt_rendered": "model.call.start",
    "model_call": "model.call.end",
    "tool_call": "tool.call.start",
    "tool_result": "tool.call.end",
    "tool_error": "tool.call.error",
    "memory_retrieval": "memory.retrieve.end",
    "advisor_enter": "planner.step",
    "advisor_exit": "planner.step",
    "agent_final": "agent.run.end",
    "error": "tool.call.error",
}


def convert(raw: dict, framework: str = "spring_ai") -> dict:
    """把一条 Spring AI raw 事件转成 UATR。

    Spring AI 事件字段（camelCase）：
      eventType, stepNumber, caseRunId, caseId, runId, timestamp,
      agentName, toolName, toolArguments, toolResult, errorMessage,
      finalAnswer, promptHash, inputTokens, outputTokens,
      memoryQuery, memoryHits, advisor, status, latencyMs
    """
    # 先用通用 mapping 转 v0 snake_case
    ev = {}
    for k, v in raw.items():
        ev[DEFAULT_MAPPING.get(k, k)] = v

    # 再 v0 → UATR
    uatr = C.v0_to_uatr(ev, framework)
    # 特殊处理：Spring AI 的 eventType 可能已经直接是 v0 event 名
    raw_event = raw.get("eventType") or raw.get("event") or ev.get("event")
    if raw_event in SPRING_AI_TO_UATR:
        uatr["event_type"] = SPRING_AI_TO_UATR[raw_event]
    # Spring AI 特有字段补充
    if raw.get("toolName"):
        uatr["component"] = {"type": "tool", "name": raw["toolName"]}
    if raw.get("toolArguments"):
        uatr.setdefault("attributes", {})["tool.arguments"] = raw["toolArguments"]
    if raw.get("toolResult"):
        uatr["output"] = {"summary": str(raw["toolResult"])[:200]}
    if raw.get("finalAnswer"):
        uatr["output"] = {"final_answer": raw["finalAnswer"]}
    if raw.get("latencyMs"):
        uatr.setdefault("metrics", {})["latency_ms"] = raw["latencyMs"]
    if raw.get("inputTokens"):
        uatr.setdefault("metrics", {})["input_tokens"] = raw["inputTokens"]
    if raw.get("outputTokens"):
        uatr.setdefault("metrics", {})["output_tokens"] = raw["outputTokens"]
    if raw.get("promptHash"):
        uatr.setdefault("attributes", {})["prompt_hash"] = raw["promptHash"]
    if raw.get("memoryQuery"):
        uatr.setdefault("attributes", {})["memory.query"] = raw["memoryQuery"]
    if raw.get("memoryHits"):
        uatr.setdefault("attributes", {})["memory.hits"] = raw["memoryHits"]
    if raw.get("advisor"):
        uatr.setdefault("attributes", {})["advisor"] = raw["advisor"]
    if raw.get("errorMessage"):
        uatr["status"] = "error"
        uatr.setdefault("attributes", {})["error"] = raw["errorMessage"]
    return uatr


def convert_file(input_path: Path, output_path: Path) -> tuple[int, int]:
    """转换整个文件。返回 (n_valid, n_invalid)。"""
    events = C.load_jsonl(input_path)
    valid, invalid = [], []
    for raw in events:
        uatr = convert(raw)
        errs = C.validate_event(uatr)
        if errs:
            uatr["_validation_errors"] = errs
            invalid.append(uatr)
        else:
            valid.append(uatr)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ev in valid:
            f.write(C.json.dumps(ev, ensure_ascii=False) + "\n")
    if invalid:
        invalid_path = output_path.with_suffix(".invalid.jsonl")
        with invalid_path.open("w", encoding="utf-8") as f:
            for ev in invalid:
                f.write(C.json.dumps(ev, ensure_ascii=False) + "\n")
    return len(valid), len(invalid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    p = Path(args.input)
    if not p.exists():
        sys.stderr.write(f"文件不存在: {p}\n")
        return 2

    if args.check:
        events = C.load_jsonl(p)
        n_valid, n_invalid = 0, 0
        for raw in events:
            uatr = convert(raw)
            if C.validate_event(uatr):
                n_invalid += 1
            else:
                n_valid += 1
        print(f"valid={n_valid} invalid={n_invalid} total={len(events)}")
        return 0 if n_invalid == 0 else 1

    if not args.out:
        ap.error("--out 或 --check 必填")

    n_valid, n_invalid = convert_file(Path(args.input), Path(args.out))
    print(f"converted: valid={n_valid} invalid={n_invalid}")
    print(f"output: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
