#!/usr/bin/env python3
"""test_e2e_mock.py — agent-eval-v1.1 合并版端到端 mock 测试。

跑通 skill 自带的端到端 mock 样例（examples/.agent-eval/，adapter=mock）：
  eval_runner → diagnoser → case_quality_checker → mutation_generator
  → case_optimizer(dry-run) → case_iteration_report

验证：
- 8 条 mock case 全部跑完（runner 不崩）
- diagnoser 能归因 F3/F7（mock 故意制造的失败）
- case_quality_checker 输出 12 维评分（V1.1 核心）
- mutation_generator 输出 kill matrix（V1.1 核心）
- case_optimizer dry-run 生成建议
- case_iteration_report 产出 MD + HTML
- 合并的 cost_tracker 在同一 run 上能 build-spans + report（V1.1 + dev-skill-eval 共存）

运行：python tests/test_e2e_mock.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
EXAMPLES_CFG = SKILL_ROOT / "examples" / ".agent-eval"


def _run(script: str, *args: str, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestE2EMockPipeline(unittest.TestCase):
    """端到端 mock 全流程。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="ae-e2e-"))
        cls.cfg_dir = cls.tmp / ".agent-eval"
        shutil.copytree(EXAMPLES_CFG, cls.cfg_dir)
        cls.cfg = cls.cfg_dir / "config.yaml"

        # 阶段 0：跑 baseline（8 条 mock case）
        r = _run(
            "eval_runner",
            "--config",
            str(cls.cfg),
            "--split",
            "train",
            "--variant",
            "baseline",
            "--label",
            "e2e",
            cwd=cls.tmp,
        )
        assert r.returncode == 0, f"eval_runner baseline 失败:\nSTDOUT:{r.stdout}\nSTDERR:{r.stderr}"
        runs = list(cls.cfg_dir.glob("runs/*.jsonl"))
        assert runs, "没生成 run 文件"
        cls.run_id = runs[0].stem

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_01_runner_produced_core_outputs(self):
        """runs / traces / scores / reports 四件套齐全。"""
        for sub in ["runs", "traces", "scores", "reports"]:
            d = self.cfg_dir / sub
            self.assertTrue(d.exists() and any(d.iterdir()), f"{sub}/ 为空")

        scores = json.loads((self.cfg_dir / "scores" / f"{self.run_id}.json").read_text())
        agg = scores.get("aggregate", {})
        self.assertIn("weighted_score", agg, f"分数结构异常: {list(scores.keys())}")
        # mock 故意制造失败 → 不会满分
        self.assertLess(agg["weighted_score"], 0.95, "mock 应该不是满分（有故意失败）")

    def test_02_diagnoser_attributes_failures(self):
        """diagnoser 能归因 F3/F7（mock 故意制造）。"""
        r = _run("diagnoser", "--config", str(self.cfg), "--latest", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        diag_md = self.cfg_dir / "reports" / f"{self.run_id}_diagnosis.md"
        self.assertTrue(diag_md.exists(), "诊断 MD 未生成")
        diag_json = self.cfg_dir / "reports" / f"{self.run_id}_diagnosis.json"
        self.assertTrue(diag_json.exists(), "诊断 JSON 未生成")
        diag = json.loads(diag_json.read_text())
        # mock 规则：loan_risk_001 漏调 analyze_cashflow（F3.1）+ 不提担保（F7.3）
        # diagnoser JSON 结构：by_failure_type = { "F3.1": 1, "F7.3": 6, ... }
        self.assertIn(
            "by_failure_type",
            diag,
            f"诊断 JSON 缺少 by_failure_type，实际 keys: {list(diag.keys())}",
        )
        all_codes = set(diag["by_failure_type"].keys())
        self.assertTrue(
            all_codes & {"F3.1", "F7.3"},
            f"未归因到 F3.1/F7.3，实际归因: {all_codes}",
        )
        self.assertGreater(diag.get("n_diagnoses", 0), 0, "诊断数为 0")

    def test_03_case_quality_checker_12dim(self):
        """V1.1 核心：12 维质量评分。"""
        r = _run("case_quality_checker", "--config", str(self.cfg), "--split", "train", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        q = self.cfg_dir / "reports" / "case_quality_train.json"
        self.assertTrue(q.exists(), "质量报告未生成")
        data = json.loads(q.read_text())
        # V1.1 质量报告结构：dimensions(12 维) + weighted_total + passes_threshold
        self.assertIn("weighted_total", data, f"质量报告结构异常: {list(data.keys())}")
        self.assertIn("dimensions", data, f"质量报告缺 dimensions: {list(data.keys())}")
        self.assertEqual(len(data["dimensions"]), 12, f"应 12 维，实际 {len(data['dimensions'])}")
        # 3 个 Agent 专属维度必须在
        for d in ["tool_coverage", "workflow_coverage", "memory_coverage"]:
            self.assertIn(d, data["dimensions"], f"缺 Agent 专属维度 {d}")

    def test_04_mutation_generator_kill_matrix(self):
        """V1.1 核心：mutation kill matrix。"""
        r = _run(
            "mutation_generator",
            "--config",
            str(self.cfg),
            "--latest",
            "--split",
            "train",
            cwd=self.tmp,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        # mutation 报告产物
        mut_files = list(self.cfg_dir.glob("reports/*mutation*")) + list(
            self.cfg_dir.glob("reports/*kill*")
        )
        self.assertTrue(mut_files, "mutation 产物未生成")

    def test_05_case_optimizer_dry_run(self):
        """V1.1 核心：用例自优化 dry-run（只生成建议，不改 cases）。"""
        r = _run(
            "case_optimizer",
            "--config",
            str(self.cfg),
            "--latest",
            "--split",
            "train",
            cwd=self.tmp,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        # dry-run 产物在 .agent-eval/data/prop-<ts>-<split>.json
        prop_files = list(self.cfg_dir.glob("data/prop-*.json"))
        self.assertTrue(prop_files, f"优化建议 proposal 未生成，stdout={r.stdout[-300:]}")
        prop = json.loads(prop_files[0].read_text())
        # proposal 至少含建议类型统计
        self.assertTrue(
            any(k in prop for k in ("add", "modify", "deprecate", "spec_changes", "summary")),
            f"proposal 结构异常: {list(prop.keys())}",
        )

    def test_06_case_iteration_report(self):
        """V1.1 核心：迭代报告 MD + HTML。"""
        r = _run("case_iteration_report", "--config", str(self.cfg), "--latest", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        it_md = list(self.cfg_dir.glob("reports/*iteration*.md"))
        it_html = list(self.cfg_dir.glob("reports/*iteration*.html"))
        self.assertTrue(it_md or it_html, "迭代报告未生成")

    def test_07_merged_cost_tracker_works_on_same_run(self):
        """合并验证：dev-skill-eval 的 cost_tracker 在 v1.1 的 run 上可用。"""
        r = _run(
            "cost_tracker",
            "--config",
            str(self.cfg),
            "--run",
            self.run_id,
            "--build-spans",
            cwd=self.tmp,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        spans = self.cfg_dir / "traces" / f"{self.run_id}.spans.jsonl"
        self.assertTrue(spans.exists() and spans.stat().st_size > 0, "spans 未生成")

        r2 = _run(
            "cost_tracker",
            "--config",
            str(self.cfg),
            "--run",
            self.run_id,
            "--report",
            "--aggregate-by",
            "case",
            cwd=self.tmp,
        )
        self.assertEqual(r2.returncode, 0, r2.stderr)
        reports = list(self.cfg_dir.glob(f"reports/{self.run_id}_cost_*.json"))
        self.assertTrue(reports, "成本报表未生成")


if __name__ == "__main__":
    unittest.main(verbosity=2)
