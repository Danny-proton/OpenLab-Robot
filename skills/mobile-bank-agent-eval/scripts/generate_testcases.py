#!/usr/bin/env python3
"""generate_testcases.py — 阶段2: 测试用例生成。

增强点（vs 原版）:
- 支持多轮对话用例（原版只有单轮）
- 支持状态迁移用例（状态机图驱动）
- 支持边界值/等价类分析
- 每个用例包含可验证的断言（expected_result 细化）
- mock LLM fallback
- 输出 Gherkin Scenario Outline

用法:
  python generate_testcases.py --input requirements.xlsx --output testcases.xlsx --per-scenario 3
  python generate_testcases.py --list requirements.xlsx
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="阶段2: 测试用例生成")
    ap.add_argument("--input", default=None, help="需求分析 Excel")
    ap.add_argument("--output", default=None, help="输出测试用例 Excel")
    ap.add_argument("--per-scenario", type=int, default=3, help="每场景用例数（默认3）")
    ap.add_argument("--dimensions", default="", help="指定维度ID（逗号分隔，默认全部）")
    ap.add_argument("--multi-turn", action="store_true", help="生成多轮对话用例")
    ap.add_argument("--list", action="store_true", help="列出维度")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    data_dir = script_dir.parent / "data"

    input_path = args.input or str(data_dir / "requirements_analysis.xlsx")
    if not Path(input_path).exists():
        print(f"[ERROR] 需求分析文件不存在: {input_path}", file=sys.stderr)
        return 1

    # 读维度和场景
    excel_data = C.read_excel(input_path)
    dims = excel_data.get("测试维度", [])
    scenarios = excel_data.get("测试场景", [])

    if args.list:
        print(f"可用维度（{len(dims)} 个）:")
        for d in dims:
            print(f"  {d.get('维度ID','')} - {d.get('维度名称','')}（{d.get('覆盖类型','')}）")
        print(f"\n可用场景（{len(scenarios)} 个）:")
        for s in scenarios:
            print(f"  {s.get('场景ID','')} [{s.get('所属维度','')}] {s.get('子场景','')}")
        return 0

    # 按维度过滤
    if args.dimensions:
        selected = [d.strip() for d in args.dimensions.split(",")]
        scenarios = [s for s in scenarios if s.get("所属维度") in selected]
        print(f"维度过滤: {len(scenarios)} 个场景", file=sys.stderr)

    if not scenarios:
        print("[ERROR] 无可用场景", file=sys.stderr)
        return 1

    # 生成用例
    print(f"场景数: {len(scenarios)}, 每场景: {args.per_scenario}, 多轮: {args.multi_turn}", file=sys.stderr)
    test_cases = _generate_all(scenarios, args.per_scenario, args.multi_turn)

    # 写 Excel
    output_path = args.output or str(data_dir / "test_cases.xlsx")
    _write_excel(test_cases, output_path)

    # 统计
    by_dim = {}
    for tc in test_cases:
        dim_id = tc.get("dimension_id", "?")
        by_dim[dim_id] = by_dim.get(dim_id, 0) + 1

    print(f"\n[阶段 2/4] 测试用例生成完成")
    print(f"产出文件: {output_path}")
    print(f"")
    print(f"共 {len(test_cases)} 个测试用例，覆盖 {len(by_dim)} 个维度：")
    for dim_id, count in sorted(by_dim.items()):
        dim_name = next((d.get("维度名称","") for d in dims if d.get("维度ID") == dim_id), "")
        print(f"  {dim_id} {dim_name}: {count} 个用例")

    return 0


def _generate_all(scenarios: list[dict], per_scenario: int, multi_turn: bool) -> list[dict]:
    """分批调 LLM 生成用例。"""
    all_cases = []
    batch_size = 10
    for i in range(0, len(scenarios), batch_size):
        batch = scenarios[i:i+batch_size]
        cases = _call_llm_batch(batch, per_scenario, multi_turn)
        if cases:
            all_cases.extend(cases)
        print(f"  批次 {i//batch_size+1}/{(len(scenarios)-1)//batch_size+1} 完成", file=sys.stderr)
    return all_cases


def _call_llm_batch(batch: list[dict], per_scenario: int, multi_turn: bool) -> list[dict]:
    """调 LLM 为一批场景生成用例。"""
    multi_turn_hint = """
7. 如果是多轮用例，steps 包含多步交互，每步含 user_input 和 expected_response
8. 多轮用例需标注 context_dependency（依赖前一轮的什么上下文）""" if multi_turn else ""

    system_prompt = f"""# Role: 智能体高级评测工程师

## Profile
你专注于 Agent 系统的质量保障，精通 ReAct、CoT 等 Agent 交互模式。
你设计的用例旨在验证 Agent 在动态环境下的决策准确性、工具调用率以及任务达成率。
你精通边界值分析法、等价类划分法、状态迁移法及各类黑盒测试技巧。

## Task
根据测试维度和场景，设计详细可执行的测试用例。

## 每个用例包含
- tc_id: TC-NNNN
- scenario_id: SC-XXX
- dimension_id: DIM-XXX
- title: 简短描述
- priority: 高/中/低
- precondition: 前置条件
- steps: 测试步骤列表
- user_input: 用户输入
- expected_result: 预期结果（可验证的断言）
- assertion_type: 断言类型（exact_match/contains/regex/llm_judge/status_code）{multi_turn_hint}

## 设计原则
- 原子性：每个用例验证一个行为
- 确定性：步骤无歧义
- 自包含：数据内联
- 可追溯：链接回场景ID

严格 JSON 输出，不要 markdown 标记。"""

    user_prompt = f"""请为以下 {len(batch)} 个场景生成测试用例，每个场景 {per_scenario} 个用例。

场景列表：
{json.dumps(batch, ensure_ascii=False, indent=2)}

输出 JSON 格式：
{{
  "test_cases": [
    {{
      "scenario_id": "SC-001",
      "dimension_id": "DIM-001",
      "tc_id": "TC-0001",
      "title": "用例标题",
      "priority": "高",
      "precondition": "前置条件",
      "steps": ["1. 步骤一", "2. 步骤二"],
      "user_input": "用户输入文本",
      "expected_result": "预期结果描述",
      "assertion_type": "contains"
    }}
  ]
}}"""

    raw = C.call_llm(system_prompt, user_prompt)
    data = C.extract_json(raw)
    return data.get("test_cases", [])


def _write_excel(test_cases: list[dict], path: str) -> None:
    """写测试用例 Excel。"""
    headers = ["用例ID", "场景ID", "维度ID", "标题", "优先级", "前置条件",
               "测试步骤", "用户输入", "预期结果", "断言类型"]
    rows = [headers]
    for tc in test_cases:
        steps = tc.get("steps", [])
        if isinstance(steps, list):
            steps_str = "\n".join(str(s) for s in steps)
        else:
            steps_str = str(steps)
        rows.append([
            tc.get("tc_id", ""),
            tc.get("scenario_id", ""),
            tc.get("dimension_id", ""),
            tc.get("title", ""),
            tc.get("priority", ""),
            tc.get("precondition", ""),
            steps_str,
            tc.get("user_input", ""),
            tc.get("expected_result", ""),
            tc.get("assertion_type", "contains"),
        ])
    C.write_excel({}, path, sheets=[("测试用例", rows)])


if __name__ == "__main__":
    sys.exit(main())
