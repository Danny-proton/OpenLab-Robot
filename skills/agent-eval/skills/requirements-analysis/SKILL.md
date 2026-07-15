---
name: requirements-analysis
description: "需求分析子 skill（阶段 1）。把需求文本拆成测试维度和场景。本子 skill 内含完整 prompt 文字，指示 Agent 用 Task 工具生成结构化 JSON，再调 generate_requirements.py 写成 Excel。脚本不调任何外部 LLM。"
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Edit, Task, AskUserQuestion
---

# 需求分析子 skill（阶段 1 / 4）

> **架构定位**：这是"大 skill 套小 skill 套 script"结构里的**小 skill** 层。
> prompt 拼装和用例生成在本文件里用文字呈现，由 Agent（你，Claude）自己读、自己想、自己生成 JSON；
> 然后**调用 Task 工具**把生成工作委派给一个隔离子 agent（避免主上下文被大量 case 污染）；
> 最后调 `generate_requirements.py` 这个**机械脚本**把 JSON 写成 Excel。
> 脚本零 LLM 调用，与任何外部模型 URL / API key 完全解耦。

## 你的输入

- `description`：用户提供的 Agent 需求说明文本（可能是 PRD 摘要、产品描述、功能清单）
- 若用户给的是已有测试用例文件，走"逆向分析"模式（见下文）

## 你的输出

- `data/requirements_analysis.xlsx`（3 个 sheet：测试维度 / 测试场景 / Skill 归属建议）
- stdout 输出 JSON 摘要（供下一阶段消费）

## 第 1 步：确认需求文本

如果用户没给 `description`，用 `AskUserQuestion` 问：

> 请提供被测 Agent 的需求说明（PRD 摘要 / 功能描述 / 业务场景清单），用于生成测试维度和场景。

如果用户给的是已有测试用例（JSON/YAML/Excel），走逆向分析（见第 4 步）。

## 第 2 步：用 Task 工具委派生成（正向分析）

**不要自己一次性生成全部内容**，而是用 `Task` 工具 spawn 一个子 agent，把下面的 prompt 完整传给它。这样主上下文保持干净，且可并行。

调用 `Task` 工具，`subagent_type` 用 `general-purpose`，`prompt` 字段填入下面【生成 prompt】整段（把 `{{DESCRIPTION}}` 替换为用户需求文本）：

---

### 【生成 prompt】（正向分析）—— 传给 Task 子 agent

```
你是一位资深智能体（Agent）系统架构师与 QA 专家，精通 agent_evaluation 业务测试覆盖方法论。

你审视需求时，不把 Agent 视为简单的文本生成器，而是视其为一个具备"目标-感知-规划-记忆-执行"闭环的复杂动态系统。

请仔细阅读下面的【Agent 需求说明】，找出其中隐藏的架构漏洞、死循环风险以及工程落地痛点，并按金融领域测试覆盖框架生成测试维度与场景：

参考覆盖框架（6 类）：
1. 业务场景覆盖 — 按业务功能拆解用户典型场景（账户服务、转账支付、存款、贷款、信用卡、投资理财、投诉售后等）
2. 业务流程覆盖 — 正常路径、替代路径、异常路径
3. 用户角色与意图覆盖 — 身份差异、意图多样性（查询、操作、投诉、闲聊等）
4. 业务规则与约束覆盖 — if-then 逻辑、数值约束、合规要求（如适当性管理、禁止刚性兑付）
5. 输入形态与上下文覆盖 — 不完整信息、错别字、指代消解、多轮上下文
6. 安全与边界覆盖 — 敏感信息泄露、越权操作、提示注入、诱导突破

具体要求：
- 每个测试维度对应上述 6 个覆盖类型之一
- 维度名称应体现具体业务场景（如「账户服务场景覆盖」而非仅「业务场景覆盖」）
- 场景描述需结合需求中的具体功能点
- 每个维度至少包含 2-3 个具体场景
- 维度 ID 用 DIM-001 / DIM-002 ... 顺序编号
- 场景 ID 用 SC-001 / SC-002 ... 顺序编号，并标注所属维度

【Agent 需求说明】：
{{DESCRIPTION}}

请严格按以下 JSON 格式输出（只输出 JSON，不要 markdown 标记，不要解释）：
{
  "dimensions": [
    {"id": "DIM-001", "name": "维度名称", "type": "覆盖类型"}
  ],
  "scenarios": [
    {"id": "SC-001", "dimension": "DIM-001", "name": "子场景", "description": "描述"}
  ],
  "skill_suggestions": [
    {"dimension_id": "DIM-001", "dimension_name": "维度名称", "skill": "所属Skill", "reason": "理由"}
  ]
}

skill 字段从以下选其一：orchestrator / requirements-analysis / test-case-generator / test-executor / test-reporter / 建议 新建。
```

