#!/usr/bin/env python3
"""abtest.py — baseline vs candidate A/B 评测。

candidate patch 已经被用户手动 apply 到 agent，本脚本只负责：
1. 跑 candidate variant 在指定 split 上
2. 加载 baseline 的 score
3. 对比并给出 accept/reject 建议

用法:
  python abtest.py \
    --config .agent-eval/config.yaml \
    --baseline <baseline_run_id> \
    --candidate-patch .agent-eval/patches/candidate_001.md \
    --split regression \
    --label candidate_001

输出:
  .agent-eval/runs/<candidate_run_id>.jsonl
  .agent-eval/traces/<candidate_run_id>.jsonl
  .agent-eval/scores/<candidate_run_id>.json
  .agent-eval/reports/abtest_<baseline>_vs_<candidate>.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import scorer as S  # noqa: E402
import eval_runner as ER  # noqa: E402
import report as R  # noqa: E402


# 接受条件（来自 guide 06）
def evaluate_accept(
    baseline_score: dict,
    candidate_score: dict,
    train_threshold: float = 0.03,
    latency_max_ratio: float = 1.5,
) -> dict:
    """返回 {decisions: [...], recommendation: ACCEPT/REJECT/INCONCLUSIVE}。"""
    b_agg = baseline_score.get("aggregate", {})
    c_agg = candidate_score.get("aggregate", {})

    b_train = b_agg.get("weighted_score", 0.0)
    c_train = c_agg.get("weighted_score", 0.0)
    delta = c_train - b_train

    decisions = []

    # 条件 1: train_score 提升 >= threshold
    decisions.append({
        "id": 1,
        "name": "train_score_improvement",
        "pass": delta >= train_threshold,
        "baseline": b_train,
        "candidate": c_train,
        "delta": round(delta, 3),
        "threshold": train_threshold,
    })

    # 条件 2: regression_hard_fail == 0
    c_hard = c_agg.get("n_hard_fail", 0)
    decisions.append({
        "id": 2,
        "name": "regression_hard_fail_zero",
        "pass": c_hard == 0,
        "candidate_hard_fail": c_hard,
    })

    # 条件 3: forbidden_tool_violation == 0
    c_forbidden = 0
    for pc in candidate_score.get("per_case", []):
        for hf in pc.get("hard_fails", []):
            if "forbidden_tool_called" in hf:
                c_forbidden += 1
    decisions.append({
        "id": 3,
        "name": "forbidden_tool_violation_zero",
        "pass": c_forbidden == 0,
        "candidate_forbidden_violation": c_forbidden,
    })

    # 条件 4: 无新 failure_type
    # 简化：candidate 的失败 case 集合应 ⊆ baseline 的（按 case_id）
    b_failed = {pc["case_id"] for pc in baseline_score.get("per_case", []) if pc.get("is_hard_fail") or pc.get("weighted_score", 0) < 0.6}
    c_failed = {pc["case_id"] for pc in candidate_score.get("per_case", []) if pc.get("is_hard_fail") or pc.get("weighted_score", 0) < 0.6}
    new_failed = c_failed - b_failed
    decisions.append({
        "id": 4,
        "name": "no_new_failure",
        "pass": len(new_failed) == 0,
        "new_failed_cases": sorted(new_failed),
    })

    # 条件 5: latency_p50 不超 1.5x
    b_lat = b_agg.get("latency_p50", 0)
    c_lat = c_agg.get("latency_p50", 0)
    latency_ok = c_lat <= b_lat * latency_max_ratio if b_lat > 0 else True
    decisions.append({
        "id": 5,
        "name": "latency_no_blow_up",
        "pass": latency_ok,
        "baseline_p50": b_lat,
        "candidate_p50": c_lat,
        "max_allowed": int(b_lat * latency_max_ratio),
    })

    all_pass = all(d["pass"] for d in decisions)
    # INCONCLUSIVE: train_score 完全没变
    if abs(delta) < 0.001 and c_hard == 0:
        recommendation = "INCONCLUSIVE"
    elif all_pass:
        recommendation = "ACCEPT"
    else:
        recommendation = "REJECT"

    return {
        "decisions": decisions,
        "recommendation": recommendation,
        "baseline_run_id": baseline_score.get("run_id"),
        "candidate_run_id": candidate_score.get("run_id"),
        "split": "regression",  # 由调用方覆盖
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--candidate-patch", required=True, help="candidate patch 文件路径（仅用于记录）")
    ap.add_argument("--split", default="regression")
    ap.add_argument("--label", default="candidate")
    ap.add_argument("--train-threshold", type=float, default=0.03)
    ap.add_argument("--latency-max-ratio", type=float, default=1.5)
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    C.ensure_dirs(cfg)

    # 加载 baseline score
    baseline_score_path = cfg.scores_dir / f"{args.baseline}.json"
    if not baseline_score_path.exists():
        sys.stderr.write(f"baseline score 不存在: {baseline_score_path}\n")
        return 2
    baseline_score = json.loads(baseline_score_path.read_text(encoding="utf-8"))

    # 跑 candidate
    print(f"[abtest] 跑 candidate variant on split={args.split}")
    candidate_run_id = C.make_run_id("candidate", args.label)
    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])

    if cfg.adapter_name == "mock":
        adapter = {"type": "mock"}
    else:
        adapter = C.load_adapter(cfg.adapter_path())

    runs_path = cfg.runs_dir / f"{candidate_run_id}.jsonl"
    for i, case in enumerate(cases, 1):
        cid = case.get("id", f"case_{i}")
        print(f"  [{i}/{len(cases)}] {cid} ...", end=" ", flush=True)
        try:
            record = ER.run_one_case(cfg, adapter, case, candidate_run_id)
            C.append_jsonl(runs_path, record)
            print(f"ok ({record['latency_ms']}ms)")
        except Exception as e:
            err = {
                "case_id": cid, "case_run_id": f"{candidate_run_id}::{cid}",
                "run_id": candidate_run_id, "status": "runner_error",
                "latency_ms": 0, "final_answer": "", "trace_path": "",
                "error": {"type": type(e).__name__, "message": str(e)},
                "ts": C.now_iso(),
            }
            C.append_jsonl(runs_path, err)
            print(f"RUNNER_ERROR: {e}")

    # 打分
    print("[abtest] 打分 candidate...")
    candidate_score = S.score_run(cfg, candidate_run_id, cases)

    # 对比
    print("[abtest] 对比...")
    verdict = evaluate_accept(
        baseline_score, candidate_score,
        args.train_threshold, args.latency_max_ratio,
    )
    verdict["split"] = args.split

    # 写 A/B 报告
    out = cfg.reports_dir / f"abtest_{args.baseline}_vs_{candidate_run_id}.md"
    R.render_abtest_report(cfg, args.baseline, candidate_run_id, args.candidate_patch, verdict, baseline_score, candidate_score)
    print(f"[abtest] 报告: {out}")

    # v0.5: 生成 candidate 的 HTML 报告（带 baseline 对比）
    try:
        import html_report as HR
        import charts as CH
        import diagnoser as D
        # 诊断 candidate
        diag = D.diagnose_run(cfg, candidate_run_id, args.split)
        C.write_json(cfg.reports_dir / f"{candidate_run_id}_diagnosis.json", diag)
        # charts（带 baseline 对比）
        cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])
        charts_data = CH.build_charts(cfg, candidate_run_id, candidate_score, diag, baseline_score, cases)
        C.write_json(cfg.scores_dir / f"{candidate_run_id}.charts.json", charts_data)
        # HTML
        html_path = HR.generate_html_report(cfg, candidate_run_id, candidate_score, charts_data, diag, baseline_score, verdict)
        print(f"[abtest] HTML 报告: {html_path}")
    except Exception as e:
        print(f"[abtest] HTML 报告生成失败（不影响主流程）: {e}")

    print(f"[abtest] 建议: {verdict['recommendation']}")
    for d in verdict["decisions"]:
        status = "PASS" if d["pass"] else "FAIL"
        print(f"  [{status}] 条件{d['id']} {d['name']}")
    return 0 if verdict["recommendation"] == "ACCEPT" else 1


if __name__ == "__main__":
    sys.exit(main())
