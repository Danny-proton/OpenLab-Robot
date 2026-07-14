#!/usr/bin/env python3
"""generate_requirements.py — 阶段1: 需求分析。

增强点（vs mobileAgentTest 原版）:
- 10 个测试维度（原版 6 个，新增多轮状态/异常恢复/性能延迟/合规监管）
- 支持 Gherkin 格式输出（原版只有 Excel）
- mock LLM fallback（无 API key 也能跑通）
- 维度粒度更细（每个维度 3-5 个场景，原版 2-3 个）
- 输出 UATR trace 事件

用法:
  python generate_requirements.py --description "需求文本" --output requirements.xlsx
  python generate_requirements.py --description "需求文本" --gherkin output.feature
  python generate_requirements.py --list requirements.xlsx
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
    ap = argparse.ArgumentParser(description="阶段1: 需求分析")
    ap.add_argument("--description", default="", help="需求描述文本（多行用 \\n 分隔）")
    ap.add_argument("--input", default="", help="输入文件路径（正向读文件，逆向读用例）")
    ap.add_argument("--output", default=None, help="输出 Excel 路径")
    ap.add_argument("--gherkin", default=None, help="输出 Gherkin .feature 文件路径")
    ap.add_argument("--reverse", action="store_true", help="逆向分析模式")
    ap.add_argument("--list", default=None, help="列出 Excel 中的维度")
    args = ap.parse_args()

    # --list 模式
    if args.list:
        _list_dimensions(args.list)
        return 0

    # 获取描述文本
    description = ""
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            description = f.read()
    elif args.description:
        description = args.description.replace("\\n", "\n")

    if not description and not args.reverse:
        print("[ERROR] 请提供 --description 或 --input", file=sys.stderr)
        return 1

    # 调 LLM（或 mock）
    if args.reverse:
        data = _reverse_analysis(args.input)
    else:
        data = _forward_analysis(description)

    # 写 Excel
    output_path = args.output or str(Path(__file__).parent.parent / "data" / "requirements_analysis.xlsx")
    _write_excel(data, output_path)

    # 写 Gherkin（可选）
    if args.gherkin:
        _write_gherkin(data, args.gherkin)

    # 输出结果
    dims = data.get("dimensions", [])
    scs = data.get("scenarios", [])
    print(f"[阶段 1/4] 需求分析完成")
    print(f"产出文件: {output_path}")
    print(f"")
    print(f"共 {len(dims)} 个测试维度，{len(scs)} 个测试场景：")
    for d in dims:
        print(f"  • {d.get('id','')} {d.get('name','')}（{d.get('type','')}）")
    print(f"")
    print(f"场景列表（前 5 个）:")
    for s in scs[:5]:
        print(f"  - {s.get('id','')} {s.get('name','')}: {s.get('description','')[:60]}")

    return 0


def _forward_analysis(description: str) -> dict:
    """正向分析：需求文本 → 测试维度 + 场景。"""
    system_prompt = """# Role: 资深智能体系统架构师与 QA 专家

## Profile
你精通智能体（Agent）系统的测试与设计，熟悉单 Agent 及多 Agent 协作架构。
你审视需求时，不把 Agent 视为简单的文本生成器，而是视其为一个具备"目标-感知-规划-记忆-执行"闭环的复杂动态系统。

## Task
请仔细阅读【Agent 需求说明】，找出其中隐藏的架构漏洞、死循环风险以及工程落地痛点，生成测试维度和场景。

## 10 个测试覆盖维度（必须覆盖）
1. 业务场景覆盖 — 按业务功能拆解用户典型场景
2. 业务流程覆盖 — 正常路径、替代路径、异常路径
3. 用户角色与意图覆盖 — 身份差异、意图多样性
4. 业务规则与约束覆盖 — if-then 逻辑、数值约束、合规要求
5. 输入形态与上下文覆盖 — 不完整信息、错别字、指代消解、多轮上下文
6. 安全与边界覆盖 — 敏感信息泄露、越权操作、提示注入
7. 多轮对话状态覆盖 — 上下文保持、状态迁移、指代消解
8. 异常恢复流程覆盖 — 超时、网络错误、数据异常后恢复
9. 性能与延迟边界覆盖 — 大数据量、高并发、延迟容忍
10. 合规与监管覆盖 — 适当性管理、禁止刚性兑付、信息披露

