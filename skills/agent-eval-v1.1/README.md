# Agent Eval Skill V1.1 — 用例自优化版

> 业界空白能力：首次实现 test-case 自优化（改测试本身），与 prompt 自优化（改被测 Agent）正交运行。

基于 agent-eval v2.3.0-mobile-bank 演进，聚焦**用例自优化**。

**v1.1.2（本次）**：可视化统一收尾——eval loop 深度报告（html_report.py，12 节）迁入深色玻璃态设计体系 + 门户平均分/趋势数据修复 + KPI 单行布局与数字动画 + 四处报告统一 `prefers-reduced-motion`。

**v1.1.1**：在 v1.1.0 基础上完成"报告统一管理 + 执行流程进度管理 + 可视化深度优化"三件事。

## V1.1 核心创新

完成一轮评测后，自动迭代测试用例集，使下一轮测试的覆盖度和有效率提升：

```
一轮评测 → prompt 自优化（改 Agent）→ 用例自优化（改测试）→ 重跑 → 双闭环
```

| 能力 | 说明 |
|------|------|
| 错误分布分析 | 从 F1-F8 诊断识别集中失败类型 |
| Spec 缺口识别 | 维度/工具/DFX 缺口 + 过简单维度 |
| 12 维质量评分 | 9 标准 + 3 Agent 专属（工具/工作流/记忆覆盖率） |
| Mutation kill matrix | 6 类变异，参考 Meta ACH arXiv 2501.12862 |
| 增强建议生成 | add/modify/deprecate/spec_changes 四类 |
| 迭代报告 | MD + HTML，含质量分前后对比 |
| **【v1.1.1】报告统一门户** | 单 HTML 聚合 5 页：Overview/Reports/Progress/Iterations/Quality |
| **【v1.1.1】进度埋点** | sidecar 持久化到 progress.jsonl，门户实时聚合 9 步时间线 |
| **【v1.1.1】深色玻璃态可视化** | 3 处报告统一升级：渐变高亮 + 悬浮升起 + SVG 图表 + tooltip |
| **【v1.1.2】eval 深度报告视觉统一** | html_report.py 12 节报告深色玻璃态重构：玻璃卡片 + 悬浮发光 + 入场动画 + 图表深色适配，打印仍输出浅色 |
| **【v1.1.2】门户数据修复** | 修复 scores JSON aggregate 嵌套读取（平均分/Run 趋势恢复显示）+ KPI 单行布局 + 数字 count-up 动画 |

## 与 v2.3.0 的区别

| 维度 | v2.3.0-mobile-bank | v1.1.0（本版本） |
|------|-------------------|----------------|
| 优化对象 | 被测 Agent（prompt/tool/workflow/reference） | **+ 测试本身（case/spec/因子）** |
| 质量评分 | 无 | 12 维确定性评分 |
| Mutation 测试 | 无 | 6 类变异 kill matrix |
| 需求分析 | 6 覆盖框架 | + UC 15 字段块 + testspec 4 表 |
| 用例自检 | 9 维 | + 20 项（16 成熟 + 4 Agent 专属） |
| mock 系统 | 3 种失败触发 | 8 种（mock_config） |

## 完整能力（保留 v2.3.0 全部 + 新增）

### 保留（v2.3.0 原样）
- 4 阶段流水线（需求分析→用例生成→执行→报告）+ Excel I/O
- excel_to_uatr 桥接器（Excel→UATR trace + cases YAML）
- F1-F8 失败归因 + HRPO 层次化根因
- 9 个评审 Agent（6 规则型 + 3 决策型）
- reference 自动注入 + auto_patcher A/B 全自动优化
- ask_setup 向导 + SideCar + memory_kb + 报告管理 + Dashboard + CI 回归
- 3 个 adapter（mock/spring_ai_http/openlab_robot）

### V1.1 新增
- **5 个脚本**（零 LLM）：case_io / case_quality_checker / case_optimizer / mutation_generator / case_iteration_report
- **1 个子 skill**：test-case-self-optimization（阶段 4.5）
- **吸收 test-design-agent-raw**：UC 15 字段 + testspec 4 表 + 16 项自检 + 7 方法库
- **mock 系统扩展**：8 种失败触发模式
- **6 个文档**：DELTA / PRD_REQUIREMENT_TESTDESIGN / PRD_MOCK_SYSTEM / PRD_CASE_SELF_OPTIMIZATION（重写）/ DESIGN_OVERVIEW（更新）/ guide 17

### v1.1.1 新增（报告统一管理 + 进度埋点 + 可视化重构）
- **2 个脚本**（零 LLM）：`progress_tracker.py`（进度事件持久化）/ `report_portal.py`（5 页统一门户）
- **sidecar.py 改造**：向后兼容，emit JSON 到 stdout 同时持久化到 progress.jsonl，session_id 自动续接
- **3 处报告可视化重构**：generate_report / case_iteration_report / report_portal 统一深色玻璃态设计语言
- **SVG 图表**：进度环 / sparkline / 12 维雷达 / 维度通过率条形 / 优先级堆叠柱 / 响应时间分布 / Pareto / Mutation 热力图，全部带原生 tooltip
- **1 个 PRD**：`docs/PRD_REPORT_PORTAL.md`（含验收标准 §8）
- **修复**：generate_report.py 的 `output_path` 未定义 bug

