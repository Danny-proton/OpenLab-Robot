# Mobile Bank Agent Eval Skill

手机银行 Agent 自动评测 skill，基于 agent-eval 主轴补充用例生成和执行能力。

## 核心能力

- **4 阶段流水线**: 需求分析 → 用例生成 → 测试执行 → 报告生成
- **10 个测试维度**: 业务场景/流程/角色/规则/输入/安全/多轮/异常/性能/合规
- **3 种执行模式**: mock / HTTP / OpenLab Robot (cc-haha)
- **UATR trace**: 含调用结构（span_id / 参数 / 结果 / 延迟）
- **失败归因**: F1-F8 分类
- **专业 HTML 报告**: 汇总卡片 + 维度分析 + 调用结构树 + 响应时间
- **mock LLM fallback**: 无 API key 全流程可跑通
- **4 个标准 Agent**: requirements-analyst / test-case-designer / test-executor / report-writer

## 快速开始

```bash
# 1. 复制到 skills 目录
cp -r mobile-bank-agent-eval .claude/skills/

# 2. 跑完整流水线（mock 模式，无需 API key）
SKILL_PATH=.claude/skills/mobile-bank-agent-eval
python $SKILL_PATH/scripts/generate_requirements.py \
  --description "手机银行助手：账户查询、转账、理财、信用卡" \
  --output $SKILL_PATH/data/requirements_analysis.xlsx

python $SKILL_PATH/scripts/generate_testcases.py \
  --input $SKILL_PATH/data/requirements_analysis.xlsx \
  --output $SKILL_PATH/data/test_cases.xlsx --per-scenario 3

python $SKILL_PATH/scripts/execute_testcases.py \
  --input $SKILL_PATH/data/test_cases.xlsx \
  --output $SKILL_PATH/data/execution_results.xlsx --mock

python $SKILL_PATH/scripts/generate_report.py \
  --requirements $SKILL_PATH/data/requirements_analysis.xlsx \
  --testcases $SKILL_PATH/data/test_cases.xlsx \
  --results $SKILL_PATH/data/execution_results.xlsx \
  --trace $SKILL_PATH/data/trace.jsonl \
  --output $SKILL_PATH/data/test_report.html

# 3. 打开报告
open $SKILL_PATH/data/test_report.html
```

## 与 mobileAgentTest 原版对比

| 维度 | 原版 | 本版 |
|------|------|------|
| Skill 格式 | OpenCode 自定义 | Claude Code 标准 frontmatter |
| 测试维度 | 6 个 | **10 个**（+多轮/异常/性能/合规） |
| 用例生成 | 单轮 | **多轮 + 状态迁移** |
| 执行模式 | 仅 HTTP | **mock + HTTP + OpenLab Robot** |
| LLM 依赖 | 必须有 API key | **mock fallback** |
| Trace | 无 | **UATR 含调用结构** |
| 报告 | 基础 HTML | **HTML + 调用结构树 + 失败归因** |
| Agent | 无 | **4 个标准 frontmatter agent** |
| 断言 | 无 | **5 种断言类型** |

## 目录结构

```
mobile-bank-agent-eval/
├── SKILL.md
├── README.md
├── scripts/
│   ├── common.py                    # 共享工具 + mock LLM
│   ├── generate_requirements.py     # 阶段1
│   ├── generate_testcases.py        # 阶段2
│   ├── execute_testcases.py         # 阶段3
│   └── generate_report.py           # 阶段4
├── agents/                          # 4 个标准 agent
│   ├── requirements-analyst.md
│   ├── test-case-designer.md
│   ├── test-executor.md
│   └── report-writer.md
├── guides/                          # 5 篇文档
├── examples/.mobile-eval/           # 示例配置
└── data/                            # 运行产物
```

## 依赖

- Python 3.9+
- PyYAML（可选，配置文件用）
- openpyxl（可选，Excel 读写；无则 fallback CSV）
- requests（可选，HTTP 执行模式）

无任何依赖也能跑（mock 模式 + CSV fallback）。

## License

MIT
