---
name: orchestrator
description: "编排子 skill。按用户需求依次执行四阶段脚本。"
---

# Orchestrator

按用户需求依次执行阶段。每个阶段用 `execute_script` 运行主 SKILL.md 中的命令，然后将工具返回的 stdout 文本原样输出。

阶段顺序：
1. 需求分析（requirements-analysis）
2. 用例生成（test-case-generator）
3. 用例执行（test-executor）
4. 报告生成（test-reporter）

如果前一阶段的产出文件已存在，则跳过直接进入下一阶段。
