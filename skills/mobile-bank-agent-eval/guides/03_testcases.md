# Guide 03 — 测试用例生成

从需求分析 Excel 生成详细测试用例。

## 用例结构

每个用例包含：
- tc_id: TC-NNNN
- scenario_id: SC-XXX
- dimension_id: DIM-XXX
- title: 简短描述
- priority: 高/中/低
- precondition: 前置条件
- steps: 测试步骤
- user_input: 用户输入
- expected_result: 预期结果
- assertion_type: 断言类型

## 断言类型

| 类型 | 说明 | 适用 |
|------|------|------|
| exact_match | 完全匹配 | 固定答案 |
| contains | 包含关键词 | 大部分场景 |
| regex | 正则匹配 | 格式校验 |
| status_code | HTTP 200 | 接口测试 |
| llm_judge | LLM 判断 | 复杂语义 |

## 增强功能

- `--multi-turn`: 生成多轮对话用例
- `--dimensions DIM-001,DIM-002`: 指定维度
- `--per-scenario N`: 每场景用例数
