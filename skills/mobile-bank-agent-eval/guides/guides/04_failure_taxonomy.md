# Guide 04 — 失败归因 Taxonomy

这是整个 skill 的核心。评测本身不产生价值，**把失败归因到可修改对象上**才产生价值。

## 7 类失败（F1–F7）

每类失败对应一个可修改组件。diagnoser 必须把每条失败 case 归到至少一类，并给出 trace 证据。

### F1 — Skill 触发失败

**修改对象**：`SKILL.md` description / examples / skillOverrides

**子类**：
- F1.1 skill 没触发（用户意图匹配，但 skill 没被加载）
- F1.2 skill 误触发（skill 被加载了，但任务其实不相关）
- F1.3 skill 触发了但没加载关键 reference（SKILL.md 里指向的 guide/reference 没被读）

**trace 证据**：
- F1.1 / F1.2：没有 `prompt_rendered` 事件中包含被测 skill 的 system prompt hash，或者反过来出现了不该出现的 skill hash。
- F1.3：`prompt_rendered` 里有 skill hash，但 trace 里没有 `memory_retrieval` 或 `Read` 事件指向 reference 文件。

**判定逻辑**：F1 主要发生在 Claude Code skill 评测场景。对 Spring AI agent，F1 一般不适用。

---

### F2 — 任务理解失败

**修改对象**：Prompt（system prompt 的任务说明部分）

**子类**：
- F2.1 没识别任务类型（如把"风险审查"当成"贷款审批"）
- F2.2 没识别场景阶段（如应该在"初审"阶段却跳到"终审"）
- F2.3 没识别硬约束（如"必须先校验担保信息"被忽略）

**trace 证据**：
- `agent_final.final_answer` 里缺少 case `expected.final_decision.contains` 中的关键概念词。
- `tool_call` 调用了与任务类型不符的工具（如风险审查 case 里调了 `approve_loan_directly`）。
- `model_call` 后没有 `tool_call`，直接跳到 `agent_final`——意味着 agent 没分析就给结论。

**判定逻辑**：F2 的特征是"模型一开始就走错路"，不是某个工具调错，而是整体方向错。

---

### F3 — 工具选择失败

**修改对象**：Tool Schema（`@Tool` description / tool name）+ Tool Policy（启停 / 顺序）

**子类**：
- F3.1 漏工具（`expected_tools.required` 里有，但 trace 里没调）
- F3.2 调错工具（调了一个相似但不该调的工具）
- F3.3 重复调用（同一工具同一参数调用 ≥ 3 次）
- F3.4 工具顺序错误（`expected_tools.order.soft` 偏离严重）

**trace 证据**：
- F3.1：trace 里 `tool_call` 事件集合 ⊉ required，差集非空。
- F3.2：trace 里出现了不在 required 也不在 optional 的工具，或 forbidden 工具（forbidden 直接硬失败，不到 F3）。
- F3.3：相邻 `tool_call` 事件的 `tool` + `arguments` hash 相同。
- F3.4：实际 `tool_call` 序列与 `expected_tools.order.soft` 的 LCS ratio < 0.5。

**判定逻辑**：F3 是"该用 A 用了 B"或"该用 A 没用"。区别于 F4（用了 A 但参数错）。

---

### F4 — 工具参数失败

**修改对象**：Tool Schema（参数 description / enum / required）+ Memory/Reference（字段映射表）

**子类**：
- F4.1 参数缺失（必填参数没传）
- F4.2 字段映射错误（从用户输入到工具参数的映射错，如把 `applicant_id` 当成 `application_id`）
- F4.3 枚举值错误（传了不在 enum 里的值）
- F4.4 ID / 页面对象错误（传了错的 ID，导致 tool_result 返回空或 404）

**trace 证据**：
- F4.1：`tool_call.arguments` 缺少 schema 里 required 的字段。
- F4.2：`tool_call.arguments` 里字段值与 `case.input` 里的字段对应不上（需要 case 里提供 `expected.argument_mapping` 才能判定）。
- F4.3：`tool_call.arguments` 里某字段值不在 schema enum 里，或 `tool_result.status == "error"` 且错误信息提示 enum 违规。
- F4.4：`tool_result.status == "error"` 或 `result` 为空，且 `tool_call` 不属于 F3.3 重复调用。

**判定逻辑**：F4 是"工具选对了但用错了"。诊断时要把 `tool_call.arguments` 和 case 提供的期望参数对齐。

---

### F5 — Workflow 失败

**修改对象**：Workflow / Advisor（Spring AI Advisor 链 / 前置校验 / 后置检查 / 重试策略）

