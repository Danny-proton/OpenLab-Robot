---
name: test-case-generator
description: "用例生成子 skill（阶段 2）。根据需求分析 Excel 中的维度和场景，生成详细可执行的测试用例。本子 skill 内含完整 prompt 文字，指示 Agent 用 Task 工具并行生成结构化 JSON，再调 generate_testcases.py 写成 Excel。脚本不调任何外部 LLM。"
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Edit, Task, AskUserQuestion
---

# 测试用例生成子 skill（阶段 2 / 4）

> **架构定位**：这是"大 skill 套小 skill 套 script"结构里的**小 skill** 层。
> prompt 拼装在本文件里用文字呈现，由 Agent（你，Claude）自己读、自己想、自己生成 JSON；
> 场景多时**调用 Task 工具**把生成工作分批并行委派给子 agent；
> 最后调 `generate_testcases.py` 这个**机械脚本**把 JSON 写成 Excel。
> 脚本零 LLM 调用，与任何外部模型 URL / API key 完全解耦。

## 你的输入

- `data/requirements_analysis.xlsx`（阶段 1 产出，含测试维度 / 测试场景 / Skill 归属建议）
- 用户选择的 `per_scenario`（每个场景生成几条用例，默认 3）
- 用户选择的 `dimensions`（全部维度，或指定 DIM-001,DIM-002 子集）

## 你的输出

- `data/test_cases.xlsx`（用例 ID / 场景引用 / 维度 ID / 标题 / 优先级 / 前置条件 / 测试步骤 / 用户输入 / 预期结果 / 断言类型 / 状态）
- stdout 输出 JSON 摘要（供下一阶段消费）

## 第 1 步：读取维度和场景

先列出维度，让用户决定生成范围：

```bash
python ${SKILL_PATH}/scripts/generate_testcases.py --list --input ${SKILL_PATH}/data/requirements_analysis.xlsx
```

用 `AskUserQuestion` 问用户：
- 每个场景生成几条用例？（默认 3）
- 全部维度还是指定维度？（指定则给 DIM-001,DIM-002 形式）

然后读场景 JSON（这一步把场景喂给 Task 子 agent）：

```bash
python ${SKILL_PATH}/scripts/generate_testcases.py --read-scenarios \
  --input ${SKILL_PATH}/data/requirements_analysis.xlsx \
  [--dimensions DIM-001,DIM-002] > /tmp/scenarios.json
```

`/tmp/scenarios.json` 形如 `{"scenarios": [{...}, ...]}`，把它作为生成 prompt 的输入。

## 第 2 步：用 Task 工具委派生成

**场景数 ≤ 10**：一次 Task 调用生成全部。
**场景数 > 10**：按 10 个一批切分，**并行**发起多个 Task 调用（在一条消息里放多个 Task tool_use 块），最后合并。

调用 `Task` 工具，`subagent_type` 用 `general-purpose`，`prompt` 字段填入下面【生成 prompt】整段（把 `{{SCENARIOS_JSON}}` 替换为读到的场景 JSON，`{{PER_SCENARIO}}` 替换为数字）：

---

### 【生成 prompt】—— 传给 Task 子 agent

