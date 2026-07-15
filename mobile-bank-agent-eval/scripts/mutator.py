#!/usr/bin/env python3
"""mutator.py — 根据诊断结果生成 candidate patch 计划。

不自动 apply patch。只生成 .agent-eval/patches/candidate_<N>.md。

用法:
  python mutator.py --config .agent-eval/config.yaml --run <run_id> --budget small
  python mutator.py --config .agent-eval/config.yaml --latest
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# budget -> (max_patches, max_files_per_patch)
BUDGETS = {
    "small": (3, 2),
    "medium": (5, 3),
    "large": (10, 5),
}


def load_mutator_rules(cfg: C.EvalConfig) -> dict[str, dict]:
    """加载 mutators/*.yaml，返回 {rule_id: rule}。"""
    rules: dict[str, dict] = {}
    if not cfg.mutators_dir.exists():
        return rules
    for p in sorted(cfg.mutators_dir.glob("*.yaml")):
        data = C.load_yaml(p)
        for r in data.get("rules", []) or []:
            rid = r.get("id")
            if rid:
                rules[rid] = r
    return rules


def make_patch(
    cfg: C.EvalConfig,
    diagnoses: list[dict],
    rules: dict[str, dict],
    budget: str,
    out_dir: Path,
) -> list[Path]:
    max_patches, max_files = BUDGETS[budget]
    # 按 failure_type 聚合
    by_type: dict[str, list[dict]] = {}
    for d in diagnoses:
        by_type.setdefault(d["failure_type"], []).append(d)

    # 优先级：F3 / F4 > F5 > F6 > F2 > F1 > F7 > UNKNOWN
    priority = ["F3", "F4", "F5", "F6", "F2", "F1", "F7", "UNKNOWN"]
    ordered_types: list[str] = []
    for p in priority:
        for ft in by_type:
            if ft.startswith(p) and ft not in ordered_types:
                ordered_types.append(ft)
    # 兜底：剩下的
    for ft in by_type:
        if ft not in ordered_types:
            ordered_types.append(ft)

    written: list[Path] = []
    for i, ft in enumerate(ordered_types[:max_patches], start=1):
        ds = by_type[ft]
        # 取第一条诊断的 mutation_rule 作为代表
        rule_id = ds[0].get("suggested_mutation_rule")
        rule = rules.get(rule_id, {})
        target = ds[0].get("suggested_mutation_target")
        patch_id = f"candidate_{i:03d}"

        # 构造 patch 内容
        md_lines: list[str] = []
        md_lines.append(f"# Patch Plan: {patch_id}")
        md_lines.append("")
        md_lines.append(f"- **failure_type**: `{ft}`")
        md_lines.append(f"- **mutation_target**: `{target}`")
        md_lines.append(f"- **mutation_rule**: `{rule_id}`")
        md_lines.append(f"- **affected_cases**: {[d['case_id'] for d in ds]}")
        md_lines.append(f"- **risk**: {rule.get('risk', 'low')}")
        md_lines.append("")
        md_lines.append("## 问题描述")
        for d in ds:
            md_lines.append(f"- case `{d['case_id']}`: {d['failure_label']}")
            for ev in d["evidence"]:
                md_lines.append(f"  - step={ev['step']} event=`{ev['event']}`: {ev['reason']}")
        md_lines.append("")
        md_lines.append("## Mutation 规则")
        md_lines.append(f"- **what**: {rule.get('what', '(未定义)')}")
        md_lines.append(f"- **why**: {rule.get('why', '(未定义)')}")
        md_lines.append(f"- **how**: {rule.get('how', '(未定义)')}")
        md_lines.append("")
        md_lines.append("## 预期改动文件")
        targets = rule.get("target_files", [f"<{target}_file>"])[:max_files]
        for tf in targets:
            md_lines.append(f"- `{tf}`")
        md_lines.append("")
        md_lines.append("## 预期修掉的 failure_id")
        md_lines.append(f"- `{ft}` 涉及的 {len(ds)} 条诊断")
        md_lines.append("")
        md_lines.append("## 回滚方法")
        md_lines.append(f"```bash")
        md_lines.append(f"git checkout -- <修改的文件>")
        md_lines.append(f"# 或")
        md_lines.append(f"git revert <commit>")
        md_lines.append(f"```")
        md_lines.append("")
        md_lines.append("## 验证步骤")
        md_lines.append("1. 手动 apply 本 patch 描述的改动到上述文件")
        md_lines.append("2. 运行 A/B: `python abtest.py --baseline <baseline_run_id> --candidate-patch <本文件路径> --split regression`")
        md_lines.append("3. 只有 abtest 报告显示 ACCEPT 才能保留改动")

        out_path = out_dir / f"{patch_id}.md"
        out_path.write_text("\n".join(md_lines), encoding="utf-8")
        written.append(out_path)

    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--budget", choices=list(BUDGETS), default="small")
    ap.add_argument("--out", default=None, help="输出目录，默认 .agent-eval/patches/")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    out_dir = Path(args.out) if args.out else cfg.patches_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = args.run
    if args.latest:
        runs = sorted((cfg.runs_dir).glob("*.jsonl"))
        if not runs:
            sys.stderr.write("没有找到任何 run\n")
            return 2
        run_id = runs[-1].stem
        print(f"[mutator] latest run_id={run_id}")

    diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
    if not diag_path.exists():
        sys.stderr.write(f"诊断文件不存在: {diag_path}\n请先运行 diagnoser.py\n")
        return 2
    diag = json.loads(diag_path.read_text(encoding="utf-8"))
    diagnoses = diag.get("diagnoses", [])
    if not diagnoses:
        print("[mutator] 无诊断记录，不需要生成 patch")
        return 0

    rules = load_mutator_rules(cfg)
    print(f"[mutator] 加载 {len(rules)} 条 mutation 规则")
    print(f"[mutator] 诊断 {len(diagnoses)} 条，budget={args.budget}")

    written = make_patch(cfg, diagnoses, rules, args.budget, out_dir)
    print(f"[mutator] 生成 {len(written)} 个 candidate patch:")
    for p in written:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
