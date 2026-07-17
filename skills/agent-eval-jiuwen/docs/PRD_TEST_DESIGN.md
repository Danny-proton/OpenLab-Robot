# 测试设计 PRD

## 输入

| 输入 | 格式 | 说明 |
|------|------|------|
| Agent PRD | 文本 | 产品需求文档 |
| Agent SPEC | 文本 | 技术规格 |
| 代码扫描记忆 | JSON | 工具列表/参数schema/Advisor链 |
| 历史 case | YAML | 已有用例（迭代时） |
| 历史错误 | JSON | 上轮 F1-F8 分布 |

## 8 阶段流程

1. **需求分解**：功能点/非功能点/约束/边界
2. **SPEC 解析**：工具列表/Advisor链/业务规则→可测试断言
3. **测试因子提取**：等价类/边界值/状态迁移/正交/决策表/场景法
4. **测试方法库选择**：根据因子类型选方法
5. **用例生成**：Agent 通过子 skill 自己生成
6. **格式化检查**：YAML格式/字段完整/id唯一
7. **用例自检**：9维度质量检查
8. **用例自优化**：错误分布分析→迭代增强

## DFX 覆盖

性能/兼容/可靠/安全/韧性/可服务/可维护

## 用例质量检查（9维度）

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

## 进度：75%（v2.3.0-mobile-bank 架构修正后）

- [x] 10维度框架
- [x] 子skill prompt（需求分析+用例设计）—— v2.3.0 prompt 从脚本移入子 skill 文字，Agent 用 Task 工具生成
- [x] case_io.py（YAML读写）—— 由 excel_to_uatr.py 桥接器承担（Excel→YAML）
- [x] excel_adapter.py（Excel→YAML）—— excel_to_uatr.py 实现
- [x] 4 阶段流水线接入 eval loop —— excel_to_uatr.py 桥接到 UATR trace + cases YAML
- [x] 脚本零 LLM —— v2.3.0 剥离 generate_requirements.py / generate_testcases.py 的 LLM 调用
- [ ] spec_parser.py（PRD/SPEC 解析）—— 扩展点：新增 skills/spec-parser/ 子 skill + 机械脚本
- [ ] test_method_library.yaml（方法库）—— 扩展点
- [ ] case_quality_checker.py（9 维度检查）—— test-case-generator 子 skill 第 5 步用 Task 工具实现
- [ ] 用例自优化闭环 —— 阶段 5-7 由主分支 diagnoser/multi_judge/auto_patcher 承担

## 架构原则（v2.3.0 新增）

- **脚本零 LLM**：`scripts/` 下任何脚本不得调外部 LLM API（OpenAI/DeepSeek/自建模型 URL 一律禁止）
- **prompt 在子 skill**：生成性 prompt 全部在 `skills/*/SKILL.md` 里以文字呈现，Agent 自己读、自己生成 JSON
- **Task 工具委派**：子 skill 指示 Agent 用 Task 工具 spawn 子 agent 生成结构化用例（场景多时并行）
- **桥接而非重写**：4 阶段 Excel 流水线通过 `excel_to_uatr.py` 接入主分支 eval loop，不复制诊断/优化逻辑
