#!/usr/bin/env python3
"""sidecar.py — 评测进度状态面板。

每次执行前/后调用，输出标准化的进度 JSON。
Claude Code 提取此 JSON 渲染为进度卡片。

V1.1.1 升级：
- `--persist`（默认开）自动把事件落盘到 data/progress.jsonl（经 progress_tracker）。
- `--no-persist` 关闭落盘（CI 等场景）。
- stdout JSON 输出不变，向后兼容现有 orchestrator 调用契约。

用法:
  python sidecar.py --status running --step 2 --step-name "跑基线" --total-steps 9
  python sidecar.py --status completed --step 2 --result '{"weighted_score": 0.723}'
  python sidecar.py --status running --step 3 --no-persist   # CI 不落盘
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


STEPS = {
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


def _normalize_step(step: int) -> float:
    """把 step 归一化为浮点序号。

    step=45 表示阶段 4.5（用例自优化），归一化为 4.5；
    其他直接返回原值。这样 progress_pct 不会爆表。
    """
    if step >= 10:
        return step / 10.0
    return float(step)


def emit_status(
    status: str,
    step: int,
    step_name: str | None = None,
    total_steps: int = 9,
    **kwargs,
) -> str:
    """输出标准化状态 JSON（字符串）。"""
    if step_name is None:
        step_name = STEPS.get(step, f"步骤 {step}")
    step_norm = _normalize_step(step)
    payload = {
        "tool": "agent-eval",
        "timestamp": C.now_iso(),
        "status": status,  # pending | running | completed | failed | skipped
        "step": step,
        "step_name": step_name,
        "total_steps": total_steps,
        "progress_pct": min(100, round(step_norm / total_steps * 100)),
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


def _persist_event(args, extra: dict) -> None:
    """经 progress_tracker 落盘本条事件。失败仅告警，不影响主流程。"""
    try:
        import progress_tracker as PT
        # 推断 config 路径：优先 --config，否则从 cwd 向上找 .agent-eval/config.yaml
        cfg_path = getattr(args, "config", None)
        if not cfg_path:
            try:
                cfg_dir = C.find_agent_eval_dir()
                cfg_path = str(cfg_dir / "config.yaml")
            except FileNotFoundError:
                sys.stderr.write("[sidecar] 未找到 .agent-eval/，跳过进度落盘\n")
                return
        cfg = C.EvalConfig.load(Path(cfg_path).resolve())
        PT.emit(
            cfg,
            status=args.status,
            step=args.step,
            step_name=args.step_name,
            total_steps=args.total_steps,
            run_id=args.run_id,
            session_id=getattr(args, "session_id", None),
            score=args.score,
            extra=extra or None,
        )
    except Exception as e:
        sys.stderr.write(f"[sidecar] 进度落盘失败（不影响主流程）: {e}\n")


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
    ap.add_argument("--extra", help="附加字段 JSON 字符串（落盘用，如 '{\"n_done\":3}'）")
    ap.add_argument("--session-id", help="会话 ID（未传则由 progress_tracker 自动推断/生成）")
    ap.add_argument("--config", help=".agent-eval/config.yaml 路径（落盘用；未传则自动查找）")
    ap.add_argument("--text", action="store_true", help="同时输出文本卡片")
    # 落盘开关：默认开。--no-persist 关闭。argparse 用 store_false 的互斥组不便，这里用两个 flag。
    ap.add_argument("--persist", dest="persist", action="store_true", default=True,
                    help="落盘到 data/progress.jsonl（默认开）")
    ap.add_argument("--no-persist", dest="persist", action="store_false",
                    help="关闭落盘（CI 等场景）")
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
    extra_for_persist: dict = dict(extra)
    if args.extra:
        try:
            extra_for_persist.update(json.loads(args.extra))
        except Exception as e:
            print(f"[warn] --extra 解析失败: {e}", file=sys.stderr)

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

    # V1.1.1: 落盘进度事件
    if args.persist:
        _persist_event(args, extra_for_persist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
