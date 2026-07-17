#!/usr/bin/env python3
"""case_optimizer.py — 用例自优化核心：错误分布分析 + 缺口识别 + 建议生成 + apply。

V1.1 的核心脚本。把诊断结果 + 评分 + 用例集 + 质量 + mutation 综合分析，
生成结构化优化建议（add/modify/deprecate/spec_changes），可选 apply 到 cases YAML。

零 LLM。所有建议基于规则映射 F-type → case template。创造性内容生成由 Agent（子 skill）完成。

用法:
  # 分析 + 生成建议（dry-run，不写 cases）
  python case_optimizer.py --config .agent-eval/config.yaml --run <run_id> --split train

  # 分析 + 生成 + 自动 apply
  python case_optimizer.py --config .agent-eval/config.yaml --run <run_id> --split train --apply

  # 非交互（CI，全部接受）
  python case_optimizer.py --config .agent-eval/config.yaml --run <run_id> --split train --apply --non-interactive
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import case_io as CIO  # noqa: E402
import case_quality_checker as CQC  # noqa: E402
import mutation_generator as MG  # noqa: E402


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

CONCENTRATION_RATIO_THRESHOLD = 0.4
CONCENTRATION_COUNT_THRESHOLD = 3
LOW_SCORE_DIM_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# Step 1: 错误分布分析
# ---------------------------------------------------------------------------

def analyze_error_distribution(diagnosis: dict) -> dict[str, Any]:
    """分析 F1-F8 分布，识别集中类型。"""
    by_type: dict[str, int] = diagnosis.get("by_failure_type", {}) or {}
    total = sum(by_type.values()) if by_type else 0

    distribution: dict[str, dict] = {}
    for ft, count in sorted(by_type.items()):
        ratio = count / total if total > 0 else 0.0
        concentrated = ratio >= CONCENTRATION_RATIO_THRESHOLD or count >= CONCENTRATION_COUNT_THRESHOLD
        distribution[ft] = {
            "count": count,
            "ratio": round(ratio, 4),
            "concentrated": concentrated,
        }

    concentrated_types = [ft for ft, d in distribution.items() if d["concentrated"]]

    return {
        "total_diagnoses": total,
        "by_failure_type": distribution,
        "concentrated_types": concentrated_types,
    }


# ---------------------------------------------------------------------------
# Step 2: Spec 缺口识别
# ---------------------------------------------------------------------------

def identify_spec_gaps(
    cases: list[dict],
    diagnosis: dict,
    req_dimensions: list[str] | None,
    all_tools: list[str] | None,
) -> list[dict]:
    """识别 spec 缺口：维度缺口/工具缺口/DFX缺口/过简单维度。"""
    gaps: list[dict] = []

    # 维度缺口
    covered_dims = set(c.get("dimension_id") for c in cases if c.get("dimension_id"))
    dim_source = req_dimensions or []
    for dim in dim_source:
        if dim not in covered_dims:
            gaps.append({
                "type": "dimension_gap",
                "dimension_id": dim,
                "case_count": 0,
                "severity": "high",
                "reason": f"维度 {dim} 无用例覆盖",
            })

    # 工具缺口
    if all_tools is None:
        all_tools = CIO.extract_all_tools(cases)
    covered_tools: set[str] = set()
    for c in cases:
        et = c.get("expected_tools") or {}
        for t in et.get("required", []) or []:
            covered_tools.add(t)
    for tool in all_tools:
        if tool not in covered_tools:
            gaps.append({
                "type": "tool_gap",
                "tool": tool,
                "case_count": 0,
                "severity": "medium",
                "reason": f"工具 {tool} 无用例覆盖",
            })

    # DFX 缺口
    dfx_types = CQC.DFX_TYPES
    covered_dfx = set(c.get("category") for c in cases if c.get("category") in dfx_types)
    for dfx in dfx_types:
        if dfx not in covered_dfx:
            gaps.append({
                "type": "dfx_gap",
                "dfx_type": dfx,
                "case_count": 0,
                "severity": "medium",
                "reason": f"DFX 类型 {dfx} 无用例覆盖",
            })

    # 过简单维度（100% 通过 且 用例数 >= 2）
    # 从 scores 推断
    per_case_scores = {}
    if diagnosis.get("scores"):
        per_case_scores = diagnosis["scores"].get("per_case", [])
    else:
        # 尝试从单独的 scores 文件读（由 main 传入）
        pass

    return gaps


def identify_easy_dimensions(
    cases: list[dict],
    per_case_scores: list[dict],
) -> list[dict]:
    """识别过简单维度（100% 通过 且 用例数 >= 2）。"""
    if not per_case_scores:
        return []
    # 按 dimension_id 聚合
    dim_cases: dict[str, list[str]] = {}
    for c in cases:
        dim = c.get("dimension_id")
        if dim:
            dim_cases.setdefault(dim, []).append(c.get("id", ""))

    score_by_case = {pc.get("case_id"): pc for pc in per_case_scores}
    easy: list[dict] = []
    for dim, cids in dim_cases.items():
        if len(cids) < 2:
            continue
        all_pass = all(
            score_by_case.get(cid, {}).get("weighted_score", 0) >= 0.6
            for cid in cids
        )
        if all_pass:
            easy.append({
                "type": "easy_dimension",
                "dimension_id": dim,
                "case_count": len(cids),
                "case_ids": cids,
                "severity": "low",
                "reason": f"维度 {dim} 的 {len(cids)} 条用例全部通过，可能太简单",
            })
    return easy


# ---------------------------------------------------------------------------
# Step 3: 用例质量检查（调 case_quality_checker）
# ---------------------------------------------------------------------------

def run_quality_check(
    cfg: C.EvalConfig,
    cases: list[dict],
    req_dimensions: list[str] | None,
    scores: dict | None,
) -> dict:
    return CQC.check_quality(
        cases,
        req_dimensions=req_dimensions,
        scores=scores,
        all_tools=CIO.extract_all_tools(cases),
    )


# ---------------------------------------------------------------------------
# Step 4: Mutation 分析（调 mutation_generator）
# ---------------------------------------------------------------------------

def run_mutation_analysis(
    cfg: C.EvalConfig,
    cases: list[dict],
    run_id: str,
) -> dict:
    traces_by_case = MG.load_traces_by_case(cfg, run_id)
    return MG.run_kill_matrix(cases, traces_by_case, run_id)


# ---------------------------------------------------------------------------
# Step 5: 生成增强建议
# ---------------------------------------------------------------------------

# F-type → 用例增强模板
F_TYPE_CASE_TEMPLATES: dict[str, dict] = {
    "F3.1": {
        "name_suffix": "工具选择边界-漏工具检测",
        "category": "functional",
        "reason": "F3.1 工具选择失败集中，需补充工具选择边界用例",
        "extra_scoring": ["step_count_exceeds_1.5x"],
    },
    "F3.3": {
        "name_suffix": "重复调用检测",
        "category": "functional",
        "reason": "F3.3 重复调用失败，需补充重复调用检测用例",
        "extra_scoring": ["tool_repeat_3x"],
    },
    "F4.4": {
        "name_suffix": "工具参数边界",
        "category": "functional",
        "reason": "F4.4 工具参数失败，需补充参数边界用例",
        "extra_scoring": [],
    },
    "F5.3": {
        "name_suffix": "异常恢复-fallback",
        "category": "dfx_reliability",
        "reason": "F5.3 Workflow fallback 失败，需补充异常恢复场景用例",
        "extra_scoring": [],
    },
    "F6.1": {
        "name_suffix": "记忆检索触发",
        "category": "functional",
        "reason": "F6.1 Memory 失败，需补充记忆检索触发用例",
        "extra_scoring": ["missing_memory_use"],
    },
    "F7.3": {
        "name_suffix": "业务规则断言增强",
        "category": "functional",
        "reason": "F7.3 漏业务规则，需增强业务规则断言",
        "extra_scoring": ["missing_required_business_rule"],
    },
    "F7.4": {
        "name_suffix": "幻觉检测",
        "category": "adversarial",
        "reason": "F7.4 幻觉失败，需补充幻觉检测用例",
        "extra_scoring": ["hallucination_detected"],
    },
    "F8.1": {
        "name_suffix": "效率-轮数控制",
        "category": "dfx_performance",
        "reason": "F8.1 轮数过多，需补充效率断言用例",
        "extra_scoring": ["step_count_exceeds_1.5x"],
    },
    "F8.2": {
        "name_suffix": "效率-决策后即执行",
        "category": "dfx_performance",
        "reason": "F8.2 重复规划，需补充效率断言用例",
        "extra_scoring": ["step_count_exceeds_1.5x"],
    },
    "F8.4": {
        "name_suffix": "效率-避免探索式徘徊",
        "category": "dfx_performance",
        "reason": "F8.4 探索式徘徊，需补充效率断言用例",
        "extra_scoring": ["step_count_exceeds_1.5x"],
    },
}


def _next_case_id(cases: list[dict], prefix: str | None = None) -> str:
    """生成下一个不冲突的 case id。

    自动从现有 cases 推断命名前缀（如 loan_risk_），保持命名一致性。
    """
    existing = {c.get("id", "") for c in cases}
    if prefix is None:
        # 从现有 cases 推断前缀：取第一个 case id 的非数字部分作为前缀
        for c in cases:
            cid = c.get("id", "")
            if cid:
                # 去掉末尾的数字部分
                import re
                m = re.match(r"^(.*?)(\d+)$", cid)
                if m:
                    prefix = m.group(1)
                    break
        if prefix is None:
            prefix = "case_"
    # 确保 prefix 以下划线结尾
    if not prefix.endswith("_"):
        prefix = prefix + "_"
    n = 1
    while f"{prefix}{n:03d}" in existing:
        n += 1
    return f"{prefix}{n:03d}"


# F-type → hard_fail_if 条件映射
FT_TO_HARD_FAIL: dict[str, list[str]] = {
    "F3.1": [],  # 漏工具由 expected_tools.required 断言隐含
    "F3.3": ["tool_repeat_3x"],
    "F4.4": [],  # 参数错由 tool_result.status=error 隐含，无独立 hard_fail 条件
    "F5.3": [],  # fallback 失败由 workflow 检查隐含
    "F6.1": ["missing_memory_use"],
    "F7.3": ["missing_required_business_rule"],
    "F7.4": ["hallucination_detected"],
    "F8.1": ["step_count_exceeds_1.5x"],
    "F8.2": ["step_count_exceeds_1.5x"],
    "F8.4": ["step_count_exceeds_1.5x"],
}


def _ft_to_hard_fail(ft: str) -> list[str]:
    """把失败类型映射成有效的 hard_fail_if 条件列表。"""
    return FT_TO_HARD_FAIL.get(ft, [])


def generate_add_cases(
    cases: list[dict],
    error_dist: dict,
    spec_gaps: list[dict],
    survived_mutations: list[dict],
) -> list[dict]:
    """生成新增用例建议。"""
    add_cases: list[dict] = []
    added_reasons: set[str] = set()
    # 追踪本批已生成的 id，避免批量冲突
    existing_ids = {c.get("id", "") for c in cases}
    pending_ids: set[str] = set()

    def next_id() -> str:
        import re
        prefix = "case_"
        for c in cases:
            cid = c.get("id", "")
            if cid:
                m = re.match(r"^(.*?)(\d+)$", cid)
                if m:
                    prefix = m.group(1)
                    break
        if not prefix.endswith("_"):
            prefix = prefix + "_"
        n = 1
        while f"{prefix}{n:03d}" in existing_ids or f"{prefix}{n:03d}" in pending_ids:
            n += 1
        new_id = f"{prefix}{n:03d}"
        pending_ids.add(new_id)
        return new_id

    # 1. 基于错误集中
    for ft in error_dist.get("concentrated_types", []):
        # 匹配模板（精确或父类）
        template = F_TYPE_CASE_TEMPLATES.get(ft)
        if not template:
            # 模糊匹配 F3 / F4 等
            parent = ft.split(".")[0]
            for k, v in F_TYPE_CASE_TEMPLATES.items():
                if k.startswith(parent):
                    template = v
                    break
        if not template:
            continue
        reason = template["reason"]
        if reason in added_reasons:
            continue
        added_reasons.add(reason)

        new_id = next_id()
        add_cases.append({
            "suggested_id": new_id,
            "reason": reason,
            "trigger_failure_type": ft,
            "case": {
                "id": new_id,
                "name": f"自优化-{template['name_suffix']}",
                "agent": cases[0].get("agent", "agent") if cases else "agent",
                "task": f"针对 {ft} 失败类型补充的边界用例，待 Agent 细化",
                "input": {"user_message": "(待 Agent 生成)", "application_id": "AUTO"},
                "expected": {"final_decision": {"contains": ["(待 Agent 生成)"]}},
                "expected_tools": {"required": [], "forbidden": []},
                "business_rules": {"must_satisfy": []},
                "expected_steps": 9,
                "scoring": {"hard_fail_if": ["forbidden_tool_called"] + template["extra_scoring"]},
                "test_level": "gray_box",
                "category": template["category"],
                "lifecycle": "draft",
            },
        })

    # 2. 基于 spec 缺口（维度缺口）
    for gap in spec_gaps:
        if gap["type"] == "dimension_gap":
            new_id = next_id()
            add_cases.append({
                "suggested_id": new_id,
                "reason": gap["reason"],
                "trigger_failure_type": "spec_gap",
                "case": {
                    "id": new_id,
                    "name": f"自优化-维度{gap['dimension_id']}覆盖",
                    "agent": cases[0].get("agent", "agent") if cases else "agent",
                    "task": f"补充维度 {gap['dimension_id']} 的用例覆盖，待 Agent 细化",
                    "input": {"user_message": "(待 Agent 生成)"},
                    "expected": {"final_decision": {"contains": ["(待 Agent 生成)"]}},
                    "expected_tools": {"required": [], "forbidden": []},
                    "business_rules": {"must_satisfy": []},
                    "expected_steps": 8,
                    "scoring": {"hard_fail_if": ["forbidden_tool_called"]},
                    "test_level": "gray_box",
                    "category": "functional",
                    "lifecycle": "draft",
                    "dimension_id": gap["dimension_id"],
                },
            })
        elif gap["type"] == "dfx_gap":
            new_id = next_id()
            add_cases.append({
                "suggested_id": new_id,
                "reason": gap["reason"],
                "trigger_failure_type": "spec_gap",
                "case": {
                    "id": new_id,
                    "name": f"自优化-DFX{gap['dfx_type']}覆盖",
                    "agent": cases[0].get("agent", "agent") if cases else "agent",
                    "task": f"补充 DFX {gap['dfx_type']} 的用例覆盖，待 Agent 细化",
                    "input": {"user_message": "(待 Agent 生成)"},
                    "expected": {"final_decision": {"contains": ["(待 Agent 生成)"]}},
                    "expected_tools": {"required": [], "forbidden": []},
                    "business_rules": {"must_satisfy": []},
                    "expected_steps": 8,
                    "scoring": {"hard_fail_if": ["forbidden_tool_called"]},
                    "test_level": "gray_box",
                    "category": gap["dfx_type"],
                    "lifecycle": "draft",
                },
            })

    # 3. 基于 survived mutation（限制数量，避免过多）
    for sm in survived_mutations[:3]:  # 最多建议 3 条
        new_id = next_id()
        add_cases.append({
            "suggested_id": new_id,
            "reason": f"mutation {sm['mutation']} 未被用例 {sm['case_id']} 检出，需增强",
            "trigger_failure_type": sm["target_failure_type"],
            "case": {
                "id": new_id,
                "name": f"自优化-mutation{sm['mutation']}检出",
                "agent": cases[0].get("agent", "agent") if cases else "agent",
                "task": f"增强用例以检出 {sm['mutation_name']}，待 Agent 细化",
                "input": {"user_message": "(待 Agent 生成)"},
                "expected": {"final_decision": {"contains": ["(待 Agent 生成)"]}},
                "expected_tools": {"required": [], "forbidden": []},
                "business_rules": {"must_satisfy": []},
                "expected_steps": 8,
                "scoring": {"hard_fail_if": ["forbidden_tool_called"] + _ft_to_hard_fail(sm["target_failure_type"])},
                "test_level": "gray_box",
                "category": "adversarial",
                "lifecycle": "draft",
            },
        })

    return add_cases


def generate_modify_cases(
    cases: list[dict],
    quality_result: dict,
    error_dist: dict,
) -> list[dict]:
    """生成修改用例建议。"""
    modify_cases: list[dict] = []

    # 1. 基于低分维度
    for dim_id in quality_result.get("low_score_dimensions", []):
        dim_info = quality_result["dimensions"].get(dim_id, {})
        if dim_id == "assertion_verifiable":
            # 给断言不可验证的 case 加可验证断言
            detail = dim_info.get("detail", {})
            for cid in detail.get("unverifiable_ids", []):
                modify_cases.append({
                    "case_id": cid,
                    "reason": f"用例 {cid} 的 expected 断言不可机器验证，需补充 contains/equals/regex",
                    "field": "expected.final_decision.contains",
                    "old_value": None,
                    "new_value": ["(待 Agent 补充可验证断言)"],
                    "trigger_failure_type": "quality_low",
                })
        elif dim_id == "length_reasonable":
            detail = dim_info.get("detail", {})
            for cid in detail.get("unreasonable_ids", []):
                modify_cases.append({
                    "case_id": cid,
                    "reason": f"用例 {cid} 长度不合理（步数>10 或 task 过长），需精简",
                    "field": "expected_steps",
                    "old_value": None,
                    "new_value": 9,
                    "trigger_failure_type": "quality_low",
                })
        elif dim_id == "ambiguity_free":
            detail = dim_info.get("detail", {})
            for cid in detail.get("ambiguous_ids", []):
                modify_cases.append({
                    "case_id": cid,
                    "reason": f"用例 {cid} 含二义性词汇，需消除歧义",
                    "field": "task",
                    "old_value": None,
                    "new_value": "(待 Agent 重写，去除'等等/之类的/可能'等词)",
                    "trigger_failure_type": "quality_low",
                })

    # 2. 基于 F8 集中：给相关 case 加 step_count_exceeds_1.5x 硬失败
    f8_types = [ft for ft in error_dist.get("concentrated_types", []) if ft.startswith("F8")]
    if f8_types:
        for c in cases:
            sc = c.get("scoring") or {}
            hfi = sc.get("hard_fail_if") or []
            if "step_count_exceeds_1.5x" not in hfi:
                modify_cases.append({
                    "case_id": c.get("id"),
                    "reason": f"F8 集中，给用例 {c.get('id')} 补充效率硬失败断言",
                    "field": "scoring.hard_fail_if",
                    "old_value": hfi,
                    "new_value": hfi + ["step_count_exceeds_1.5x"],
                    "trigger_failure_type": "F8",
                })

    # 3. 基于 F7.3：给漏业务规则的 case 加 missing_required_business_rule 硬失败
    if "F7.3" in error_dist.get("concentrated_types", []):
        for c in cases:
            sc = c.get("scoring") or {}
            hfi = sc.get("hard_fail_if") or []
            if "missing_required_business_rule" not in hfi:
                modify_cases.append({
                    "case_id": c.get("id"),
                    "reason": f"F7.3 集中，给用例 {c.get('id')} 补充业务规则硬失败断言",
                    "field": "scoring.hard_fail_if",
                    "old_value": hfi,
                    "new_value": hfi + ["missing_required_business_rule"],
                    "trigger_failure_type": "F7.3",
                })

    return modify_cases


def generate_deprecate_cases(cases: list[dict]) -> list[dict]:
    """生成废弃用例建议（重复用例）。"""
    deprecate: list[dict] = []
    # 找重复：相同 name + 相似 task
    seen_names: dict[str, list[str]] = {}
    for c in cases:
        if c.get("lifecycle") == "deprecated":
            continue
        name = c.get("name", "")
        if name in seen_names:
            seen_names[name].append(c.get("id", ""))
        else:
            seen_names[name] = [c.get("id", "")]

    for name, ids in seen_names.items():
        if len(ids) > 1:
            # 废弃后面的，保留第一个
            for cid in ids[1:]:
                deprecate.append({
                    "case_id": cid,
                    "reason": f"与 {ids[0]} 重复（同名：{name}），降低有效用例率",
                    "action": "mark_deprecated",
                })
    return deprecate


def generate_spec_changes(
    cases: list[dict],
    error_dist: dict,
    spec_gaps: list[dict],
) -> list[dict]:
    """生成 spec 变更建议。"""
    changes: list[dict] = []

    # F8 集中 → 加全局效率规则
    if any(ft.startswith("F8") for ft in error_dist.get("concentrated_types", [])):
        changes.append({
            "type": "add_business_rule",
            "rule_id": "global_step_count_limit",
            "description": "所有用例执行步数不得超过 expected_steps 的 1.5 倍",
            "applies_to": "all cases",
            "reason": "F8 集中说明缺少全局效率约束",
        })

    # F7.3 集中 → 加业务规则完整性规则
    if "F7.3" in error_dist.get("concentrated_types", []):
        changes.append({
            "type": "add_business_rule",
            "rule_id": "global_business_rule_completeness",
            "description": "所有用例的 business_rules.must_satisfy 必须可机器验证（trace_event_contains 或 final_answer_contains）",
            "applies_to": "all cases",
            "reason": "F7.3 集中说明业务规则断言不够强",
        })

    # 工具缺口 → 加工具覆盖规则
    tool_gaps = [g for g in spec_gaps if g["type"] == "tool_gap"]
    if tool_gaps:
        changes.append({
            "type": "add_coverage_rule",
            "rule_id": "tool_coverage_requirement",
            "description": f"以下工具必须有用例覆盖：{', '.join(g['tool'] for g in tool_gaps)}",
            "applies_to": "test suite",
            "reason": "工具覆盖率不足",
        })

    return changes


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def generate_proposal(
    cfg: C.EvalConfig,
    run_id: str,
    split: str,
    cases: list[dict],
    diagnosis: dict,
    scores: dict | None,
    req_dimensions: list[str] | None,
    trigger: str = "manual",
) -> dict[str, Any]:
    """生成完整优化建议。"""
    all_tools = CIO.extract_all_tools(cases)

    # Step 1: 错误分布
    error_dist = analyze_error_distribution(diagnosis)

    # Step 2: spec 缺口
    spec_gaps = identify_spec_gaps(cases, diagnosis, req_dimensions, all_tools)
    per_case_scores = (scores or {}).get("per_case", [])
    easy_dims = identify_easy_dimensions(cases, per_case_scores)
    spec_gaps.extend(easy_dims)

    # Step 3: 质量检查
    quality_result = run_quality_check(cfg, cases, req_dimensions, scores)

    # Step 4: mutation 分析
    mutation_result = run_mutation_analysis(cfg, cases, run_id)

    # Step 5: 生成建议
    add_cases = generate_add_cases(cases, error_dist, spec_gaps, mutation_result["survived_mutations"])
    modify_cases = generate_modify_cases(cases, quality_result, error_dist)
    deprecate_cases = generate_deprecate_cases(cases)
    spec_changes = generate_spec_changes(cases, error_dist, spec_gaps)

    # 质量分预估（apply 后）
    quality_before = quality_result["weighted_total"]
    # 粗估：每条 add +0.02，每条 modify +0.01，每条 deprecate +0.005
    quality_after_est = quality_before + len(add_cases) * 0.02 + len(modify_cases) * 0.01 + len(deprecate_cases) * 0.005
    quality_after_est = min(quality_after_est, 1.0)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    proposal_id = f"prop-{ts}-{split}"

    # 确定触发原因
    if not trigger or trigger == "manual":
        if error_dist["concentrated_types"]:
            trigger = "error_concentration"
        elif spec_gaps:
            trigger = "coverage_gap"
        else:
            trigger = "round_complete"

    return {
        "proposal_id": proposal_id,
        "run_id": run_id,
        "split": split,
        "generated_at": C.now_iso(),
        "trigger": trigger,
        "analysis": {
            "error_distribution": error_dist,
            "spec_gaps": spec_gaps,
            "quality_scores": {
                dim_id: {
                    "name": d["name"],
                    "score": d["score"],
                    "weight": d["weight"],
                }
                for dim_id, d in quality_result["dimensions"].items()
            },
            "quality_weighted_total": quality_result["weighted_total"],
            "quality_low_score_dimensions": quality_result["low_score_dimensions"],
            "mutation_kills": {
                "total_mutations": mutation_result["total_mutations"],
                "killed": mutation_result["killed"],
                "survived": mutation_result["survived"],
                "kill_rate": mutation_result["kill_rate"],
                "survived_mutations": mutation_result["survived_mutations"],
            },
        },
        "add_cases": add_cases,
        "modify_cases": modify_cases,
        "deprecate_cases": deprecate_cases,
        "spec_changes": spec_changes,
        "quality_before": {"weighted_total": quality_before},
        "quality_after_estimated": {"weighted_total": round(quality_after_est, 4)},
        "summary": _build_summary(
            error_dist, spec_gaps, quality_result, mutation_result,
            add_cases, modify_cases, deprecate_cases, spec_changes,
            quality_before, quality_after_est,
        ),
        # 附带完整质量 + mutation 结果（供报告用）
        "_full_quality": quality_result,
        "_full_mutation": mutation_result,
    }


def _build_summary(
    error_dist, spec_gaps, quality_result, mutation_result,
    add_cases, modify_cases, deprecate_cases, spec_changes,
    quality_before, quality_after_est,
) -> str:
    parts: list[str] = []
    if error_dist["concentrated_types"]:
        parts.append(f"检出错误集中：{', '.join(error_dist['concentrated_types'])}")
    if spec_gaps:
        parts.append(f"{len(spec_gaps)} 个 spec 缺口")
    parts.append(f"质量分 {quality_before:.3f}")
    parts.append(f"mutation 检出率 {mutation_result['kill_rate']:.1%}")
    parts.append(f"建议新增 {len(add_cases)}、修改 {len(modify_cases)}、废弃 {len(deprecate_cases)}、spec变更 {len(spec_changes)}")
    parts.append(f"预计质量分 {quality_before:.3f}→{quality_after_est:.3f}")
    return "；".join(parts) + "。"


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def apply_proposal_to_cases(
    cfg: C.EvalConfig,
    split: str,
    proposal: dict,
    non_interactive: bool = False,
) -> dict[str, Any]:
    """apply 建议到 cases YAML。"""
    cases = CIO.load_cases(cfg, split)

    # 备份
    backup = CIO.backup_cases(cfg, split)

    # apply
    new_cases, apply_summary = CIO.apply_proposal(cfg, split, cases, proposal)

    # 写回
    CIO.save_cases(cfg, split, new_cases)

    # 记录迭代
    iter_record = {
        "timestamp": C.now_iso(),
        "proposal_id": proposal["proposal_id"],
        "run_id": proposal["run_id"],
        "split": split,
        "accepted": True,
        "non_interactive": non_interactive,
        "quality_before": proposal.get("quality_before", {}),
        "quality_after_estimated": proposal.get("quality_after_estimated", {}),
        "apply_summary": apply_summary,
        "backup_file": str(backup) if backup else None,
    }
    CIO.log_iteration(cfg, iter_record)

    return apply_summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="用例自优化：错误分布+缺口+建议生成+apply")
    ap.add_argument("--config", required=True)
    ap.add_argument("--run")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--split", default="train")
    ap.add_argument("--apply", action="store_true", help="apply 建议到 cases YAML")
    ap.add_argument("--dry-run", action="store_true", help="只生成不 apply（默认）")
    ap.add_argument("--non-interactive", action="store_true", help="非交互模式，全部接受")
    ap.add_argument("--out", help="输出 proposal JSON 路径")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    C.ensure_dirs(cfg)

    import diagnoser as D
    run_id = args.run
    if args.latest or not run_id:
        run_id = D.find_latest_run(cfg)
        if not run_id:
            sys.stderr.write("[case_optimizer] 无历史 run，请先跑 eval_runner + diagnoser\n")
            return 2
        print(f"[case_optimizer] latest run_id={run_id}")

    # 加载诊断
    diag_path = cfg.reports_dir / f"{run_id}_diagnosis.json"
    if not diag_path.exists():
        sys.stderr.write(f"[case_optimizer] 诊断文件不存在: {diag_path}\n请先运行 diagnoser.py\n")
        return 2
    diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))

    # 加载 scores
    scores = None
    score_path = cfg.scores_dir / f"{run_id}.json"
    if score_path.exists():
        scores = json.loads(score_path.read_text(encoding="utf-8"))

    # 加载 cases
    cases = CIO.load_cases(cfg, args.split)

    # 加载 requirements 维度
    req_dims = CQC.load_req_dimensions(cfg)

    # 生成建议
    print(f"[case_optimizer] 生成优化建议（run={run_id}, split={args.split}）...")
    proposal = generate_proposal(cfg, run_id, args.split, cases, diagnosis, scores, req_dims)

    # 写 proposal JSON
    out_path = Path(args.out) if args.out else (CIO.data_dir(cfg) / f"{proposal['proposal_id']}.json")
    # 去掉内部字段
    proposal_clean = {k: v for k, v in proposal.items() if not k.startswith("_")}
    C.write_json(out_path, proposal_clean)
    print(f"[case_optimizer] 建议 JSON: {out_path}")

    # 也保存完整版（含 _full_quality/_full_mutation，供报告用）
    full_path = CIO.data_dir(cfg) / f"{proposal['proposal_id']}.full.json"
    C.write_json(full_path, proposal)

    # 打印摘要
    print(f"\n[case_optimizer] === 建议摘要 ===")
    print(f"触发: {proposal['trigger']}")
    print(f"错误集中: {proposal['analysis']['error_distribution']['concentrated_types'] or '无'}")
    print(f"spec 缺口: {len(proposal['analysis']['spec_gaps'])} 个")
    print(f"质量分: {proposal['quality_before']['weighted_total']:.3f} → {proposal['quality_after_estimated']['weighted_total']:.3f}")
    print(f"mutation 检出率: {proposal['analysis']['mutation_kills']['kill_rate']:.1%}")
    print(f"新增用例: {len(proposal['add_cases'])}")
    print(f"修改用例: {len(proposal['modify_cases'])}")
    print(f"废弃用例: {len(proposal['deprecate_cases'])}")
    print(f"spec 变更: {len(proposal['spec_changes'])}")
    print(f"摘要: {proposal['summary']}")

    # apply
    if args.apply:
        if not args.non_interactive:
            print("\n[case_optimizer] ⚠️ 即将 apply 建议到 cases YAML。")
            print(f"  新增 {len(proposal['add_cases'])} / 修改 {len(proposal['modify_cases'])} / 废弃 {len(proposal['deprecate_cases'])}")
            # 非交互模式无法真正问用户，这里默认 apply（CI 用 --non-interactive）
            print("[case_optimizer] 非交互环境默认 apply（加 --non-interactive 跳过此提示）")

        apply_summary = apply_proposal_to_cases(cfg, args.split, proposal, args.non_interactive)
        print(f"\n[case_optimizer] === apply 完成 ===")
        print(f"新增: {apply_summary['added']}")
        print(f"修改: {apply_summary['modified']}")
        print(f"废弃: {apply_summary['deprecated']}")
        if apply_summary.get("backup_file"):
            print(f"备份: {apply_summary['backup_file']}")
    else:
        print(f"\n[case_optimizer] dry-run 模式，未 apply。加 --apply 写入 cases YAML。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
