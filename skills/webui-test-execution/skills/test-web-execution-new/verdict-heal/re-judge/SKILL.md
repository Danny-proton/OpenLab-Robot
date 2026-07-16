---
name: verdict-heal/re-judge
description: 重新判定技能。在环境或脚本修复后，对同一测试步骤进行重新判定，确认真实测试结果。
version: V1.0
---

# 重新判定

> 在修复环境或脚本故障后，对原测试步骤进行重新判定，排除故障干扰后的真实测试结果。

---

## 一、重新判定触发条件

```
触发场景:
  - env-remediate 修复成功 → 重新判定
  - tool-remediate 修复成功 → 重新判定
  - script-remediate 修复成功 → 重新判定
  - fault-classify 判定为 MISMATCH → 直接重新判定

不触发场景:
  - 修复失败 → 标记步骤为 FAIL，进入下一步骤
  - 连续 2 次修复后仍失败 → 标记为 FAIL，记录原因
```

---

## 二、重新判定流程

```
输入: 修复后的操作步骤 + 原测试步骤的预期结果
输出: 修正后的判定结果

步骤:
  1. 读取修复结果（来自各 remediate skill）
  2. 执行修正后的操作序列
  3. 对每个操作:
     a. 执行操作
     b. 截图记录
     c. take_snapshot 验证
  4. 对比操作结果与原预期
  5. 输出重新判定结果
```

---

## 三、判定对比

### 3.1 与原判定对比

```
原判定结果: PASS/FAIL
修复后判定: PASS/FAIL

对比逻辑:
  - 原 PASS → 修复后仍 PASS: 无变化，确认为 PASS
  - 原 PASS → 修复后 FAIL: 重新判定有误，标记 NEED_REVIEW
  - 原 FAIL → 修复后 PASS: 修复成功，确认为 PASS
  - 原 FAIL → 修复后 FAIL: 修复未解决根因，返回 fault-classify 重新分类
```

### 3.2 判定输出

```json
{
  "step_number": 3,
  "original_verdict": "FAIL",
  "original_reason": "元素 uid 不存在",
  "remediation_skill": "tool-remediate",
  "remediation_result": "SUCCESS",
  "retry_operations": [
    {
      "tool": "click",
      "target_uid": "3_25",
      "screenshot": "TC_001/step_03_retry_fill_username.png",
      "result": "PASS"
    }
  ],
  "re_judged_verdict": "PASS",
  "confidence": "HIGH",
  "notes": "原故障为元素定位问题，修复后重新执行通过"
}
```

---

## 四、重试策略

```
重试次数:
  - 环境故障: 最多重试 1 次（修复后重新判定）
  - 工具故障: 最多重试 2 次
  - 脚本故障: 最多重试 2 次
  - 预期不符: 最多重试 1 次（重新判定）

连续失败处理:
  - 超过重试次数仍失败: 标记为 FAIL
  - 记录完整故障链: 原操作 → 分类 → 修复 → 重试 → 最终结果
```

---

## 五、关键规则

1. **必须验证**: 重新判定前必须确认修复已生效（take_snapshot 验证）
2. **截图记录**: 每次重试必须截图，与原始截图对比
3. **不隐藏失败**: 修复后仍失败的步骤如实标记为 FAIL
4. **完整记录**: 记录完整的故障链（原操作 → 分类 → 修复 → 重试 → 结果）
5. **不跳过步骤**: 即使修复后通过，也要完整执行所有操作步骤
6. **置信度标注**: 对重新判定结果标注置信度（HIGH/MEDIUM/LOW）