### v1.1.2 新增（可视化统一收尾 + 数据修复）
- **html_report.py 深色玻璃态重构**：eval loop 12 节深度报告迁入统一设计体系（玻璃卡片 + 渐变描边 + 悬浮升起/发光 + 入场动画 + 热力图/雷达/时间线深色适配 + SVG 单元格 hover 提亮），`@media print` 保留浅色打印
- **门户数据修复**：`_load_runs_summary` 下钻 scores JSON 的 `aggregate` 嵌套字段，Overview 平均分 / Run 分数趋势 sparkline 恢复显示
- **门户交互增强**：6 张 KPI 卡桌面端单行排布；KPI 数字 count-up 滚动动画
- **可访问性**：4 个报告生成器统一支持 `prefers-reduced-motion`
- **示例重生成**：`data/test_report.html` 用深色主题重新生成

## 安装

```bash
cp -r skills/agent-eval-v1.1 .claude/skills/agent-eval
```

## 快速开始（mock 端到端，零外部依赖）

> ✅ **开箱即跑**：skill 自带 mock 数据——`examples/.agent-eval/cases/train.yaml` 含 8 条手机银行用例（覆盖 8 种失败触发模式），`examples/.agent-eval/adapters/mock.yaml` 是内置 mock adapter。`scaffold` 会把这些一并复制到目标目录，**无需启动任何后端服务**即可跑通完整评测闭环。

### 0. 环境准备（一次性）

```bash
# 仅两个第三方依赖，所有脚本零 LLM
pip install pyyaml openpyxl
```

### 1. 一键 mock demo（最小可跑通）

```bash
SKILL_DIR=.claude/skills/agent-eval

# 初始化（自动复制 8 条 mock 用例 + mock adapter + config 到 ./.agent-eval/）
python $SKILL_DIR/scripts/eval_runner.py --scaffold .

# 跑一轮评测（mock，8 条用例，无需任何后端）
python $SKILL_DIR/scripts/eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline
# 产出：.agent-eval/reports/<run_id>.html + .md + traces + scores
```

预期输出：`TRACE 总分: 3.71/5.0 (一般)` + HTML 报告路径。到这一步 mock demo 已跑通。

### 2. 完整闭环（诊断 → 自优化 → 报告 → 门户）

```bash
# 3. F1-F8 诊断
python $SKILL_DIR/scripts/diagnoser.py --config .agent-eval/config.yaml --latest

# 4. 用例自优化（dry-run 看建议）
python $SKILL_DIR/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train

# 5. 用例自优化（apply 写入 cases YAML）
python $SKILL_DIR/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train --apply --non-interactive

# 6. 迭代报告（MD + HTML，深色玻璃态可视化）
python $SKILL_DIR/scripts/case_iteration_report.py --config .agent-eval/config.yaml --latest

# 7. 生成统一门户（v1.1.1，聚合报告/进度/迭代/质量分到同一网站）
python $SKILL_DIR/scripts/report_portal.py --config .agent-eval/config.yaml
# 产出 .agent-eval/reports/portal.html，浏览器打开即可
```

### mock 数据说明

| 文件 | 内容 |
|------|------|
| `examples/.agent-eval/cases/train.yaml` | 8 条手机银行用例，每条带 `mock_config.mode` 指定失败触发 |
| `examples/.agent-eval/adapters/mock.yaml` | mock adapter，按 `mock_config.mode` 模拟 8 种失败（skip_tool/repeat_tool/wrong_param/empty_result/hallucinate/redundant/no_memory/success） |
| `examples/.agent-eval/config.yaml` | 默认用 mock adapter，开箱即跑 |
| `examples/.agent-eval/cases/adversarial.yaml` | 对抗用例 |
| `examples/.agent-eval/cases/regression.yaml` | 回归用例 |

8 种失败触发模式覆盖 F1-F8 全部失败类型，mock 系统会模拟出真实的诊断/优化场景，无需真实手机银行 agent 后端。


### 进度埋点（v1.1.1）

sidecar 每步自动持久化到 `.agent-eval/data/progress.jsonl`，无需额外配置：

```bash
python $SKILL_DIR/scripts/sidecar.py --status running --step 1 --step-name "需求分析"
python $SKILL_DIR/scripts/sidecar.py --status completed --step 1

# 查看进度时间线
python $SKILL_DIR/scripts/progress_tracker.py --config .agent-eval/config.yaml timeline
python $SKILL_DIR/scripts/progress_tracker.py --config .agent-eval/config.yaml summary
```

## 命令速查

