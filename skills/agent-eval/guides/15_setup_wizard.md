# Guide 15 — Setup Wizard 信息收集

agent-eval 在启动和关键决策点会主动收集用户信息。设计原则：**不问已有的，只问缺失的，给合理默认值**。

## 5 个环节的信息收集

### 1. 首次启动（startup）

**触发时机**：用户第一次跑 `eval_runner.py`，或 `.agent-eval/config.yaml` 不存在/不完整。

**收集内容**：
| 字段 | 来源优先级 | 默认值 | 缺失时是否必问 |
|------|-----------|--------|--------------|
| adapter 类型 | config > 默认 | openlab_robot | ✅ 必问 |
| openlab_bin | config | ~/cc-haha/bin/claude-haha | ✅ 必问（OpenLab Robot 时）|
| anthropic_auth_token | config > 环境变量 | — | ✅ 必问 |
| anthropic_model | config > 环境变量 | claude-sonnet-4-20250514 | ❌ 有默认 |
| workdir | config | /tmp/openlab-work | ❌ 有默认 |
| permission_mode | config | bypassPermissions | ❌ 有默认 |
| max_turns / max_budget | config | 20 / 1.0 | ❌ 有默认 |

**问题示例**：
```
Q: 你要评测的 Agent 是什么类型？
  - OpenLab Robot (推荐): 基于 cc-haha / Claude Code 的 agent
  - Spring AI: Spring AI ChatClient agent
  - 其他 HTTP: 任意 HTTP API agent
  - Mock 测试: 不用真实 agent，跑通流程

Q: OpenLab Robot (cc-haha) 的可执行文件路径？
  - ~/cc-haha/bin/claude-haha (推荐)
  - ~/projects/cc-haha/bin/claude-haha
  - PATH 中已有
  - 自定义路径

Q: ANTHROPIC API key 没设置。你要怎么提供？
  - 环境变量已设: 我刚 export 了，重新读
  - 写入 config (推荐): 写到 adapter yaml
  - 稍后配置: 先跳过
```

### 2. 评测环节（eval）

**触发时机**：每次跑 `eval_runner.py`。

**收集内容**：
| 字段 | 默认值 | 说明 |
|------|--------|------|
| split | train | train / regression / adversarial |
| variant | baseline | baseline / candidate_xxx |
| label | 空 | run_id 短标签 |

**问题示例**：
```
Q: 跑哪个 split？
  - train (推荐): 训练集，迭代优化用
  - regression: 回归集，接受 patch 前必须跑
  - adversarial: 对抗集，压测边缘场景

Q: variant 标签？
  - baseline (推荐): 基线版本
  - candidate: 候选版本（优化后）
```

### 3. 多 Agent 评测（judge）

**触发时机**：跑 `multi_judge.py` 时。

**收集内容**：
| 字段 | 默认值 | 说明 |
|------|--------|------|
| 规则型 Judge | 全开 | DomainJudge / ToolTraceJudge / WorkflowJudge / FaithfulnessJudge / RegressionJudge / SafetyJudge |
| LLM 型 Judge | 仅 Gatekeeper | OptimizerPlanner / PatchWriter / ReportWriter 默认关 |
| 共识阈值 | 0.7 | 低于此值说明 Judge 分歧大 |
| 安全否决 | 强制 | SafetyJudge veto 直接 REJECT |

**问题示例**：
```
Q: 启动哪些规则型 Judge？（多选）
  - DomainJudge (推荐): 业务规则覆盖
  - ToolTraceJudge (推荐): 工具调用轨迹
  - WorkflowJudge (推荐): 流程完整性
  - FaithfulnessJudge (推荐): 证据一致性
  - RegressionJudge (推荐): 回归风险（仅 A/B）
  - SafetyJudge (推荐): 安全合规（可一票否决）

Q: 是否启用 LLM 型 Judge？（多选）
  - Gatekeeper (推荐): 最终裁决
  - OptimizerPlanner: 优化规划（不写代码）
  - PatchWriter: 生成代码 patch
  - ReportWriter: 撰写报告

Q: Judge 共识阈值？
  - 0.7 (推荐): 70% 一致率才算可信
  - 0.5 (宽松): 50% 即可
  - 0.9 (严格): 90% 一致率

Q: SafetyJudge 一票否决？
  - 强制否决 (推荐): 安全违规 = 直接 REJECT
  - 仅警告: 只记录，不强制
```

