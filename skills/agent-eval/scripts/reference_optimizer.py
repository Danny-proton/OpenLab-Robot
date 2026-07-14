#!/usr/bin/env python3
"""reference_optimizer.py — 自动生成并注入 reference 文件。

v1.1 的核心新能力。根据 HRPO 层次化分析结果，生成具体的 reference 文件
（执行路径 / 工具决策树 / 字段映射 / 行动约束等），并直接写到项目的
.agent-eval/agent_assets/ 目录，让 agent 下次运行时少走弯路。

为什么这个能力重要：
- 客户痛点是"笨模型跑十几轮"，根因往往是模型不知道最优路径
- reference 文件把"经验"固化下来，让模型一次走对
- 比 prompt 改动更稳（prompt 太长会污染），reference 按需加载

用法:
  # 基于 HRPO 分析生成 reference
  python reference_optimizer.py --config .agent-eval/config.yaml --run <run_id>

  # 基于 HRPO 分析生成 + 自动注入到 agent_assets
  python reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --apply

  # 只生成不 apply（默认）
  python reference_optimizer.py --config .agent-eval/config.yaml --run <run_id> --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


# ---------------------------------------------------------------------------
# reference 文件模板（每个对应一种 F8 子类或 F2-F7 的根因）
# ---------------------------------------------------------------------------

REFERENCE_TEMPLATES: dict[str, str] = {
    "execution_path.md": """# 执行路径 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：告诉 agent 每类任务的最优工具调用顺序，避免反复探索。

## 任务类型识别

接到贷款申请后，先识别任务类型：
- **个人贷款申请** → 走"个人贷款路径"
- **企业贷款申请** → 走"企业贷款路径"
- **贷后管理** → 走"贷后路径"

## 个人贷款路径（最优 7 步）

1. `loadLoanApplication(application_id)` — 加载申请
2. `queryCreditScore(id_card)` — 征信查询
3. `checkAntiFraud(id_card, amount)` — 反欺诈
4. `analyzeCashflow(application_id)` — 流水分析
5. `checkDebtRatio(id_card)` — 负债查询
6. `checkGuaranteeInfo(application_id)` — 担保查询
7. 综合判断 → 输出风险等级

## 企业贷款路径（最优 8 步）

1. `loadLoanApplication(application_id)` — 加载申请
2. `verifyBusiness(credit_code)` — 工商核验
3. `queryCreditScore(credit_code)` — 征信查询
4. `checkAntiFraud(credit_code, amount)` — 反欺诈
5. `analyzeCashflow(application_id)` — 流水分析
6. `checkDebtRatio(credit_code)` — 负债查询
7. `checkGuaranteeInfo(application_id)` — 担保查询
8. 综合判断 → 输出风险等级

## 硬约束

- **禁止跳过步骤**：每一步都必须执行，即使上一步结果看起来 OK
- **禁止重复调用**：同一工具同一参数只调一次
- **禁止反向调用**：必须先 loadLoanApplication 再查征信/流水/负债（因为需要 id_card）

## 判定规则（一步到位）

| 征信评分 | 流水波动 | 负债率 | 担保 | → 风险等级 |
|---------|---------|-------|------|-----------|
| < 650 | * | * | * | reject |
| >= 650 | > 0.3 | * | * | high |
| >= 650 | <= 0.3 | > 0.7 | * | high |
| >= 650 | <= 0.3 | <= 0.7 | 缺失 | high（建议补充材料）|
| >= 650 | <= 0.3 | <= 0.7 | 完整 | low/medium |
""",

    "act_after_decide.md": """# 行动约束 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：约束 agent "决策后立即执行"，避免连续思考不行动。

## 核心约束

**每次 model_call 后，必须立即跟一个 tool_call。**

禁止的模式：
```
model_call（我想想）→ model_call（我再想想）→ model_call（还是想想）→ tool_call
```

正确的模式：
```
model_call（决定调 X）→ tool_call(X) → model_call（看结果决定下一步）→ tool_call(Y)
```

## 例外情况

只有以下情况允许连续 model_call：
1. 解析 tool_result 的复杂返回（最多 1 次额外思考）
2. 生成最终答案（agent_final 前的总结）

## 自检规则

