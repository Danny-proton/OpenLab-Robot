#!/usr/bin/env python3
"""report.py — 生成 markdown 报告。

被 eval_runner / abtest 进程内调用，也提供 CLI 单独生成：
  python report.py --config .agent-eval/config.yaml --run <run_id>
  python report.py --config .agent-eval/config.yaml --abtest <baseline_run_id> <candidate_run_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def render_run_report(cfg: C.EvalConfig, run_id: str, score: dict) -> Path:
    out = cfg.reports_dir / f"{run_id}.md"
    agg = score.get("aggregate", {})
    lines: list[str] = []
    lines.append(f"# 评测报告 — {run_id}\n")
    lines.append("## 汇总\n")
    lines.append(f"- case 数: {agg.get('n_cases')}")
    lines.append(f"- 成功: {agg.get('n_success')}")
    lines.append(f"- 硬失败: {agg.get('n_hard_fail')}")
    lines.append(f"- 加权总分: **{agg.get('weighted_score')}**")
    lines.append(f"- 分数范围: {agg.get('score_min')} ~ {agg.get('score_max')} (stdev={agg.get('score_stdev')})")
    lines.append(f"- latency p50: {agg.get('latency_p50')}ms / mean: {agg.get('latency_mean')}ms")
    lines.append("")

    lines.append("## 单 case 分数\n")
    lines.append("| case_id | weighted_score | hard_fail | task_success | tool_correctness | business_rule | output_schema | efficiency |")
    lines.append("|---------|---------------|-----------|--------------|------------------|---------------|---------------|------------|")
    for pc in score.get("per_case", []):
        m = pc.get("metrics", {})
        def sc(key): 
            v = m.get(key, {}).get("score", "-")
            return f"{v:.2f}" if isinstance(v, (int, float)) else v
        lines.append(
            f"| {pc.get('case_id')} | {pc.get('weighted_score', 0):.3f} | "
            f"{'是' if pc.get('is_hard_fail') else '否'} | "
            f"{sc('task_success')} | {sc('tool_correctness')} | "
            f"{sc('business_rule_coverage')} | {sc('output_schema_validity')} | "
            f"{sc('efficiency')} |"
        )
    lines.append("")

    # 硬失败详情
    hard_fails = [pc for pc in score.get("per_case", []) if pc.get("is_hard_fail")]
    if hard_fails:
        lines.append("## 硬失败详情\n")
        for pc in hard_fails:
            lines.append(f"### `{pc.get('case_id')}`")
            for hf in pc.get("hard_fails", []):
                lines.append(f"- {hf}")
            lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def render_abtest_report(
    cfg: C.EvalConfig,
    baseline_run_id: str,
    candidate_run_id: str,
    patch_path: str,
    verdict: dict,
    baseline_score: dict,
    candidate_score: dict,
) -> Path:
    out = cfg.reports_dir / f"abtest_{baseline_run_id}_vs_{candidate_run_id}.md"
    lines: list[str] = []
    lines.append(f"# A/B 报告: {baseline_run_id} vs {candidate_run_id}\n")
    lines.append(f"- baseline: `{baseline_run_id}`")
    lines.append(f"- candidate: `{candidate_run_id}`")
    lines.append(f"- patch: `{patch_path}`")
    lines.append(f"- **建议: `{verdict['recommendation']}`**\n")

    lines.append("## 接受条件判定\n")
    lines.append("| # | 条件 | 结果 | 详情 |")
    lines.append("|---|------|------|------|")
    for d in verdict["decisions"]:
        status = "✅ PASS" if d["pass"] else "❌ FAIL"
        # 把 detail 字段拼成短字符串
        detail_parts = []
        for k, v in d.items():
            if k in ("id", "name", "pass"):
                continue
            detail_parts.append(f"{k}={v}")
        detail = ", ".join(detail_parts)
        lines.append(f"| {d['id']} | {d['name']} | {status} | {detail} |")
    lines.append("")

    b_agg = baseline_score.get("aggregate", {})
    c_agg = candidate_score.get("aggregate", {})
    lines.append("## 汇总对比\n")
    lines.append("| 指标 | baseline | candidate | delta |")
    lines.append("|------|----------|-----------|-------|")
    def row(name, key, fmt="{:.3f}"):
        b = b_agg.get(key, 0)
        c = c_agg.get(key, 0)
        try:
            delta = c - b
            return f"| {name} | {fmt.format(b)} | {fmt.format(c)} | {fmt.format(delta)} |"
        except (TypeError, ValueError):
            return f"| {name} | {b} | {c} | - |"
    lines.append(row("加权总分", "weighted_score"))
    lines.append(row("硬失败数", "n_hard_fail", "{:d}"))
    lines.append(row("成功数", "n_success", "{:d}"))
    lines.append(row("latency_p50", "latency_p50", "{:d}"))
    lines.append("")

    # 单 case 对比
    b_per = {pc["case_id"]: pc for pc in baseline_score.get("per_case", [])}
    c_per = {pc["case_id"]: pc for pc in candidate_score.get("per_case", [])}
    all_ids = sorted(set(b_per.keys()) | set(c_per.keys()))
    lines.append("## 单 case 对比\n")
    lines.append(f"> 注：baseline 和 candidate 可能跑在不同 split 上（baseline 通常在 train，candidate 在 {verdict.get('split', 'regression')}）。")
    lines.append(f"> 同 case_id 才能直接对比；只出现在一侧的 case 表示该 split 独有的 case。\n")
    lines.append("| case_id | baseline | candidate | delta | 状态 |")
    lines.append("|---------|----------|-----------|-------|------|")
    for cid in all_ids:
        b = b_per.get(cid, {}).get("weighted_score", "-")
        c = c_per.get(cid, {}).get("weighted_score", "-")
        try:
            d = c - b
            ds = f"{d:+.3f}"
        except TypeError:
            ds = "-"
        if isinstance(b, (int, float)) and isinstance(c, (int, float)):
            if c > b:
                status = "⬆ 改善"
            elif c < b:
                status = "⬇ 退化"
            else:
                status = "= 持平"
        else:
            status = "?"
        b_str = f"{b:.3f}" if isinstance(b, (int, float)) else b
        c_str = f"{c:.3f}" if isinstance(c, (int, float)) else c
        lines.append(f"| {cid} | {b_str} | {c_str} | {ds} | {status} |")
    lines.append("")

    # 建议
    lines.append("## 下一步\n")
    if verdict["recommendation"] == "ACCEPT":
        lines.append("1. `git add` 改动的文件并提交：")
        lines.append("   ```bash")
        lines.append(f'   git commit -m "agent-eval: accept {Path(patch_path).stem} ({candidate_run_id})"')
        lines.append("   ```")
        lines.append("2. 把这次 accept 记录追加到 `.agent-eval/reports/accepted_patches.md`")
        lines.append("3. 下一次 A/B 的 baseline 改为本次 candidate")
    elif verdict["recommendation"] == "REJECT":
        lines.append("1. **立即回滚** candidate 改动：")
        lines.append("   ```bash")
        lines.append("   git checkout -- <被改动的文件>")
        lines.append("   ```")
        lines.append("2. 检查上方 FAIL 的条件，重新看诊断是否归因正确")
        lines.append("3. 必要时重新跑 `diagnoser.py` 和 `mutator.py`")
    else:  # INCONCLUSIVE
        lines.append("1. patch 可能没生效——确认改动是否真的 apply 了")
        lines.append("2. 确认 adapter 配置是否正确")
        lines.append("3. 重新跑 candidate variant")

    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run")
    ap.add_argument("--abtest", nargs=2, metavar=("BASELINE", "CANDIDATE"))
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())

    if args.abtest:
        baseline_run_id, candidate_run_id = args.abtest
        # 简化：需要外部已生成 verdict.json
        # 这里只从 scores 读取并重新渲染
        b_score = json.loads((cfg.scores_dir / f"{baseline_run_id}.json").read_text(encoding="utf-8"))
        c_score = json.loads((cfg.scores_dir / f"{candidate_run_id}.json").read_text(encoding="utf-8"))
        # 找 patch path
        abtest_glob = list(cfg.reports_dir.glob(f"abtest_{baseline_run_id}_vs_{candidate_run_id}.md"))
        patch_path = abtest_glob[0].name if abtest_glob else "(unknown)"
        # 重新算 verdict
        import abtest as AB
        verdict = AB.evaluate_accept(b_score, c_score)
        out = render_abtest_report(cfg, baseline_run_id, candidate_run_id, patch_path, verdict, b_score, c_score)
        print(out)
        return 0

    if args.run:
        score = json.loads((cfg.scores_dir / f"{args.run}.json").read_text(encoding="utf-8"))
        out = render_run_report(cfg, args.run, score)
        print(out)
        return 0

    ap.error("需要 --run 或 --abtest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