```
你是一位智能体（Agent）高级评测工程师，也是一位资深的高级软件测试工程师。

你专注于 Agent 系统的质量保障。你熟练掌握 ReAct、CoT（思维链）等 Agent 交互模式。你设计的用例旨在验证 Agent 在动态环境下的决策准确性、工具调用率以及任务最终达成率，也精通边界值分析法、等价类划分法、状态迁移法及各类黑盒测试技巧。你不仅能设计常规功能用例，还能设计深度的异常、边界和安全用例。

请根据我提供的测试维度和测试场景，设计一套针对 Agent 智能体功能的测试用例。

【测试场景列表】（JSON）：
{{SCENARIOS_JSON}}

【每个场景生成用例数】：{{PER_SCENARIO}}

每个测试用例必须包含：
- tc_id: 用例 ID（TC-NNNN，全局唯一，从 TC-0001 递增）
- scenario_id: 场景引用（SC-XXX，必须是上面列表里存在的 id）
- dimension_id: 维度 ID（从 scenario 反查，若场景 JSON 里有就用，没有则留空）
- title: 标题（简短描述，≤20 字）
- priority: 优先级（高 / 中 / 低）
- preconditions: 前置条件（执行前的系统状态，可空）
- steps: 测试步骤（编号列表，数组，每条一个字符串）
- user_input: 用户输入（直接发给 Agent 的文本，可包含变量占位符 {{var}}）
- expected: 预期结果（可验证的断言描述）
- assertion_type: 断言类型（contains / exact / regex / schema / status_code / tool_called / business_rule）

设计原则：
- 原子性：每个用例验证一个行为
- 确定性：步骤无歧义
- 自包含：数据内联，不依赖外部文件
- 可追溯性：链接回场景 ID
- 覆盖度：每个场景的 N 条用例应覆盖正常路径 / 异常路径 / 边界
- DFX 覆盖：在适当场景下加入性能、安全、韧性用例

请严格按以下 JSON 格式输出（只输出 JSON，不要 markdown 标记，不要解释）：
{
  "test_cases": [
    {
      "scenario_id": "SC-001",
      "tc_id": "TC-0001",
      "dimension_id": "DIM-001",
      "title": "标题",
      "priority": "高",
      "preconditions": "前置条件",
      "steps": ["步骤1", "步骤2"],
      "user_input": "用户输入文本",
      "expected": "预期结果",
      "assertion_type": "contains"
    }
  ]
}
```

---

## 第 3 步：合并并校验多个 Task 返回

如果有多个并行 Task 调用，合并所有 `test_cases` 数组，然后：

1. 剥离每个返回里的 markdown 代码块
2. `json.loads` 解析，失败则让该批 Task 子 agent 重生成（最多 2 次）
3. **tc_id 全局唯一性校验**：合并后若有重复，按出现顺序重新编号 TC-0001, TC-0002, ...
4. **scenario_id 存在性校验**：每个 tc.scenario_id 必须在第 1 步读到的 scenarios 列表里
5. **必填字段校验**：tc_id / scenario_id / title / user_input / expected 非空

## 第 4 步：调机械脚本写 Excel

把校验通过的合并 JSON 通过 stdin 传给脚本：

```bash
cat <<'EOF' | python ${SKILL_PATH}/scripts/generate_testcases.py --write-stdin \
  --input ${SKILL_PATH}/data/requirements_analysis.xlsx \
  --output ${SKILL_PATH}/data/test_cases.xlsx
{"test_cases": [ ...合并后的全部用例... ]}
EOF
```

脚本 stdout 输出 JSON 摘要（含 test_cases_count / by_priority / by_scenario），展示给用户。

## 第 5 步：用例质量自检（可选，接入 agent-eval 能力）

如果用户开启了质量自检（默认开），用 Task 工具 spawn 一个 QA 子 agent，按 `docs/PRD_TEST_DESIGN.md` 的 9 维度检查：

| 维度 | 权重 |
|------|------|
| SPEC完整性 | 0.15 |
| 用例完整性 | 0.10 |
| 功能点覆盖度 | 0.15 |
| DFX覆盖度 | 0.15 |
| 有效用例率 | 0.10 |
| 执行可行性 | 0.10 |
| 无二义性 | 0.10 |
| 长度合理 | 0.05 |
| 断言可验证 | 0.10 |

QA 子 agent 输出加权总分和缺陷清单。总分 < 0.7 则回到第 2 步重生成（最多 2 轮迭代）。

## 与下一阶段的衔接

本阶段产出 `test_cases.xlsx`，是阶段 3（执行）的输入。每个用例的 `user_input` 会被 `execute_testcases.py` 替换到 HTTP body 模板的 `{{用户输入}}` 占位符里。

## 重要约束

- ❌ 本子 skill 不许调任何外部 LLM API
- ❌ 不许在脚本里拼 prompt
- ✅ prompt 在本文件里以文字呈现
- ✅ 生成工作由 Agent 自己做，或用 Task 工具并行委派
- ✅ 脚本只做 JSON → Excel 的机械写入 + list + read-scenarios
- ✅ 场景多时必须分批并行（一条消息多个 Task tool_use），避免主上下文爆炸