如果你发现自己连续思考超过 2 次没行动，立即问自己：
- "我现在应该调哪个工具？" → 调它
- "我是否已经拿到所有必需数据？" → 如果是，输出结论；如果否，调下一个工具

## 反模式清单

- ❌ "让我先分析一下任务" → 然后又"分析一下" → 然后又"分析一下"
- ❌ "我需要确认一下" → 然后又"确认一下" → 然后又"确认一下"
- ✅ "我需要确认申请详情" → 立即调 loadLoanApplication
""",

    "tool_usage_guide.md": """# 工具使用指南 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：每个工具的参数校验清单 + 结果字段说明，避免"调一次没拿到完整结果又调一次"。

## loadLoanApplication

**参数校验**：
- `application_id`：必填，格式 A001 / A002 等大写字母+数字

**结果字段**：
- `application_id` — 申请编号
- `applicant_name` — 申请人姓名
- `id_card` — 身份证号（后续查征信用）
- `amount` — 申请金额
- `term_months` — 期限
- `loan_type` — personal / enterprise
- `purpose` — 用途

**常见错误**：
- 传了小写 application_id → 工具返回 not_found
- 没拿 id_card 就去查征信 → 参数缺失

## queryCreditScore

**参数校验**：
- `id_card`：必填，18 位身份证号 或 18 位统一社会信用代码

**结果**：350-950 之间的整数
- < 650 → 高风险
- 650-720 → 中等
- > 720 → 良好

## analyzeCashflow

**参数校验**：
- `application_id`：必填

**结果**：0-1 之间的波动率
- > 0.3 → 高波动，高风险
- 0.2-0.3 → 中等
- < 0.2 → 稳定

## checkDebtRatio

**参数校验**：
- `id_card`：必填

**结果**：0-1 之间的负债率
- > 0.7 → 高负债，高风险
- 0.5-0.7 → 中等
- < 0.5 → 健康

## checkGuaranteeInfo

**参数校验**：
- `application_id`：必填

**结果**：
- `complete`：true/false
- `type`：property(抵押) / guarantor(担保人) / missing(缺失)

**重要**：`complete=false` 时，最终结论必须提示"建议补充材料"，禁止给出"通过"
""",

    "tool_decision_tree.md": """# 工具选择决策树 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：基于当前状态的 if-then 规则，让模型不用每次重新推理该调什么工具。

## 决策树

```
IF 还没加载申请详情:
    → 调 loadLoanApplication
    
ELIF 已加载申请 BUT 没查征信:
    → 调 queryCreditScore(id_card 从申请详情取)
    
ELIF 已查征信 BUT 没做反欺诈:
    → 调 checkAntiFraud
    
ELIF 已反欺诈 BUT 没分析流水:
    → 调 analyzeCashflow
    
ELIF 已分析流水 BUT 没查负债:
    → 调 checkDebtRatio
    
ELIF 已查负债 BUT 没查担保:
    → 调 checkGuaranteeInfo
    
ELIF 所有工具都调完:
    → 综合判定，输出风险等级 + 最终结论
    → 禁止再调任何工具
    
ELSE:
    → 异常状态，检查是否漏步骤
```

## 禁止的决策路径

- ❌ "我觉得流水有问题，再调一次 analyzeCashflow" → 重复调用
- ❌ "我先查一下负债再说" → 跳过流水分析
- ❌ "担保信息可能变了，再查一次" → 无理由重复

## 风险等级判定（查完所有数据后）

```
IF credit_score < 650:
    risk_level = "reject"
ELIF cashflow_volatility > 0.3 OR debt_ratio > 0.7:
    risk_level = "high"
    next = "human_review"
ELIF NOT guarantee_complete:
    risk_level = "high"
    next = "human_review"
    conclusion_must_include = "建议补充担保材料"
ELIF cashflow_volatility > 0.2 OR debt_ratio > 0.5:
    risk_level = "medium"
    next = "post_loan"
ELSE:
    risk_level = "low"
    next = "post_loan"
```
""",

    "field_mapping.md": """# 字段映射表 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：明确用户输入字段 → 工具参数字段的映射，避免传错参数。

## 申请详情字段映射

