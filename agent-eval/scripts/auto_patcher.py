#!/usr/bin/env python3
"""auto_patcher.py — 自动 apply patch + 跑 A/B 验证。

v1.1 的核心。把"生成 patch → 手动 apply → 跑 A/B"这个人工循环自动化。

工作流：
1. 读最新诊断 + HRPO 分析
2. 调 reference_optimizer 生成 reference 文件并 apply
3. 调 mutator 生成 prompt/tool patch 建议
4. 如果 --auto-apply，自动 apply 这些 patch 到目标文件
5. 跑 A/B（candidate vs baseline）
6. 跑 multi_judge 评审
7. 根据 Gatekeeper 决策：
   - ACCEPT → 自动 git commit + mark-good
   - REJECT → 自动 git checkout 回滚

用法:
  # 全自动模式（生成 + apply + A/B + 评审 + accept/rollback）
  python auto_patcher.py --config .agent-eval/config.yaml \\
      --baseline-run <run_id> --split regression --auto-apply

  # 半自动（生成 + A/B，但不自动 apply patch，只 apply reference）
  python auto_patcher.py --config .agent-eval/config.yaml \\
      --baseline-run <run_id> --split regression
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import reference_optimizer as RO  # noqa: E402
import mutator as M  # noqa: E402
import abtest as AB  # noqa: E402
import multi_judge as MJ  # noqa: E402
import ci_regression as CI  # noqa: E402


def git_run(cwd: Path, *args: str) -> tuple[int, str]:
    """跑 git 命令。返回 (exit_code, output)。"""
    try:
        r = subprocess.run(
            ["git"] + list(args),
            cwd=cwd, capture_output=True, text=True, timeout=30,
        )
        return r.returncode, r.stdout + r.stderr
    except Exception as e:
        return 1, str(e)


def auto_apply_references(cfg: C.EvalConfig, run_id: str) -> list[str]:
    """自动生成并 apply reference 文件。返回写入的文件路径。"""
    print("\n[auto_patcher] === 步骤 1: 生成并注入 reference ===")
    diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
    if not diag_path.exists():
        print(f"[auto_patcher] 诊断文件不存在，跳过 reference 生成")
        return []
    diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))

    hrpo_path = cfg.scores_dir / f"{run_id}.opik_hrpo.json"
    hrpo_result = None
    if hrpo_path.exists():
        hrpo_result = json.loads(hrpo_path.read_text(encoding="utf-8"))

    references = RO.generate_references(diagnosis, hrpo_result)
    if not references:
        print("[auto_patcher] 无需生成 reference")
        return []

    written = RO.apply_references(cfg, references)
    print(f"[auto_patcher] 注入 {len(written)} 个 reference:")
    for p in written:
        print(f"  - {p}")
    return written


def auto_apply_patches(cfg: C.EvalConfig, run_id: str) -> list[str]:
    """调 mutator 生成 patch 建议。v1.1 不自动改 prompt/tool 代码（风险高），
    只生成 patch 计划让用户/Claude Code 手动 apply。
    reference 文件才自动 apply（风险低）。"""
    print("\n[auto_patcher] === 步骤 2: 生成 patch 建议 ===")
    # 调 mutator 生成 patch 计划
    diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
    if not diag_path.exists():
        print("[auto_patcher] 无诊断，跳过 patch 生成")
        return []

    import diagnoser as D
    diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))
    rules = M.load_mutator_rules(cfg)
    if not diagnosis.get("diagnoses"):
        print("[auto_patcher] 无失败诊断，跳过 patch 生成")
        return []

    written = M.make_patch(cfg, diagnosis.get("diagnoses", []), rules, "small", cfg.patches_dir)
    print(f"[auto_patcher] 生成 {len(written)} 个 patch 计划:")
    for p in written:
        print(f"  - {p.relative_to(cfg.root)}")
    print("[auto_patcher] patch 计划已生成，需手动 apply（reference 已自动 apply）")
    return written


def run_ab_with_judges(
    cfg: C.EvalConfig,
    baseline_run_id: str,
    split: str,
    label: str,
) -> dict:
    """跑 A/B + multi_judge，返回综合结果。"""
    print(f"\n[auto_patcher] === 步骤 3: A/B 验证 (baseline={baseline_run_id}) ===")

    # 生成 candidate run_id
    candidate_run_id = C.make_run_id("candidate", label)
    cases = C.load_yaml(cfg.cases_dir / f"{split}.yaml").get("cases", [])

    if cfg.adapter_name == "mock":
        adapter = {"type": "mock"}
    else:
        adapter = C.load_adapter(cfg.adapter_path())

    # 跑 candidate
    import eval_runner as ER
    import scorer as S
    runs_path = cfg.runs_dir / f"{candidate_run_id}.jsonl"
    for i, case in enumerate(cases, 1):
        cid = case.get("id", f"case_{i}")
        print(f"  [{i}/{len(cases)}] {cid} ...", end=" ", flush=True)
        try:
            record = ER.run_one_case(cfg, adapter, case, candidate_run_id)
            C.append_jsonl(runs_path, record)
            print(f"ok ({record['latency_ms']}ms)")
        except Exception as e:
            print(f"ERROR: {e}")

    # 打分
    print("[auto_patcher] 打分 candidate...")
    candidate_score = S.score_run(cfg, candidate_run_id, cases)

    # 加载 baseline score
    baseline_score_path = cfg.scores_dir / f"{baseline_run_id}.json"
    if not baseline_score_path.exists():
        print(f"[auto_patcher] baseline score 不存在: {baseline_score_path}")
        return {"error": "no baseline"}
    baseline_score = json.loads(baseline_score_path.read_text(encoding="utf-8"))

    # A/B verdict
    print("[auto_patcher] A/B 对比...")
    verdict = AB.evaluate_accept(baseline_score, candidate_score)
    verdict["split"] = split

    # multi_judge
    print("[auto_patcher] 多 Judge 评审...")
    judges_result = MJ.run_judges(
        cfg, candidate_run_id, cases, candidate_score, baseline_score, verdict
    )

    # 写 judges json
    C.write_json(cfg.reports_dir / f"{candidate_run_id}_judges.json", judges_result)

    return {
        "baseline_run_id": baseline_run_id,
        "candidate_run_id": candidate_run_id,
        "abtest_verdict": verdict,
        "gatekeeper": judges_result.get("gatekeeper", {}),
        "candidate_score": candidate_score.get("aggregate", {}),
        "baseline_score": baseline_score.get("aggregate", {}),
        "judges": judges_result,
    }


def auto_accept_or_rollback(
    cfg: C.EvalConfig,
    result: dict,
    reference_files: list[str],
    auto_apply: bool,
) -> str:
    """根据 Gatekeeper 决策，自动 accept（git commit）或 rollback（git checkout）。"""
    print("\n[auto_patcher] === 步骤 4: Gatekeeper 决策 ===")
    gate = result.get("gatekeeper", {})
    verdict = gate.get("verdict", "REJECT")
    rationale = gate.get("decision_rationale", "")
    print(f"[auto_patcher] Gatekeeper: {verdict}")
    print(f"[auto_patcher] 理由: {rationale}")
    print(f"[auto_patcher] 条件: {json.dumps(gate.get('conditions_met', {}), ensure_ascii=False)}")

    cand_agg = result.get("candidate_score", {})
    base_agg = result.get("baseline_score", {})
    delta = cand_agg.get("weighted_score", 0) - base_agg.get("weighted_score", 0)
    print(f"[auto_patcher] 分数 delta: {delta:+.3f} ({base_agg.get('weighted_score',0):.3f} → {cand_agg.get('weighted_score',0):.3f})")

    # 步数对比（关键指标）
    cand_steps = cand_agg.get("latency_mean", 0)  # 简化：用 latency 近似
    base_steps = base_agg.get("latency_mean", 0)
    if cand_steps and base_steps:
        step_delta_pct = (cand_steps - base_steps) / base_steps * 100
        print(f"[auto_patcher] latency delta: {step_delta_pct:+.1f}% ({base_steps}ms → {cand_steps}ms)")

    if not auto_apply:
        print("\n[auto_patcher] 非自动模式，不执行 git 操作")
        return verdict

    project_root = cfg.root.parent  # .agent-eval 的上级目录

    if verdict == "ACCEPT":
        print("\n[auto_patcher] === ACCEPT: git commit ===")
        # git add reference 文件
        for ref in reference_files:
            git_run(project_root, "add", ref)
        # commit
        candidate_id = result.get("candidate_run_id", "")
        msg = f"agent-eval: accept {candidate_id} ({verdict}, score delta {delta:+.3f})"
        code, out = git_run(project_root, "commit", "-m", msg)
        print(f"[auto_patcher] git commit: {code}")
        if out.strip():
            print(f"  {out.strip()[:200]}")
        # mark good
        CI.mark_good(cfg, candidate_id)
        print(f"[auto_patcher] marked {candidate_id} as last_known_good")
        return "ACCEPT"
    else:
        print("\n[auto_patcher] === REJECT: git checkout 回滚 reference ===")
        for ref in reference_files:
            git_run(project_root, "checkout", "--", ref)
        print("[auto_patcher] 已回滚 reference 文件")
        return "REJECT"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--baseline-run", required=True, help="baseline run_id")
    ap.add_argument("--split", default="regression")
    ap.add_argument("--label", default="auto")
    ap.add_argument("--auto-apply", action="store_true",
                    help="自动 apply reference + 自动 git commit/rollback")
    ap.add_argument("--skip-reference", action="store_true",
                    help="跳过 reference 生成（只跑 A/B）")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    C.ensure_dirs(cfg)

    # 1. 生成并 apply reference
    reference_files = []
    if not args.skip_reference:
        reference_files = auto_apply_references(cfg, args.baseline_run)

    # 2. 生成 patch 建议（不自动 apply）
    auto_apply_patches(cfg, args.baseline_run)

    # 3. A/B + multi_judge
    result = run_ab_with_judges(cfg, args.baseline_run, args.split, args.label)

    if "error" in result:
        print(f"[auto_patcher] 错误: {result['error']}")
        return 1

    # 4. accept or rollback
    final_verdict = auto_accept_or_rollback(
        cfg, result, reference_files, args.auto_apply
    )

    print(f"\n[auto_patcher] === 完成: {final_verdict} ===")
    return 0 if final_verdict == "ACCEPT" else 1


if __name__ == "__main__":
    sys.exit(main())
