# Agent 测试优化平台 · 业界调研报告

> 调研时间：2025 年
> 覆盖：测试用例自动生成 / 自优化 / 流程管控 / 优化器对比 / 测试设计 Skill 输入 / 用例质量检查
> 凡未在公开资料中明确找到的，均标注「未找到」

---

## 一、测试用例自动生成（Agent 领域）

### 1.1 业界怎么做的

#### (1) DeepEval 的 Synthesizer 机制（Confident AI，开源）
- **概念分层**：DeepEval 把测试资产分成两层：`Golden`（"待定测试用例"，含输入与期望结果，缺动态元素）→ 在评估时再转成 `LLMTestCase`。
- **Synthesizer 四步流水线**（官方文档 + Medium 实操）：
  1. **Input Generation**：在有无 context 的情况下合成 golden 的 input；
  2. **（输入演进/过滤）**：过滤掉合成质量差的输入；
  3. **Expected Output Generation**（被官方描述为"trivial one-step"，在最终合成前一步完成）；
  4. **合成 Golden**：组装成可评估样本。
- 支持单轮与多轮（ConversationSimulator，用 synthetic user 模拟对话）。
- 使用 critic model 做质量把关，可对接任意 LLM provider（model-agnostic）。
- 配合 `GEval`（研究背书的打分指标，基于 CoT + LLM-as-judge）做生成质量评估。

#### (2) Opik（Comet，开源）的 Dataset 管理
- **数据来源三种**：CSV 上传、SDK/API 写入、从生产 Trace 导出（把真实流量变成回归集）。
- **Experiment 机制**：Experiment 把 dataset items 与 traces 关联起来，形成"数据 → 执行 → 评估"的结构化链路；Dashboard 提供实验对比图表。
- **Dataset 版本/复用**：dataset 可被多个 experiment 复用，是优化器（MetaPrompt/HRPO/GEPA 等）的统一输入。

