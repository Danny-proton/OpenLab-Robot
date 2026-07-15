# 报告模板：Failure Analysis

这个模板用于深度失败分析报告。

## 失败概览

本轮共 {{ n_failed }} 条 case 失败，按类型分布：

| 失败类型 | 数量 | 占比 | 代表 case |
|---------|------|------|----------|
{{ failure_table }}

## 逐类分析

{{ per_type_analysis }}

## 根因

{{ root_cause }}

## Mutation 建议

{{ mutation_suggestions }}

## 预期修复后效果

{{ expected_improvement }}
