# Guide 05 — 优化策略

这份指南定义：针对每类失败，应该改什么组件、用什么 mutation 规则、生成的 patch 长什么样。

## 核心原则

**v0 不做玄学搜索**。不做贝叶斯优化、不做 GEPA、不做进化搜索。v0 的优化算法是：

```
for round in 1..N:
    run baseline on train cases
    collect failed cases
    diagnose failure type (F1-F7)
    generate 1-3 candidate patches per failure cluster
    run each candidate on failed cases first (small sample)
    keep top 1 candidate
    run top candidate on regression cases
    accept if improvement and no regression hard fail
    else rollback
```

也就是：**失败案例优先局部验证 → 小样本通过 → 回归集验证 → Git diff 接受**。

候选生成可以由 Claude Code 做，但**接受规则必须由 runner 决定**。不要让 Claude 自己说"我觉得更好"。

## 每类失败的 mutation 规则

### F1 — Skill 触发失败

**修改对象**：`SKILL.md` description / examples / skillOverrides

**mutation 规则**（在 `mutators/skill_rules.yaml` 里）：

| 子类 | mutation |
|------|----------|
| F1.1 没触发 | description 增加明确触发词；把宽泛描述改成任务型描述；增加 example 触发场景 |
| F1.2 误触发 | description 增加 should-not-trigger 反例；拆分过大的 skill |
| F1.3 没加载 reference | SKILL.md body 里把 reference 引用从弱引用改成强引用（"必须先读 X 再做 Y"）；把关键 reference 内容直接内联到 SKILL.md |

**patch 形式**：直接修改 `SKILL.md` 文件，输出 unified diff。

---

### F2 — 任务理解失败

**修改对象**：Prompt（system prompt 的任务说明部分）

**mutation 规则**（在 `mutators/prompt_rules.yaml` 里）：

| 子类 | mutation |
|------|----------|
| F2.1 没识别任务类型 | system prompt 开头增加任务类型识别段："当用户说 X 时，本 agent 的任务是 Y"；增加任务类型枚举 |
| F2.2 没识别场景阶段 | system prompt 增加阶段判断逻辑："先判断当前处于 [初审/复审/终审] 哪个阶段，再决定调用哪些工具" |
| F2.3 没识别硬约束 | system prompt 增加硬约束清单："以下约束必须满足，违反则直接拒绝输出结论：..." |

**patch 形式**：修改 prompt 文件（`.agent-eval/agent_assets/system_prompt.md` 或项目里实际的 prompt 文件），输出 unified diff。

---

### F3 — 工具选择失败

**修改对象**：Tool Schema（`@Tool` description / tool name）+ Tool Policy

**mutation 规则**（在 `mutators/tool_rules.yaml` 里）：

| 子类 | mutation |
|------|----------|
| F3.1 漏工具 | 给该工具的 `@Tool` description 增加适用场景说明；在相似工具的 description 里增加排他说明；检查 Tool Policy 是否误禁用 |
| F3.2 调错工具 | 给两个相似工具增加区分说明（"用 A 当 X，用 B 当 Y"）；考虑重命名工具让区别更明显 |
| F3.3 重复调用 | 在 Tool Policy 里增加"同工具同参数 3 次后禁用"规则；或增加 advisor 检查重复调用 |
| F3.4 顺序错误 | 在 system prompt 里增加工具调用顺序说明；或在 Tool Policy 里增加软顺序约束 |

**patch 形式**：修改 `@Tool` 注解的 description 字符串、Tool Policy 配置文件，输出 unified diff。

---

### F4 — 工具参数失败

**修改对象**：Tool Schema（参数 description / enum / required）+ Memory/Reference（字段映射表）

**mutation 规则**（在 `mutators/tool_rules.yaml` 里）：

| 子类 | mutation |
|------|----------|
| F4.1 参数缺失 | 在 `@Tool` 参数 description 里明确标注 required；增加参数示例 |
| F4.2 字段映射错误 | 在 Memory/Reference 里增加字段映射表（"用户输入 X → 工具参数 Y"）；在 system prompt 里引用该映射表 |
| F4.3 枚举值错误 | 在 `@Tool` schema 里增加 enum 约束；在参数 description 里列出合法值 |
| F4.4 ID 错误 | 在 Tool Schema 里增加 ID 格式校验；在工具返回 404 时给出可恢复提示（"ID 不存在，请先用 list_X 工具查询"） |

**patch 形式**：修改 `@Tool` 注解 / Memory 文件，输出 unified diff。

---

### F5 — Workflow 失败

**修改对象**：Workflow / Advisor（Spring AI Advisor 链）

