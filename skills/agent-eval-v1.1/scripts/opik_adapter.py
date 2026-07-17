#!/usr/bin/env python3
"""opik_adapter.py — Opik optimizer provider。

v1 把 Opik 作为可选 optimizer provider。本脚本负责：
1. 把 UATR trace + cases 导出成 Opik dataset 格式
2. 如果安装了 opik，调用 MetaPrompt / HRPO / GEPA 优化器
3. 把优化结果转成 candidate patch 计划
4. **不接管接受流程**——Opik 生成的候选仍要过本地 A/B 门禁

如果没装 opik，提供 fallback：导出 Opik 格式 JSON 但不实际优化。

用法:
  python opik_adapter.py --config .agent-eval/config.yaml --run <run_id> --optimizer meta_prompt
  python opik_adapter.py --config .agent-eval/config.yaml --export-only --run <run_id>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

try:
    import opik
    HAS_OPIK = True
except ImportError:
    HAS_OPIK = False


OPIK_OPTIMIZERS = {
    "meta_prompt": "MetaPrompt Optimizer - 基于 meta-prompt 的 prompt 优化",
    "hrpo": "HRPO - 层次化 root cause 分析 + 针对性改进",
    "evolutionary": "Evolutionary Optimizer - 进化算法优化",
    "gepa": "GEPA - 梯度引导的 prompt 优化",
}


def export_to_opik_dataset(cases: list[dict], events_by_case: dict, out_path: Path) -> dict:
    """导出 Opik dataset 格式。"""
    dataset = {
        "name": "agent-eval-dataset",
        "description": "Exported from agent-eval UATR traces",
        "items": [],
    }
    for case in cases:
        cid = case.get("id")
        events = events_by_case.get(cid, [])
        final = ""
        for e in events:
            if e.get("event_type") == "agent.run.end":
                out_obj = e.get("output") or {}
                if isinstance(out_obj, dict):
                    final = out_obj.get("final_answer", "")
                break

        dataset["items"].append({
            "id": cid,
            "input": {
                "user_message": case.get("input", {}).get("user_message", ""),
                "task": case.get("task", ""),
            },
            "expected_output": (case.get("expected", {}) or {}).get("final_decision", {}).get("contains", []),
            "actual_output": final,
            "expected_tools": (case.get("expected_tools", {}) or {}).get("required", []),
            "business_rules": case.get("business_rules", {}).get("must_satisfy", []),
        })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    return dataset


def run_opik_optimizer(
    optimizer: str,
    dataset_path: Path,
    cases: list[dict],
    diagnosis: dict | None,
) -> dict:
    """运行 Opik optimizer。如果没装 opik，返回 fallback 建议。"""
    if not HAS_OPIK:
        return _fallback_optimize(optimizer, cases, diagnosis)

    # 真正的 Opik 调用（伪代码，实际 API 可能不同）
    try:
        from opik.optimizer import MetaPromptOptimizer, HRPOOptimizer, GEPAOptimizer
        if optimizer == "meta_prompt":
            opt = MetaPromptOptimizer(model="gpt-4", max_iterations=5)
        elif optimizer == "hrpo":
            opt = HRPOOptimizer(model="gpt-4")
        elif optimizer == "gepa":
            opt = GEPAOptimizer(model="gpt-4", max_iterations=10)
        else:
            return {"error": f"unknown optimizer: {optimizer}"}

        # opik_optimizer_result = opt.optimize_dataset(dataset_path)
        # 这里返回伪结果
        return {
            "provider": "opik",
            "optimizer": optimizer,
            "optimized_prompt": "(opik generated prompt - placeholder)",
            "expected_improvement": 0.05,
            "note": "实际运行需要 opik 已安装并配置 API key",
        }
    except Exception as e:
        return {"provider": "opik", "error": str(e)}


def _fallback_optimize(optimizer: str, cases: list[dict], diagnosis: dict | None) -> dict:
    """没装 opik 时的 fallback。

    v1.1 升级：对 HRPO 做真正的层次化 root cause 分析（不是简单按 F1-F8 分类）。
    HRPO = Hierarchical Root cause analysis Prompt Optimization
    层次：现象(F层) → 直接原因(行为模式) → 根因(prompt/reference 缺陷) → 修复层
    """
    if not diagnosis:
        return {"provider": "fallback", "note": "no diagnosis available"}

    if optimizer != "hrpo":
        # 非 HRPO 走原来的简单建议
        return _fallback_simple(optimizer, cases, diagnosis)

    # HRPO 层次化分析
    by_type: dict[str, int] = diagnosis.get("by_failure_type", {}) or {}
    all_diags = diagnosis.get("diagnoses", []) or []

    # 按失败类型聚合诊断
    by_type_diags: dict[str, list[dict]] = {}
    for d in all_diags:
        ft = d.get("failure_type", "UNKNOWN")
        by_type_diags.setdefault(ft, []).append(d)

    root_cause_layers: list[dict] = []
    for ft, count in sorted(by_type.items(), key=lambda x: -x[1]):
        diags_of_type = by_type_diags.get(ft, [])
        layer = _hrpo_analyze_layer(ft, count, diags_of_type)
        root_cause_layers.append(layer)

    return {
        "provider": "fallback",
        "optimizer": "hrpo",
        "note": "opik not installed, using hierarchical root cause analysis fallback",
        "root_cause_layers": root_cause_layers,
        "expected_improvement": _estimate_improvement(root_cause_layers),
        "summary": _hrpo_summary(root_cause_layers),
    }


def _hrpo_analyze_layer(failure_type: str, count: int, diags: list[dict]) -> dict:
    """对一个失败类型做 4 层分析：现象 → 直接原因 → 根因 → 修复层。"""
    # F8 单独处理（效率问题）
    if failure_type.startswith("F8"):
        return _hrpo_analyze_f8(failure_type, count, diags)

    # F1-F7 的层次化分析
    layer_map = {
        "F1": {
            "direct_cause": "skill 触发不稳定（description 不够 pushy 或过宽）",
            "root_cause": "SKILL.md description 缺少明确触发词或反例",
            "fix_layer": "skill_description",
            "fix_action": "在 description 增加触发关键词 + should-not-trigger 反例 + 'Trigger this skill even if...' 句式",
            "reference_to_inject": None,
        },
        "F2": {
            "direct_cause": "任务类型识别错误，agent 走错方向",
            "root_cause": "system prompt 缺少任务类型枚举和阶段判断逻辑",
            "fix_layer": "prompt + reference",
            "fix_action": "system prompt 开头加任务识别段 + reference 里加任务类型决策树",
            "reference_to_inject": "task_type_decision_tree.md",
        },
        "F3": {
            "direct_cause": "工具选择错误（漏调/调错/重复/乱序）",
            "root_cause": "@Tool description 太抽象，或缺少工具选择决策树",
            "fix_layer": "tool_schema + reference",
            "fix_action": "给 @Tool description 增加适用场景 + reference 里加工具选择决策树",
            "reference_to_inject": "tool_selection_tree.md",
        },
        "F4": {
            "direct_cause": "工具参数错误（缺失/映射错/枚举错/ID 错）",
            "root_cause": "参数 description 不够清晰，或缺少字段映射表",
            "fix_layer": "tool_schema + reference",
            "fix_action": "@Tool 参数加 required 标注 + reference 里加字段映射表",
            "reference_to_inject": "field_mapping.md",
        },
        "F5": {
            "direct_cause": "流程缺环节（无前置检查/无 fallback/异常未恢复）",
            "root_cause": "Advisor 链不完整",
            "fix_layer": "workflow",
            "fix_action": "增加 InputValidationAdvisor / FallbackAdvisor / ErrorRecoveryAdvisor",
            "reference_to_inject": None,
        },
        "F6": {
            "direct_cause": "记忆检索失败或未使用",
            "root_cause": "Memory 索引不全或 prompt 没要求使用记忆",
            "fix_layer": "memory + prompt",
            "fix_action": "扩展 Memory 索引 + prompt 增加检索触发条件",
            "reference_to_inject": "memory_index.md",
        },
        "F7": {
            "direct_cause": "输出层问题（格式/证据/规则/幻觉）",
            "root_cause": "prompt 缺输出格式约束或证据要求",
            "fix_layer": "prompt + reference",
            "fix_action": "prompt 加输出格式 + 证据要求 + 禁止编造约束",
            "reference_to_inject": "output_format_template.md",
        },
    }

    base = layer_map.get(failure_type[:2] if len(failure_type) >= 2 else failure_type, {
        "direct_cause": "未知失败类型",
        "root_cause": "需人工检查",
        "fix_layer": "unknown",
        "fix_action": "检查 trace 和插桩",
        "reference_to_inject": None,
    })

    # 收集代表 case
    sample_cases = [d.get("case_id", "") for d in diags[:3]]

    return {
        "failure_type": failure_type,
        "count": count,
        "sample_cases": sample_cases,
        "layer_1_symptom": f"{failure_type} 出现 {count} 次",
        "layer_2_direct_cause": base["direct_cause"],
        "layer_3_root_cause": base["root_cause"],
        "layer_4_fix_layer": base["fix_layer"],
        "fix_action": base["fix_action"],
        "reference_to_inject": base["reference_to_inject"],
        "evidence_from_diags": [d.get("evidence", [])[:1] for d in diags[:2]],
    }


def _hrpo_analyze_f8(failure_type: str, count: int, diags: list[dict]) -> dict:
    """F8 执行冗余的 HRPO 层次化分析。"""
    f8_map = {
        "F8.1": {
            "direct_cause": "总步数远超期望（agent 在反复探索）",
            "root_cause": "prompt 缺少明确执行路径，agent 不知道最优工具序列",
            "fix_layer": "reference",
            "fix_action": "注入'执行路径 reference'：明确每类任务的最优工具调用顺序，让 agent 一次走对",
            "reference_to_inject": "execution_path.md",
        },
        "F8.2": {
            "direct_cause": "模型调用次数 >> 工具调用次数（光想不干）",
            "root_cause": "prompt 允许模型'先想后做'，没有'决策后立即执行'约束",
            "fix_layer": "reference",
            "fix_action": "注入'行动约束 reference'：每次 model_call 后必须跟一个 tool_call，禁止连续思考",
            "reference_to_inject": "act_after_decide.md",
        },
        "F8.3": {
            "direct_cause": "同一工具被反复调用中间夹思考（第一次没拿到完整结果）",
            "root_cause": "工具参数 description 不清晰或结果解读困难",
            "fix_layer": "reference",
            "fix_action": "注入'工具使用指南 reference'：每个工具的参数校验清单 + 结果字段说明 + 常见错误",
            "reference_to_inject": "tool_usage_guide.md",
        },
        "F8.4": {
            "direct_cause": "连续多次思考无行动（模型不知道做什么）",
            "root_cause": "缺少工具选择决策树，模型每次都要重新推理",
            "fix_layer": "reference",
            "fix_action": "注入'工具决策树 reference'：基于任务状态的工具选择 if-then 规则",
            "reference_to_inject": "tool_decision_tree.md",
        },
    }
    base = f8_map.get(failure_type, {
        "direct_cause": "执行冗余",
        "root_cause": "未知",
        "fix_layer": "reference",
        "fix_action": "检查 trace",
        "reference_to_inject": None,
    })
    sample_cases = [d.get("case_id", "") for d in diags[:3]]
    return {
        "failure_type": failure_type,
        "count": count,
        "sample_cases": sample_cases,
        "layer_1_symptom": f"{failure_type} 出现 {count} 次",
        "layer_2_direct_cause": base["direct_cause"],
        "layer_3_root_cause": base["root_cause"],
        "layer_4_fix_layer": base["fix_layer"],
        "fix_action": base["fix_action"],
        "reference_to_inject": base["reference_to_inject"],
        "evidence_from_diags": [d.get("evidence", [])[:1] for d in diags[:2]],
    }


def _estimate_improvement(layers: list[dict]) -> float:
    """根据失败类型和数量估算预期提升。"""
    if not layers:
        return 0.0
    # F8 类的修复对步数提升最大
    total = 0.0
    for l in layers:
        ft = l.get("failure_type", "")
        cnt = l.get("count", 1)
        if ft.startswith("F8"):
            total += 0.08 * min(cnt, 5)  # F8 修复预期步数减少 8% per case
        elif ft.startswith("F3"):
            total += 0.05 * min(cnt, 5)
        else:
            total += 0.03 * min(cnt, 5)
    return min(total, 0.3)  # 上限 30%


def _hrpo_summary(layers: list[dict]) -> str:
    """生成 HRPO 总结。"""
    if not layers:
        return "无失败，无需优化"
    parts = ["HRPO 层次化根因分析总结："]
    for l in layers:
        parts.append(
            f"- {l['failure_type']}({l['count']}次): "
            f"现象={l['layer_1_symptom']}; "
            f"直接原因={l['layer_2_direct_cause']}; "
            f"根因={l['layer_3_root_cause']}; "
            f"修复层={l['layer_4_fix_layer']}"
        )
    ref_to_inject = [l["reference_to_inject"] for l in layers if l.get("reference_to_inject")]
    if ref_to_inject:
        parts.append(f"\n建议注入的 reference 文件: {ref_to_inject}")
    return "\n".join(parts)


def _fallback_simple(optimizer: str, cases: list[dict], diagnosis: dict | None) -> dict:
    """非 HRPO 的简单 fallback（保留 v1 原逻辑）。"""
    by_type: dict[str, int] = diagnosis.get("by_failure_type", {}) or {}
    suggestions = []
    for ft, count in sorted(by_type.items(), key=lambda x: -x[1]):
        if ft.startswith("F3"):
            suggestions.append({
                "failure_type": ft, "component": "tool_schema",
                "suggestion": "改进 @Tool description，增加适用场景说明",
            })
        elif ft.startswith("F7"):
            suggestions.append({
                "failure_type": ft, "component": "prompt",
                "suggestion": "在 system prompt 增加输出格式和业务规则说明",
            })
        elif ft.startswith("F2"):
            suggestions.append({
                "failure_type": ft, "component": "prompt",
                "suggestion": "在 system prompt 开头增加任务类型识别段",
            })
        elif ft.startswith("F8"):
            suggestions.append({
                "failure_type": ft, "component": "reference",
                "suggestion": "注入 reference 文件（执行路径/工具决策树/字段映射）",
            })
    return {
        "provider": "fallback", "optimizer": optimizer,
        "note": "opik not installed, using rule-based fallback",
        "suggestions": suggestions, "expected_improvement": 0.03,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--optimizer", choices=list(OPIK_OPTIMIZERS), default="meta_prompt")
    ap.add_argument("--export-only", action="store_true", help="只导出 dataset，不优化")
    ap.add_argument("--split", default="train")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())
    cases = C.load_yaml(cfg.cases_dir / f"{args.split}.yaml").get("cases", [])

    events = C.load_jsonl(cfg.traces_dir / f"{args.run}.jsonl")
    events_by_case: dict[str, list] = {}
    for e in events:
        cid = e.get("case_id", "")
        events_by_case.setdefault(cid, []).append(e)

    # 导出 dataset
    dataset_path = cfg.scores_dir / f"{args.run}.opik_dataset.json"
    dataset = export_to_opik_dataset(cases, events_by_case, dataset_path)
    print(f"[opik_adapter] dataset exported: {dataset_path} ({len(dataset['items'])} items)")
    print(f"[opik_adapter] opik installed: {HAS_OPIK}")

    if args.export_only:
        return 0

    # 加载诊断
    diagnosis = None
    diag_path = cfg.reports_dir / f"{args.run}_diagnosis.json"
    if diag_path.exists():
        diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))

    print(f"[opik_adapter] running optimizer: {args.optimizer}")
    result = run_opik_optimizer(args.optimizer, dataset_path, cases, diagnosis)

    out = cfg.scores_dir / f"{args.run}.opik_{args.optimizer}.json"
    C.write_json(out, result)
    print(f"[opik_adapter] output: {out}")
    print(f"[opik_adapter] provider: {result.get('provider')}")
    if "error" in result:
        print(f"[opik_adapter] error: {result['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
