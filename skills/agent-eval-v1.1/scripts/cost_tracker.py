#!/usr/bin/env python3
"""cost_tracker.py — Span 管理、Token 计量、成本归因和报表聚合。

用法:
  python cost_tracker.py --config .agent-eval/config.yaml --run <run_id> --build-spans
  python cost_tracker.py --config .agent-eval/config.yaml --run <run_id> --report
  python cost_tracker.py --config .agent-eval/config.yaml --run <run_id> --aggregate-by case
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------------------------------------------------------------------
# 模型定价表（内置，可配置）
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input_per_1m": 3.0, "output_per_1m": 15.0},
    "claude-opus-4-20250514": {"input_per_1m": 15.0, "output_per_1m": 75.0},
    "claude-haiku-3-20240307": {"input_per_1m": 0.25, "output_per_1m": 1.25},
    "claude-3-5-sonnet-20241022": {"input_per_1m": 3.0, "output_per_1m": 15.0},
    "claude-3-opus-20240229": {"input_per_1m": 15.0, "output_per_1m": 75.0},
    "claude-3-haiku-20240307": {"input_per_1m": 0.25, "output_per_1m": 1.25},
    "gpt-4o": {"input_per_1m": 2.5, "output_per_1m": 10.0},
    "gpt-4o-mini": {"input_per_1m": 0.15, "output_per_1m": 0.6},
    "deepseek-chat": {"input_per_1m": 0.14, "output_per_1m": 0.28},
    "deepseek-reasoner": {"input_per_1m": 0.55, "output_per_1m": 2.19},
}


def get_pricing(model: str) -> dict[str, float]:
    """获取模型定价，未找到则返回默认值。"""
    # 尝试精确匹配
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    # 尝试前缀匹配
    for k, v in MODEL_PRICING.items():
        if model.startswith(k.split("-")[0]):
            return v
    return {"input_per_1m": 3.0, "output_per_1m": 15.0}


def calculate_cost(tokens_input: int, tokens_output: int, model: str) -> float:
    """计算单次 LLM 调用的成本（美元）。"""
    pricing = get_pricing(model)
    cost = (
        tokens_input * pricing["input_per_1m"] / 1_000_000
        + tokens_output * pricing["output_per_1m"] / 1_000_000
    )
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Span 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Span:
    span_id: str = ""
    parent_id: Optional[str] = None
    name: str = ""
    start: str = ""
    end: str = ""
    duration_ms: int = 0
    tokens_input: int = 0
    tokens_output: int = 0
    cost_cents: float = 0.0
    attributes: dict = field(default_factory=dict)
    status: str = "complete"
    case_id: str = ""
    cost_status: str = "complete"  # "complete" or "incomplete"

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Span":
        return cls(
            span_id=d.get("span_id", ""),
            parent_id=d.get("parent_id"),
            name=d.get("name", ""),
            start=d.get("start", ""),
            end=d.get("end", ""),
            duration_ms=d.get("duration_ms", 0),
            tokens_input=d.get("tokens_input", 0),
            tokens_output=d.get("tokens_output", 0),
            cost_cents=d.get("cost_cents", 0.0),
            attributes=d.get("attributes", {}),
            status=d.get("status", "complete"),
            case_id=d.get("case_id", ""),
            cost_status=d.get("cost_status", "complete"),
        )


def spans_path(cfg: C.EvalConfig, run_id: str) -> Path:
    return cfg.traces_dir / f"{run_id}.spans.jsonl"


def load_spans(cfg: C.EvalConfig, run_id: str) -> list[Span]:
    path = spans_path(cfg, run_id)
    if not path.exists():
        return []
    spans = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line.strip():
            spans.append(Span.from_dict(json.loads(line)))
    return spans


def save_span(cfg: C.EvalConfig, run_id: str, span: Span) -> None:
    path = spans_path(cfg, run_id)
    C.append_jsonl(path, span.to_dict())


def build_spans_from_trace(
    cfg: C.EvalConfig,
    run_id: str,
    cases: list[dict],
    model: str = "claude-sonnet-4-20250514",
) -> list[Span]:
    """从 trace 事件构建 Span 树。"""
    trace_path = cfg.traces_dir / f"{run_id}.jsonl"
    if not trace_path.exists():
        return []

    events = C.load_jsonl(trace_path)
    runs = C.load_jsonl(cfg.runs_dir / f"{run_id}.jsonl")
    runs_by_case = {r["case_id"]: r for r in runs}

    spans: list[Span] = []
    span_counter = 0

    # 根 Span
    root_span = Span(
        span_id="span_root",
        parent_id=None,
        name="eval_run",
        start=events[0].get("timestamp", C.now_iso()) if events else C.now_iso(),
        end="",
        duration_ms=0,
        attributes={
            "model": model,
            "prompt_version": _compute_prompt_version(cfg),
            "adapter": cfg.adapter_name,
        },
        status="complete",
    )

    # 按 case 分组构建 Span
    for case in cases:
        cid = case.get("id", "")
        case_run_id = f"{run_id}::{cid}"
        case_events = [e for e in events if e.get("case_run_id") == case_run_id]

        if not case_events:
            continue

        span_counter += 1
        case_span = Span(
            span_id=f"span_{span_counter:03d}",
            parent_id="span_root",
            name=f"case_exec:{cid}",
            start=case_events[0].get("timestamp", ""),
            end=case_events[-1].get("timestamp", ""),
            attributes={
                "case_id": cid,
                "risk_level": case.get("risk_level", "unknown"),
                "dimension": ", ".join(case.get("dimensions", []) or ["functional"]),
            },
            case_id=cid,
        )

        # 子 Span：每个工具调用和模型调用
        total_tokens_in = 0
        total_tokens_out = 0
        for ev in case_events:
            event_type = ev.get("event_type", ev.get("event", ""))
            if event_type in ("tool.call.start", "tool_call"):
                span_counter += 1
                tool_name = ev.get("component", {}).get("name", ev.get("tool", "unknown"))
                child = Span(
                    span_id=f"span_{span_counter:03d}",
                    parent_id=case_span.span_id,
                    name=f"tool_call:{tool_name}",
                    start=ev.get("timestamp", ""),
                    end="",
                    attributes={
                        "tool_input": ev.get("attributes", {}).get("tool.arguments", ev.get("arguments", {})),
                    },
                    case_id=cid,
                )
                spans.append(child)
            elif event_type in ("tool.call.end", "tool_result"):
                # 匹配对应的 start span，补充 end 时间和输出
                tool_name = ev.get("component", {}).get("name", ev.get("tool", "unknown"))
                for s in spans:
                    if s.name == f"tool_call:{tool_name}" and s.parent_id == case_span.span_id and not s.end:
                        s.end = ev.get("timestamp", "")
                        s.attributes["tool_output"] = ev.get("output", {}).get("summary", ev.get("result", ""))
                        break
            elif event_type in ("model.call.end", "model_call"):
                metrics = ev.get("metrics", {})
                ti = metrics.get("input_tokens", 0)
                to = metrics.get("output_tokens", 0)
                total_tokens_in += ti
                total_tokens_out += to

                span_counter += 1
                cost = calculate_cost(ti, to, model)
                child = Span(
                    span_id=f"span_{span_counter:03d}",
                    parent_id=case_span.span_id,
                    name=f"model_call:{ev.get('component', {}).get('name', ev.get('model', 'llm'))}",
                    start=ev.get("timestamp", ""),
                    end=ev.get("timestamp", ""),
                    tokens_input=ti,
                    tokens_output=to,
                    cost_cents=cost,
                    attributes={
                        "model": ev.get("attributes", {}).get("gen_ai.system", model),
                    },
                    case_id=cid,
                    cost_status="complete" if (ti > 0 or to > 0) else "incomplete",
                )
                spans.append(child)

        # 补全 case_span 的 token 和成本
        case_span.tokens_input = total_tokens_in
        case_span.tokens_output = total_tokens_out
        case_span.cost_cents = calculate_cost(total_tokens_in, total_tokens_out, model)
        case_span.cost_status = "complete" if (total_tokens_in > 0 or total_tokens_out > 0) else "incomplete"
        spans.append(case_span)

    # 补全 root_span
    if spans:
        root_span.start = min(s.start for s in spans if s.start)
        root_span.end = max(s.end for s in spans if s.end)
        if root_span.start and root_span.end:
            try:
                t0 = datetime.fromisoformat(root_span.start)
                t1 = datetime.fromisoformat(root_span.end)
                root_span.duration_ms = int((t1 - t0).total_seconds() * 1000)
            except (ValueError, TypeError):
                pass
        root_span.tokens_input = sum(s.tokens_input for s in spans)
        root_span.tokens_output = sum(s.tokens_output for s in spans)
        root_span.cost_cents = sum(s.cost_cents for s in spans)

    spans.insert(0, root_span)
    return spans


def _compute_prompt_version(cfg: C.EvalConfig) -> str:
    """计算当前 Skill 的 prompt hash（SKILL.md + agents/*.md 的 SHA-256 前 16 位）。"""
    import hashlib
    h = hashlib.sha256()
    skill_root = C.skill_dir()

    # 读取 SKILL.md
    skill_md = skill_root / "SKILL.md"
    if skill_md.exists():
        h.update(skill_md.read_bytes())

    # 读取所有 agents/*.md
    agents_dir = skill_root / "agents"
    if agents_dir.exists():
        for p in sorted(agents_dir.glob("*.md")):
            h.update(p.read_bytes())

    return "sha256:" + h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# 成本报表聚合
# ---------------------------------------------------------------------------

def aggregate_costs(
    cfg: C.EvalConfig,
    run_id: str,
    aggregate_by: str = "case",
) -> dict:
    """按指定维度聚合成本。"""
    spans = load_spans(cfg, run_id)
    if not spans:
        return {"error": f"no spans found for run {run_id}"}

    result: dict[str, Any] = {
        "run_id": run_id,
        "aggregate_by": aggregate_by,
        "total_tokens_input": sum(s.tokens_input for s in spans),
        "total_tokens_output": sum(s.tokens_output for s in spans),
        "total_cost_cents": sum(s.cost_cents for s in spans),
        "groups": [],
    }

    if aggregate_by == "case":
        case_spans: dict[str, list[Span]] = {}
        for s in spans:
            if s.case_id:
                case_spans.setdefault(s.case_id, []).append(s)

        for cid, cs in sorted(case_spans.items()):
            result["groups"].append({
                "key": cid,
                "tokens_input": sum(s.tokens_input for s in cs),
                "tokens_output": sum(s.tokens_output for s in cs),
                "cost_cents": sum(s.cost_cents for s in cs),
                "duration_ms": sum(s.duration_ms for s in cs),
                "n_spans": len(cs),
            })

    elif aggregate_by == "tool":
        tool_spans: dict[str, list[Span]] = {}
        for s in spans:
            if s.name.startswith("tool_call:"):
                tool_name = s.name.replace("tool_call:", "")
                tool_spans.setdefault(tool_name, []).append(s)

        for tool, ts in sorted(tool_spans.items()):
            result["groups"].append({
                "key": tool,
                "tokens_input": sum(s.tokens_input for s in ts),
                "tokens_output": sum(s.tokens_output for s in ts),
                "cost_cents": sum(s.cost_cents for s in ts),
                "call_count": len(ts),
                "avg_duration_ms": int(sum(s.duration_ms for s in ts) / len(ts)) if ts else 0,
            })

    elif aggregate_by == "dimension":
        dim_spans: dict[str, list[Span]] = {}
        for s in spans:
            dim = s.attributes.get("dimension", "unknown")
            for d in str(dim).split(","):
                d = d.strip()
                if d:
                    dim_spans.setdefault(d, []).append(s)

        for dim, ds in sorted(dim_spans.items()):
            result["groups"].append({
                "key": dim,
                "tokens_input": sum(s.tokens_input for s in ds),
                "tokens_output": sum(s.tokens_output for s in ds),
                "cost_cents": sum(s.cost_cents for s in ds),
                "n_cases": len(set(s.case_id for s in ds if s.case_id)),
            })

    elif aggregate_by == "time":
        time_spans: dict[str, list[Span]] = {}
        for s in spans:
            if s.start:
                date_key = s.start[:10]  # YYYY-MM-DD
                time_spans.setdefault(date_key, []).append(s)

        for date_key, ts in sorted(time_spans.items()):
            result["groups"].append({
                "key": date_key,
                "tokens_input": sum(s.tokens_input for s in ts),
                "tokens_output": sum(s.tokens_output for s in ts),
                "cost_cents": sum(s.cost_cents for s in ts),
                "n_spans": len(ts),
            })

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Span 管理 + 成本追踪")
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--build-spans", action="store_true", help="从 trace 构建 Span 树")
    ap.add_argument("--report", action="store_true", help="生成成本报表")
    ap.add_argument("--aggregate-by", default="case",
                     choices=["case", "tool", "dimension", "time", "iteration"])
    ap.add_argument("--model", default="claude-sonnet-4-20250514")
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])

    if args.build_spans:
        spans = build_spans_from_trace(cfg, args.run, cases, args.model)
        # 清除旧 spans
        sp = spans_path(cfg, args.run)
        if sp.exists():
            sp.unlink()
        for s in spans:
            save_span(cfg, args.run, s)
        print(f"[cost_tracker] 构建 {len(spans)} 个 Span，已写入 {sp}")
        return 0

    if args.report:
        report = aggregate_costs(cfg, args.run, args.aggregate_by)
        report_path = cfg.reports_dir / f"{args.run}_cost_{args.aggregate_by}.json"
        C.write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"[cost_tracker] 报表已写入 {report_path}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())