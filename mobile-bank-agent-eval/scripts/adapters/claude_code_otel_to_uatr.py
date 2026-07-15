#!/usr/bin/env python3
"""claude_code_otel_to_uatr.py — Claude Code OTel span → UATR 转换器。

Claude Code 开启增强 telemetry 后会导出 OTel span：
  claude_code.interaction  → agent.run.start / agent.run.end
  claude_code.llm_request  → model.call.start / model.call.end
  claude_code.tool         → tool.call.start / tool.call.end
  claude_code.tool.blocked_on_user → human.approval.request
  claude_code.tool.execution → tool.call.end
  claude_code.hook         → planner.step
  Task 子 agent 嵌套 span → agent.delegate

用法:
  python claude_code_otel_to_uatr.py --input otel_spans.jsonl --out uatr.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import common as C  # noqa: E402


# Claude Code span name → UATR event_type
# 一个 span 通常有开始和结束，转成 .start / .end 两个事件
SPAN_TO_UATR = {
    "claude_code.interaction": "agent.run",
    "claude_code.llm_request": "model.call",
    "claude_code.tool": "tool.call",
    "claude_code.tool.execution": "tool.call",  # 已是结束事件
    "claude_code.tool.blocked_on_user": "human.approval",
    "claude_code.hook": "planner",
    "claude_code.subagent_delegation": "agent.delegate",
}


def convert_span(span: dict) -> list[dict]:
    """一个 OTel span 转成 1-2 个 UATR 事件（start + end）。"""
    name = span.get("name", "")
    span_id = span.get("span_id", "")
    parent_span_id = span.get("parent_span_id", "")
    trace_id = span.get("trace_id", "")
    start_ts = span.get("start_time")
    end_ts = span.get("end_time")
    attrs = span.get("attributes") or {}
    status = "error" if span.get("status_code") == "ERROR" else "success"

    # 找 base event_type
    base = None
    for k, v in SPAN_TO_UATR.items():
        if name.startswith(k):
            base = v
            break
    if not base:
        base = "planner.step"

    # case_id / run_id 从 attributes 提取
    case_run_id = attrs.get("case_run_id", "")
    case_id = attrs.get("case_id", "")
    run_id = attrs.get("run_id", "")

    common_fields = {
        "schema_version": C.UATR_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "case_run_id": case_run_id,
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "framework": "claude_code",
        "source": "otel_export",
        "actor": {"type": "agent", "name": attrs.get("agent_name", "claude-code"),
                  "role": "executor"},
        "attributes": dict(attrs),
        "status": status,
    }

    events: list[dict] = []

    # 如果是 blocked_on_user，只生成一个 request 事件
    if "blocked_on_user" in name:
        ev = dict(common_fields)
        ev["event_type"] = "human.approval.request"
        ev["timestamp"] = start_ts or C.now_iso()
        if "approval_message" in attrs:
            ev["input"] = {"summary": attrs["approval_message"]}
        events.append(ev)
        return events

    # 如果是 tool.execution，只生成一个 end 事件
    if name == "claude_code.tool.execution":
        ev = dict(common_fields)
        ev["event_type"] = "tool.call.end"
        ev["timestamp"] = end_ts or C.now_iso()
        tool_name = attrs.get("tool_name", "unknown")
        ev["component"] = {"type": "tool", "name": tool_name}
        if "tool_result" in attrs:
            ev["output"] = {"summary": str(attrs["tool_result"])[:200]}
        if "latency_ms" in attrs:
            ev["metrics"] = {"latency_ms": attrs["latency_ms"]}
        events.append(ev)
        return events

    # 默认生成 start + end 两个事件
    if start_ts:
        ev_start = dict(common_fields)
        ev_start["event_type"] = base + ".start"
        ev_start["timestamp"] = start_ts
        if base == "tool.call":
            tool_name = attrs.get("tool_name", "unknown")
            ev_start["component"] = {"type": "tool", "name": tool_name}
            if "tool_arguments" in attrs:
                ev_start["attributes"]["tool.arguments"] = attrs["tool_arguments"]
        elif base == "agent.run":
            ev_start["component"] = {"type": "agent", "name": "claude-code"}
        events.append(ev_start)

    if end_ts:
        ev_end = dict(common_fields)
        ev_end["event_type"] = base + ".end"
        ev_end["timestamp"] = end_ts
        if base == "tool.call":
            tool_name = attrs.get("tool_name", "unknown")
            ev_end["component"] = {"type": "tool", "name": tool_name}
            if "tool_result" in attrs:
                ev_end["output"] = {"summary": str(attrs["tool_result"])[:200]}
        elif base == "agent.run":
            ev_end["component"] = {"type": "agent", "name": "claude-code"}
            if "final_answer" in attrs:
                ev_end["output"] = {"final_answer": attrs["final_answer"]}
        if "latency_ms" in attrs:
            ev_end["metrics"] = {"latency_ms": attrs["latency_ms"]}
        if "input_tokens" in attrs:
            ev_end.setdefault("metrics", {})["input_tokens"] = attrs["input_tokens"]
        if "output_tokens" in attrs:
            ev_end.setdefault("metrics", {})["output_tokens"] = attrs["output_tokens"]
        events.append(ev_end)

    # 如果都没生成（缺 ts），至少生成一个
    if not events:
        ev = dict(common_fields)
        ev["event_type"] = base + ".start" if base else "planner.step"
        ev["timestamp"] = C.now_iso()
        events.append(ev)

    return events


def convert_file(input_path: Path, output_path: Path) -> tuple[int, int]:
    spans = C.load_jsonl(input_path)
    all_events: list[dict] = []
    n_invalid = 0
    for span in spans:
        for ev in convert_span(span):
            errs = C.validate_event(ev)
            if errs:
                ev["_validation_errors"] = errs
                n_invalid += 1
            all_events.append(ev)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for ev in all_events:
            f.write(C.json.dumps(ev, ensure_ascii=False) + "\n")
    return len(all_events) - n_invalid, n_invalid


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
        spans = C.load_jsonl(p)
        n_valid, n_invalid = 0, 0
        for span in spans:
            for ev in convert_span(span):
                if C.validate_event(ev):
                    n_invalid += 1
                else:
                    n_valid += 1
        print(f"valid={n_valid} invalid={n_invalid}")
        return 0 if n_invalid == 0 else 1

    if not args.out:
        ap.error("--out 或 --check 必填")

    n_valid, n_invalid = convert_file(Path(args.input), Path(args.out))
    print(f"converted: valid={n_valid} invalid={n_invalid}")
    print(f"output: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
