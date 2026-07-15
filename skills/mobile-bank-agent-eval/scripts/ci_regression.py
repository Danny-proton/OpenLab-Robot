#!/usr/bin/env python3
"""ci_regression.py — CI 持续回归评测。

v1 的 CI 集成入口。在 CI 环境跑：
1. 跑 regression split 评测
2. 对比上次已知好版本（last_known_good）
3. 检测是否有新硬失败 / 新 forbidden tool / 严重退化
4. 输出 CI 友好的结论（exit code 0/1）

用法:
  # CI 模式（exit 0 = 通过，1 = 回归）
  python ci_regression.py --config .agent-eval/config.yaml \\
      --baseline-run <last_known_good_run_id> \\
      --split regression

  # 更新 last_known_good
  python ci_regression.py --config .agent-eval/config.yaml \\
      --mark-good <run_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import eval_runner as ER  # noqa: E402
import scorer as S  # noqa: E402
import multi_judge as MJ  # noqa: E402


def get_last_known_good(cfg: C.EvalConfig) -> str | None:
    """读取 last_known_good run_id。"""
    p = cfg.root / "last_known_good.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("run_id")


def mark_good(cfg: C.EvalConfig, run_id: str) -> None:
    """标记某个 run 为 last_known_good。"""
    p = cfg.root / "last_known_good.json"
    data = {"run_id": run_id, "marked_at": C.now_iso()}
    C.write_json(p, data)


def run_regression_test(
    cfg: C.EvalConfig,
    baseline_run_id: str | None,
    split: str = "regression",
) -> dict:
    """跑一次回归测试。"""
    # 跑当前版本
    cases = C.load_yaml(cfg.cases_dir / f"{split}.yaml").get("cases", [])
    if cfg.adapter_name == "mock":
        adapter = {"type": "mock"}
    else:
        adapter = C.load_adapter(cfg.adapter_path())

    current_run_id = C.make_run_id("ci", "regression")
    runs_path = cfg.runs_dir / f"{current_run_id}.jsonl"
    for case in cases:
        record = ER.run_one_case(cfg, adapter, case, current_run_id)
        C.append_jsonl(runs_path, record)

    # 打分
    current_score = S.score_run(cfg, current_run_id, cases)

    # 如果有 baseline，对比
    verdict = {
        "current_run_id": current_run_id,
        "baseline_run_id": baseline_run_id,
        "split": split,
        "passed": True,
        "reasons": [],
        "regression_detected": False,
    }

    if baseline_run_id:
        baseline_score_path = cfg.scores_dir / f"{baseline_run_id}.json"
        if baseline_score_path.exists():
            baseline_score = json.loads(baseline_score_path.read_text(encoding="utf-8"))

            # 跑 multi_judge（含 RegressionJudge）
            judges_result = MJ.run_judges(
                cfg, current_run_id, cases, current_score, baseline_score, None
            )
            verdict["judges"] = {
                "gatekeeper": judges_result.get("gatekeeper", {}),
                "regression_judge": next(
                    (j for j in judges_result.get("all_judges", [])
                     if j.get("judge") == "RegressionJudge"), None
                ),
            }

            # 判定
            reg_judge = verdict["judges"]["regression_judge"]
            if reg_judge and reg_judge.get("verdict") == "fail":
                verdict["passed"] = False
                verdict["regression_detected"] = True
                verdict["reasons"].append(f"RegressionJudge fail: {reg_judge.get('evidence')}")

            # 检查硬失败数
            b_hard = baseline_score.get("aggregate", {}).get("n_hard_fail", 0)
            c_hard = current_score.get("aggregate", {}).get("n_hard_fail", 0)
            if c_hard > b_hard:
                verdict["passed"] = False
                verdict["regression_detected"] = True
                verdict["reasons"].append(f"硬失败数 {b_hard} → {c_hard}")

            # 检查 forbidden tool
            c_forbidden = sum(
                1 for pc in current_score.get("per_case", [])
                for hf in pc.get("hard_fails", [])
                if "forbidden_tool" in hf
            )
            if c_forbidden > 0:
                verdict["passed"] = False
                verdict["regression_detected"] = True
                verdict["reasons"].append(f"forbidden tool violations: {c_forbidden}")
        else:
            verdict["reasons"].append(f"baseline score not found: {baseline_score_path}")

    # 生成 trend 记录
    trend_path = cfg.root / "regression_trend.jsonl"
    trend_entry = {
        "ts": C.now_iso(),
        "current_run_id": current_run_id,
        "baseline_run_id": baseline_run_id,
        "passed": verdict["passed"],
        "weighted_score": current_score.get("aggregate", {}).get("weighted_score", 0),
        "n_hard_fail": current_score.get("aggregate", {}).get("n_hard_fail", 0),
    }
    C.append_jsonl(trend_path, trend_entry)

    return verdict


def render_ci_report(verdict: dict) -> str:
    """生成 CI 友好的报告。"""
    lines = []
    status = "✅ PASS" if verdict["passed"] else "❌ FAIL"
    lines.append(f"=== Agent Eval CI Regression: {status} ===")
    lines.append(f"current_run: {verdict['current_run_id']}")
    lines.append(f"baseline_run: {verdict['baseline_run_id']}")
    lines.append(f"split: {verdict['split']}")
    if verdict["reasons"]:
        lines.append("reasons:")
        for r in verdict["reasons"]:
            lines.append(f"  - {r}")
    if verdict.get("judges", {}).get("regression_judge"):
        rj = verdict["judges"]["regression_judge"]
        lines.append(f"RegressionJudge: {rj.get('verdict')} (score={rj.get('score')})")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--baseline-run", help="baseline run_id（不填则用 last_known_good）")
    ap.add_argument("--split", default="regression")
    ap.add_argument("--mark-good", help="标记某个 run_id 为 last_known_good")
    ap.add_argument("--ci", action="store_true", help="CI 模式（简短输出，exit code 表结果）")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    C.ensure_dirs(cfg)

    if args.mark_good:
        mark_good(cfg, args.mark_good)
        print(f"[ci_regression] marked {args.mark_good} as last_known_good")
        return 0

    baseline = args.baseline_run or get_last_known_good(cfg)
    if baseline:
        print(f"[ci_regression] baseline: {baseline}")
    else:
        print("[ci_regression] no baseline (first run)")

    verdict = run_regression_test(cfg, baseline, args.split)
    report = render_ci_report(verdict)
    print(report)

    # 写 verdict json
    verdict_path = cfg.reports_dir / f"{verdict['current_run_id']}_ci_verdict.json"
    C.write_json(verdict_path, verdict)
    try:
        import report_manager as RM
        RM.register_report(
            cfg, verdict_path,
            run_id=verdict["current_run_id"],
            title=f"CI 回归判定 — {verdict['current_run_id']}",
        )
    except Exception as e:
        sys.stderr.write(f"[report_manager] 注册失败: {e}\n")

    if args.ci:
        return 0 if verdict["passed"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