**mutation 规则**（在 `mutators/workflow_rules.yaml` 里）：

| 子类 | mutation |
|------|----------|
| F5.1 缺少前置检查 | 增加 `InputValidationAdvisor`，在 agent_start 后校验输入完整性 |
| F5.2 缺少中间验证 | 在关键 `tool_result` 后增加 `ToolResultReviewAdvisor`，校验返回数据非空、字段齐全 |
| F5.3 缺少 fallback | 在 Tool Policy 里为关键工具配置 fallback 工具；或增加 `FallbackAdvisor` |
| F5.4 异常后没有恢复 | 增加重试策略（最多 N 次）；增加 `ErrorRecoveryAdvisor`，error 后切换到降级流程 |

**patch 形式**：修改 Spring AI 配置类（增加 advisor bean），输出 Java 代码 diff + 配置说明。

---

### F6 — Memory / Reference 失败

**修改对象**：Memory / Reference（项目级记忆 / CLAUDE.md / guide）

**mutation 规则**（在 `mutators/workflow_rules.yaml` 里）：

| 子类 | mutation |
|------|----------|
| F6.1 没检索到 | 在 system prompt 里增加检索触发条件（"当遇到 X 场景时，必须先检索 memory"）；在 Memory 里增加业务模块索引 |
| F6.2 检索到了但没用 | 在 system prompt 里增加"检索到的 memory_hits 必须在 final_answer 中体现"；增加后置 advisor 校验 |
| F6.3 用了过期 reference | 更新 Memory 里的字段映射；增加版本标记，agent 检索时校验版本 |

**patch 形式**：修改 Memory 文件 / CLAUDE.md / guide，输出 unified diff。

---

### F7 — 输出失败

**修改对象**：Prompt（输出格式说明）+ Memory/Reference（输出模板）

**mutation 规则**（在 `mutators/prompt_rules.yaml` 里）：

| 子类 | mutation |
|------|----------|
| F7.1 格式错 | system prompt 增加输出格式说明；在 Memory 里增加输出模板；增加 `OutputFormatAdvisor` 后置校验 |
| F7.2 结论缺证据 | system prompt 增加"每个结论必须引用 tool_result 中的数据"；增加 `EvidenceCheckAdvisor` |
| F7.3 漏业务规则 | 把漏掉的规则加到 system prompt 的硬约束清单；或加到 Memory 的业务规则索引 |
| F7.4 幻觉补充事实 | system prompt 增加"禁止编造 trace 中没有的数据"；增加 `HallucinationCheckAdvisor` |

**patch 形式**：修改 system prompt / Memory / Advisor 配置，输出 unified diff。

---

## patch 生成原则

1. **最小化**：一个 patch 只解决一类失败（F1–F7 中的一个子类）。如果一次诊断出多类失败，生成多个 patch。
2. **可回滚**：每个 patch 必须能被 `git revert` 干净撤销。禁止生成"删除原有内容"的 patch——应该用"替换"或"追加"。
3. **可读**：patch 的 description 必须说清楚改了什么、为什么改、预期修掉哪些 failure_id。
4. **不自动 apply**：mutator 只生成 patch 文件（`.agent-eval/patches/candidate_<N>.md` + 对应的 `.patch`），由用户或 Claude Code 手动 apply，然后跑 A/B。

## budget 控制

`mutator.py --budget` 控制一次生成多少 patch：

- `small`（默认）：最多 3 个 patch，每个 patch 最多改 2 个文件
- `medium`：最多 5 个 patch，每个 patch 最多改 3 个文件
- `large`：最多 10 个 patch，每个 patch 最多改 5 个文件

v0 不推荐 `large`——大 patch 几乎一定归因错了。

## 什么时候停止迭代

满足以下任一条件，停止本轮优化：

1. train split 上无失败 case。
2. 连续 3 轮迭代，candidate 都被 A/B 拒绝。
3. 达到用户指定的 `--max-rounds`。

停止后 `report.py` 生成最终报告，列出本轮所有 accepted patch 和 rejected patch 及原因。

## v0 故意不做的优化方法

| 方法 | 为什么 v0 不做 |
|------|---------------|
| 贝叶斯优化 | 需要大量样本，v0 的 case 数（20–50）撑不起 |
| GEPA / 进化搜索 | 需要明确的"prompt 基因"表示，且迭代成本高 |
| 自动 prompt 生成（如 APE） | 容易生成"看起来好但破坏可读性"的 prompt |
| 多 agent 协作优化 | 复杂度爆炸，v0 单 agent 闭环已足够 |

这些方法都可以作为 v1 的 exporter / plugin 接入，但不应进入 v0 核心路径。
