#!/usr/bin/env python3
"""openlab_robot_adapter.py — OpenLab Robot 执行 adapter。

OpenLab Robot 是基于 cc-haha（Claude Code 复现）的执行机。本 adapter 通过
subprocess 调用 cc-haha 的 CLI（./bin/claude-haha），用 stream-json 协议
获取完整 agent 执行 trace，并转成 UATR 格式供 agent-eval 评测。

调用方式：
  ./bin/claude-haha --print --verbose \
    --input-format stream-json --output-format stream-json \
    --session-id <uuid> --permission-mode bypassPermissions

stdin: 一条 NDJSON user 消息
stdout: NDJSON SDK 消息流，直到 type: 'result' 出现

用法（被 common.call_adapter 调用）:
  adapter = {
    "type": "openlab_robot",
    "bin": "/path/to/cc-haha/bin/claude-haha",
    "workdir": "/tmp/work",
    "env": {
      "ANTHROPIC_AUTH_TOKEN": "sk-xxx",
      "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
      "ANTHROPIC_MODEL": "MiniMax-M3"
    },
    "max_turns": 20,
    "max_budget_usd": 1.0,
    "timeout_s": 600,
    "allowed_tools": ["Bash", "Read", "Grep", "Glob"]
  }

也支持 CLI 独立测试:
  python openlab_robot_adapter.py --bin /path/to/claude-haha --prompt "list files" --workdir /tmp/work
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

# 让 import common 能找到
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import common as C  # noqa: E402


def call_openlab_robot(
    adapter: dict[str, Any],
    case: dict[str, Any],
    run_id: str,
    case_run_id: str,
) -> C.AdapterResult:
    """调用 OpenLab Robot (cc-haha) 执行一条 case。

    返回 AdapterResult，raw_trace 是 UATR 格式事件列表。
    """
    bin_path = adapter.get("bin", "claude-haha")
    workdir = adapter.get("workdir", "/tmp")
    timeout = adapter.get("timeout_s", 600)
    max_turns = adapter.get("max_turns")
    max_budget = adapter.get("max_budget_usd")
    allowed_tools = adapter.get("allowed_tools", [])
    permission_mode = adapter.get("permission_mode", "bypassPermissions")
    env_overrides = adapter.get("env", {})

    # 构造 prompt
    case_input = case.get("input", {}) or {}
    user_message = case_input.get("user_message", "")
    task = case.get("task", "")
    prompt = user_message if user_message else task
    if not prompt:
        return C.AdapterResult(
            final_answer="", raw_trace=[], latency_ms=0,
            status="error", error={"type": "empty_prompt", "message": "case has no user_message or task"},
        )

    # 构造 session_id
    session_id = case_run_id.replace("::", "_").replace("/", "_")[:64]

    # 构造 stdin payload: 一条 NDJSON user 消息
    user_msg = {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": prompt}]},
        "parent_tool_use_id": None,
        "session_id": session_id,
    }
    stdin_payload = (json.dumps(user_msg) + "\n").encode("utf-8")

    # 构造命令行参数
    args = [
        bin_path,
        "--print",
        "--verbose",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--session-id", session_id,
        "--permission-mode", permission_mode,
    ]
    if max_turns:
        args.extend(["--max-turns", str(max_turns)])
    if max_budget:
        args.extend(["--max-budget-usd", str(max_budget)])
    if allowed_tools:
        args.append("--allowedTools")
        args.extend(allowed_tools)

    # 环境变量
    env = os.environ.copy()
    env.update(env_overrides)
    env.setdefault("DISABLE_TELEMETRY", "1")
    env.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")

    # 确保 workdir 存在
    Path(workdir).mkdir(parents=True, exist_ok=True)

    # 跑子进程
    import time
    t0 = time.time()
    try:
        proc = subprocess.run(
            args,
            input=stdin_payload,
            capture_output=True,
            cwd=workdir,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return C.AdapterResult(
            final_answer="", raw_trace=[], latency_ms=timeout * 1000,
            status="error", error={"type": "timeout", "message": f"exceeded {timeout}s"},
        )
    except FileNotFoundError:
        return C.AdapterResult(
            final_answer="", raw_trace=[], latency_ms=0,
            status="error",
            error={"type": "bin_not_found", "message": f"cc-haha binary not found: {bin_path}"},
        )
    latency_ms = int((time.time() - t0) * 1000)

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace")[:2000]
        return C.AdapterResult(
            final_answer="", raw_trace=[], latency_ms=latency_ms,
            status="error",
            error={"type": "exit_error", "message": f"exit {proc.returncode}: {stderr}"},
        )

    # 解析 stdout NDJSON
    stdout_text = proc.stdout.decode("utf-8", "replace")
    sdk_events: list[dict] = []
    final_result: dict | None = None
    for line in stdout_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            sdk_events.append(msg)
            if msg.get("type") == "result":
                final_result = msg
        except json.JSONDecodeError:
            continue

    if not final_result:
        return C.AdapterResult(
            final_answer="", raw_trace=[], latency_ms=latency_ms,
            status="error",
            error={"type": "no_result", "message": "no result message in stdout",
                   "stderr": proc.stderr.decode("utf-8", "replace")[:1000]},
        )

    # 提取最终答案
    final_answer = final_result.get("result", "") or ""
    is_error = final_result.get("is_error", False)
    status = "error" if is_error else "success"

    # 把 SDK 事件转成 UATR trace
    uatr_events = sdk_to_uatr(sdk_events, run_id, case.get("id", "unknown"), case_run_id)

    return C.AdapterResult(
        final_answer=final_answer,
        raw_trace=uatr_events,
        latency_ms=final_result.get("duration_ms", latency_ms),
        status=status,
        error={"type": "execution_error", "message": final_result.get("errors", "")}
        if is_error else None,
    )


def sdk_to_uatr(
    sdk_events: list[dict],
    run_id: str,
    case_id: str,
    case_run_id: str,
) -> list[dict]:
    """把 cc-haha SDK 消息流转成 UATR 事件。

    SDK 消息类型 → UATR 事件类型映射:
      system.init             → agent.run.start
      assistant.tool_use      → tool.call.start
      tool_progress           → (合并到 tool.call.end)
      user.tool_result        → tool.call.end
      assistant.text          → model.call.end (含 final_answer)
      system.hook_*           → planner.step
      result.success          → agent.run.end
      result.error_*          → agent.run.end (status=error)
    """
    uatr_events: list[dict] = []
    step = 1
    ts_base = C.now_iso()

    def add(event_type: str, **kw) -> None:
        nonlocal step
        ev: dict = {
            "schema_version": C.UATR_SCHEMA_VERSION,
            "run_id": run_id,
            "case_id": case_id,
            "case_run_id": case_run_id,
            "trace_id": f"trace-{case_run_id}",
            "span_id": f"span_{step:04d}",
            "timestamp": ts_base,
            "framework": "claude_code",
            "source": "openlab_robot",
            "event_type": event_type,
            "actor": {"type": "agent", "name": "openlab-robot", "role": "executor"},
            "status": "success",
        }
        ev.update(kw)
        uatr_events.append(ev)
        step += 1

    # 收集 tool_use 信息（按 tool_use_id 索引）
    tool_uses: dict[str, dict] = {}  # tool_use_id → {name, input, start_step}
    tool_results: dict[str, dict] = {}  # tool_use_id → {content, is_error}

    for msg in sdk_events:
        msg_type = msg.get("type")

        if msg_type == "system" and msg.get("subtype") == "init":
            # agent 开始
            add("agent.run.start",
                component={"type": "agent", "name": "openlab-robot"},
                attributes={
                    "model": msg.get("model", "unknown"),
                    "cwd": msg.get("cwd", ""),
                    "permission_mode": msg.get("permissionMode", ""),
                    "tools": [t.get("name", "") for t in msg.get("tools", [])],
                })

        elif msg_type == "assistant":
            content = msg.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "tool_use":
                    tool_use_id = block.get("id", "")
                    tool_name = block.get("name", "")
                    tool_input = block.get("input", {})
                    tool_uses[tool_use_id] = {
                        "name": tool_name,
                        "input": tool_input,
                        "step": step,
                    }
                    add("tool.call.start",
                        component={"type": "tool", "name": tool_name},
                        attributes={
                            "tool_use_id": tool_use_id,
                            "tool.arguments": tool_input,
                        })
                elif block.get("type") == "text":
                    # 模型文本输出（可能是中间思考或最终答案）
                    text = block.get("text", "")
                    if text:
                        add("model.call.end",
                            component={"type": "model", "name": "claude"},
                            metrics={"input_tokens": 0, "output_tokens": 0},
                            output={"summary": text[:200], "text": text})

        elif msg_type == "tool_progress":
            tool_use_id = msg.get("tool_use_id", "")
            tool_name = msg.get("tool_name", "")
            elapsed = msg.get("elapsed_time_seconds", 0)
            # tool_progress 不单独成事件，记录下来供 tool.call.end 用
            if tool_use_id in tool_uses:
                tool_uses[tool_use_id]["elapsed"] = elapsed

        elif msg_type == "user":
            # 可能是 tool_result 回填
            tool_result = msg.get("tool_use_result")
            if tool_result:
                content = msg.get("message", {}).get("content", [])
                for block in content:
                    if block.get("type") == "tool_result":
                        tool_use_id = block.get("tool_use_id", "")
                        is_error = block.get("is_error", False)
                        result_content = block.get("content", "")
                        if isinstance(result_content, list):
                            result_text = " ".join(
                                c.get("text", "") for c in result_content if isinstance(c, dict)
                            )
                        else:
                            result_text = str(result_content)
                        tool_results[tool_use_id] = {
                            "content": result_text,
                            "is_error": is_error,
                        }
                        # 发 tool.call.end 事件
                        tu = tool_uses.get(tool_use_id, {})
                        add("tool.call.end",
                            component={"type": "tool", "name": tu.get("name", "unknown")},
                            metrics={"latency_ms": int(tu.get("elapsed", 0) * 1000)},
                            output={"summary": result_text[:200]},
                            status="error" if is_error else "success")

        elif msg_type == "system" and msg.get("subtype", "").startswith("hook_"):
            hook_name = msg.get("hook_name", "")
            hook_event = msg.get("hook_event", "")
            add("planner.step",
                component={"type": "hook", "name": hook_name},
                attributes={
                    "hook_event": hook_event,
                    "hook_id": msg.get("hook_id", ""),
                    "outcome": msg.get("outcome", ""),
                })

        elif msg_type == "result":
            subtype = msg.get("subtype", "success")
            is_error = subtype != "success"
            final_text = msg.get("result", "")
            num_turns = msg.get("num_turns", 0)
            duration_ms = msg.get("duration_ms", 0)
            total_cost = msg.get("total_cost_usd", 0)
            usage = msg.get("usage", {})

            add("agent.run.end",
                component={"type": "agent", "name": "openlab-robot"},
                metrics={
                    "latency_ms": duration_ms,
                    "cost_usd": total_cost,
                    "num_turns": num_turns,
                    "input_tokens": usage.get("input_tokens", 0) if isinstance(usage, dict) else 0,
                    "output_tokens": usage.get("output_tokens", 0) if isinstance(usage, dict) else 0,
                },
                output={"final_answer": final_text},
                status="error" if is_error else "success",
                attributes={
                    "stop_reason": msg.get("stop_reason", ""),
                    "result_subtype": subtype,
                })

    return uatr_events


def main() -> int:
    """独立测试模式。"""
    ap = argparse.ArgumentParser(description="OpenLab Robot adapter 独立测试")
    ap.add_argument("--bin", default="claude-haha", help="cc-haha binary 路径")
    ap.add_argument("--prompt", required=True, help="测试 prompt")
    ap.add_argument("--workdir", default="/tmp/openlab-test", help="工作目录")
    ap.add_argument("--timeout", type=int, default=120, help="超时秒数")
    ap.add_argument("--env", help="环境变量 JSON")
    ap.add_argument("--out", help="trace 输出文件")
    args = ap.parse_args()

    env = json.loads(args.env) if args.env else {}
    adapter = {
        "type": "openlab_robot",
        "bin": args.bin,
        "workdir": args.workdir,
        "timeout_s": args.timeout,
        "env": env,
    }
    case = {
        "id": "cli_test",
        "input": {"user_message": args.prompt},
    }

    print(f"[openlab_robot] 调用: {args.bin}")
    print(f"[openlab_robot] prompt: {args.prompt[:100]}")
    print(f"[openlab_robot] workdir: {args.workdir}")
    print()

    result = call_openlab_robot(adapter, case, "cli-test-run", "cli-test-run::cli_test")

    print(f"status: {result.status}")
    print(f"latency_ms: {result.latency_ms}")
    print(f"final_answer: {(result.final_answer or '')[:200]}")
    print(f"trace events: {len(result.raw_trace)}")
    if result.error:
        print(f"error: {result.error}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            for ev in result.raw_trace:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        print(f"\ntrace 写入: {args.out}")

    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
