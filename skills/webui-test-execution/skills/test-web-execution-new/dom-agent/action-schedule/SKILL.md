---
name: dom-agent/action-schedule
description: 动作调度技能。将推理出的操作序列转换为实际的 Chrome DevTools MCP 调用，管理操作执行顺序、截图记录和状态验证。
version: V1.0
---

# 动作调度

> 将推理出的操作序列调度为实际浏览器操作，确保每步操作后截图记录并验证结果。

---

## 一、执行框架

```
输入: intent-reason 输出的 action_sequence
输出: 操作执行结果 + 截图文件路径 + 验证状态

执行流程:
  1. 按顺序遍历 action_sequence
  2. 对每个操作:
     a. 执行 Chrome DevTools MCP 调用
     b. 立即调用 take_screenshot 保存截图
     c. 调用 take_snapshot 验证操作结果
     d. 记录截图路径和验证状态
  3. 汇总所有操作结果
```

---

## 二、操作执行规则

### 2.1 标准执行闭环

```
对每个操作:
  1. TaskGet 获取当前步骤（如需任务追踪）
  2. 执行浏览器操作（navigate/fill/click/press_key...）
  3. 立即调用 take_screenshot(filePath="用例编号/step_XX_操作描述.png")
  4. 记录截图文件路径到变量
  5. take_snapshot 验证操作结果
  6. TaskUpdate 标记当前步骤状态（如需任务追踪）
  7. 进入下一步
```

### 2.2 截图规范

> ⚠️ 截图规范详见主技能 `## 八、全局规范` §8.2，快照管理详见 `## 十、快照管理`。

**每步必截**：每个操作执行后必须同时调用 take_snapshot 和 take_screenshot
**必须指定 filePath**：take_screenshot 不带 filePath 视为无效
**命名格式**：`用例编号/step_序号_操作类型_关键词.png`

### 2.3 操作映射表

| 推理操作 | MCP 工具 | 参数示例 |
|---------|---------|---------|
| fill_form | `fill` 或 `fill_form` | `{uid: "3_24", value: "测试值"}` |
| click | `click` | `{uid: "3_25", includeSnapshot: false}` |
| navigate | `navigate_page` | `{type: "url", url: "https://..."}` |
| press_key | `press_key` | `{key: "Enter"}` |
| type_text | `type_text` | `{text: "输入文本"}` |
| scroll | `evaluate_script` | `() => window.scrollBy(0, 600)` |
| wait_for | `wait_for` | `{text: ["期望文本"], timeout: 10000}` |
| new_tab | `new_page` | `{url: "https://..."}` |
| switch_tab | `select_page` | `{pageId: 2}` |
| list_tabs | `list_pages` | 无参数 |
| close_tab | `close_page` | `{pageId: 3}` |
| hover | `hover` | `{uid: "3_26"}` |
| drag | `drag` | `{from_uid: "3_27", to_uid: "3_28"}` |
| handle_dialog | `handle_dialog` | `{action: "accept" | "dismiss"}` |
| upload_file | `upload_file` | `{uid: "3_29", filePath: "/path/file.png"}` |

---

## 三、滚动操作（统一使用 evaluate_script）

> **规则**: 页面滚动操作优先使用 `evaluate_script`，禁止用 `press_key` 滚动。
> 
> 常用 JS 代码见主技能 `## 十二、页面滚动操作`。

```javascript
// 向下滚动 600px
function() { return window.scrollBy(0, 600) }
// 滚到底部: window.scrollTo(0, document.body.scrollHeight)
// 回到顶部: window.scrollTo(0, 0)
// 滚动到元素: document.querySelector('#target').scrollIntoView({ behavior: 'smooth' })
```

---

## 四、iframe 处理

表单通常嵌套在 iframe 中（尤其是子表单场景）。

```
识别: 快照中出现 Iframe + 子 uid（如 26_18 Iframe → uid=27_xxx）
处理: click / fill_form 工具会自动跨 iframe 定位元素，无需手动处理
排查: 用 evaluate_script 遍历 document.querySelectorAll('iframe') 找到目标 iframe
```

**关键**: 不要假设 JS (`evaluate_script`) 在主页面能操作 iframe 内的 Element UI 组件。

详细说明见 `dom-agent/intent-reason` §3.4.7。

---

## 五、异常处理调度

### 5.1 常见异常及处理

| 异常场景 | 处理策略 |
|---------|---------|
| 元素 uid 找不到 | 重新 take_snapshot → 获取最新 uid |
| 元素在 iframe 内 | 用 evaluate_script 定位 iframe，click/fill_form 自动跨帧无需切换 |
| 页面空白 | evaluate_script 检查状态 → 重新 new_page |
| 弹窗未关闭 | click 关闭按钮 / press_key "Escape" |
| 操作无响应 | 检查元素是否 visible → 滚动到可见区域 |
| HTTPS 警告 | click "高级" → click "继续前往" |
| 截图保存失败 | 检查目录是否存在 → 创建目录后重试 |

### 5.2 回退策略

```
操作失败:
  1. 检查 snapshot 确认当前页面状态
  2. 判断失败原因（ENV/TOOL/SCRIPT）
  3. 尝试修正后重新执行
  4. 按故障类型重试: 环境故障最多 1 次，工具/脚本故障最多 2 次
  5. 超过重试次数 → 标记为失败并记录原因
```

---

## 六、执行结果记录

```json
{
  "operation": "fill_form",
  "target_uid": "3_24",
  "arguments": { "value": "测试值" },
  "screenshot_path": "TC_001/step_03_fill_username.png",
  "snapshot_after": "操作后的 snapshot 关键信息",
  "validation": "PASS | FAIL | SKIP",
  "error": "失败时的错误描述"
}
```

---

## 七、关键规则

1. **每步必截**: 操作 → 截图 → 验证 → 下一步，不可跳步
2. **截图必须有 filePath**: 否则视为无效截图
3. **滚动用 evaluate_script**: 不用 press_key 滚动
4. **失败可重试**: 环境故障最多 1 次，工具/脚本故障最多 2 次，超过后标记失败
5. **不合并操作**: 每个操作独立执行、独立截图
6. **页面导航用 new_page**: 不同系统间导航不要覆盖已有页签（详见主技能 §8.6）
7. **操作前取最新 uid**: uid 每次操作后可能变化，操作前必须重新 take_snapshot（详见主技能 §8.4）
