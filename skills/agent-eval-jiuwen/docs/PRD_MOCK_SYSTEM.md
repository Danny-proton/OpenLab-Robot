# PRD — Mock 系统设计（V1.1）

> 本文档定义 V1.1 的 mock 系统，用于**端到端测试用例自优化流程**。
> mock 系统不真实调用 Agent，而是根据 case 配置机械生成 UATR trace，触发各类 F1-F8 失败，
> 让 case_optimizer / mutation_generator / case_iteration_report 能在没有真实 Agent 的情况下跑通。

## 1. 设计目标

1. **零外部依赖**：不调真实 LLM / 不依赖 HTTP 服务，纯 Python 机械生成 trace
2. **可控失败**：能按 case 配置触发 F3.1/F7.3/F8.2/F8.4 等各类失败
3. **覆盖自优化场景**：mock 产出的 trace 要能让 case_optimizer 检出"集中失败"、"覆盖缺口"、"质量低分"
4. **支持 mutation**：mutation_generator 在 mock trace 基础上做变异，再用 diagnoser 检查

## 2. 现有 mock 能力（common.py `_call_mock`）

| 触发条件 | 行为 | 产出失败 |
|---------|------|---------|
| case.id 以 `001` 结尾 + required 含 analyze_cashflow | 漏调 analyze_cashflow | F3.1 工具选择失败 |
| business_rules 含 missing_guarantee | final 不提"担保" | F7.3 漏业务规则 |
| case.id 以 `002` 结尾 | 工具前插 2 次多余 model_call | F8.2 重复规划 / F8.4 探索式徘徊 |
| 其他 | 调全工具 + 合规答案 | （成功） |

**问题**：现有 mock 只覆盖 3 类失败，不足以测试 case_optimizer 的全部场景（spec 缺口/质量低分/mutation survived）。

## 3. V1.1 mock 扩展

### 3.1 新增 mock 行为规则

| 规则 ID | 触发条件 | 行为 | 产出失败 | 用于测试 |
|---------|---------|------|---------|---------|
| mock_skip_tool | case.mock_config.skip_tool 字段 | 漏调指定工具 | F3.1 | 错误集中分析 |
| mock_wrong_param | case.mock_config.wrong_param 字段 | 工具参数传错 | F4.4 | 参数边界用例增强 |
| mock_empty_result | case.mock_config.empty_result 字段 | 工具返回空 | F5.3 | fallback 场景缺口 |
| mock_hallucinate | case.mock_config.hallucinate 字段 | final 编造数字 | F7.4 | 幻觉检测用例 |
| mock_redundant | case.mock_config.redundant_steps=N | 插入 N 次多余 model_call | F8.2/F8.4 | 效率断言增强 |
| mock_repeat_tool | case.mock_config.repeat_tool 字段 | 同工具重复 3 次 | F3.3 | repeat 断言增强 |
| mock_no_memory | case.expect_memory_use=true + mock_config.no_memory=true | 不调 memory_retrieval | F6.1 | 记忆覆盖缺口 |
| mock_success | 无 mock_config 或 mock_config.mode=success | 调全工具+合规答案 | （成功） | 100% 通过（过简单检测） |

### 3.2 case YAML 扩展字段

```yaml
cases:
  - id: loan_risk_001
    # ... 原有字段 ...
    mock_config:                    # 仅 mock adapter 用，真实 adapter 忽略
      mode: skip_tool               # skip_tool | wrong_param | empty_result | hallucinate | redundant | repeat_tool | no_memory | success
      skip_tool: analyze_cashflow   # mode=skip_tool 时指定漏调哪个
      wrong_param: {tool: queryCreditScore, field: id_card, value: applicant_name}
      empty_result: checkGuaranteeInfo
      hallucinate: "征信评分 850"    # final 里编造的数字
      redundant_steps: 4            # 插入 4 次多余 model_call
      repeat_tool: analyze_cashflow # 重复调用 3 次
```

### 3.3 mock 与 mutation 的区别

- **mock**：在 case YAML 里配置，**模拟被测 Agent 的固有行为**（这个 Agent 本身就会漏调工具）
- **mutation**：在 case_optimizer 阶段动态注入，**模拟变异 Agent 行为**（测试用例能否检出变异）

两者都产出 trace，但目的不同：mock 用于跑一轮评测，mutation 用于 kill matrix。

## 4. 测试用例集设计（覆盖自优化全部场景）

