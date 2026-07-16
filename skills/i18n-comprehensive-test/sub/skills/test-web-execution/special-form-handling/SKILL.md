---
name: special-form-handling
description: 特殊 UI 组件表单处理指南。适用于各种前端框架中无法直接用通用工具操作的组件，覆盖只读下拉框、日期选择器、自定义单选/复选框、Textarea 等。
---

# 特殊 UI 组件表单处理指南

> 本技能适用于各种前端框架（Element UI、Ant Design、Vuetify 等）中的**特殊 UI 组件**。通用工具（`fill`/`click`）无法直接操作的场景，优先尝试通用方式，仍失败则参考本技能处理。

---

## 一、通用工具优先（最高优先级）

对任意框架的表单，**优先使用通用工具**，仅在通用工具失效时回退到特殊处理：

| 工具 | 适用场景 |
|------|---------|
| `fill` | 单字段填写：文本框、文本域（清空后填写）、日期字段、非 readonly 输入框 |
| `click` | 单选/复选框、下拉框展开及选项选择、日期数字选择、按钮操作 |
| `fill_form` | 一次性填写多个字段（批量填写） |
| `evaluate_script` | 主要用于排查，不直接用于表单值操作 |

**铁律**：能用 `fill` / `click` 解决的，不用 `fill_form`；能解决的，绝不绕道 JS。

---

## 二、iframe 处理

表单通常嵌套在 iframe 中。`click` / `fill` / `fill_form` 工具会自动跨 iframe 定位元素，无需手动处理。

---

## 三、下拉框操作

> ⚠️ 许多框架的下拉框是 `readonly` 输入框，**不能用 `fill` 填写**。

```
步骤:
1. take_snapshot → 找到 readonly 的 textbox（下拉框组件）
2. click 该 textbox uid → 展开选项列表
3. 快照底部会出现选项，找到目标选项的 uid
4. click 选项 uid → 完成选择
5. take_snapshot 验证 value 已更新
```

**禁止**：
- `evaluate_script` 给下拉框注入值（前端框架响应式不更新）
- `fill()` 给 `readonly` 下拉框输入文字
- **唯一正确方式**：`click` 展开 → 找选项 uid → `click` 选项 uid

---

## 四、单选/复选框

- **直接用 `click` 点击 radio/checkbox 的 uid**
- 操作后用快照验证 `checked` 属性

**不要用 JS 操作**：表单框架可能使用自定义状态管理，JS 赋值不触发组件更新。

---

## 五、日期选择器

```
步骤:
1. take_snapshot → 找到日期字段（readonly textbox）
2. fill 填写目标日期值（格式如 "2026-05-26"）
3. 日历弹出后 take_snapshot，查找日期数字 uid
4. click 目标日期数字 uid
5. take_snapshot 验证 value 已更新
```

**关键点**：
- 日期填值后必须 click 日期数字，**不能点关闭按钮**（等于取消选择）
- fill 后日历可能未渲染，需 take_snapshot 等日期 uid 出现后再点
- 反复 fill 会导致日历反复弹出，fill 只执行一次

---

## 六、Textarea 处理

已存在内容时 `fill()` 是追加而非替换。

**清空已有内容**：
```
1. click 聚焦 textarea
2. Ctrl+A → 全选
3. Delete → 删除
4. fill 输入新文本
```

---

## 七、弹窗处理

- **Alert/Toast**（自动消失）：截图后继续，无需关闭
- **模态弹窗**（带 X 关闭）：必须关闭后再继续

> 如果 snapshot 中仍有 `dialog modal` 类型的 uid，说明弹窗未关闭。

---

## 八、避坑速查

| 坑 | 解决 |
|----|------|
| 下拉框 readonly 不能用 fill | click 展开 → click 选项 uid |
| JS 操作 radio/checkbox 不生效 | 改用 click 直接点击 uid |
| 日期选择器反复弹出 | fill 一次后等日历渲染，再 click 日期数字 |
| 日期填值后点关闭按钮 | 必须 click 日期数字，不能点关闭 |
| fill 覆盖 textarea 已有内容 | 先 Ctrl+A → Delete 清空 |
| JS 清空 textarea | 必须键盘操作 Ctrl+A → Delete |
| 关闭弹窗后 checkbox 状态丢失 | 重新打开检查并补选 |
| 模态弹窗未关闭继续操作 | 必须关闭后再继续 |
