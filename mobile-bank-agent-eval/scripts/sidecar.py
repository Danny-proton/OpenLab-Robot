#!/usr/bin/env python3
"""sidecar.py — 评测进度状态面板。

每次执行前/后调用，输出标准化的进度 JSON。
Claude Code 提取此 JSON 渲染为进度卡片。

用法:
  python sidecar.py --status running --step 2 --step-name "跑基线" --total-steps 9
  python sidecar.py --status completed --step 2 --result '{"weighted_score": 0.723}'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


STEPS = {
    1: "启动前信息收集",
    2: "跑基线评测",
    3: "失败诊断",
    4: "多 Judge 评审",
    5: "HRPO 分析",
    6: "生成 reference",
    7: "A/B + 全自动优化",
    8: "生成报告",
    9: "生成 Dashboard",
}


def emit_status(
    status: str,
    step: int,
    step_name: str | None = None,
    total_steps: int = 9,
    **kwargs,
) -> str:
    """输出标准化状态 JSON。"""
    if step_name is None:
        step_name = STEPS.get(step, f"步骤 {step}")
    payload = {
        "tool": "agent-eval",
        "timestamp": C.now_iso(),
        "status": status,  # pending | running | completed | failed | skipped
        "step": step,
        "step_name": step_name,
        "total_steps": total_steps,
        "progress_pct": round(step / total_steps * 100),
    }
    payload.update(kwargs)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_text_card(status_json: str) -> str:
    """把状态 JSON 渲染为纯文本卡片。"""
    try:
        d = json.loads(status_json)
    except Exception:
        return status_json
    lines = [
        "┌─────────────────────────────────┐",
        "│  📊 Agent Eval 状态             │",
        "│  ─────────────────────────────  │",
        f"│  🏃 当前步骤: {d.get('step', 0)}/{d.get('total_steps', 9)} {d.get('step_name', '')[:8].ljust(8)} │",
        f"│  📈 状态: {d.get('status', 'unknown').ljust(18)} │",
    ]
    if "run_id" in d:
        lines.append(f"│  📦 Run: {str(d['run_id'])[:23].ljust(23)} │")
    if "score" in d:
        lines.append(f"│  🎯 分数: {str(d['score'])[:21].ljust(21)} │")
    if "n_hard_fail" in d:
        lines.append(f"│  ❌ 硬失败: {str(d['n_hard_fail'])[:19].ljust(19)} │")
    lines.append("└─────────────────────────────────┘")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", required=True,
                    choices=["pending", "running", "completed", "failed", "skipped"])
    ap.add_argument("--step", required=True, type=int)
    ap.add_argument("--step-name")
    ap.add_argument("--total-steps", type=int, default=9)
    ap.add_argument("--run-id")
    ap.add_argument("--score")
    ap.add_argument("--result", help="额外结果 JSON 字符串")
    ap.add_argument("--text", action="store_true", help="同时输出文本卡片")
    args = ap.parse_args()

    extra: dict = {}
    if args.run_id:
        extra["run_id"] = args.run_id
    if args.score:
        extra["score"] = args.score
    if args.result:
        try:
            extra.update(json.loads(args.result))
        except Exception as e:
            print(f"[warn] --result 解析失败: {e}", file=sys.stderr)

    payload = emit_status(
        args.status, args.step, args.step_name, args.total_steps, **extra
    )
    print(payload)
    if args.text:
        try:
            print(render_text_card(payload))
        except UnicodeEncodeError:
            # Windows 控制台可能不支持 emoji，回退到纯 ASCII 边框
            print(render_text_card(payload).encode("ascii", "ignore").decode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