V1.1 的 `cases/train.yaml` 扩展到 8 条用例，覆盖所有自优化触发点：

| case_id | 场景 | mock 行为 | 产出失败 | 自优化触发 |
|---------|------|----------|---------|-----------|
| loan_risk_001 | 企业流水异常 | skip_tool=analyze_cashflow | F3.1 | 错误集中（F3） |
| loan_risk_002 | 正常通过 | redundant_steps=4 | F8.2/F8.4 | 错误集中（F8）+ 断言增强 |
| loan_risk_003 | 高负债 | success（但断言弱） | 无失败（过简单） | 过简单维度检测 |
| loan_risk_004 | 担保缺失 | empty_result=checkGuaranteeInfo | F5.3 | fallback 场景缺口 |
| loan_risk_005 | 工具参数边界 | wrong_param | F4.4 | 参数边界用例增强 |
| loan_risk_006 | 幻觉检测 | hallucinate="评分850" | F7.4 | 幻觉检测用例 |
| loan_risk_007 | 多轮上下文 | no_memory=true | F6.1 | 记忆覆盖缺口 |
| loan_risk_008 | 重复调用 | repeat_tool=analyze_cashflow | F3.3 | repeat 断言增强 |

预期自优化产出：
- 错误集中：F3（001/008）、F8（002）、F7（006）
- spec 缺口：DFR（可靠性）0 用例 → 需补
- 质量低分：断言可验证维度（多 case 缺 expected_tools 或 business_rules 可机器验证）
- mutation survived：mut_skip_tool 在 003/005/007/008 未检出 → 需增强

## 5. mock trace 生成逻辑（实现）

`common.py` 的 `_call_mock` 扩展：读取 `case.mock_config`，按 mode 分支生成 trace。

```python
def _call_mock(adapter, case, run_id, case_run_id):
    mc = case.get("mock_config") or {}
    mode = mc.get("mode", "default")
    
    if mode == "skip_tool":
        return _mock_skip_tool(case, mc, run_id, case_run_id)
    elif mode == "wrong_param":
        return _mock_wrong_param(case, mc, run_id, case_run_id)
    # ... 其他 mode
    
    # 默认逻辑（保留原有 001/002 规则）
    return _mock_default(case, run_id, case_run_id)
```

每个 mode 生成符合 UATR schema 的 trace 事件，确保 diagnoser 能正确归因。

## 6. 端到端测试流程

```bash
# 1. 初始化
python scripts/eval_runner.py --scaffold /tmp/test-v1.1
cp -r skills/agent-eval-v1.1/examples/.agent-eval/* /tmp/test-v1.1/.agent-eval/
# 替换 train.yaml 为 V1.1 的 8 条用例

# 2. 跑一轮评测（mock）
cd /tmp/test-v1.1
python $SKILL_DIR/scripts/eval_runner.py --config .agent-eval/config.yaml --split train --variant baseline --label "v1.1-test"

# 3. 诊断
python $SKILL_DIR/scripts/diagnoser.py --config .agent-eval/config.yaml --latest

# 4. 用例质量检查
python $SKILL_DIR/scripts/case_quality_checker.py --config .agent-eval/config.yaml --split train

# 5. mutation kill matrix
python $SKILL_DIR/scripts/mutation_generator.py --config .agent-eval/config.yaml --latest --split train

# 6. 用例自优化（生成建议）
python $SKILL_DIR/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train --dry-run

# 7. 用例自优化（apply）
python $SKILL_DIR/scripts/case_optimizer.py --config .agent-eval/config.yaml --latest --split train --apply

# 8. 迭代报告
python $SKILL_DIR/scripts/case_iteration_report.py --config .agent-eval/config.yaml --latest

# 9. 重跑评测（用更新后的 cases）
python $SKILL_DIR/scripts/eval_runner.py --config .agent-eval/config.yaml --split train --variant optimized --label "v1.1-opt"

# 10. 对比质量分
python $SKILL_DIR/scripts/case_quality_checker.py --config .agent-eval/config.yaml --split train
```

## 7. 验收标准

- [x] mock 能触发 F3.1/F3.3/F4.4/F5.3/F6.1/F7.3/F7.4/F8.2/F8.4 全部失败类型
- [x] 8 条测试用例覆盖所有自优化触发点
- [x] 端到端流程跑通无错误
- [x] apply 后重跑质量分提升（before < after）
- [x] mutation kill matrix 有 survived 变异被检出
- [x] 迭代报告 MD + HTML 正确生成
