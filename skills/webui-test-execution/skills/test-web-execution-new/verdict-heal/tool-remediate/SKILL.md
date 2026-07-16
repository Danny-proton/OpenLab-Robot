---
name: verdict-heal/tool-remediate
description: 工具修复技能。处理工具类故障（元素定位失败、操作无响应、MCP 工具调用失败等），提供替代方案和修复策略。
version: V1.0
---

# 工具修复

> 针对工具类故障进行修复，包括元素定位失败、操作无响应、工具不可用等场景。

---

## 一、修复场景

### 1.1 元素不存在（uid 找不到）

```
场景: snapshot 中找不到目标元素的 uid
修复:
  1. 重新 take_snapshot 确认元素是否已变化
  2. 检查元素是否在下拉展开/折叠面板展开后出现
  3. 检查元素是否在 iframe 中（click/fill_form 会自动跨 iframe）
  4. 检查元素是否为 SVG（SVG 元素不在 a11y 树中，无 uid）
  5. 如果是 SVG 元素，用 evaluate_script 定位并点击:
     function() { document.querySelector('.svg-class').click() }
```

### 1.2 元素不可见

```
场景: 元素存在但操作无响应
修复:
  1. 检查元素是否被滚动出视口:
     function(el) { const r = el.getBoundingClientRect(); return r.top < window.innerHeight; }
  2. 如果不在视口，先滚动:
     function() { document.querySelector('#target').scrollIntoView() }
  3. 检查元素是否被折叠面板隐藏，先展开父面板
  4. 检查元素是否 disabled
```

### 1.3 操作无响应

```
场景: click/fill 操作后页面无变化
修复:
  1. 重新 take_snapshot 确认元素状态是否变化
  2. 如果是下拉框: 确认用了 click 展开 → click 选项，而非 fill
  3. 如果是 radio/checkbox: 确认用了 click uid，而非 evaluate_script
  4. 如果是 textarea: 确认用了 Ctrl+A → Delete → 输入，而非 fill 覆盖
  5. 如果是 readonly 字段: 确认该字段是否可编辑
```

### 1.4 MCP 工具不可用

```
场景: MCP 工具返回错误（如 DevTools 连接断开）
修复:
  1. list_pages 检查页签状态
  2. 如果页签仍在: 重新 select_page 切换到目标页签
  3. 如果页签已关闭: 用 new_page 重新打开
  4. 如果 MCP 服务不可用: 检查 Chrome DevTools 连接状态
```

### 1.5 SVG 元素登录方式选择

```
场景: 登录方式图标使用 SVG 呈现，在 a11y snapshot 中不生成 uid
识别特征: DOM 选择器为 .login_method_tab .item
修复: 用 evaluate_script JS 点击:
  document.querySelectorAll('.login_method_tab .item')[N].click()
```

### 1.6 隐藏 Checkbox 操作

```
场景: Element UI 的 checkbox 原生 input 是隐藏的（opacity:0）
修复: 点击可见的视觉层:
  document.querySelector('.el-checkbox__inner').click()
```

### 1.7 输入框识别

```
场景: 系统 DOM 上可能存在多组 input，需要识别可见的输入框
修复: 用 evaluate_script 检查所有 input 的可见性:
  [...document.querySelectorAll('input')].map((el, i) => ({
    index: i, type: el.type,
    visible: el.offsetParent !== null && el.style.opacity !== '0'
  }))
```

---

## 二、修复流程

```
输入: fault-classify 输出的故障分类结果
输出: 修复后的操作 + 验证结果

步骤:
  1. 读取故障分类结果
  2. 判断工具故障类型
  3. 执行对应修复策略
  4. 重新执行原操作
  5. 验证操作结果
```

---

## 三、辅助修复命令

```javascript
// 检查元素可见性
function(selector) {
  const el = document.querySelector(selector);
  if (!el) return { found: false };
  const rect = el.getBoundingClientRect();
  const style = window.getComputedStyle(el);
  return {
    found: true,
    visible: rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden',
    inViewport: rect.top >= 0 && rect.top < window.innerHeight,
    disabled: el.disabled,
    readonly: el.readOnly
  };
}

// 查找所有 iframe
function() {
  return [...document.querySelectorAll('iframe')].map((f, i) => ({
    index: i,
    src: f.src,
    id: f.id,
    name: f.name
  }));
}

// 查找 SVG 元素
function(selector) {
  return document.querySelectorAll(selector);
}
```

---

## 四、输出格式

```json
{
  "fault_category": "TOOL",
  "sub_category": "元素不存在",
  "remediation": "重新 take_snapshot → 确认元素状态",
  "remediation_result": "SUCCESS | FAILED",
  "new_uid": "3_25",
  "retry_operation": {
    "tool": "click",
    "target_uid": "3_25"
  },
  "verification": "PASS | FAIL"
}
```

---

## 五、关键规则

1. **先快照后修复**: 每次修复前必须先 take_snapshot 获取最新状态
2. **SVG 元素用 JS**: SVG 元素不在 a11y 树中，必须用 evaluate_script 定位
3. **iframe 自动跨域**: click/fill_form 会自动跨 iframe 操作，无需特殊处理
4. **工具选择修正**: 工具选择错误时，先修正工具再重试
5. **修复重试**: 工具修复可重试 2 次，仍失败则返回 fault-classify 重新分类
6. **滚动辅助**: 元素不可见时先滚动到视口再操作