| 用户输入 / 申请详情字段 | 工具参数字段 | 说明 |
|------------------------|------------|------|
| `application_id` | `application_id` (loadLoanApplication) | 直接传 |
| `id_card` (从申请详情取) | `id_card` (queryCreditScore) | 必须先 loadLoanApplication 拿到 |
| `id_card` (从申请详情取) | `id_card` (checkDebtRatio) | 同上 |
| `credit_code` (企业申请) | `credit_code` (verifyBusiness) | 企业贷款时用 |
| `credit_code` (企业申请) | `id_card` (queryCreditScore) | 企业用同一字段查征信 |
| `application_id` | `application_id` (analyzeCashflow) | 直接传 |
| `application_id` | `application_id` (checkGuaranteeInfo) | 直接传 |
| `id_card` + `amount` | `id_card`, `amount` (checkAntiFraud) | 两个字段都必填 |

## 常见映射错误

- ❌ 把 `applicant_name` 当成 `id_card` 传给 queryCreditScore
- ❌ 企业贷款时把 `application_id` 传给 verifyBusiness（应该传 `credit_code`）
- ❌ checkAntiFraud 只传 id_card 忘传 amount
""",

    "output_format_template.md": """# 输出格式模板 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：约束最终答案的格式和必要内容。

## 风险审查结论格式

最终回答必须包含以下部分：

```
【风险审查结论】
风险等级: <low/medium/high/reject>

【关键指标】
- 征信评分: <数字>
- 流水波动: <数字> (高/中/低)
- 负债率: <数字> (高/中/低)
- 担保状态: <完整/缺失>

【风险点】
- <风险点1>
- <风险点2>（如无写"暂无明显风险点"）

【建议】
<通过/拒件/补充材料/人工复核> + 原因
```

## 必须包含的关键词

最终回答必须出现：`流水波动`、`负债`、`担保`（无论结果如何）

## 禁止行为

- ❌ 编造 trace 中没有的数字
- ❌ 给出结论但不引用 tool_result 数据
- ❌ 担保缺失时给出"通过"结论
""",

    "task_type_decision_tree.md": """# 任务类型决策树 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：帮助 agent 第一时间识别任务类型，走对路径。

## 任务识别决策树

```
IF 用户提到"贷款申请" OR "审批" OR "风险评估":
    IF 申请金额 > 0 AND 有企业名称:
        task_type = "企业贷款审查"
        path = "企业贷款路径"
    ELSE:
        task_type = "个人贷款审查"
        path = "个人贷款路径"
        
ELIF 用户提到"贷后" OR "还款" OR "监控":
    task_type = "贷后管理"
    path = "贷后路径"
    
ELIF 用户提到"补充材料" OR "重新申请":
    task_type = "复申请"
    path = "重新走审查路径"
    
ELSE:
    task_type = "未知"
    → 询问用户具体需求
```

## 阶段判断

识别任务类型后，还要判断当前阶段：
- **初审**：第一次审查，必须跑全工具
- **复审**：已一审，检查一审提出的问题是否解决
- **终审**：仅校验材料完整性，不重新分析
""",

    "memory_index.md": """# Memory 索引 Reference

> 本文件由 agent-eval reference_optimizer 自动生成。
> 作用：扩展 memory 检索索引，让 agent 能找到历史经验。

## 业务模块索引

| 场景关键词 | 检索关键词 | memory 内容 |
|-----------|-----------|------------|
| 流水异常 | `cashflow_volatility` | 近6个月波动>30%必须提示风险 |
| 担保缺失 | `missing_guarantee` | 担保缺失时结论必须是"补充材料" |
| 高负债 | `high_debt_ratio` | 负债率>70%必须提示风险 |
| 征信差 | `low_credit_score` | 征信<650直接拒件 |
| 多头借贷 | `multi_loan` | 反欺诈检测到多头借贷必须人工复核 |

## 检索触发条件

处理以下场景时，必须先调 retrieve_memory：
- 流水波动 > 0.3
- 负债率 > 0.7
- 征信评分 < 650
- 担保信息缺失
- 反欺诈返回 multi_loan

## 使用要求

retrieve_memory 后，memory_hits 中的关键信息必须：
1. 出现在最终回答中
2. 影响工具调用决策

