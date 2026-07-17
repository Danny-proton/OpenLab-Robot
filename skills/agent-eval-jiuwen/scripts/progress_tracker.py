#!/usr/bin/env python3
"""progress_tracker.py — 执行进度埋点（telemetry）持久化层。

V1.1.1 新增。解决 sidecar.py 只把状态打到 stdout 即丢失的问题。

职责：
- 存储：把 sidecar 产生的进度事件 append 到 data/progress.jsonl
- 查询：latest / list / timeline / summary，供 report_portal.py 与人工查询消费

sidecar.py 是事件生产者，本模块是存储 + 查询。零 LLM，纯 JSONL I/O + 聚合。

事件 schema（progress.jsonl 每行一条）:
  {
    "event_id": "evt_...",
    "tool": "agent-eval",
    "timestamp": "ISO",
    "status": "running|completed|failed|skipped|pending",
    "step": int,
    "step_name": str,
    "total_steps": int,
    "progress_pct": int,
    "run_id": str|null,
    "session_id": str,
    "duration_ms": int|null,   # 终态事件填
    "score": str|null,
    "extra": dict
  }

用法:
  # 落盘一条事件（sidecar 内部调用，也可直接用）
  python progress_tracker.py --config .agent-eval/config.yaml emit \\
    --status running --step 3 --step-name "用例执行" --run-id <run_id>

  # 查询
  python progress_tracker.py --config .agent-eval/config.yaml latest
  python progress_tracker.py --config .agent-eval/config.yaml list --limit 50
  python progress_tracker.py --config .agent-eval/config.yaml timeline
  python progress_tracker.py --config .agent-eval/config.yaml summary
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

# 与 sidecar.py 的 STEPS 对齐（9 步 eval loop）。手机银行流水线可传 --total-steps 覆盖。
DEFAULT_STEPS = {
    1: "需求分析",
    2: "用例生成",
    3: "用例执行+桥接",
    4: "报告生成",
    5: "F1-F8 诊断",
    6: "多 Judge 评审",
    7: "优化迭代",
    8: "生成 reference",
    9: "生成统一门户",
    45: "用例自优化",  # 阶段 4.5，用 step=45 上报
}

PROGRESS_FILENAME = "progress.jsonl"
_ACTIVE_SESSIONS: dict[str, dict[str, Any]] = {}


def _normalize_step(step: int) -> float:
    """把 step 归一化为浮点序号。

    step=45 表示阶段 4.5（用例自优化），归一化为 4.5，避免 progress_pct 爆表。
    与 sidecar.py 的 _normalize_step 保持一致。
    """
    if step >= 10:
        return step / 10.0
    return float(step)


# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------

def data_dir(cfg: C.EvalConfig) -> Path:
    """进度数据目录：.agent-eval/data/（与 case_iterations.jsonl 同目录）。"""
    d = cfg.root / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def progress_path(cfg: C.EvalConfig) -> Path:
    return data_dir(cfg) / PROGRESS_FILENAME


# ---------------------------------------------------------------------------
# session_id 管理
# ---------------------------------------------------------------------------

def _new_session_id() -> str:
    return "sess_" + datetime.now().strftime("%Y%m%d-%H%M%S")


def _resolve_session_id(session_id: str | None, run_id: str | None,
                        events: list[dict[str, Any]]) -> str:
    """决定本次事件的 session_id：
    1. 显式传入优先；
    2. 否则若 run_id 能匹配到历史事件，沿用其 session_id；
    3. 否则若近 30 分钟内有 pending/running 且无终态的 session，沿用；
    4. 否则新建。
    """
    if session_id:
        return session_id
    if run_id:
        for e in reversed(events):
            if e.get("run_id") == run_id and e.get("session_id"):
                return e["session_id"]
    # 找最近一个未结束的 session
    now = datetime.now().astimezone()
    for e in reversed(events):
        if e.get("status") in ("running", "pending") and e.get("session_id"):
            try:
                ts = datetime.fromisoformat(e["timestamp"])
                if (now - ts).total_seconds() < 1800:  # 30 分钟内
                    return e["session_id"]
            except Exception:
                continue
    return _new_session_id()


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------

def emit(
    cfg: C.EvalConfig,
    status: str,
    step: int,
    step_name: str | None = None,
    total_steps: int = 9,
    run_id: str | None = None,
    session_id: str | None = None,
    score: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """落盘一条进度事件并返回该事件。"""
    if step_name is None:
        step_name = DEFAULT_STEPS.get(step, f"步骤 {step}")
    events = C.load_jsonl(progress_path(cfg))
    sid = _resolve_session_id(session_id, run_id, events)
    now = C.now_iso()

    duration_ms: int | None = None
    # 终态事件：计算同 session 同 step 从首条 running 到现在的耗时
    if status in ("completed", "failed", "skipped"):
        start_ts: str | None = None
        for e in events:
            if (e.get("session_id") == sid and e.get("step") == step
                    and e.get("status") == "running"):
                start_ts = start_ts or e.get("timestamp")
        if start_ts:
            try:
                duration_ms = int(
                    (datetime.fromisoformat(now) - datetime.fromisoformat(start_ts)
                     ).total_seconds() * 1000
                )
            except Exception:
                duration_ms = None

    event = {
        "event_id": "evt_" + now.replace(":", "").replace("-", "").replace("+", "Z")[:20],
        "tool": "agent-eval",
        "timestamp": now,
        "status": status,
        "step": step,
        "step_name": step_name,
        "total_steps": total_steps,
        "progress_pct": min(100, round(_normalize_step(step) / total_steps * 100)) if total_steps else 0,
        "run_id": run_id,
        "session_id": sid,
        "duration_ms": duration_ms,
        "score": score,
        "extra": dict(extra) if extra else {},
    }
    C.append_jsonl(progress_path(cfg), event)
    return event


# ---------------------------------------------------------------------------
# 查询
# ---------------------------------------------------------------------------

def load_events(cfg: C.EvalConfig) -> list[dict[str, Any]]:
    return C.load_jsonl(progress_path(cfg))


def latest(cfg: C.EvalConfig) -> dict[str, Any] | None:
    events = load_events(cfg)
    return events[-1] if events else None


def list_events(cfg: C.EvalConfig, limit: int = 50,
                session_id: str | None = None,
                run_id: str | None = None) -> list[dict[str, Any]]:
    events = load_events(cfg)
    out = []
    for e in reversed(events):
        if session_id and e.get("session_id") != session_id:
            continue
        if run_id and e.get("run_id") != run_id:
            continue
        out.append(e)
        if len(out) >= limit:
            break
    return out


def timeline(cfg: C.EvalConfig) -> dict[str, Any]:
    """按 session 聚合，输出每个 session 的 9 步状态 + duration_ms。

    供 report_portal.py Progress 页直接渲染。
    """
    events = load_events(cfg)
    # 按 session 分组，保留顺序
    sessions: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for e in events:
        sid = e.get("session_id", "unknown")
        if sid not in sessions:
            sessions[sid] = []
            order.append(sid)
        sessions[sid].append(e)

    out_sessions: list[dict[str, Any]] = []
    for sid in order:
        evs = sessions[sid]
        # 按 step 聚合
        steps_map: dict[int, dict[str, Any]] = {}
        for e in evs:
            s = e.get("step", 0)
            cur = steps_map.setdefault(s, {
                "step": s,
                "name": e.get("step_name", DEFAULT_STEPS.get(s, f"步骤 {s}")),
                "status": "pending",
                "duration_ms": None,
                "started_at": None,
                "ended_at": None,
                "run_id": e.get("run_id"),
                "error": None,
                "extra": {},
            })
            status = e.get("status", "pending")
            ts = e.get("timestamp")
            if status == "running" and cur["started_at"] is None:
                cur["started_at"] = ts
            if status in ("completed", "failed", "skipped"):
                cur["ended_at"] = ts
                cur["status"] = status
                if e.get("duration_ms") is not None:
                    cur["duration_ms"] = e["duration_ms"]
                if status == "failed":
                    cur["error"] = (e.get("extra") or {}).get("error")
            elif status == "running" and cur["status"] == "pending":
                cur["status"] = "running"
                cur["started_at"] = ts
            # 合并 extra
            cur["extra"].update(e.get("extra") or {})
            if e.get("run_id"):
                cur["run_id"] = e["run_id"]

        steps_list = [steps_map[s] for s in sorted(steps_map)]
        # 当前状态 = 最后一条事件
        last = evs[-1] if evs else {}
        current_step = last.get("step", 0)
        current_status = last.get("status", "pending")
        total_steps = last.get("total_steps", 9)
        out_sessions.append({
            "session_id": sid,
            "run_id": last.get("run_id"),
            "started_at": evs[0].get("timestamp") if evs else None,
            "ended_at": evs[-1].get("timestamp") if evs else None,
            "current_step": current_step,
            "current_step_name": last.get("step_name"),
            "current_status": current_status,
            "progress_pct": round(current_step / total_steps * 100) if total_steps else 0,
            "total_steps": total_steps,
            "n_events": len(evs),
            "steps": steps_list,
        })

    return {"sessions": out_sessions, "total_sessions": len(out_sessions)}


def summary(cfg: C.EvalConfig) -> dict[str, Any]:
    """总览统计。"""
    events = load_events(cfg)
    tl = timeline(cfg)
    sessions = tl["sessions"]
    completed = [s for s in sessions if s["current_status"] in ("completed", "skipped")]
    failed = [s for s in sessions if s["current_status"] == "failed"]
    running = [s for s in sessions if s["current_status"] == "running"]

    # 各步骤平均耗时
    step_durations: dict[int, list[int]] = {}
    for s in sessions:
        for st in s["steps"]:
            if st["duration_ms"] is not None:
                step_durations.setdefault(st["step"], []).append(st["duration_ms"])
    avg_step_ms = {
        s: int(sum(v) / len(v)) for s, v in step_durations.items() if v
    }

    return {
        "total_events": len(events),
        "total_sessions": len(sessions),
        "completed_sessions": len(completed),
        "failed_sessions": len(failed),
        "running_sessions": len(running),
        "avg_step_ms": avg_step_ms,
        "latest": events[-1] if events else None,
        "latest_session": sessions[-1] if sessions else None,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="执行进度埋点持久化 + 查询")
    ap.add_argument("--config", required=True)
    ap.add_argument("--json", action="store_true", help="以 JSON 输出")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # emit
    p_emit = sub.add_parser("emit", help="落盘一条进度事件")
    p_emit.add_argument("--status", required=True,
                        choices=["pending", "running", "completed", "failed", "skipped"])
    p_emit.add_argument("--step", required=True, type=int)
    p_emit.add_argument("--step-name")
    p_emit.add_argument("--total-steps", type=int, default=9)
    p_emit.add_argument("--run-id")
    p_emit.add_argument("--session-id")
    p_emit.add_argument("--score")
    p_emit.add_argument("--extra", help="附加 JSON 字符串")

    # list
    p_list = sub.add_parser("list", help="列出最近事件")
    p_list.add_argument("--limit", type=int, default=50)
    p_list.add_argument("--session-id")
    p_list.add_argument("--run-id")

    sub.add_parser("latest", help="最近一条事件")
    sub.add_parser("timeline", help="按 session/step 聚合的时间线")
    sub.add_parser("summary", help="总览统计")

    args = ap.parse_args()
    cfg = C.EvalConfig.load(Path(args.config).resolve())

    if args.cmd == "emit":
        extra = None
        if args.extra:
            try:
                extra = json.loads(args.extra)
            except Exception as e:
                sys.stderr.write(f"[progress_tracker] --extra 解析失败: {e}\n")
        ev = emit(cfg, args.status, args.step, args.step_name,
                  args.total_steps, args.run_id, args.session_id,
                  args.score, extra)
        print(json.dumps(ev, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "list":
        out = list_events(cfg, args.limit, args.session_id, args.run_id)
        if args.json or True:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "latest":
        ev = latest(cfg)
        if not ev:
            sys.stderr.write("[progress_tracker] 无事件\n")
            return 2
        print(json.dumps(ev, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "timeline":
        print(json.dumps(timeline(cfg), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "summary":
        print(json.dumps(summary(cfg), ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