#### (3) 学术界 LLM-based Test Generation
| 论文/工具 | 来源 | 核心方法 |
|---|---|---|
| **CodaMosa** (ICSE'23, Lemieux 等) | CMU/Microsoft | 搜索式测试 (SBST) 跑到覆盖率平台期后，调用 Codex LLM 生成"跳板"输入以逃离平台期。混合 SBST + LLM。 |
| **ChatTester** (FSE'24, Yuan & Lou) | UIUC | 用 ChatGPT 自我改进生成的单测，比手写多产出 34.3% 可编译测试。强调 LLM 自批评循环。 |
| **ChatUniTest** (浙大 ZJU-ACES-ISE) | 开源 | LLM 生成 + 编译验证 + 修复的框架式单测生成。 |
| **TiCoder** (Microsoft Research) | 论文 | Test-Driven Interactive Code Generation，用测试做意图澄清（partial formalization）。 |
| **PRIMG** (arXiv 2505.05584) | — | mutation testing 引导 LLM 生成 Solidity 智能合约测试。 |
| **LLM4Fin** (华东师大) | PDF | 完全自动化的 LLM 测试用例生成，应用 BVA + 等价类划分策略保证覆盖。 |

#### (4) 测试因子提取方法（等价类/边界值/状态迁移/正交/决策表/场景法 在 LLM 时代）
- **Boundary Value Analysis + LLM**：arXiv 2501.14465《Boundary Value Test Input Generation Using Prompt Engineering with LLMs》评估 LLM 生成白盒边界值输入的能力。
- **等价类 + 边界值**：LLM4Fin 把这两类传统策略显式编码进 prompt，保证生成覆盖。
- MDPI Electronics 综述《Large Language Models for C Test Case Generation》明确指出 ECP（等价类划分）与 BVA 是 LLM 测试生成中最常被引用的两类黑盒策略。
- **状态迁移/正交/决策表/场景法**：未找到专门针对 LLM 时代的、与上面同等量级的代表性论文；目前业界多是把它们作为"测试设计知识"塞进 prompt（提示工程层面），缺乏系统化的 LLM 原生方法。**这是明显的空白区**。

#### (5) SPEC → 测试用例自动化
- **SPECMATE**（Fraunhofer/research）：从非正式 acceptance criteria 半自动建模生成测试，轻量建模（activity diagram / decision table）。
- **diva-portal 硕士论文**：用 GPT-4o 从汽车软件需求自动生成功能测试用例，并定义质量度量。
- **NVIDIA Developer Blog**《Building AI Agents to Automate Software Test Case Creation》：用 LLM agent 框架生成多类软件测试。
- **arXiv 2510.23350**：用 LLM 生成测试用例来验证形式化规约（formal spec）。
- **TestSprite**：从 PRD 解析生成 Playwright UI 测试。

### 1.2 关键能力清单
- [ ] **合成数据生成**：无种子也能合成 input/expected（DeepEval Synthesizer）。
- [ ] **多模态/多轮对话生成**：ConversationSimulator 类的 synthetic user 模拟。
- [ ] **数据集版本与复用**：dataset 作为 experiment/optimizer 的统一输入。
- [ ] **生产 trace 回采**：把真实流量转回归集（Opik trace export）。
- [ ] **传统测试因子 LLM 化**：等价类/边界值显式编码进 prompt 并验证有效性。
- [ ] **SPEC/PRD 解析**：自然语言/半形式化需求 → 结构化测试因子。
- [ ] **生成质量把关**：critic model / LLM-as-judge / 可编译性校验（ChatTester/ChatUniTest）。
- [ ] **覆盖率逃离**：SBST 平台期时用 LLM 注入新输入（CodaMosa 思路）。

### 1.3 我们的差距
- 缺少"Golden → TestCase"分层资产模型，测试数据与执行结果耦合较紧。
- 没有"Synthesizer 四步流水线"这种可插拔的合成框架；多依赖一次性 prompt 生成。
- 状态迁移/正交/决策表/场景法在 LLM 时代的方法学几乎是空白（业界也弱，但有先发机会）。
- 缺少从生产 trace 回采做回归集的能力。
- SPEC 解析多为整段 prompt，缺少"测试因子抽取 → 设计策略路由"的结构化管线。

---

## 二、测试用例自优化（迭代增强）

### 2.1 业界有没有"用例自优化"概念？谁在做？
- **直接以"test case self-optimization"命名产品：未找到**。但相关概念分散存在：
  - **Self-Improving LLM Agents at Test-Time**（arXiv 2510.07841）：测试时自改进，利用自身不确定预测。
  - **Gödel Agent**（OpenReview）：自指框架，agent 递归自改进，不依赖预设 routine。
  - **Arize "Self-Improving LLM Evaluation"**：feedback loop + few-shot + fine-tune 迭代精化评估。
  - **Opik 的 HRPO / GEPA**：本质是对 *prompt* 自优化，但其失败模式分析、变异反思的思路可迁移到 *测试用例* 自优化。
  - **Addy Osmani《Self-Improving Coding Agents》**：以"测试通过"为代理信号形成自愈循环。
- 结论：业界有"自优化 agent/prompt"的产品，但**没有把"测试用例"作为一等优化对象**的产品级实现——这是差异化机会。

### 2.2 测试用例质量度量标准
- **ISO/IEC 25010:2023** 产品质量模型：8 大特性（功能适合性 Functional Suitability、性能效率 Performance Efficiency、兼容性 Compatibility、交互可用性 Usability、可靠性 Reliability、安全性 Security、维护性 Maintainability、可移植性 Portability；2023 版新增/调整后含 9 大特性）。每特性下有子特性与度量项。ResearchGate 有"ISO 25010 Quality Measures Catalogue in Industrial Context"。
- **IEEE 829**：测试文档标准（测试计划、用例、规程、报告），可与 CI/CD 自动生成/报告对接。
- **TIOBE Quality Indicator**：基于 ISO 25010 的工业质量指标聚合。
- Agent 场景下业界常用：答案相关性、上下文精确率/召回率、幻觉率、轨迹正确性、工具调用正确性、任务完成率（Opik/DeepEval 内置指标族）。

### 2.3 覆盖率度量（Agent 场景怎么定义）
- **传统代码覆盖**：statement / branch / function / MC/DC（LaunchDarkly、Atlassian、SonarSource、web.dev 四种覆盖讲解）。
- **Agent 覆盖**（AutoExplore《Measuring AI agent coverage》）：把代码覆盖概念外推到 agent——分支覆盖 = 决策路径覆盖；并讨论 agent 特有的"行为覆盖"。
- **功能覆盖**：用例覆盖到的需求点/功能点比例。
- **轨迹覆盖 (Trajectory coverage)**：Opik 的 `Trajectory accuracy`、`Agent tool correctness` 指标隐含轨迹覆盖思想。
- 业界对 Agent 的"覆盖率"尚无统一标准定义，是活跃但未定型领域。

### 2.4 DFX 测试覆盖（性能/兼容/可靠/安全/韧性/可服务/可维护）
- **韧性/可靠性 (Resilience)**：**Chaos Engineering for AI Agents** 已成热点。
  - `deepankarm/agent-chaos`（GitHub）：向 agent 注入失败，配合 LLM-as-judge 评估。
  - Harness **AI Reliability Agent**：用 AI 自动化 chaos 工程。
  - arXiv 2511.07865《LLM-Powered Fully Automated Chaos Engineering》。
  - 实践：随机化 API 延迟/配额/错误响应，验证 agent 降级与恢复。
- **安全 (Security)**：DeepEval/Opik 内置 Moderation、Compliance risk、Prompt injection（red teaming）类指标；arXiv 2507.22133 做攻击 prompt 优化。
- **性能 (Performance)**：成本/延迟跟踪（Opik cost tracking、Langfuse）。
- **兼容/可服务/可维护**：**未找到**针对 Agent 的专门 DFX 覆盖框架；多沿用 ISO 25010 子特性 + 自定义指标。

### 2.5 错误分布分析驱动用例增强（mutation testing 思路）
- **Meta ACH 系统**（arXiv 2501.12862《Mutation-Guided LLM-based Test Generation at Meta》）：业界首个工业级 LLM mutation testing 部署；生成少量"模拟故障(mutant)"，看测试能否检出，反向驱动用例增强。Meta Engineering Blog 2025-09 有专文。
- **SMART**（arXiv 2603.24560）：提升 LLM 生成 mutant 的有效性与有效性。
- **PRIMG**：mutation 优先级引导 LLM 测试生成（智能合约）。
- arXiv 2406.09843：系统研究 LLM 在 mutation testing 中的表现。
- 思路迁移：把"变异测试"的 *kill matrix* 当作"错误分布"，驱动测试用例补强——这与"用例自优化"天然契合。

### 2.6 关键能力清单
- [ ] 用例质量度量基线（ISO 25010 子特性映射到 Agent 指标）。
- [ ] 多维覆盖率：功能/代码分支/轨迹/行为。
- [ ] Mutation-driven 用例增强（kill matrix → 补测）。
- [ ] DFX 专项覆盖：韧性(chaos)、安全(red team)、性能、兼容。
- [ ] 失败模式聚类分析（类 HRPO 的 root cause）。
- [ ] 自优化闭环：失败分析 → 用例补强 → 重跑 → 度量提升。

### 2.7 我们的差距
- 没有"用例自优化"作为显式产品概念（业界也没有，可抢占定义权）。
- 覆盖率只到功能层，缺轨迹/行为/mutation 覆盖。
- DFX 中韧性(chaos)、可服务、可维护几乎未覆盖。
- 缺少错误分布→用例增强的自动闭环（mutation 思路未落地）。

---

## 三、总流程管控（参考 Opik 功能）

### 3.1 Opik 的 Experiment 管理机制
- **Experiment = Dataset × Execution**：把 dataset items 与 traces 关联，每次评估产生一组 traces，结构化对比。
- **评估流程**：Define what good looks like（reference dataset 或 plain-text assertion）→ Opik 自动跑 → Surface errors → Dashboard 对比。
- **多轮/多智能体**：支持 Evaluate agent trajectories、multi-turn agents、Annotation Queues（人工标注队列）。
- **中断恢复**：Resume an interrupted evaluation。

### 3.2 Opik 的 Optimizer 选择（官方 Selection Matrix）
来源：`/docs/opik/development/optimization-runs/algorithms/overview`

| Optimizer | 来源 | 最适合 | 关键输入 | 备注 |
|---|---|---|---|---|
| **MetaPrompt** | Opik 自研 | 通用 prompt 精化 | Prompt + dataset + metric | reasoning LLM 批判并重写，支持 MCP 工具与 function schema |
| **HRPO** | Opik 自研 | 复杂 prompt 的根因分析 | 带 detailed reason 的 metric | 分批分析失败 → 综合主题 → 定向修复 |
| **Few-Shot Bayesian** | Opik 自研 | 优化 few-shot 示例集 | 含 demonstrations 的 dataset | 用 Optuna 选示例数量/顺序 |
| **Evolutionary** | Opik + DEAP | 探索多样 prompt 结构 | mutation/crossover 参数 | 多目标（分数 vs 长度），LLM 驱动遗传算子 |
| **GEPA** | 外部 (gepa-ai) | 单轮、重反思任务 | gepa 依赖 + reflection minibatch | Opik 做包装，保留其 Pareto 搜索 |
| **Parameter** | Opik 自研 | temperature/top_p 调参 | 参数搜索空间 | 不改 prompt，Bayesian(Optuna TPE) 两阶段搜索 + FANOVA 重要性 |

选择流程：①识别约束（措辞/工具/参数）→ ②检查 dataset 就绪度（reflection 类需 reason 字段）→ ③按矩阵选 → ④可链式（如 HRPO 找模式 → Parameter 调参）。

### 3.3 Langfuse 的 Trace 管理和 Score 机制
来源：Langfuse Scores Data Model 文档。
- **Score 数据模型**：每个 Score 精确关联 *之一* —— Trace / Observation / Session / DatasetRun。
- **Score 类型**：NUMERIC / CATEGORICAL / BOOLEAN / TEXT。
- **Score 来源**：`API`（SDK）、`EVAL`（自动评估器，如 LLM-as-Judge）、`ANNOTATION`（人工标注）。
- **ScoreConfig**：保证 score 遵循特定 schema（UI 或 API 定义），实现指标可复用与可比。
- **Trace 管理**：span 树结构，可按 error status / 低 feedback score 过滤；支持分布式 trace、media 附件、Agent Graph。
- **触发机制**：score/annotation 更新可触发 LLM-as-Judge evaluator（GitHub discussion #12499）。

### 3.4 测试 Spec 沉淀和版本管理
- **Opik Prompt Library**：prompt 版本控制（version control），prompt 作为一等资产沉淀。
- **Langfuse Datasets & Experiments data-model**：dataset run + experiment 的版本化。
- DeepEval：golden dataset 作为可版本化资产。
- 业界普遍把"spec/prompt/dataset"三者做版本化并互相关联，但**测试 spec（测试设计本身）的版本管理**相对弱，多依附于 prompt/dataset 版本。

### 3.5 黑盒/白盒/灰盒（伪白盒）用例管理业界实践
- **黑盒**：DeepEval Synthesizer、Opik dataset（从需求/trace 出发，不看内部）。
- **白盒**：CodaMosa（SBST + 代码覆盖）、ChatUniTest（编译验证）、mutation testing（Meta ACH）。
- **灰盒/伪白盒**：arXiv 2501.14465 用 LLM 生成"白盒边界值"但实际不深度依赖源码语义（伪白盒）；静态分析 + LLM（Semgrep/CodeQL 规则 + LLM 解释）属灰盒。
- 业界尚未形成"黑/白/灰三档用例统一管理"的标准实践，多为各做各的。**未找到**显式以"伪白盒"命名的方法学。

### 3.6 执行进度管理和可视化
- Opik Dashboard：optimization runs 进度、trial 历史、candidate 对比、failure mode 可视化。
- Langfuse：trace/span 树、score 时序、annotation queue。
- Optimization Studio（Opik no-code）：UI 配置 + 结果审阅。
- 通用：CI/CD 集成（DeepEval 跑成 pytest、Jenkins 触发、Slack 告警）。

### 3.7 关键能力清单
- [ ] Experiment = Dataset × Execution 的结构化关联。
- [ ] Optimizer 选择矩阵 + 链式编排。
- [ ] Score 三源（API/EVAL/ANNOTATION）+ ScoreConfig schema。
- [ ] Trace span 树 + 按错误/低分过滤。
- [ ] Prompt/Dataset/Spec 版本化与互相关联。
- [ ] 黑/白/灰盒用例分类管理。
- [ ] 执行进度 + 失败模式可视化。
- [ ] 中断恢复 + no-code studio。

### 3.8 我们的差距
- 缺少"Experiment"层抽象（数据/执行/评估三层解耦）。
- 优化器只有单一策略，没有选择矩阵和链式编排。
- Score 缺乏 schema 化与三源统一。
- 黑/白/灰盒用例无分类治理。
- 可视化止于执行结果，缺失败模式聚类视图。

---

## 四、优化器对比

### 4.1 Opik HRPO（Hierarchical Reflective Prompt Optimizer）
- **全称**：Hierarchical Reflective Prompt Optimizer（模块名 `hierarchical_reflective_optimizer`）。
- **算法**：
  1. 拉取评估结果，按 batch 分组并行分析失败样本；
  2. 每个 batch 用 LLM 做 *root cause analysis*（要求 metric 返回 `reason` 字段，这是关键依赖）；
  3. 跨 batch 综合失败主题；
  4. 针对每个根因生成 *surgical*（定向）prompt 修订；
  5. 迭代直到收敛。
- **适用**：已有几轮手工调优的复杂 prompt，想搞清"为什么挂"。
- **输入**：ChatPrompt + dataset + 带 reason 的 metric。
- **输出**：优化后 prompt + trial history + 失败模式分析。
- **成本**：中等（分批并行，但需 reason 字段，metric 设计成本高）。

### 4.2 Opik GEPA（Genetic-Pareto，外部包装）
- **论文**：arXiv 2507.19457《GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning》。
- **算法**：
  1. **Reflection**：采样轨迹（reasoning/tool calls/outputs），用自然语言反思诊断问题、提出并测试 prompt 更新；
  2. **Evolution**：在自身尝试的 *Pareto 前沿* 上组合互补经验；
  3. 语言作为可解释学习介质，远比稀疏标量 reward 信息密度高。
- **效果**：6 任务上平均超 GRPO 6%（最高 20%），rollout 少 35×；超 MIPROv2 10%+（AIME-2025 +12%）。
- **适用**：单轮任务（一输入一输出）、重反思、希望少 rollout 高收益。
- **输入**：单 system prompt + task model + reflection model + reflection_minibatch_size。
- **输出**：优化后 prompt + Pareto 前沿历史。
- **限制**：当前不支持 `optimize_tools=True`（工具描述优化降级）；只单轮。
- **成本**：低 rollout、高单次反思成本；适合预算紧但任务清晰。

### 4.3 Opik MetaPrompt
- **算法**：用 *reasoning LLM* 批判并重写初始 prompt，迭代精化措辞/结构/清晰度；每轮生成 N 个候选，按 metric 选优。
- **适用**：prompt 核心思路对、只是表达不够好的通用精化；支持 MCP 工作流与 tool schema。
- **输入**：Prompt + dataset + metric + n_samples。
- **输出**：精化 prompt + 候选历史。
- **成本**：低-中，最易上手。

### 4.4 DeepEval PromptOptimizer
- **定位**：基于 50+ 评估指标结果自动改 prompt，跑成 CI。
- **算法族（6 个）**：含 **COPRO**（Co-operative Prompt Optimizer，协作式，源自 DSPy）、**MIPROv2**（Multiprompt Instruction Proposal Optimizer v2，源自 DSPy《Optimizing Instructions...》）、**GEPA**（同上，进化+Pareto）等。LinkedIn 介绍：用遗传算法分析 eval feedback 自动重写，维持候选种群。
- **输入**：prompt + 评估指标（50+ 内置）+ 数据集。
- **输出**：优化 prompt + 评估对比。
- **适用**：已在 DeepEval 体系内、想把 prompt opt 接入 CI/CD 的团队。
- **成本**：随算法而异，GEPA 较省，MIPROv2/COPRO 中等。

### 4.5 对比总表
| 优化器 | 优化对象 | 核心机制 | 输入要求 | 适用场景 | 相对成本 |
|---|---|---|---|---|---|
| HRPO | system prompt | 分批根因分析 + 定向修复 | metric 必须带 reason | 复杂 prompt 排障 | 中 |
| GEPA | 单 system prompt | 反思 + Pareto 进化 | task+reflection model | 单轮重反思 | 低 rollout/中算力 |
| MetaPrompt | system prompt | reasoning LLM 批判重写 | prompt+dataset+metric | 通用精化 | 低 |
| Evolutionary | prompt 结构 | DEAP 选择/交叉/变异 | 种群/遗传参数 | 多目标/逃局部最优 | 中-高 |
| Few-Shot Bayesian | few-shot 示例 | Optuna 选数量/顺序 | demonstrations | 示例集优化 | 中 |
| Parameter | temperature/top_p | Optuna TPE + FANOVA | 参数搜索空间 | prompt 已定调参 | 低 |
| DeepEval PromptOptimizer | prompt | COPRO/MIPROv2/GEPA 等 | 50+ 指标 + 数据集 | DeepEval CI 体系内 | 随算法 |

### 4.6 关键能力清单
- [ ] 多优化器统一 API（`optimize_prompt` / `OptimizationResult`）。
- [ ] 选择矩阵（按约束/数据就绪度路由）。
- [ ] 优化器链式编排（HRPO → Parameter）。
- [ ] 失败根因分析能力（HRPO 类）。
- [ ] 反思 + Pareto 搜索（GEPA 类）。
- [ ] 多目标优化（Evolutionary 类）。
- [ ] 工具/参数联合优化（Parameter + tool schema）。

### 4.7 我们的差距
- 只有单一优化策略，缺选择矩阵和统一 API。
- 无根因分析驱动（HRPO 类）。
- 无 Pareto 多目标反思（GEPA 类）。
- 优化对象只到 prompt，未到 *测试用例/测试设计* 本身。

---

## 五、测试设计 Skill 的输入

### 5.1 "待测系统 Agent 的扫描记忆"是什么概念？业界类似？
- **业界直接对应概念：未找到**。"扫描记忆"是一个较新的提法，公开产品/论文中未见同名概念。
- **最接近的业界实践**：
  - **Agent Memory 系统**：MemGPT 类长期记忆、Opik/Langfuse 的 trace 历史沉淀（可视为"系统行为记忆"）。
  - **代码扫描快照**：静态分析 + LLM（arXiv 2506.10330、Semgrep+LLM、CodeQL 规则提取）把扫描结果结构化存档。
  - **Observability 回采**：Opik 把生产 trace 沉淀为 dataset，本质是"系统运行记忆"。
- **可定义为本平台概念**：把"对被测 Agent 的多次扫描/探活/trace 采集"结构化为一份可复用的"扫描记忆"（含接口签名、工具清单、典型轨迹、已知失败模式），作为测试设计 Skill 的上下文输入。

### 5.2 Agent PRD/SPEC 解析的自动化方法
- **TestSprite**：PRD → 解析需求 → 自动生成 Playwright 测试。
- **NVIDIA Blog**：LLM agent 框架解析需求生成多类测试。
- **diva-portal 论文**：GPT-4o 解析汽车软件需求生成功能用例 + 质量度量。
- **Spec-driven 工具**：BMAD、Spec-Kit、OpenSpec（ranthebuilder 评测对比，13 维评分）。
- **Test-Driven AI Agent Definition (TDAD)**（arXiv 2603.08806）：TestSmith 把 spec YAML 编译成可执行测试。
- 通用做法：把 PRD 当结构化文档（角色/实体/动作/触发/工作流），用 LLM 抽取这些槽位（Medium《Automated Test Case Creation from Requirements Using NLP》）。

### 5.3 从代码扫描提取测试因子的方法
- **静态分析 + LLM**（arXiv 2506.10330）：静态框架先检出 bug/漏洞/smell，LLM 再做语义增强。
- **Semgrep + LLM**（Semgrep AI 团队）：语法扫描不替代，LLM 补语义判断。
- **CodeQL 规则 + LLM**（bykologlu 工具）：从 CWE/CodeQL 抽规则送 LLM 分析。
- **AST + LLM**：解析函数签名/分支/输入域 → 喂 LLM 生成等价类/边界值（arXiv 2501.14465 白盒边界值）。
- 关键：纯 LLM 代码分析假阳性高，**静态分析提供精确锚点 + LLM 提供语义生成**是主流组合。

### 5.4 测试方法库的设计（业界有没有标准化测试方法库？）
- **标准化测试方法库：未找到** LLM 时代的统一标准库。
- 现存相关：
  - **测试设计模式目录**（refactoring.guru 式 catalog，QA 自动化 Page Object/Builder 等）。
  - **Test Idea Catalogs**（Chris Kenst，测试启发式思路集）。
  - **SEI Testing Taxonomy**（CMU SEI，按 what-based/when-based 分类测试类型）。
  - **DeepEval 50+ 指标库**、**Opik 内置指标族**（hallucination、G-Eval、context precision/recall、trajectory accuracy 等）——这是"评估方法库"而非"测试设计方法库"。
- 传统黑盒方法学（等价类/边界值/状态迁移/正交/决策表/场景法/因果图）散见于 ISTQB 教材，**无 LLM 原生的标准化方法库**。这是可建库的机会。

### 5.5 关键能力清单
- [ ] "扫描记忆"结构化（接口/工具/轨迹/失败模式四元组）。
- [ ] PRD/SPEC 槽位抽取（角色/实体/动作/触发/工作流）。
- [ ] 静态分析锚点 + LLM 语义生成组合。
- [ ] 测试方法库（传统七法 + Agent 专项：trajectory/工具调用/red team/chaos）。
- [ ] 方法→因子→用例的路由策略。

### 5.6 我们的差距
- "扫描记忆"概念尚未定义与落地（业界空白，需自建）。
- PRD 解析为整段 prompt，缺槽位化抽取。
- 代码扫描与 LLM 未组合（要么纯静态，要么纯 LLM）。
- 无标准化测试方法库，方法选择靠人。

---

## 六、用例质量检查

### 6.1 用例二义性检测（NLP 方法）
- **需求二义性检测 NLP 工具对比**（ceur-ws Vol-3122《Using NLP Tools to Detect Ambiguities in System Requirements - A Comparison Study》）：对比多种 NLP 工具在需求二义性检测上的效果。
- **Pragmatic Ambiguity Detection**（IJISAE 2681）：语用二义性检测。
- **Automated Repair of Ambiguous Requirements**（arXiv 2505.07270）：全自动修复二义需求，证明可端到端自动修。
- **Ambiguity Identification and Measurement**（ResearchGate）：三个实验评估 NLP 工具对二义性的识别质量。
- **The Case for Ambiguity Detection in NLI**（arXiv 2507.15114）：从自然语言推理分歧角度建模二义性。
- 方法：词义消歧、依存分析、语用推理、LLM-as-judge 投票分歧检测。

### 6.2 用例完整性检查标准
- **ISO 25010 Functional Suitability**：完整性 (Completeness) 是子特性之一。
- **IEEE 829**：用例必备字段（ID/输入/预期/前置/后置/步骤）。
- **Acceptance Criteria 最佳实践**（VirtuosoQA）：须覆盖 happy path、error、boundary、integration、performance。
- 业界把"完整性"落在字段齐全 + 覆盖维度齐全两层面。

### 6.3 用例执行可行性验证
- **直接以"test case feasibility validation"命名的产品/论文：未找到**。
- 间接实现：
  - **ChatUniTest**：编译 + 运行验证生成用例可执行性（feasibility 的工程实现）。
  - **CodaMosa**：可执行性作为 SBST 的内置约束。
  - **DeepEval**：生成后跑实际 pipeline 拿 actual_output，隐含可行性验证。
- 这是工程上靠"跑一遍"实现，缺独立的方法学。

### 6.4 用例过长检测
- **专门针对"用例过长"的检测方法/产品：未找到**。
- 间接：Evolutionary Optimizer 支持"score vs prompt length"多目标（可迁移到用例长度）；DeepEval/Opik 的 token 计数与成本跟踪可作长度代理。
- 这是可用简单启发式（步骤数/token/分支深度阈值）补齐的点。

### 6.5 SPEC 完整性度量
- **ISO 25010 + IEEE 829** 提供字段级完整性。
- **Requirements Quality Metrics** 研究（Fraunhofer IESE 用 LLM 生成用例并评估需求质量）。
- **TIOBE Quality Indicator** 把 ISO 25010 聚合成可量化指标。
- 学术：diva-portal 论文定义了从需求到用例的质量度量。
- 业界缺 Agent SPEC 专用的完整性度量（多沿用软件需求质量指标）。

### 6.6 关键能力清单
- [ ] 二义性自动检测（NLP + LLM 投票分歧）。
- [ ] 二义性自动修复（arXiv 2505.07270 思路）。
- [ ] 完整性检查（字段 + 覆盖维度双校验）。
- [ ] 可执行性验证（编译/试跑）。
- [ ] 过长检测（步骤/token/分支深度阈值）。
- [ ] SPEC 完整性度量（字段率 + 覆盖率 + 质量分）。

### 6.7 我们的差距
- 二义性检测未引入 NLP/LLM 投票分歧方法。
- 完整性靠人工 review，无字段+维度双校验自动化。
- 可执行性靠"跑一遍"，无独立预检。
- 过长检测缺失（易补）。
- SPEC 完整性无量化度量。

---

## 七、总结与建议

### 7.1 业界全景一句话
**测试生成成熟（DeepEval/Opik/CodaMosa）→ 流程管控成型（Opik Experiment/Langfuse Score）→ 优化器丰富（HRPO/GEPA/MetaPrompt 六件套）→ 但"测试用例自身"的自优化与质量度量仍是空白。**

### 7.2 三个最大差距（高优先补齐）
1. **"用例自优化"产品化**：业界有 prompt 自优化（HRPO/GEPA）但无 test-case 自优化。把 HRPO 的根因分析 + mutation testing 的 kill matrix 迁移到测试用例，形成"失败分析 → 用例补强 → 重跑 → 度量"闭环，可抢占定义权。
2. **测试设计方法库 + 选择路由**：传统七法（等价类/边界值/状态迁移/正交/决策表/场景法/因果图）在 LLM 时代无标准库，业界也弱。建库 + 按因子自动路由是差异化壁垒。
3. **黑/白/灰（伪白盒）三档用例统一管理 + 多维覆盖率**：业界各做各的，缺统一框架。把轨迹覆盖/行为覆盖/mutation 覆盖纳入，配合 chaos(red team/韧性) 补 DFX。

### 7.3 可直接复用的业界组件
- **资产模型**：DeepEval 的 Golden→TestCase 分层；Opik 的 Experiment=Dataset×Execution。
- **Score 模型**：Langfuse 三源(API/EVAL/ANNOTATION)+ScoreConfig schema。
- **优化器**：HRPO（根因）、GEPA（反思+Pareto）、MetaPrompt（通用）直接可借鉴 API 设计。
- **mutation 思路**：Meta ACH 系统的 kill matrix → 补测。
- **二义性修复**：arXiv 2505.07270 的端到端自动修复。

### 7.4 需自建（业界空白）
- "扫描记忆"结构化概念。
- 测试用例自优化闭环。
- LLM 原生测试方法库 + 路由。
- Agent 场景覆盖率标准（轨迹/行为/mutation）。
- Agent DFX 覆盖（韧性 chaos 已有开源雏形 agent-chaos，可接入）。

---

## 附：关键资料索引
- DeepEval Synthesizer：https://deepeval.com/docs/golden-synthesizer
- Opik 优化器总览：https://www.comet.com/docs/opik/development/optimization-runs/algorithms/overview
- Opik HRPO：https://www.comet.com/docs/opik/development/optimization-runs/algorithms/hierarchical_adaptive_optimizer
- Opik GEPA：https://www.comet.com/docs/opik/development/optimization-runs/algorithms/gepa_optimizer
- GEPA 论文：https://arxiv.org/abs/2507.19457
- Langfuse Scores Data Model：https://langfuse.com/docs/evaluation/scores/data-model
- CodaMosa：https://arxiv.org/html/2503.14000v1
- ChatTester：https://mingwei-liu.github.io/assets/pdf/FSE24_chatTester_cameraReady.pdf
- Meta ACH mutation：https://arxiv.org/abs/2501.12862
- BVA+LLM：https://arxiv.org/html/2501.14465v1
- SPECMATE：https://www.sciencedirect.com/science/article/abs/pii/S095058492500268X
- 二义性修复：https://arxiv.org/html/2505.07270v1
- agent-chaos：https://github.com/deepankarm/agent-chaos