禁止检索后忽略结果。
""",
}


# F8 子类 / 失败类型 → reference 文件名 映射
FAILURE_TO_REFERENCE: dict[str, str] = {
    "F8.1": "execution_path.md",
    "F8.2": "act_after_decide.md",
    "F8.3": "tool_usage_guide.md",
    "F8.4": "tool_decision_tree.md",
    "F2": "task_type_decision_tree.md",
    "F4": "field_mapping.md",
    "F6": "memory_index.md",
    "F7": "output_format_template.md",
}


def generate_references(diagnosis: dict, hrpo_result: dict | None = None) -> dict[str, str]:
    """根据诊断 + HRPO 分析，生成需要注入的 reference 文件内容。

    返回 {filename: content}。
    """
    needed_files: set[str] = set()

    # 从 HRPO root_cause_layers 提取
    if hrpo_result and hrpo_result.get("root_cause_layers"):
        for layer in hrpo_result["root_cause_layers"]:
            ref = layer.get("reference_to_inject")
            if ref:
                needed_files.add(ref)

    # 从诊断的 failure_type 提取（双保险）
    by_type: dict[str, int] = diagnosis.get("by_failure_type", {}) or {}
    for ft in by_type:
        # 先精确匹配 F8.x
        if ft in FAILURE_TO_REFERENCE:
            needed_files.add(FAILURE_TO_REFERENCE[ft])
        # 再模糊匹配 F2/F4/F6/F7
        elif ft[:2] in FAILURE_TO_REFERENCE:
            needed_files.add(FAILURE_TO_REFERENCE[ft[:2]])

    # 生成内容
    result: dict[str, str] = {}
    for fname in sorted(needed_files):
        if fname in REFERENCE_TEMPLATES:
            result[fname] = REFERENCE_TEMPLATES[fname]
    return result


def apply_references(cfg: C.EvalConfig, references: dict[str, str]) -> list[str]:
    """把 reference 文件写到 .agent-eval/agent_assets/ 目录。

    返回写入的文件路径列表。
    """
    assets_dir = cfg.root / "agent_assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for fname, content in references.items():
        path = assets_dir / fname
        path.write_text(content, encoding="utf-8")
        written.append(str(path.relative_to(cfg.root)))
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--apply", action="store_true", help="直接写入 .agent-eval/agent_assets/")
    ap.add_argument("--dry-run", action="store_true", help="只打印不写文件（默认）")
    ap.add_argument("--out", help="输出目录（默认 .agent-eval/patches/references/）")
    args = ap.parse_args()

    cfg = C.EvalConfig.load(Path(args.config).resolve())

    # 加载诊断
    diag_path = cfg.reports_dir / f"{args.run}_diagnosis.json"
    if not diag_path.exists():
        sys.stderr.write(f"诊断文件不存在: {diag_path}\n请先运行 diagnoser.py\n")
        return 2
    diagnosis = json.loads(diag_path.read_text(encoding="utf-8"))

    # 加载 HRPO 结果（如果有）
    hrpo_path = cfg.scores_dir / f"{args.run}.opik_hrpo.json"
    hrpo_result = None
    if hrpo_path.exists():
        hrpo_result = json.loads(hrpo_path.read_text(encoding="utf-8"))

    # 生成 reference
    references = generate_references(diagnosis, hrpo_result)
    if not references:
        print("[reference_optimizer] 无需生成 reference（没有 F8 或相关失败）")
        return 0

    print(f"[reference_optimizer] 生成 {len(references)} 个 reference 文件:")
    for fname in references:
        print(f"  - {fname}")

    if args.apply:
        written = apply_references(cfg, references)
        print(f"\n[reference_optimizer] 已写入 {len(written)} 个文件到 .agent-eval/agent_assets/:")
        for p in written:
            print(f"  - {p}")
        print("\n[reference_optimizer] 下一步：在 agent 的 system prompt 里增加引用：")
        print("  '处理任务前，必须先读 .agent-eval/agent_assets/<reference>.md'")
        print("  然后跑 A/B 验证：python abtest.py --baseline <baseline> --candidate-patch <references> --split regression")
    else:
        out_dir = Path(args.out) if args.out else (cfg.patches_dir / "references")
        out_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in references.items():
            (out_dir / fname).write_text(content, encoding="utf-8")
        print(f"\n[reference_optimizer] dry-run 模式，文件写到: {out_dir}")
        print("[reference_optimizer] 用 --apply 直接注入到 agent_assets/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
