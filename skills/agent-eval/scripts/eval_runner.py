#!/usr/bin/env python3
"""eval_runner.py — 跑一次评测 run。

用法:
  # 首次初始化项目
  python eval_runner.py --scaffold .

  # 跑基线
  python eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline

  # 恢复中断的 run
  python eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline --resume <run_id>

输出:
  .agent-eval/runs/<run_id>.jsonl   每条 case 一行
  .agent-eval/traces/<run_id>.jsonl 规范化 trace 事件
  .agent-eval/scores/<run_id>.json  单 case + 汇总分数
  .agent-eval/reports/<run_id>.md   人读报告

依赖: PyYAML。无其它第三方依赖。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# 让脚本既能被 `python scripts/eval_runner.py` 直接跑，
# 也能被 `python -m scripts.eval_runner` 跑。
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import scorer as S  # noqa: E402
import trace_normalizer as TN  # noqa: E402
import report as R  # noqa: E402


def load_cases(cfg: C.EvalConfig, split: str) -> list[dict]:
    p = cfg.cases_dir / f"{split}.yaml"
    if not p.exists():
        sys.stderr.write(f"[eval_runner] 找不到 split 文件: {p}\n")
        sys.exit(2)
    raw = C.load_yaml(p)
    # split 文件格式: {cases: [...]}
    cases = raw.get("cases", [])
    if not cases:
        sys.stderr.write(f"[eval_runner] {p} 里没有 cases\n")
        sys.exit(2)
    return cases


def run_one_case(
    cfg: C.EvalConfig,
    adapter: dict,
    case: dict,
    run_id: str,
) -> dict:
    case_id = case.get("id", "unknown")
    case_run_id = f"{run_id}::{case_id}"

    t0 = time.time()
    result = C.call_adapter(adapter, case, run_id, case_run_id)
    latency_ms = int((time.time() - t0) * 1000)

    # 规范化 trace
    normalized, invalid = TN.normalize(
        result.raw_trace,
        run_id=run_id,
        case_id=case_id,
        case_run_id=case_run_id,
        mapping=adapter.get("trace_mapping"),
        redact_fields=adapter.get("redact_fields"),
    )

    # 写 trace
    trace_path = cfg.traces_dir / f"{run_id}.jsonl"
    for ev in normalized:
        C.append_jsonl(trace_path, ev)
    if invalid:
        invalid_path = cfg.traces_dir / f"{run_id}.invalid.jsonl"
        for ev in invalid:
            C.append_jsonl(invalid_path, ev)

    record = {
        "case_id": case_id,
        "case_run_id": case_run_id,
        "run_id": run_id,
        "status": result.status,
        "latency_ms": result.latency_ms,
        "final_answer": result.final_answer,
        "trace_path": str(trace_path.relative_to(cfg.root)),
        "error": result.error,
        "ts": C.now_iso(),
    }
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description="agent-eval 评测 runner")
    ap.add_argument("--scaffold", metavar="DIR", help="初始化目标目录")
    ap.add_argument("--config", help=".agent-eval/config.yaml 路径")
    ap.add_argument("--split", default="train", help="train / regression / adversarial")
    ap.add_argument("--variant", default="baseline", help="baseline / candidate_xxx")
    ap.add_argument("--label", default=None, help="run_id 短标签")
    ap.add_argument("--resume", default=None, help="恢复指定 run_id")
    ap.add_argument("--limit", type=int, default=None, help="只跑前 N 条 case（调试用）")
    args = ap.parse_args()

    # scaffold 模式
    if args.scaffold:
        C.scaffold(Path(args.scaffold).resolve())
        return 0

    if not args.config:
        ap.error("--config 必填（除非用 --scaffold）")

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    C.ensure_dirs(cfg)

    # 决定 run_id
    if args.resume:
        run_id = args.resume
        sys.stdout.write(f"[eval_runner] 恢复 run_id={run_id}\n")
    else:
        run_id = C.make_run_id(args.variant, args.label)
        sys.stdout.write(f"[eval_runner] 新 run_id={run_id}\n")

    runs_path = cfg.runs_dir / f"{run_id}.jsonl"
    existing = C.load_jsonl(runs_path)
    done_case_ids = {r["case_id"] for r in existing}

    # 加载 cases
    cases = load_cases(cfg, args.split)
    if args.limit:
        cases = cases[: args.limit]

    # 加载 adapter
    if cfg.adapter_name == "mock":
        adapter = {"type": "mock"}
    else:
        adapter_path = cfg.adapter_path()
        if not adapter_path.exists():
            sys.stderr.write(f"[eval_runner] adapter 文件不存在: {adapter_path}\n")
            return 2
        adapter = C.load_adapter(adapter_path)

    sys.stdout.write(
        f"[eval_runner] split={args.split} cases={len(cases)} adapter={cfg.adapter_name}\n"
    )

    # 跑 case
    n_ok, n_fail = 0, 0
    for i, case in enumerate(cases, 1):
        cid = case.get("id", f"case_{i}")
        if cid in done_case_ids:
            sys.stdout.write(f"  [{i}/{len(cases)}] {cid} 跳过（已存在）\n")
            continue
        sys.stdout.write(f"  [{i}/{len(cases)}] {cid} ... ")
        sys.stdout.flush()
        try:
            record = run_one_case(cfg, adapter, case, run_id)
            C.append_jsonl(runs_path, record)
            if record["status"] == "success":
                n_ok += 1
                sys.stdout.write(f"ok ({record['latency_ms']}ms)\n")
            else:
                n_fail += 1
                sys.stdout.write(f"FAIL ({record['status']})\n")
        except Exception as e:
            n_fail += 1
            err_record = {
                "case_id": cid,
                "case_run_id": f"{run_id}::{cid}",
                "run_id": run_id,
                "status": "runner_error",
                "latency_ms": 0,
                "final_answer": "",
                "trace_path": "",
                "error": {"type": type(e).__name__, "message": str(e)},
                "ts": C.now_iso(),
            }
            C.append_jsonl(runs_path, err_record)
            sys.stdout.write(f"RUNNER_ERROR: {e}\n")

    sys.stdout.write(
        f"[eval_runner] done. success={n_ok} fail={n_fail}\n"
    )

    # 打分
    sys.stdout.write("[eval_runner] 计算分数...\n")
    score = S.score_run(cfg, run_id, cases)

    # TRACE 五维评测（可选：config.yaml 中未配置 trace 段则跳过）
    sys.stdout.write("[eval_runner] 计算 TRACE 五维评分...\n")
    try:
        import tracer_scorer as TS
        trace_result = TS.score_trace_run(cfg, run_id, score, cases)
        sys.stdout.write(f"[eval_runner] TRACE 总分: {trace_result['trace_normalized_score']:.2f}/5.0 ({trace_result['status_label']})\n")
    except Exception as e:
        sys.stdout.write(f"[eval_runner] TRACE 评分跳过: {e}\n")
        trace_result = None

    # 报告
    sys.stdout.write("[eval_runner] 生成报告...\n")
    R.render_run_report(cfg, run_id, score)

    # v0.5: 生成 HTML 报告 + charts.json
    try:
        import diagnoser as D
        import html_report as HR
        import charts as CH
        # 诊断
        diag = D.diagnose_run(cfg, run_id, args.split)
        diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
        C.write_json(diag_path, diag)
        try:
            import report_manager as RM
            RM.register_report(cfg, diag_path, run_id=run_id, title=f"诊断数据 — {run_id}")
        except Exception as e:
            sys.stderr.write(f"[report_manager] 注册失败: {e}\n")
        # charts
        charts_data = CH.build_charts(cfg, run_id, score, diag, None, cases)
        C.write_json(cfg.scores_dir / f"{run_id}.charts.json", charts_data)
        # HTML
        html_path = HR.generate_html_report(cfg, run_id, score, charts_data, diag)
        sys.stdout.write(f"[eval_runner] HTML 报告: {html_path}\n")
    except Exception as e:
        sys.stdout.write(f"[eval_runner] HTML 报告生成失败（不影响主流程）: {e}\n")

    sys.stdout.write(
        f"[eval_runner] 汇总分数: {score['aggregate']['weighted_score']:.3f}\n"
        f"[eval_runner] 报告: {cfg.reports_dir / (run_id + '.md')}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
