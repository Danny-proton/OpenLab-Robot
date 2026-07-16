---
name: dom-agent/verdict-judge
description: 结果判定技能。对比操作执行结果与预期结果，判定测试步骤是否通过，生成验证报告。
version: V1.0
---

# 结果判定

> 基于执行结果与预期结果的对比，判定测试步骤的通过/失败状态。

---

## 一、判定框架

```
输入:
  - 预期结果: 测试步骤中定义的 expected outcome
  - 实际结果: action-schedule 输出的操作执行结果 + 截图
  - 页面状态: 操作后的快照/截图内容

判定流程:
  1. 提取预期结果中的关键断言点
  2. 对比实际结果与每个断言点
  3. 综合所有断言得出判定结论
  4. 生成判定报告
```

---

## 二、判定维度

### 2.1 页面级判定

| 维度 | 判定方式 | 通过标准 |
|------|---------|---------|
| 页面导航 | 对比实际 URL 与预期 URL | URL 匹配 |
| 页面标题 | 对比 document.title | 标题包含预期关键词 |
| 元素存在 | snapshot 中是否包含目标元素 | 目标元素 uid 存在 |
| 元素状态 | 检查元素 value/checked/enabled | 值与预期一致 |
| 弹窗出现 | snapshot 中出现 dialog/modal | 弹窗包含预期内容 |
| 错误提示 | snapshot 中出现错误文本 | 无预期外的错误 |
| 空白页 | 页面内容为空 | 页面有实质内容 |

### 2.2 截图视觉判定

| 维度 | 判定方式 |
|------|---------|
| 页面渲染 | 截图中的页面内容与预期一致 |
| 错误提示 | 截图中的错误信息可辨识 |
| 操作反馈 | 截图中的操作结果（如选中、填写）可验证 |
| 页面异常 | 截图中的页面异常（空白、报错）可识别 |

---

## 三、判定流程

### 3.1 单步判定

```
步骤:
  1. 获取操作后的 snapshot（action-schedule 已记录）
  2. 获取操作后的截图（action-schedule 已保存）
  3. 提取关键信息:
     - 页面 URL/title
     - 相关元素的 value/checked
     - 是否有弹窗
     - 是否有错误提示
  4. 对比预期结果
  5. 输出 PASS/FAIL/NEED_VISUAL_CHECK
```

### 3.2 视觉判定补充

```
当 snapshot 无法完全验证时:
  1. 重新 take_screenshot（保存验证截图）
  2. 通过截图视觉检查:
     - 表单字段是否显示预期值
     - 下拉框是否显示选中项
     - 按钮状态是否正确
     - 错误信息是否正确
  3. 记录视觉判定结果
```

### 3.3 辅助判定命令

```javascript
// 获取页面关键状态
function() {
  return {
    title: document.title,
    url: window.location.href,
    bodyText: document.body.textContent.trim().substring(0, 500),
    errorCount: document.querySelectorAll('.error, .err, [role="alert"]').length,
    dialogCount: document.querySelectorAll('dialog, .modal').length,
    inputValues: [...document.querySelectorAll('input, select, textarea')]
      .filter(el => el.offsetParent !== null)
      .slice(0, 10)
      .map(el => ({ tag: el.tagName, type: el.type, value: el.value, checked: el.checked }))
  };
}
```

---

## 四、判定输出格式

### 4.1 单步判定

```json
{
  "step_number": 3,
  "step_description": "填写用户名",
  "expected": "用户名字段显示 'testuser'",
  "actual": {
    "element_found": true,
    "element_value": "testuser",
    "element_uid": "3_24",
    "screenshot": "TC_001/step_03_fill_username.png",
    "visual_check": "截图确认字段显示正确值"
  },
  "verdict": "PASS",
  "confidence": "HIGH | MEDIUM | LOW",
  "notes": "可选说明"
}
```

### 4.2 整体判定

```json
{
  "test_case_id": "TC_001",
  "total_steps": 5,
  "passed": 5,
  "failed": 0,
  "skipped": 0,
  "overall_verdict": "PASS | FAIL | PARTIAL",
  "details": [
    { "step": 1, "verdict": "PASS" },
    { "step": 2, "verdict": "PASS" },
    ...
  ],
  "failures": [],
  "screenshots": [
    { "step": 1, "path": "TC_001/step_01_navigate.png" },
    { "step": 2, "path": "TC_001/step_02_fill_form.png" }
  ]
}
```

---

## 五、判定规则

1. **快照为主，截图为辅**: 优先通过 snapshot 验证，snapshot 无法确认时用截图辅助
2. **确定性判定**: value/checked 等明确属性判定为 PASS/FAIL
3. **视觉判定标注**: 截图判定标注为 NEED_VISUAL_CHECK，置信度为 MEDIUM
4. **错误优先**: 发现错误提示时，需判断是否为预期内的错误
5. **弹窗影响**: 未关闭弹窗时判定为 FAIL（操作未正常完成）
6. **完整性检查**: 所有步骤判定完成后汇总整体结果
7. **报告输出**: 判定结果必须输出结构化报告并保存到文件
