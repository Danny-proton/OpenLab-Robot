#!/usr/bin/env python3
"""test_unit.py — agent-eval-v1.1 合并版单元测试。

覆盖三类：
1. 所有 42 个 scripts/*.py 可 import（含 v1.1 36 + dev-skill-eval 6）
2. 所有带 argparse 的脚本 --help 可正常退出（CLI 契约不破）
3. dev-skill-eval 合并进来的 6 个新脚本功能可用（annotator / cost_tracker /
   stratified_sampler / xlsx_importer 真跑一次；annotate_server / sse_stream
   只验证可构造，不真正起 HTTP 服务）

依赖：PyYAML、openpyxl（已用于 xlsx_importer）。无 pytest 依赖，纯 unittest。
运行：python tests/test_unit.py
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL_ROOT / "scripts"
EXAMPLES_CFG = SKILL_ROOT / "examples" / ".agent-eval"

# 让被测脚本能 import common
sys.path.insert(0, str(SCRIPTS))


def _import_all_scripts() -> tuple[list[str], list[tuple[str, str, str]]]:
    import importlib

    ok: list[str] = []
    fail: list[tuple[str, str, str]] = []
    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name == "__init__.py":
            continue
        try:
            importlib.import_module(f.stem)
            ok.append(f.stem)
        except Exception as e:  # noqa: BLE001
            fail.append((f.stem, type(e).__name__, str(e)))
    return ok, fail


def _run(script: str, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{script}.py"), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestImports(unittest.TestCase):
    """1. 全部 scripts 可 import。"""

    def test_all_scripts_import(self):
        ok, fail = _import_all_scripts()
        self.assertEqual(fail, [], f"导入失败的脚本: {fail}")
        # 合并后应是 42 个（v1.1 36 + dev-skill-eval 6）
        self.assertGreaterEqual(len(ok), 42, f"脚本数 {len(ok)} 少于预期 42")
        # 6 个新增脚本必须在
        for s in [
            "annotate_server",
            "annotator",
            "cost_tracker",
            "sse_stream",
            "stratified_sampler",
            "xlsx_importer",
        ]:
            self.assertIn(s, ok, f"合并新增脚本 {s} 未导入成功")

    def test_common_is_superset_of_gitee(self):
        """v1.1 common.py 必须含 dev-skill-eval 需要的 mock_config 分支。"""
        import common as C  # noqa: N813

        self.assertTrue(hasattr(C, "_call_mock_config"), "v1.1 common 缺少 _call_mock_config")
        self.assertTrue(hasattr(C, "_call_mock_legacy"), "v1.1 common 缺少 _call_mock_legacy")
        self.assertTrue(hasattr(C, "EvalConfig"), "common 缺少 EvalConfig")
        self.assertTrue(hasattr(C, "load_yaml"), "common 缺少 load_yaml")
        self.assertTrue(hasattr(C, "scaffold"), "common 缺少 scaffold")


class TestCLISmoke(unittest.TestCase):
    """2. --help 不报错。"""

    CLI_SCRIPTS = [
        "eval_runner",
        "diagnoser",
        "multi_judge",
        "opik_adapter",
        "reference_optimizer",
        "auto_patcher",
        "html_report",
        "pdf_report",
        "dashboard",
        "ci_regression",
        "ask_setup",
        "report_manager",
        "scorer",
        "mutator",
        "abtest",
        "case_io",
        "case_quality_checker",
        "case_optimizer",
        "mutation_generator",
        "case_iteration_report",
        "progress_tracker",
        "report_portal",
        "generate_requirements",
        "generate_testcases",
        "execute_testcases",
        "excel_to_uatr",
        "generate_report",
        # dev-skill-eval 合并进来的 6 个
        "annotate_server",
        "annotator",
        "cost_tracker",
        "sse_stream",
        "stratified_sampler",
        "xlsx_importer",
    ]

    def test_help_exits_zero(self):
        failures = []
        for s in self.CLI_SCRIPTS:
            r = subprocess.run(
                [sys.executable, str(SCRIPTS / f"{s}.py"), "--help"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # argparse --help 退出码 0
            if r.returncode != 0 or "usage:" not in r.stdout:
                failures.append((s, r.returncode, r.stderr[:160]))
        self.assertEqual(failures, [], f"--help 失败的脚本: {failures}")


class TestGiteeFeaturesFunctional(unittest.TestCase):
    """3. dev-skill-eval 合并的 6 个脚本真跑一次。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ae-unit-"))
        self.cfg_dir = self.tmp / ".agent-eval"
        shutil.copytree(EXAMPLES_CFG, self.cfg_dir)
        # 跑一次 baseline 供 cost_tracker / annotator 消费
        r = _run(
            "eval_runner",
            "--config",
            str(self.cfg_dir / "config.yaml"),
            "--split",
            "train",
            "--variant",
            "baseline",
            "--label",
            "unit",
            cwd=self.tmp,
        )
        self.assertEqual(r.returncode, 0, f"eval_runner 失败: {r.stderr}")
        runs = list(self.cfg_dir.glob("runs/*.jsonl"))
        self.assertTrue(runs, "没生成 run 文件")
        self.run_id = runs[0].stem

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_annotator_stats_validate(self):
        r = _run("annotator", "--config", str(self.cfg_dir / "config.yaml"), "--stats", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stderr)
        # stats 输出 JSON 片段
        self.assertIn("pass_fail", r.stdout)
        r2 = _run("annotator", "--config", str(self.cfg_dir / "config.yaml"), "--validate", cwd=self.tmp)
        self.assertEqual(r2.returncode, 0, r2.stderr)

    def test_cost_tracker_build_spans_and_report(self):
        r = _run(
            "cost_tracker",
            "--config",
            str(self.cfg_dir / "config.yaml"),
            "--run",
            self.run_id,
            "--build-spans",
            cwd=self.tmp,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        spans_file = self.cfg_dir / "traces" / f"{self.run_id}.spans.jsonl"
        self.assertTrue(spans_file.exists(), "spans.jsonl 未生成")
        self.assertGreater(spans_file.stat().st_size, 0)

        r2 = _run(
            "cost_tracker",
            "--config",
            str(self.cfg_dir / "config.yaml"),
            "--run",
            self.run_id,
            "--report",
            "--aggregate-by",
            "tool",
            cwd=self.tmp,
        )
        self.assertEqual(r2.returncode, 0, r2.stderr)
        report_files = list(self.cfg_dir.glob(f"reports/{self.run_id}_cost_*.json"))
        self.assertTrue(report_files, "成本报表未生成")

    def test_stratified_sampler_fallback(self):
        # config.yaml 未启用 stratified_sampling → 返回全部用例
        r = _run(
            "stratified_sampler",
            "--config",
            str(self.cfg_dir / "config.yaml"),
            "--split",
            "train",
            "--sample-size",
            "3",
            cwd=self.tmp,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sampled_count", r.stdout)

    def test_xlsx_importer_export_annotations(self):
        r = _run(
            "xlsx_importer",
            "--config",
            str(self.cfg_dir / "config.yaml"),
            "--export-annotations",
            cwd=self.tmp,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        tpl = self.cfg_dir / "annotations_template.xlsx"
        self.assertTrue(tpl.exists(), "annotations_template.xlsx 未生成")
        self.assertGreater(tpl.stat().st_size, 1000)

    def test_annotate_server_and_sse_stream_constructible(self):
        # 不真正起服务，只验证模块可 import 且有 main()
        import annotate_server  # noqa: F401
        import sse_stream  # noqa: F401

        self.assertTrue(callable(annotate_server.main))
        self.assertTrue(callable(sse_stream.main))


if __name__ == "__main__":
    unittest.main(verbosity=2)