### 4 阶段流水线
```bash
# 阶段1: 需求分析（prompt 在子 skill，Agent 用 Task 工具生成 JSON）
python $SKILL_DIR/scripts/generate_requirements.py --list $SKILL_DIR/data/requirements_analysis.xlsx

# 阶段2: 用例生成
python $SKILL_DIR/scripts/generate_testcases.py --list --input $SKILL_DIR/data/requirements_analysis.xlsx

# 阶段3a: 执行
python $SKILL_DIR/scripts/execute_testcases.py --input $SKILL_DIR/data/test_cases.xlsx --output $SKILL_DIR/data/execution_results.xlsx --base-url http://localhost:8080/api/chat

# 阶段3b: 桥接
python $SKILL_DIR/scripts/excel_to_uatr.py --requirements $SKILL_DIR/data/requirements_analysis.xlsx --testcases $SKILL_DIR/data/test_cases.xlsx --results $SKILL_DIR/data/execution_results.xlsx --config .agent-eval/config.yaml --variant baseline

# 阶段4: 报告
python $SKILL_DIR/scripts/generate_report.py --requirements $SKILL_DIR/data/requirements_analysis.xlsx --testcases $SKILL_DIR/data/test_cases.xlsx --results $SKILL_DIR/data/execution_results.xlsx --output $SKILL_DIR/data/test_report.md
```

### eval loop（主分支）
```bash
python $SKILL_DIR/scripts/diagnoser.py --config .agent-eval/config.yaml --latest
python $SKILL_DIR/scripts/multi_judge.py --config .agent-eval/config.yaml --run <run_id> --split train
python $SKILL_DIR/scripts/reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply
python $SKILL_DIR/scripts/auto_patcher.py --config .agent-eval/config.yaml --baseline-run <run_id> --split regression --auto-apply
```

### 用例自优化（V1.1 新增）
```bash
# 12 维质量检查
python $SKILL_DIR/scripts/case_quality_checker.py --config .agent-eval/config.yaml --split train

# 变异 kill matrix
python $SKILL_DIR/scripts/mutation_generator.py --config .agent-eval/config.yaml --latest --split train

# 用例自优化（dry-run）
python $SKILL_DIR/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train

# 用例自优化（apply）
python $SKILL_DIR/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train --apply --non-interactive

# 迭代报告
python $SKILL_DIR/scripts/case_iteration_report.py --config .agent-eval/config.yaml --latest

# cases 校验
python $SKILL_DIR/scripts/case_io.py --config .agent-eval/config.yaml --split train --validate
```

## 文档

| 文档 | 说明 |
|------|------|
| `SKILL.md` | 主 skill 入口 |
| `VERSION.md` | 版本历史 |
| `docs/DESIGN_OVERVIEW.md` | 设计总纲 |
| `docs/DELTA_GENERAL_TO_AGENT.md` | 通用测试转 Agent 评测的新增点 |
| `docs/PRD_REQUIREMENT_TESTDESIGN.md` | 需求分析与测试设计流程 |
| `docs/PRD_CASE_SELF_OPTIMIZATION.md` | 用例自优化详细设计 |
| `docs/PRD_MOCK_SYSTEM.md` | mock 系统设计 |
| `docs/PRD_REPORT_PORTAL.md` | 【v1.1.1】报告门户 + 进度埋点 PRD（含验收标准） |
| `docs/PRD_ORCHESTRATION.md` | 总流程管控 |
| `docs/ADAPTER_SPEC.md` | 适配器接口规范 |
| `docs/RESEARCH_REPORT.md` | 业界调研报告 |
| `guides/01-17` | 17 篇技术指南（guide 11 含门户章节） |

## 端到端验证结果

mock 系统测试（8 条用例）：
- 诊断 14 条（F3.1/F4.4/F5.3/F6.1/F7.3/F7.4/F8.1/F8.2/F8.4）
- 质量分：0.88 → 0.99（apply 后）
- mutation 检出率：42%
- 新增 9 条用例填补 spec 缺口

v1.1.1 验证：
- sidecar → progress_tracker pipeline：3 个 step 事件 session_id 续接正确，timeline 正确计算 duration_ms
- report_portal.py：44KB 门户 HTML，5 页全部有数据（8 报告 / 1 session / 1 迭代 / 12 维质量分）
- generate_report.py：31KB HTML，3 张 SVG 图表 + 9 tooltip + 8 hover 规则
- case_iteration_report.py：41KB HTML，3 张 SVG 图表 + 51 tooltip，深色玻璃态与门户一致

## 架构原则

1. **脚本零 LLM**：所有脚本不调外部 LLM，创造性工作由 Agent 完成
2. **prompt 在子 skill**：生成性 prompt 在 `skills/*/SKILL.md`，不埋在脚本里
3. **桥接而非重写**：4 阶段流水线通过 excel_to_uatr 接入 eval loop
4. **双闭环**：prompt 自优化 + 用例自优化正交运行
5. **向后兼容**：新增字段旧用例无也能跑

## 业界对标

| 来源 | 借鉴点 |
|------|--------|
| Meta ACH (arXiv 2501.12862) | Mutation kill matrix |
| Opik HRPO | 根因分析迁移到用例 |
| DeepEval Synthesizer | Golden→TestCase 分层 |
| test-design-agent-raw | UC 15 字段 + testspec 4 表 + 16 自检 |
| ISO 25010 / IEEE 829 | 质量标准 |

**业界空白**：有 prompt 自优化，无 test-case 自优化产品化。V1.1 填补此空白。
