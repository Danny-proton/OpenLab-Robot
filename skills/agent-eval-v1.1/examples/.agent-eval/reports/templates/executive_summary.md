# 报告模板：Executive Summary

这个模板用于 `.agent-eval/reports/templates/executive_summary.md`，
当用户想手动写一份给领导看的执行摘要时使用。

## 模板内容

本轮共评测 {{ n_cases }} 条 case，其中 train {{ n_train }} 条、
regression {{ n_regression }} 条、adversarial {{ n_adversarial }} 条。

总体 Task Success 从 {{ baseline_success_rate }}% 提升到 {{ candidate_success_rate }}%，
提升 {{ delta_pp }} 个百分点。

Required Tool Recall 从 {{ baseline_recall }}% 提升到 {{ candidate_recall }}%。

主要失败类型从 "{{ baseline_top_failure }}" 转移为 "{{ candidate_top_failure }}"。

Regression 集未发现 hard fail，{{ accept_recommendation }}。

## 关键指标

| 指标 | Baseline | Candidate | Delta |
|------|----------|-----------|-------|
| Task Success | {{ baseline_task_success }} | {{ candidate_task_success }} | {{ delta_task_success }} |
| Tool Correctness | {{ baseline_tool }} | {{ candidate_tool }} | {{ delta_tool }} |
| Business Rule | {{ baseline_rule }} | {{ candidate_rule }} | {{ delta_rule }} |
| Latency p50 | {{ baseline_latency }}ms | {{ candidate_latency }}ms | {{ delta_latency }}ms |

## 风险

{{ risk_summary }}

## 建议

{{ recommendation }}
