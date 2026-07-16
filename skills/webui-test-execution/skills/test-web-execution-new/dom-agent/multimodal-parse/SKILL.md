---
name: dom-agent/multimodal-parse
description: 多模态页面解析技能。从 a11y 快照、页面截图、DOM 结构中提取结构化信息，识别页面类型、元素状态和关键内容。
version: V1.0
---

# 多模态页面解析

> 从多源信息（文本快照、截图、DOM）中解析页面状态，为意图推理提供结构化输入。

---

## 一、解析数据源

| 数据源 | 工具 | 获取内容 | 用途 |
|--------|------|---------|------|
| a11y 快照 | `take_snapshot` | 页面文本树（元素 uid、标签、文本、属性） | 元素定位与状态识别 |
| 页面截图 | `take_screenshot` | 页面视觉渲染结果 | 视觉验证与错误识别 |
| 页面状态 | `evaluate_script` | DOM 数据、URL、标题、控制台 | 排查不在 a11y 树中的信息 |

---

## 二、解析流程

```
1. 获取快照: take_snapshot(verbose=false)
2. 获取截图: take_screenshot(filePath="...")
3. 解析快照: 提取页面结构、元素列表、当前状态
4. 补充信息: 通过 evaluate_script 获取不在快照中的信息
5. 输出结构化数据: 页面类型、关键元素、弹窗/错误状态
```

---

## 三、页面类型识别

### 3.1 常见页面类型特征

| 页面类型 | 识别特征 | 关键字段 |
|---------|---------|---------|
| 登录页 | 有 username/password 输入框 + 登录按钮 | 账号框、密码框、登录按钮 |
| 表单页 | 有表单字段（textbox/select/radio/checkbox）+ 提交按钮 | 字段列表、必填标记(*) |
| 列表页 | 有表格/卡片列表 + 翻页控件 | 行数据、页码、搜索框 |
| 详情页 | 有标题 + 详情展示区域 | 详情字段、操作按钮 |
| 弹窗 | snapshot 中出现 dialog/modal 元素 | 弹窗标题、关闭按钮 |
| 报错页 | snapshot 中出现错误提示文本 | 错误信息、重试按钮 |
| 空白页 | 快照中仅有 RootWebArea，无实质内容 | title 可能为空或加载中 |

### 3.2 空白页检测

```javascript
() => {
  const bodyText = document.body.textContent.trim();
  const inputCount = document.querySelectorAll('input').length;
  const buttonCount = document.querySelectorAll('button, [role="button"]').length;
  return {
    isEmpty: bodyText.length < 50 && inputCount === 0 && buttonCount === 0,
    hasInputs: inputCount,
    hasButtons: buttonCount
  };
}
```

---

## 四、元素状态解析

### 4.1 输入框状态

```
文本框 (textbox):
  - uid 标记: textbox
  - 关注: value 属性、placeholder、readonly

下拉框 (readonly textbox):
  - uid 标记: textbox, expandable, haspopup="menu"
  - 注意: 需用 click 展开 → click 选项，不能用 fill/evaluate_script

单选/复选框:
  - uid 标记: radio / checkbox
  - 关注: checked 属性
```

### 4.2 按钮状态

```
普通按钮:
  - uid 标记: button
  - 关注: enabled/disable, label 文本

可展开菜单:
  - uid 标记: button, expandable, haspopup="menu"
  - 注意: 展开后选项出现在 snapshot 底部
```

### 4.3 弹窗状态

```
模态弹窗:
  - snapshot 中出现: dialog, modal
  - 特征: 有关闭按钮 (X) 或确认/取消按钮
  - 处理: 必须关闭后才能继续操作

通知弹窗:
  - 特征: 短暂提示（如 "Operation successful."）
  - 处理: 自动消失，截图记录后继续
```

---

## 五、解析输出

```json
{
  "page_type": "form | list | detail | login | error | blank | other",
  "page_title": "页面标题",
  "page_url": "当前 URL",
  "elements": [
    { "uid": "1_5", "type": "textbox", "label": "字段名", "value": "", "required": true }
  ],
  "dialogs": [
    { "type": "modal", "title": "弹窗标题", "has_close_btn": true }
  ],
  "errors": [
    { "text": "错误提示信息", "location": "页面顶部" }
  ]
}
```

---

## 六、关键规则

1. **快照驱动**: 每次解析前必须 `take_snapshot`，uid 每次操作后可能变化
2. **截图辅助**: 截图用于视觉验证，不能替代快照中的结构化信息
3. **JS 补充**: 不在 a11y 树中的元素（SVG/隐藏 DOM）用 `evaluate_script` 补充
4. **弹窗优先**: 解析时先检查是否有未关闭的弹窗，弹窗会阻塞后续操作
5. **错误前置**: 发现错误提示优先处理，记录在 errors 数组中
