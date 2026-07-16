#!/usr/bin/env python3
"""case_io.py — cases YAML 读写，保留完整 canonical schema。

V1.1 用例自优化的基础模块。负责：
- 读 cases/<split>.yaml（完整 schema：expected_tools/business_rules/expected_steps/scoring + V1.1 新增 test_level/category/lifecycle/dimension_id/scenario_id/mock_config）
- 写回时保留所有字段（不丢字段）
- 校验 schema（字段完整性）
- diff（before/after 对比，用于迭代报告）

零 LLM。纯 YAML I/O + 校验。

用法:
  # 读
  python case_io.py --config .agent-eval/config.yaml --split train --read

  # 校验
  python case_io.py --config .agent-eval/config.yaml --split train --validate

  # diff（对比两个 split）
  python case_io.py --config .agent-eval/config.yaml --split train --diff-train-after cases/train_after.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------------------------------------------------------------------
# canonical schema 定义
# ---------------------------------------------------------------------------

# 必填字段（缺则校验失败）
REQUIRED_FIELDS = {"id", "name", "agent", "task", "input", "expected"}

# 完整字段集合（V1.1 canonical schema）
FULL_FIELDS = {
    # 基础
    "id", "name", "agent", "task",
    # 输入
    "input",  # {user_message, application_id, attachments}
    # 第1层断言：输出层
    "expected",  # {final_decision: {contains|equals|regex|schema}}
    # 第2层断言：行为层
    "expected_tools",  # {required, forbidden, order.soft}
    # 第3层断言：规则层
    "business_rules",  # {must_satisfy: [{id, description, trace_event_contains|final_answer_contains}]}
    # 第4层断言：过程层
    "expected_steps",  # int
    # 第5层断言：硬失败
    "scoring",  # {hard_fail_if: [...]}
    # V1.1 新增
    "test_level",      # black_box | gray_box | white_box
    "category",        # functional | dfx_security | dfx_reliability | dfx_performance | dfx_compatibility | adversarial
    "lifecycle",       # active | deprecated | draft
    "dimension_id",    # 关联需求维度
    "scenario_id",     # 关联需求场景
    "expect_skill_trigger",  # {prompt_hash}
    "expect_preflight_advisor",  # bool
    "expect_memory_use",  # bool
    # mock 配置（仅 mock adapter）
    "mock_config",
}

# 可机器验证的断言类型
ASSERTION_TYPES = {"contains", "equals", "regex", "schema", "status_code", "tool_called", "business_rule"}

# 硬失败条件
HARD_FAIL_CONDITIONS = {
    "forbidden_tool_called",
    "missing_required_business_rule",
    "invalid_json_schema",
    # V1.1 新增
    "step_count_exceeds_1.5x",
    "tool_repeat_3x",
    "hallucination_detected",
    "missing_memory_use",
}

TEST_LEVELS = {"black_box", "gray_box", "white_box"}
CATEGORIES = {"functional", "dfx_security", "dfx_reliability", "dfx_performance",
              "dfx_compatibility", "dfx_serviceability", "dfx_maintainability",
              "adversarial"}
LIFECYCLES = {"active", "deprecated", "draft"}


# ---------------------------------------------------------------------------
# 读
# ---------------------------------------------------------------------------

def load_cases(cfg: C.EvalConfig, split: str = "train") -> list[dict[str, Any]]:
    """读 cases/<split>.yaml，返回 cases 列表。"""
    path = cfg.cases_dir / f"{split}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"用例文件不存在: {path}")
    data = C.load_yaml(path)
    return data.get("cases", []) or []


def load_cases_with_meta(cfg: C.EvalConfig, split: str = "train") -> dict[str, Any]:
    """读 cases YAML 完整结构（含 meta）。"""
    path = cfg.cases_dir / f"{split}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"用例文件不存在: {path}")
    return C.load_yaml(path)


# ---------------------------------------------------------------------------
# 写（保留完整 schema）
# ---------------------------------------------------------------------------

def save_cases(cfg: C.EvalConfig, split: str, cases: list[dict[str, Any]],
               meta: dict[str, Any] | None = None) -> Path:
    """写 cases/<split>.yaml，保留完整 schema。

    自动按 id 排序，保留注释头。
    """
    path = cfg.cases_dir / f"{split}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    # 排序（按 id，但保持稳定）
    cases_sorted = sorted(cases, key=lambda c: c.get("id", ""))

    out: dict[str, Any] = {}
    if meta:
        out.update(meta)
    out["cases"] = cases_sorted

    C.dump_yaml(out, path)
    return path


def backup_cases(cfg: C.EvalConfig, split: str) -> Path | None:
    """备份当前 cases 文件到 data/ 目录。返回备份路径。"""
    src = cfg.cases_dir / f"{split}.yaml"
    if not src.exists():
        return None
    backup_dir = cfg.root / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = C.now_iso().replace(":", "-").replace("+", "Z")
    dst = backup_dir / f"{split}.{ts}.yaml"
    import shutil
    shutil.copy2(src, dst)
    return dst


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def validate_case(case: dict[str, Any]) -> list[str]:
    """校验单条 case，返回错误列表（空=合法）。"""
    errs: list[str] = []
    cid = case.get("id", "<no-id>")

    # 必填字段
    for f in REQUIRED_FIELDS:
        if f not in case:
            errs.append(f"{cid}: 缺必填字段 `{f}`")

    # id 非空
    if not case.get("id"):
        errs.append(f"case id 为空")

    # expected 结构
    exp = case.get("expected") or {}
    if exp:
        fd = exp.get("final_decision") or {}
        if fd:
            for k in fd:
                if k not in ASSERTION_TYPES and k not in ("final_decision",):
                    errs.append(f"{cid}: expected.final_decision 未知断言类型 `{k}`")

    # expected_tools 结构
    et = case.get("expected_tools") or {}
    if et:
        if "required" in et and not isinstance(et["required"], list):
            errs.append(f"{cid}: expected_tools.required 必须是 list")
        if "forbidden" in et and not isinstance(et["forbidden"], list):
            errs.append(f"{cid}: expected_tools.forbidden 必须是 list")

    # scoring.hard_fail_if
    sc = case.get("scoring") or {}
    if sc:
        hfi = sc.get("hard_fail_if") or []
        for h in hfi:
            if h not in HARD_FAIL_CONDITIONS:
                errs.append(f"{cid}: scoring.hard_fail_if 未知条件 `{h}`")

    # V1.1 字段枚举校验
    tl = case.get("test_level")
    if tl and tl not in TEST_LEVELS:
        errs.append(f"{cid}: test_level `{tl}` 不在 {TEST_LEVELS}")
    cat = case.get("category")
    if cat and cat not in CATEGORIES:
        errs.append(f"{cid}: category `{cat}` 不在 {CATEGORIES}")
    lc = case.get("lifecycle")
    if lc and lc not in LIFECYCLES:
        errs.append(f"{cid}: lifecycle `{lc}` 不在 {LIFECYCLES}")

    # expected_steps
    es = case.get("expected_steps")
    if es is not None and (not isinstance(es, int) or es < 1):
        errs.append(f"{cid}: expected_steps 必须是正整数，实际 {es!r}")

    return errs


def validate_cases(cases: list[dict[str, Any]]) -> list[str]:
    """校验用例集，返回错误列表。含 id 唯一性检查。"""
    errs: list[str] = []
    ids: set[str] = set()
    for c in cases:
        errs.extend(validate_case(c))
        cid = c.get("id", "")
        if cid in ids:
            errs.append(f"重复 case id: {cid}")
        ids.add(cid)
    return errs


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------

def diff_cases(before: list[dict], after: list[dict]) -> dict[str, Any]:
    """对比两个 cases 列表，返回 diff 结构。"""
    before_map = {c["id"]: c for c in before}
    after_map = {c["id"]: c for c in after}

    added = [aid for aid in after_map if aid not in before_map]
    removed = [bid for bid in before_map if bid not in after_map]
    modified: list[dict] = []

    for cid in before_map:
        if cid in after_map:
            b = before_map[cid]
            a = after_map[cid]
            changes = _diff_single(b, a)
            if changes:
                modified.append({"case_id": cid, "changes": changes})

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "counts": {
            "before": len(before),
            "after": len(after),
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
        },
    }


def _diff_single(before: dict, after: dict) -> list[dict]:
    """对比单条 case 的字段变化。"""
    changes: list[dict] = []
    all_keys = set(before.keys()) | set(after.keys())
    for k in all_keys:
        bv = before.get(k)
        av = after.get(k)
        if bv != av:
            changes.append({
                "field": k,
                "before": bv,
                "after": av,
            })
    return changes


# ---------------------------------------------------------------------------
# 应用优化建议（被 case_optimizer 调用）
# ---------------------------------------------------------------------------

def apply_proposal(
    cfg: C.EvalConfig,
    split: str,
    cases: list[dict],
    proposal: dict[str, Any],
) -> tuple[list[dict], dict[str, Any]]:
    """把优化建议 apply 到 cases 列表，返回 (new_cases, apply_summary)。

    proposal 结构见 PRD_CASE_SELF_OPTIMIZATION §3.3。
    """
    cases_map = {c["id"]: c for c in cases}
    added: list[str] = []
    modified: list[str] = []
    deprecated: list[str] = []

    # add_cases
    for add in proposal.get("add_cases", []):
        c = add.get("case") or {}
        cid = c.get("id") or add.get("suggested_id")
        if not cid:
            continue
        # 避免 id 冲突
        if cid in cases_map:
            # 自动加后缀
            i = 2
            while f"{cid}_{i}" in cases_map:
                i += 1
            cid = f"{cid}_{i}"
            c["id"] = cid
        # 补默认字段
        c.setdefault("test_level", "gray_box")
        c.setdefault("category", "functional")
        c.setdefault("lifecycle", "active")
        c.setdefault("expected_steps", 8)
        c.setdefault("scoring", {"hard_fail_if": ["forbidden_tool_called"]})
        cases_map[cid] = c
        added.append(cid)

    # modify_cases
    for mod in proposal.get("modify_cases", []):
        cid = mod.get("case_id")
        if cid not in cases_map:
            continue
        field = mod.get("field")
        new_val = mod.get("new_value")
        if not field:
            continue
        # 支持 dotted field（如 scoring.hard_fail_if）
        parts = field.split(".")
        target = cases_map[cid]
        for p in parts[:-1]:
            target = target.setdefault(p, {})
        target[parts[-1]] = new_val
        modified.append(cid)

    # deprecate_cases
    for dep in proposal.get("deprecate_cases", []):
        cid = dep.get("case_id")
        if cid not in cases_map:
            continue
        action = dep.get("action", "mark_deprecated")
        if action == "mark_deprecated":
            cases_map[cid]["lifecycle"] = "deprecated"
        elif action == "remove":
            cases_map.pop(cid, None)
        deprecated.append(cid)

    new_cases = list(cases_map.values())
    summary = {
        "added": added,
        "modified": modified,
        "deprecated": deprecated,
        "counts": {
            "before": len(cases),
            "after": len(new_cases),
            "added": len(added),
            "modified": len(modified),
            "deprecated": len(deprecated),
        },
    }
    return new_cases, summary


# ---------------------------------------------------------------------------
# 工具：提取所有出现过的工具
# ---------------------------------------------------------------------------

def extract_all_tools(cases: list[dict]) -> list[str]:
    """从 cases 提取所有 expected_tools.required 出现过的工具（去重保序）。"""
    seen: list[str] = []
    seen_set: set[str] = set()
    for c in cases:
        et = c.get("expected_tools") or {}
        for t in et.get("required", []) or []:
            if t not in seen_set:
                seen.append(t)
                seen_set.add(t)
    return seen


def extract_all_dimensions(cases: list[dict]) -> list[str]:
    """提取所有 dimension_id（去重保序）。"""
    seen: list[str] = []
    seen_set: set[str] = set()
    for c in cases:
        d = c.get("dimension_id")
        if d and d not in seen_set:
            seen.append(d)
            seen_set.add(d)
    return seen


def extract_all_categories(cases: list[dict]) -> list[str]:
    """提取所有 category（去重保序）。"""
    seen: list[str] = []
    seen_set: set[str] = set()
    for c in cases:
        cat = c.get("category", "functional")
        if cat not in seen_set:
            seen.append(cat)
            seen_set.add(cat)
    return seen


# ---------------------------------------------------------------------------
# 迭代历史记录
# ---------------------------------------------------------------------------

def data_dir(cfg: C.EvalConfig) -> Path:
    d = cfg.root / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_iteration(cfg: C.EvalConfig, record: dict[str, Any]) -> Path:
    """追加一条迭代记录到 data/case_iterations.jsonl。"""
    path = data_dir(cfg) / "case_iterations.jsonl"
    C.append_jsonl(path, record)
    return path


def load_iterations(cfg: C.EvalConfig) -> list[dict[str, Any]]:
    """读历史迭代记录。"""
    path = data_dir(cfg) / "case_iterations.jsonl"
    return C.load_jsonl(path)


def latest_iteration(cfg: C.EvalConfig) -> dict[str, Any] | None:
    """读最近一条迭代记录。"""
    iters = load_iterations(cfg)
    return iters[-1] if iters else None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="cases YAML 读写 + 校验 + diff")
    ap.add_argument("--config", required=True)
    ap.add_argument("--split", default="train")
    ap.add_argument("--read", action="store_true", help="读 cases 并打印 JSON")
    ap.add_argument("--validate", action="store_true", help="校验 schema")
    ap.add_argument("--diff-after", help="对比当前 split 与指定 YAML 文件")
    ap.add_argument("--list-tools", action="store_true", help="列出所有出现的工具")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = load_cases(cfg, args.split)

    if args.read:
        print(json.dumps(cases, ensure_ascii=False, indent=2))
        return 0

    if args.validate:
        errs = validate_cases(cases)
        if errs:
            print(f"校验失败 {len(errs)} 条:")
            for e in errs:
                print(f"  - {e}")
            return 1
        print(f"校验通过：{len(cases)} 条用例")
        return 0

    if args.diff_after:
        after_path = Path(args.diff_after)
        after_cases = C.load_yaml(after_path).get("cases", []) or []
        d = diff_cases(cases, after_cases)
        print(json.dumps(d, ensure_ascii=False, indent=2))
        return 0

    if args.list_tools:
        tools = extract_all_tools(cases)
        print(f"工具列表（{len(tools)}）:")
        for t in tools:
            print(f"  - {t}")
        return 0

    # 默认：打印摘要
    print(f"split={args.split} cases={len(cases)}")
    print(f"工具数: {len(extract_all_tools(cases))}")
    print(f"维度数: {len(extract_all_dimensions(cases))}")
    print(f"类别数: {len(extract_all_categories(cases))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
