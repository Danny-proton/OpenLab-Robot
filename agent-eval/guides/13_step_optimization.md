# Guide 13 — 执行冗余优化与 reference 注入 (v1.1)

v1.1 的核心目标：**让"笨模型跑十几轮"变成"两三轮搞定"**。

## 客户痛点

客户场景：同一个任务，笨模型要跑十几轮（大量 model_call + 重复 tool_call + 探索式徘徊），聪明模型两三轮就能搞定。

根因不是模型本身笨，而是：
1. prompt 没告诉模型最优执行路径
2. 没有 reference 指引工具调用顺序
3. 模型每次都要重新推理"下一步该调什么工具"

## v1.1 解决方案

### 1. F8 — 执行冗余失败（新增 failure type）

diagnoser 现在检测 4 类执行冗余：

| 子类 | 检测条件 | 典型原因 |
|------|---------|---------|
| F8.1 轮数过多 | actual_steps > expected_steps × 1.5 | prompt 缺执行路径 |
| F8.2 重复规划 | model_call + planner 次数 > tool_call × 1.5 | "光想不干" |
| F8.3 无效中间步 | toolA → think → toolA 模式 ≥ 2 次 | 第一次没拿到完整结果 |
| F8.4 探索式徘徊 | 连续 ≥ 3 次 model_call 无 tool_call | 模型不知道做什么 |

**关键设计**：F8 对所有 case 都检查，即使 case 最终成功。因为"成功但低效"也是问题。

### 2. HRPO 层次化根因分析（opik_adapter 升级）

opik_adapter 的 HRPO fallback 从"按 F1-F7 分类给通用建议"升级为真正的 4 层分析：

```
Layer 1: 现象      — F8.1 出现 1 次（22步 vs 期望9步）
Layer 2: 直接原因  — 总步数远超期望（agent 在反复探索）
Layer 3: 根因      — prompt 缺少明确执行路径，agent 不知道最优工具序列
Layer 4: 修复层    — reference
         修复动作  — 注入"执行路径 reference"：明确每类任务的最优工具调用顺序
         建议注入  — execution_path.md
```

每种失败类型都映射到一个**具体的 reference 文件**，而不是模糊的"改 prompt"。

### 3. reference_optimizer.py — 自动生成并注入 reference

8 个 reference 模板，覆盖所有 F8 子类 + F2/F4/F6/F7：

| reference 文件 | 解决问题 | 内容 |
|---------------|---------|------|
| `execution_path.md` | F8.1 轮数过多 | 每类任务的最优工具调用顺序（个人贷款 7 步 / 企业贷款 8 步）|
| `act_after_decide.md` | F8.2 光想不干 | "每次 model_call 后必须跟 tool_call" 约束 |
| `tool_usage_guide.md` | F8.3 重复调用 | 每个工具的参数校验 + 结果字段说明 |
| `tool_decision_tree.md` | F8.4 探索式徘徊 | 基于状态的 if-then 工具选择规则 |
| `field_mapping.md` | F4 参数错误 | 用户输入 → 工具参数的映射表 |
| `task_type_decision_tree.md` | F2 任务识别错 | 任务类型 + 阶段判断决策树 |
| `memory_index.md` | F6 记忆未用 | 业务模块索引 + 检索触发条件 |
| `output_format_template.md` | F7 输出问题 | 输出格式 + 必须关键词 + 禁止行为 |

**用法**：
```bash
# 生成并直接注入到 .agent-eval/agent_assets/
python reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply
```

注入后，在 agent 的 system prompt 里加一句：
> "处理任务前，必须先读 .agent-eval/agent_assets/<reference>.md"

### 4. auto_patcher.py — 全自动优化循环

把"生成 reference → apply → A/B → 评审 → accept/rollback"全自动：

```bash
python auto_patcher.py \
    --config .agent-eval/config.yaml \
    --baseline-run <run_id> \
    --split regression \
    --auto-apply
```

流程：
1. 自动生成并 apply reference 文件到 `agent_assets/`
2. 自动生成 patch 计划（prompt/tool 改动建议，不自动 apply）
3. 跑 A/B（candidate vs baseline）
4. 跑 multi_judge 评审（含 RegressionJudge）
5. Gatekeeper 决策：
   - ACCEPT → 自动 `git commit` + `mark-good`
   - REJECT → 自动 `git checkout` 回滚 reference 文件

**为什么 reference 自动 apply，patch 不自动 apply**：
- reference 文件是新增的，不改现有代码，风险低
- patch 改的是 prompt / @Tool description / Advisor 代码，风险高，需人工确认

## 笨模型 vs 聪明模型对比

v1.1 让你能量化"笨→聪明"的提升：

```
baseline（笨模型）:
  - case loan_risk_002: 22 步, model_call 7 次, tool_call 3 次
  - F8.1 + F8.2 + F8.4 命中
  - 注入 execution_path.md + act_after_decide.md + tool_decision_tree.md

candidate（注入 reference 后）:
  - case loan_risk_002: 9 步, model_call 2 次, tool_call 3 次
  - F8 全部消除
  - 步数减少 59%，model_call 减少 71%
```

auto_patcher 会自动验证这个提升，达标才 accept，不达标自动回滚。

## 与 v1 的区别

| 能力 | v1 | v1.1 |
|------|-----|------|
| 失败类型 | F1-F7 | F1-F8（+4 类执行冗余）|
| HRPO fallback | 简单分类建议 | 4 层层次化根因分析 |
| reference 生成 | 无 | 8 个模板，自动生成注入 |
| patch apply | 只生成计划 | reference 自动 apply + patch 生成计划 |
| A/B + 评审 | 手动分步 | auto_patcher 全自动 |
| 回滚 | 手动 git checkout | 自动 git checkout |
| 步数优化 | 不支持 | F8 专门检测 + reference 修复 |

## 使用建议

1. **第一次跑**：用 v1.1 跑 baseline，看 F8 诊断——如果你的 agent 跑十几轮，F8.1/F8.2/F8.4 会命中
2. **跑 HRPO**：`opik_adapter.py --optimizer hrpo`，看 4 层根因分析和建议注入的 reference
3. **跑 auto_patcher**：`auto_patcher.py --auto-apply`，自动注入 reference + A/B + 评审
4. **看结果**：
   - 如果 ACCEPT：reference 已 commit，agent 下次跑会少走弯路
   - 如果 REJECT：自动回滚，看报告找原因，可能需要手动改 prompt 后再跑
5. **迭代**：重复直到 F8 失败清零或步数达标