## 输出要求
- 每个维度至少 3-5 个具体场景
- 场景描述要具体，体现前置条件或触发条件
- 严格 JSON 格式，不要 markdown 标记"""

    user_prompt = f"""请基于以下需求描述，生成 10 个测试维度和对应的测试场景。

需求描述：
{description}

请按以下 JSON 格式输出（只输出 JSON）：
{{
  "dimensions": [
    {{"id": "DIM-001", "name": "维度名称", "type": "覆盖类型"}}
  ],
  "scenarios": [
    {{"id": "SC-001", "dimension": "DIM-001", "name": "子场景", "description": "描述"}}
  ],
  "skill_suggestions": [
    {{"dimension_id": "DIM-001", "dimension_name": "维度名称", "skill": "所属Skill", "reason": "理由"}}
  ]
}}"""

    raw = C.call_llm(system_prompt, user_prompt)
    return C.extract_json(raw)


def _reverse_analysis(input_file: str) -> dict:
    """逆向分析：从测试用例反推维度。"""
    with open(input_file, "r", encoding="utf-8") as f:
        test_cases = f.read()

    system_prompt = "你是需求分析工程师，从已有测试用例逆向分析测试维度。严格 JSON 输出。"
    user_prompt = f"""请对以下测试用例进行逆向分析：

{test_cases[:8000]}

输出 JSON 格式：
{{
  "dimensions": [{{"id": "DIM-001", "name": "维度名", "type": "类型"}}],
  "scenarios": [{{"id": "SC-001", "dimension": "DIM-001", "name": "场景", "description": "描述"}}]
}}"""

    raw = C.call_llm(system_prompt, user_prompt)
    return C.extract_json(raw)


def _write_excel(data: dict, path: str) -> None:
    """写 Excel：3 个 sheet（维度/场景/Skill建议）。"""
    sheets = [
        ("测试维度", [["维度ID", "维度名称", "覆盖类型"]] +
         [[d.get("id",""), d.get("name",""), d.get("type","")] for d in data.get("dimensions",[])]),
        ("测试场景", [["场景ID", "所属维度", "子场景", "描述"]] +
         [[s.get("id",""), s.get("dimension",""), s.get("name",""), s.get("description","")] for s in data.get("scenarios",[])]),
    ]
    suggestions = data.get("skill_suggestions", [])
    if suggestions:
        sheets.append(("Skill归属建议", [["维度ID", "维度名称", "归属Skill", "说明"]] +
                      [[s.get("dimension_id",""), s.get("dimension_name",""), s.get("skill",""), s.get("reason","")] for s in suggestions]))

    C.write_excel({}, path, sheets=sheets)


def _write_gherkin(data: dict, path: str) -> None:
    """写 Gherkin .feature 文件。"""
    lines = ["Feature: 手机银行 Agent 测试\n"]
    for dim in data.get("dimensions", []):
        lines.append(f"  # {dim.get('id','')} {dim.get('name','')}（{dim.get('type','')}）")
        dim_scenarios = [s for s in data.get("scenarios", []) if s.get("dimension") == dim.get("id")]
        for sc in dim_scenarios:
            lines.append(f"  Scenario: {sc.get('name','')}")
            lines.append(f"    # {sc.get('description','')}")
            lines.append(f"    Given 用户已登录手机银行")
            lines.append(f"    When 用户发起 \"{sc.get('name','')}\" 请求")
            lines.append(f"    Then Agent 应正确响应")
            lines.append("")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def _list_dimensions(path: str) -> None:
    """列出 Excel 中的维度。"""
    if not Path(path).exists():
        print(f"[ERROR] 文件不存在: {path}", file=sys.stderr)
        return
    data = C.read_excel(path)
    dims = data.get("测试维度", [])
    print(f"测试维度列表（{len(dims)} 个）:")
    for d in dims:
        print(f"  {d.get('维度ID','')} - {d.get('维度名称','')}（{d.get('覆盖类型','')}）")
    print()
    scs = data.get("测试场景", [])
    print(f"测试场景列表（{len(scs)} 个）:")
    for s in scs:
        print(f"  {s.get('场景ID','')} [{s.get('所属维度','')}] {s.get('子场景','')}")


if __name__ == "__main__":
    sys.exit(main())