**子类**：
- F5.1 缺少前置检查（如没校验输入完整性就开始分析）
- F5.2 缺少中间验证（如工具返回异常数据但没有 advisor 拦截）
- F5.3 缺少 fallback（工具失败后直接挂，没有降级路径）
- F5.4 异常后没有恢复（一次 error 后整个 case 失败）

**trace 证据**：
- F5.1：trace 开头没有 `advisor_enter` 事件（如缺少 `InputValidationAdvisor`）。
- F5.2：`tool_result.status == "error"` 或 `result` 明显异常（如 `null` / 空数组），但后续没有 `advisor_enter` 拦截，直接进入下一步。
- F5.3：`tool_result.status == "error"` 后直接 `agent_final` 或 `error`，没有 `tool_call` 切换到 fallback 工具。
- F5.4：`error` 事件后没有 `agent_final`，或 `agent_end.status == "error"`。

**判定逻辑**：F5 的特征是"工具和 prompt 都没错，但流程没有兜底"。这是 Spring AI Advisor 链该解决的问题。

---

### F6 — Memory / Reference 失败

**修改对象**：Memory / Reference（项目级记忆 / 业务规则 / 字段映射 / guide / CLAUDE.md）

**子类**：
- F6.1 没检索到项目记忆（`memory_retrieval` 事件命中数为 0）
- F6.2 检索到了但没使用（`memory_retrieval.memory_hits` 非空，但后续 `tool_call` / `agent_final` 没体现）
- F6.3 使用了过期 reference（记忆里的字段映射与当前系统不符）

**trace 证据**：
- F6.1：没有 `memory_retrieval` 事件，或有但 `memory_hits == []`。
- F6.2：`memory_hits` 非空，但 `agent_final.final_answer` 里没出现记忆里的关键信息，或 `tool_call.arguments` 没用上记忆里的字段映射。
- F6.3：`memory_hits` 里的字段名与 `tool_call.arguments` 里实际传的不一致（说明 agent 知道有映射但用了错的，或映射本身过期）。

**判定逻辑**：F6 是"该用历史经验没用，或用了错的"。和 F4.2 的区别：F4.2 是不知道字段怎么映射，F6 是记忆里有映射但没检索到或没用上。

---

### F7 — 输出失败

**修改对象**：Prompt（输出格式说明部分）+ Memory/Reference（输出模板）

**子类**：
- F7.1 格式错（`output_schema_validity < 1`）
- F7.2 结论缺证据（`final_answer` 给了结论但 trace 里没有支撑该结论的 `tool_result`）
- F7.3 漏业务规则（`business_rule_coverage < 1` 但不是 F2/F5 导致）
- F7.4 幻觉补充事实（`final_answer` 里出现了 trace 里没有的事实）

**trace 证据**：
- F7.1：`output_schema_validity` 分数 < 1。
- F7.2：`final_answer` 里的关键论断（如"流水波动大"）在 `tool_result` 里找不到对应数据。
- F7.3：`business_rule_coverage` 命中规则数 < 总规则数，且失败规则不是 F2（任务理解）或 F5（流程）导致的。
- F7.4：`final_answer` 里的具体数字 / 名称 / ID 在 `case.input` 和所有 `tool_result` 里都搜不到。

**判定逻辑**：F7 是"前面都对，最后输出砸了"。是兜底归因——只有 F1–F6 都不成立时才归到 F7。

---

## 多标签归因

一条失败 case 可以同时归到多类。例如：agent 漏调了 `check_debt_ratio`（F3.1），导致最终结论缺少负债分析（F7.3）。这种情况 diagnoser 会输出两条记录，分别指向不同的 mutation target。mutator 会生成一份覆盖两条的 patch（如果可能），或两份独立 patch。

## 归因优先级

当 trace 证据不足时，按以下优先级降序归因（避免无限兜底到 F7）：

1. F3 / F4（工具层，证据最硬）
2. F5（流程层，advisor 事件明确）
3. F6（记忆层，memory_retrieval 事件明确）
4. F2（任务理解，需要看 final_answer 语义）
5. F1（skill 触发，仅 Claude Code 场景）
6. F7（输出层，兜底）

## 不能归因的情况

如果 trace 太短（< 3 个事件）或缺关键字段（没有 `tool_call` 也没有 `agent_final`），diagnoser 会标记 `failure_type: UNKNOWN` 并把原因写到 `evidence`。这种情况不要硬归因——很可能是 adapter 或 Spring AI 插桩出问题，先修插桩再重跑。