---

### 【生成 prompt】（逆向分析）—— 当用户给的是已有测试用例时

```
你是一个专业的需求分析工程师。你擅长从已有的测试用例集中逆向分析，反推出测试维度和场景，并判断各维度归属于哪个 Skill。

【测试用例集】：
{{TEST_CASES_TEXT}}

请执行：
1. 解析用例结构，按子智能体、意图类型、交互轮次、边界类型等维度对用例聚类
2. 从聚类结果反向归纳出测试维度
3. 判断每个维度应归属到哪个现有 Skill（orchestrator / requirements-analysis / test-case-generator / test-executor / test-reporter）或建议新建

请严格按以下 JSON 格式输出（只输出 JSON，不要 markdown 标记）：
{
  "dimensions": [
    {"id": "DIM-001", "name": "维度名称", "type": "覆盖类型"}
  ],
  "scenarios": [
    {"id": "SC-001", "dimension": "DIM-001", "name": "子场景", "description": "描述"}
  ],
  "skill_suggestions": [
    {"dimension_id": "DIM-001", "dimension_name": "维度名称", "skill": "所属Skill", "reason": "理由"}
  ]
}
```

---

## 第 3 步：校验子 agent 返回的 JSON

子 agent 返回的文本可能裹了 markdown 代码块。你（主 Agent）负责：

1. 剥离 ```json ... ``` 包裹
2. `json.loads` 解析，失败则让 Task 子 agent 重生成（最多 2 次）
3. 校验 `dimensions` 非空、每个维度有 id/name/type；`scenarios` 非空、每个场景有 id/dimension/name
4. 校验所有 scenario.dimension 在 dimensions.id 集合里

## 第 4 步：调机械脚本写 Excel

把校验通过的 JSON 写到临时文件（或通过 stdin），调脚本：

```bash
# 方式 A：stdin 传 JSON（推荐，不留临时文件）
cat <<'EOF' | python ${SKILL_PATH}/scripts/generate_requirements.py --write-stdin --output ${SKILL_PATH}/data/requirements_analysis.xlsx
<把校验通过的 JSON 粘到这里>
EOF

# 方式 B：先写临时文件再传
python ${SKILL_PATH}/scripts/generate_requirements.py --write-file \
  --json-file /tmp/req_analysis.json \
  --output ${SKILL_PATH}/data/requirements_analysis.xlsx
```

脚本 stdout 会输出 JSON 摘要（含 dimensions_count / scenarios_count / dimensions 列表），把它展示给用户。

## 第 5 步：列出维度供用户确认

```bash
python ${SKILL_PATH}/scripts/generate_requirements.py --list ${SKILL_PATH}/data/requirements_analysis.xlsx
```

把维度列表展示给用户，询问：
- 维度是否合理？是否需要增删？
- 进入阶段 2（用例生成）时，每个场景生成几条用例？全部维度还是指定维度？

## 与 agent-eval 主能力的衔接

本阶段产出 `requirements_analysis.xlsx`，是后续所有阶段的输入。它**不直接**进入 agent-eval 的 eval loop（eval loop 消费的是 cases YAML + UATR trace）。桥接发生在阶段 3 之后：`excel_to_uatr.py` 把执行结果转成 UATR trace 喂给 diagnoser/multi_judge/optimizer。

## 重要约束

- ❌ 本子 skill 不许调任何外部 LLM API（OpenAI / DeepSeek / 自建模型 URL 一律不许）
- ❌ 不许在脚本里拼 prompt
- ✅ prompt 在本文件里以文字呈现
- ✅ 生成工作由 Agent 自己做，或用 Task 工具委派给子 agent
- ✅ 脚本只做 JSON → Excel 的机械写入 + list + read
