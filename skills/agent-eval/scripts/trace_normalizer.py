#!/usr/bin/env python3
"""trace_normalizer.py — 把 adapter 吐出的 trace 规范化到 UATR schema。

v0.5 升级：
- 自动检测 v0 / UATR 格式
- v0 自动转 UATR
- 支持 artifact 引用 + 脱敏
- 同时写 v0 兼容字段（event / step）让老 scorer 能读

被 eval_runner.py 进程内调用，也提供 CLI：
  python trace_normalizer.py --input traces/<run_id>.jsonl --check
  python trace_normalizer.py --convert spring_ai --input raw.jsonl --out uatr.jsonl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


DEFAULT_MAPPING: dict[str, str] = {
    # 外部字段名 -> 内部字段名（v0 兼容映射）
    "eventType": "event",
    "stepNumber": "step",
    "agentName": "agent",
    "toolName": "tool",
    "toolArguments": "arguments",
    "toolResult": "result",
    "errorMessage": "error",
    "finalAnswer": "final_answer",
    "promptHash": "prompt_hash",
    "inputTokens": "input_tokens",
    "outputTokens": "output_tokens",
    "memoryQuery": "memory_query",
    "memoryHits": "memory_hits",
    "timestamp": "ts",
}


def apply_mapping(ev: dict, mapping: dict[str, str] | None) -> dict:
    """把 ev 的字段按 mapping 重命名。未在 mapping 里的字段保留原名。"""
    if not mapping:
        return dict(ev)
    out: dict = {}
    for k, v in ev.items():
        out[mapping.get(k, k)] = v
    return out


def redact(ev: dict, fields: list[str] | None) -> dict:
    """脱敏。fields 是 dot-path 列表，如 ["result.ssn", "attributes.tool.arguments.id_card"]。"""
    if not fields:
        return ev
    out = dict(ev)
    for path in fields:
        parts = path.split(".")
        _redact_path(out, parts)
    return out


def _redact_path(obj, parts: list[str]) -> None:
    """递归脱敏一个 dot-path。"""
    if not parts or obj is None:
        return
    cur = obj
    for p in parts[:-1]:
        if isinstance(cur, dict):
            if p not in cur:
                return
            cur = cur[p]
        elif isinstance(cur, list):
            for item in cur:
                _redact_path(item, parts)
            return
        else:
            return
    last = parts[-1]
    if isinstance(cur, dict) and last in cur:
        cur[last] = "<redacted>"


def fill_required(ev: dict, run_id: str, case_id: str, case_run_id: str) -> dict:
    """补全必填字段（v0 + UATR）。"""
    out = dict(ev)
    out.setdefault("run_id", run_id)
    out.setdefault("case_id", case_id)
    out.setdefault("case_run_id", case_run_id)
    out.setdefault("ts", C.now_iso())
    out.setdefault("timestamp", out["ts"])
    out.setdefault("step", 0)
    if "event" not in out and "event_type" not in out:
        out["event"] = "unknown"
    return out


def normalize(
    raw_events: list[dict],
    run_id: str,
    case_id: str,
    case_run_id: str,
    mapping: dict[str, str] | None = None,
    redact_fields: list[str] | None = None,
    framework: str = "spring_ai",
) -> tuple[list[dict], list[dict]]:
    """规范化到 UATR。

    返回 (valid_events, invalid_events)。
    - valid: UATR 格式事件（同时含 v0 兼容字段）
    - invalid: 校验失败的事件
    """
    valid: list[dict] = []
    invalid: list[dict] = []
    for raw in raw_events:
        ev = apply_mapping(raw, mapping)
        ev = fill_required(ev, run_id, case_id, case_run_id)
        ev = redact(ev, redact_fields)
        # 如果不是 UATR，转成 UATR
        if not C.is_uatr(ev):
            ev = C.v0_to_uatr(ev, framework)
        # 同时保留 v0 兼容字段（event / step），让老 scorer 能读
        ev = _add_v0_compat_fields(ev)
        errs = C.validate_event(ev)
        if errs:
            ev["_validation_errors"] = errs
            invalid.append(ev)
        else:
            valid.append(ev)
    # 按 step 排序
    valid.sort(key=lambda e: e.get("step", 0) or
                           int(e.get("span_id", "span_0000").split("_")[-1])
                           if e.get("span_id") else 0)
    return valid, invalid


def _add_v0_compat_fields(ev: dict) -> dict:
    """给 UATR 事件加 v0 兼容字段（event / step / agent / tool 等），让老 scorer 能读。"""
    uatr_to_v0 = {
        "agent.run.start": "agent_start",
        "agent.run.end": "agent_end",
        "model.call.start": "prompt_rendered",
        "model.call.end": "model_call",
        "tool.call.start": "tool_call",
        "tool.call.end": "tool_result",
        "tool.call.error": "error",
        "memory.retrieve.start": "memory_retrieval",
        "memory.retrieve.end": "memory_retrieval",
        "planner.step": "advisor_enter",
        "skill.select": "agent_start",
        "skill.load": "agent_start",
        "skill.execute.start": "agent_start",
        "skill.execute.end": "agent_end",
    }
    et = ev.get("event_type", "")
    ev["event"] = uatr_to_v0.get(et, "agent_start")
    # step 从 span_id 提取
    sid = ev.get("span_id", "")
    if isinstance(sid, str) and sid.startswith("span_"):
        try:
            ev["step"] = int(sid.split("_")[-1])
        except ValueError:
            ev["step"] = 0
    else:
        ev["step"] = 0
    # agent
    actor = ev.get("actor") or {}
    if actor.get("name"):
        ev["agent"] = actor["name"]
    # tool
    comp = ev.get("component") or {}
    if comp.get("type") == "tool" and comp.get("name"):
        ev["tool"] = comp["name"]
    # arguments
    attrs = ev.get("attributes") or {}
    if "tool.arguments" in attrs:
        ev["arguments"] = attrs["tool.arguments"]
    # final_answer
    out = ev.get("output") or {}
    if "final_answer" in out:
        ev["final_answer"] = out["final_answer"]
    elif "summary" in out:
        ev["result"] = {"summary": out["summary"]}
    # metrics
    metrics = ev.get("metrics") or {}
    if "latency_ms" in metrics:
        ev["latency_ms"] = metrics["latency_ms"]
    if "input_tokens" in metrics:
        ev["input_tokens"] = metrics["input_tokens"]
    if "output_tokens" in metrics:
        ev["output_tokens"] = metrics["output_tokens"]
    # prompt_hash
    if "prompt_hash" in attrs:
        ev["prompt_hash"] = attrs["prompt_hash"]
    # model
    if "gen_ai.system" in attrs:
        ev["model"] = attrs["gen_ai.system"]
    # memory
    if "memory.query" in attrs:
        ev["memory_query"] = attrs["memory.query"]
    if "memory.hits" in attrs:
        ev["memory_hits"] = attrs["memory.hits"]
    # advisor
    if "advisor" in attrs:
        ev["advisor"] = attrs["advisor"]
    # status
    if ev.get("status") == "error":
        ev.setdefault("error", {"type": "error", "message": attrs.get("error", "")})
    return ev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="trace jsonl 文件")
    ap.add_argument("--check", action="store_true", help="只校验不输出")
    ap.add_argument("--convert", choices=["spring_ai", "claude_code", "generic"],
                    help="转换指定框架的 raw trace 到 UATR")
    ap.add_argument("--out", help="转换后的输出文件")
    args = ap.parse_args()

    p = Path(args.input)
    if not p.exists():
        sys.stderr.write(f"文件不存在: {p}\n")
        return 2
    events = C.load_jsonl(p)
    n_valid, n_invalid = 0, 0
    for ev in events:
        errs = C.validate_event(ev)
        if errs:
            n_invalid += 1
            print(f"INVALID step={ev.get('step')} event={ev.get('event') or ev.get('event_type')}: {errs}")
        else:
            n_valid += 1
    print(f"valid={n_valid} invalid={n_invalid} total={len(events)}")
    return 0 if n_invalid == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
