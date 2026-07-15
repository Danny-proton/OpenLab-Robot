# PRD — 开发进展与路线图

## 总体状态

| 模块 | 状态 | 完成度 |
|------|------|--------|
| 测试执行（eval_runner + adapter） | ✅ 已完成 | 100% |
| UATR Trace（24 类事件 + normalizer） | ✅ 已完成 | 100% |
| 评分（5 硬 + 3 软 + TRACE 五维） | ✅ 已完成 | 100% |
| 失败归因（F1-F8 + HRPO 4 层） | ✅ 已完成 | 100% |
| 多 Judge 评审（9 agent + agreement） | ✅ 已完成 | 100% |
| HTML 报告（11 节 + 9 SVG + 调用结构） | ✅ 已完成 | 95%（PDF 有 format bug） |
| Dashboard（10 页交互式） | ✅ 已完成 | 100% |
| reference 自动注入（8 模板） | ✅ 已完成 | 100% |
| auto_patcher 全自动循环 | ✅ 已完成 | 100% |
| CI 持续回归 | ✅ 已完成 | 100% |
| Excel 适配器 | ✅ 已完成 | 100% |
| 用例生成子 skill（需求分析 + 用例设计） | ✅ 已完成 | 80%（10 维度 prompt 已写，待增强 spec 解析） |
| 测试设计详细流程（spec 解析/因子提取/方法库） | 🔨 设计中 | 30%（架构已定，待实现） |
| 测试用例自优化 | 🔨 设计中 | 20%（F1-F8 分布分析已实现，迭代流程待实现） |
| 总流程管控（进度监控/可视化/归档） | 🔨 设计中 | 40%（sidecar 已有，其余待实现） |
| DeepEval/Opik 集成 | ✅ adapter 已有 | 60%（fallback 实现，真实集成待测试） |

---

## 详细进展

### ✅ 已完成

#### 1. 测试执行
- eval_runner.py：跑 case → 调 adapter → 写 trace + scores + HTML
- adapter 机制：mock / http / openlab_robot（subprocess + stream-json）
- scaffold：一键初始化 .agent-eval/ 目录

#### 2. UATR Trace
- 24 类事件（agent/model/tool/memory/skill/planner/file/shell/browser/human/judge/optimizer）
- trace_normalizer.py：v0→UATR 自动转换 + 字段映射 + 脱敏
- 调用结构树：span_id / parent_span_id / arguments / result / latency

#### 3. 评分
- 5 硬指标：task_success / tool_correctness / business_rule_coverage / output_schema_validity / efficiency
- 3 软指标：answer_relevance / evidence_faithfulness / step_efficiency（占位）
- TRACE 五维：Trust / Reliability / Adaptability / Convention / Effectiveness
- 加权总分 + hard_fail_penalty

#### 4. 失败归因
- F1 Skill 触发失败
- F2 任务理解失败
- F3 工具选择失败（F3.1-F3.4）
- F4 工具参数失败（F4.1-F4.4）
- F5 Workflow 失败（F5.1-F5.4）
- F6 Memory 失败
- F7 输出失败（F7.1-F7.4）
- F8 执行冗余失败（F8.1-F8.4）— 核心：轮数过多/重复规划/探索式徘徊
- HRPO 4 层根因分析：现象→直接原因→根因→修复层

#### 5. 多 Judge
- 9 个标准 frontmatter agent（含 memory: project）
- 规则型 Judge（确定性，无 LLM 成本）
- Gatekeeper 5 条硬规则
- SafetyJudge 一票否决
- Judge Agreement Matrix

#### 6. 报告
- HTML 11 节 + 9 SVG（scorecard/scenario/heatmap/pareto/timeline/toolgraph/iteration/patch_matrix）
- trace 调用结构树 + 调用链详情表
- Dashboard 10 页
- PDF（weasyprint，有 format bug 待修）
- report_manager.py CRUD

#### 7. 优化
- reference_optimizer.py：8 个模板自动生成注入
- auto_patcher.py：全自动循环（生成→apply→A/B→评审→accept/reject）
- Gatekeeper：机械 5 条规则 + safety veto
- ci_regression.py：CI exit 0/1 + last_known_good

#### 8. 用例生成（mobile-bank-agent-eval）
- 大skill套小skill架构
- requirements-analysis 子 skill（10 维度 prompt）
- test-case-design 子 skill（agent-eval YAML 格式）
- case_io.py（YAML 读写，不调 LLM）
- excel_adapter.py（Excel→YAML 转换）

---

### 🔨 设计中 / 待实现

#### 9. 测试设计详细流程

**目标**：从 Agent PRD/SPEC + 代码扫描记忆 → 系统化生成高质量用例

**设计流程**：
```
输入：Agent PRD + SPEC + 代码扫描记忆
  ↓
1. 需求分解（功能点/非功能点/约束/边界）
  ↓
2. SPEC 解析（提取可测试的断言/规则/约束）
  ↓
3. 测试因子提取（等价类/边界值/状态迁移/正交实验）
  ↓
4. 测试方法库选择（根据因子类型选方法）
  ↓
5. 用例生成（方法 × 因子 → 具体用例）
  ↓
6. 格式化检查（YAML 格式/字段完整性）
  ↓
7. 用例自检（二义性/过长/DFX 覆盖/执行可行性）
  ↓
8. 输出 cases YAML
```

