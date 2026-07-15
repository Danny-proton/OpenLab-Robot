# 报告模板：Iteration Analysis

这个模板用于多轮优化的迭代分析报告。

## 迭代历史

| 轮次 | Run ID | 加权总分 | 硬失败数 | Latency p50 | 决策 |
|------|--------|---------|---------|------------|------|
{{ iteration_table }}

## 趋势分析

{{ trend_analysis }}

## Patch 影响矩阵

| Patch | Task Success | Tool Recall | Business Rule | Regression Fail | Latency |
|------|-------------|-------------|---------------|-----------------|---------|
{{ patch_matrix }}

## 累积提升

从 baseline 到最终 accepted 版本：
- Task Success: {{ baseline_task_success }} → {{ final_task_success }} ({{ delta_task_success }})
- Tool Recall: {{ baseline_recall }} → {{ final_recall }} ({{ delta_recall }})
- 总接受 patch 数: {{ n_accepted }}
- 总拒绝 patch 数: {{ n_rejected }}

## 经验总结

{{ lessons_learned }}