### 4. 优化环节（optimize）

**触发时机**：跑 `auto_patcher.py` 或 `reference_optimizer.py` 时。

**收集内容**：
| 字段 | 默认值 | 说明 |
|------|--------|------|
| optimizer | hrpo | HRPO 层次化根因分析 |
| budget | small | 最多 3 个 patch |
| auto_apply_reference | True | reference 风险低，自动 apply |
| auto_apply_patch | False | patch 改代码风险高，不自动 |
| auto_git_commit | False | 不自动 commit |
| auto_git_rollback | True | REJECT 时自动回滚 |

**问题示例**：
```
Q: 用哪个优化器？
  - HRPO (推荐): 层次化根因分析，最适合缩短执行轮数
  - rule_based: 规则驱动
  - DeepEval: PromptOptimizer（需安装）
  - Opik GEPA: 梯度引导（需安装）

Q: Budget？
  - small (推荐): 最多 3 个 patch
  - medium: 最多 5 个
  - large: 最多 10 个（风险高）

Q: 自动 apply 哪些改动？（多选）
  - reference 文件 (推荐): 自动注入（风险低）
  - prompt/tool patch: 自动改代码（风险高）

Q: Gatekeeper 决策后自动执行什么？（多选）
  - ACCEPT 时 git commit
  - REJECT 时 git checkout 回滚 (推荐)
```

### 5. A/B 环节（abtest）

**触发时机**：跑 `abtest.py` 时。

**收集内容**：
| 字段 | 默认值 | 说明 |
|------|--------|------|
| baseline_run_id | 最新 | 从 runs/ 目录扫 |
| candidate_patch | 最新 | 从 patches/ 目录扫 |
| split | regression | 验证不破坏旧能力 |
| train_threshold | 0.03 | 提升 3% 才接受 |

## Claude Code 如何调用

Claude Code 读到 SKILL.md 后，在用户触发 agent-eval 时：

1. 先跑 `python ask_setup.py --stage <stage> --config <config> --emit-questions`
2. 解析输出的 JSON，拿到 `questions` 数组
3. 对每个 question 调用 `AskUserQuestion` 工具问用户
4. 收集用户答案后，写入 config 或传给后续命令

## 信息持久化

- startup 收集的信息 → 写入 `.agent-eval/config.yaml` + `.agent-eval/adapters/openlab_robot.yaml`
- judge 收集的信息 → 写入 `.agent-eval/config.yaml` 的 `judges` 段
- optimize 收集的信息 → 写入 `.agent-eval/config.yaml` 的 `optimize` 段

下次启动时，ask_setup 优先读 config，已配置的字段不再问。

## 默认 Judge 配置

**默认全开（6 个规则型）**：
- DomainJudge — 业务规则覆盖
- ToolTraceJudge — 工具调用轨迹
- WorkflowJudge — 流程完整性
- FaithfulnessJudge — 证据一致性
- RegressionJudge — 回归风险（仅 A/B）
- SafetyJudge — 安全合规

**默认开 1 个 LLM 型**：
- Gatekeeper — 最终裁决（规则版）

**默认关 3 个 LLM 型**：
- OptimizerPlanner — 需要 Claude Code 按 Agent.md 执行
- PatchWriter — 需要 Claude Code 改代码
- ReportWriter — 需要 Claude Code 写报告

**为什么这样默认**：
- 规则型 Judge 确定性、无成本，全开有益无害
- Gatekeeper 规则版足够做 accept/reject 决策
- LLM 型 Judge 有成本且需要 Claude Code 配合，按需开

## Skip 机制

如果用户用 `--non-interactive` 跑，ask_setup 不问，全部用默认值。适合 CI 场景。