**待实现**：
- [ ] spec_parser.py — 从 PRD/SPEC 提取测试因子
- [ ] test_method_library.yaml — 测试方法库（等价类/边界值/状态迁移/正交/场景/决策表）
- [ ] case_quality_checker.py — 用例自检（二义性/完整性/DFX/执行可行性）
- [ ] 子 skill prompt 增强（spec 解析 + 因子提取指导）

**DFX 维度**：
- 性能：响应时间/吞吐量/资源占用
- 兼容：多模型/多平台/多版本
- 可靠：异常恢复/重试/幂等
- 安全：注入/越权/数据泄露
- 韧性：降级/熔断/限流
- 可服务：日志/监控/告警
- 可维护：配置/文档/代码结构

#### 10. 测试用例自优化

**目标**：完成一轮测试后，分析错误分布，迭代增强用例

**触发条件**：
- 一轮测试完成后（eval_runner + diagnoser 跑完）
- 用户手动触发（"优化用例"）
- CI 自动触发（regression 通过但分数下降）

**分析维度**：
1. **错误分布分析**：F1-F8 哪类失败集中？
   - F1-F2 集中 → 用例可能没覆盖到正确的任务类型
   - F3-F4 集中 → 用例的工具期望不够细
   - F7 集中 → 用例的断言关键词不够准
   - F8 集中 → 用例的 expected_steps 不合理

2. **spec 增强机会**：
   - 测试过程中发现了新的业务规则 → 加到 spec
   - 某个维度 0 用例 → 补用例
   - 某个维度通过率 100% → 可能用例太简单，加边界用例

3. **用例质量问题**：
   - SPEC 完整性：是否覆盖了 PRD 的所有功能点
   - 用例完整性：是否有前置条件/步骤/预期/断言
   - 功能点覆盖度：10 维度是否都有用例
   - DFX 覆盖度：性能/安全/兼容等是否有用例
   - 有效用例率：是否有过时/重复/不可执行的用例
   - 执行可行性：用例是否能实际跑通
   - 二义性：步骤/预期是否有歧义
   - 过长：用例是否过于复杂
   - 明确判断条件：断言是否可验证

**迭代流程**：
```
完成一轮测试
  ↓
分析错误分布（F1-F8 统计）
  ↓
识别 spec 缺口（哪些维度/规则没覆盖）
  ↓
识别用例质量问题（二义性/不完整/DFX 缺失）
  ↓
生成增强用例建议
  ↓
与人确认（哪些改动接受）
  ↓
更新 cases YAML
  ↓
下一轮测试
```

**待实现**：
- [ ] case_optimizer.py — 用例自优化脚本
- [ ] error_distribution_analyzer — F1-F8 错误分布分析
- [ ] case_quality_metrics.py — 用例质量指标计算
- [ ] 子 skill prompt（自优化指导）

#### 11. 总流程管控

**目标**：像 Opik 一样提供全流程管控能力

**功能清单**（参考 Opik）：

| 功能 | 状态 | 说明 |
|------|------|------|
| 用例沉淀 | ✅ | cases YAML + Git |
| 阶段报告存储 | ✅ | .agent-eval/reports/ |
| 进度监控 | ✅ | sidecar.py |
| 可视化 | ✅ | HTML 报告 + Dashboard |
| 调参 | 🔨 | config.yaml 权重/阈值可调，但缺 UI |
| Spec 归档 | 🔨 | requirements.yaml 已有，缺版本管理 |
| Agent 优化器选择 | ✅ | ask_setup.py --stage optimize |
| 测试用例自优化器 | 🔨 | 待实现（见上） |
| Agent 和用例的迭代控制 | 🔨 | auto_patcher 已有 agent 迭代，用例迭代待实现 |
| 黑/白/伪白盒用例管理 | 🔨 | 黑盒=HTTP ✅ / 伪白盒=trace ✅ / 白盒=代码扫描 🔨 |
| 执行进度管理 | ✅ | run_id + resume |
| 可选择测试方法 | 🔨 | 测试方法库待实现 |
| 测试 spec 沉淀 | 🔨 | 待实现 |

#### 12. DeepEval/Opik 集成

**DeepEval**：
- adapter 已有（deepeval_adapter.py）
- fallback 模式已实现
- 真实集成待测试（需 pip install deepeval）

**Opik**：
- adapter 已有（opik_adapter.py）
- HRPO fallback 已实现
- MetaPrompt/GEPA 真实集成待测试（需 pip install opik）

**集成策略**：外部优化器只生成候选，本地 Gatekeeper 决定接受

---

## 路线图

### v2.2（下一步）
- [ ] 修复 PDF 报告 format bug
- [ ] 实现 spec_parser.py（PRD/SPEC → 测试因子）
- [ ] 实现测试方法库（test_method_library.yaml）
- [ ] 实现 case_quality_checker.py（用例自检）
- [ ] 实现用例自优化（case_optimizer.py + error_distribution_analyzer）

### v2.3
- [ ] 白盒用例管理（代码扫描 → 用例生成）
- [ ] Spec 版本管理
- [ ] 调参 UI（配置权重/阈值的交互式向导）

### v3.0
- [ ] 真实 DeepEval/Opik 集成测试
- [ ] 多项目评测看板
- [ ] 生产流量在线监控
