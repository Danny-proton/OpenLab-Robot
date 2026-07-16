---
name: dom-agent/intent-reason
description: 意图推理技能。基于解析后的页面状态和用户需求，推理当前应该执行的操作序列。
version: V1.0
---

# 意图推理

> 根据用户意图（测试步骤）和当前页面状态，推理出下一步应执行的操作。

---

## 一、推理框架

```
输入:
  - 用户意图: 当前测试步骤描述
  - 页面解析: multimodal-parse 输出的结构化页面信息
  - 测试步骤: 原始测试步骤编号与内容

推理:
  1. 匹配当前页面与预期页面是否一致
  2. 识别当前页面中可用的操作元素
  3. 判断当前步骤的可执行性
  4. 输出目标操作列表

输出:
  - 操作序列: 需要执行的操作列表
  - 元素引用: 操作对应的 uid
  - 预期结果: 操作后期望的页面状态
```

---

## 二、意图匹配规则

### 2.1 页面状态判断

| 当前页面状态 | 用户意图 | 推理结果 |
|------------|---------|---------|
| 登录页 | 填写表单 | 先执行登录操作 |
| 首页 | 查找功能 | 先执行搜索/导航操作 |
| 目标表单页 | 填写字段 | 直接执行表单填写 |
| 弹窗未关闭 | 任何操作 | 先关闭弹窗 |
| 报错页面 | 继续操作 | 先处理错误，可能需要回退 |
| 空白页 | 任何操作 | 重新加载页面或重新导航 |

### 2.2 元素可用性判断

```
元素可用条件:
  - 在 snapshot 中存在对应 uid
  - 元素可见（未隐藏）
  - 元素可交互（非 disabled）

元素不可用处理:
  - 等待页面加载完成
  - 滚动到元素可见区域
  - 检查是否需要展开/点击父元素
```

---

## 三、操作步骤推理模板

### 3.1 表单填写场景

```
推理流程:
  1. 必填字段扫描（最高优先级）: take_snapshot 扫描全表单，标记所有带 `*` 的必填字段
  2. 遍历测试步骤中的字段填写要求
  3. 对每个字段:
     a. 在 snapshot 中查找对应元素 uid
     b. 判断元素类型 → 选择操作工具
     c. 输出 (操作工具, uid, 目标值) 三元组
  4. 关闭弹窗后重新打开 → 必须重新检查并补选 checkbox/radio 状态
```

**工具选择规则**（补充主技能第 8.1 节）:

| 元素类型 | 操作方式 |
|---------|---------|
| textbox (非 readonly) | fill_form(uid, value) |
| textbox (readonly, 下拉框) | click 展开 → click 选项 uid |
| radio/checkbox | click uid |
| date-editor | fill_form(值) → click 日期数字 uid |
| textarea | click 聚焦 → Ctrl+A → Delete → 输入新值 |
| 普通按钮 | click uid |
| 触发下拉菜单 | hover(uid) → 等菜单出现 → click 选项 uid |
| 拖拽目标 | drag(from_uid, to_uid) |
| 文件上传 | upload_file(uid, filePath) |
| 浏览器 alert/confirm | handle_dialog({action: "accept" | "dismiss"}) |

### 3.2 导航搜索场景

```
推理流程:
  1. 识别页面中的搜索框 uid
  2. 输出 (fill_form/search_box_uid, 搜索词)
  3. 识别搜索结果中的目标项 uid
  4. 输出 (click, 目标项 uid)
```

### 3.3 异常处理场景

```
推理流程:
  1. 识别当前页面的异常状态
  2. 判断异常类型:
     - 页面未加载 → wait_for 或 reload
     - 元素不存在 → take_snapshot 刷新 → 重新定位
     - 弹窗阻塞 → 关闭弹窗
     - 错误提示 → 截图记录 → 判断是否可忽略
  3. 输出修正操作序列
```

### 3.4 特殊 UI 组件处理

> 适用于 Element UI、Ant Design、Vuetify 等前端框架中的特殊 UI 组件。通用工具无法直接操作的场景，优先尝试通用方式，仍失败则参考以下规则处理。

**通用工具优先**（最高优先级）：对任意框架的表单，优先使用 `fill`/`click`/`fill_form`，仅在通用工具无法完成时，才使用后续的特殊处理方式。

#### 3.4.1 只读下拉框

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

#### 3.4.2 单选/复选框

- **直接用 `click` 点击 radio/checkbox 的 uid**
- 操作后用快照验证 `checked` 属性
- **不要用 JS 操作**：表单框架可能使用自定义状态管理，JS 赋值不触发组件更新

#### 3.4.3 日期选择器

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

#### 3.4.4 Textarea 处理

已存在内容时 `fill()` 是追加而非替换。

**清空已有内容**：
```
1. click 聚焦 textarea
2. Ctrl+A → 全选
3. Delete → 删除
4. fill 输入新文本
```

#### 3.4.5 隐藏 DOM 元素与 image 类型图标

**image 类型元素**（如编辑/删除图标）：某些页面使用 `<image>` 元素表示图标按钮，在默认 a11y 树中可能不显示，**必须以 `description` 属性为准**。

```
步骤:
1. take_snapshot(verbose=true) → 获取完整 DOM 树
2. Grep 搜索 description="编辑" → 找到匹配行号
3. Read 读取匹配行附近内容 → 提取 <image> 的 uid
4. click 该 uid → 完成操作
```

**避坑**：
| 坑 | 解决 |
|----|------|
| 默认 snapshot 找不到 image 元素 | 设置 verbose=true 获取完整 DOM |
| 编辑图标不是 button 而是 image | uid 会随页面刷新变化，以 description="编辑" 为准 |

**隐藏 DOM 元素**（如 `<i class="el-icon">`）：被 `display: none` 或 `visibility: hidden` 隐藏，不在 snapshot 中，普通 `click` 也不生效。

```
步骤:
1. 用 evaluate_script 执行 JS 获取元素：document.querySelectorAll('选择器')
2. 确认索引关系
3. 对目标元素执行 .click()
```

#### 3.4.6 弹窗处理

- **Alert/Toast**（自动消失）：截图后继续，无需关闭
- **模态弹窗**（带 X 关闭）：必须关闭后再继续
- 如果 snapshot 中仍有 `dialog modal` 类型的 uid，说明弹窗未关闭

#### 3.4.7 iframe 处理

表单通常嵌套在 iframe 中。`click`/`fill`/`fill_form` 工具会自动跨 iframe 定位元素，无需手动处理。

---

## 四、推理输出格式

```json
{
  "intent": "当前测试步骤描述",
  "current_page": "当前页面类型",
  "expected_page": "期望页面类型",
  "mismatch": false,
  "action_sequence": [
    {
      "step_order": 1,
      "action": "fill_form | click | navigate_page | press_key | evaluate_script",
      "target_uid": "元素 uid（如 3_24）",
      "arguments": { "value": "填写值" },
      "reason": "推理依据"
    }
  ],
  "expected_outcome": "操作后期望的页面状态",
  "fallback": "如果失败的回退方案"
}
```

---

## 五、关键规则

1. **快照驱动推理**: 所有推理必须基于最新的 take_snapshot 结果
2. **工具选择铁律**: 能用 fill_form/click 解决的，不用 evaluate_script
3. **分页操作**: 下拉框必须 click 展开 → click 选项，禁止 JS 设值
4. **日期选择**: 先 fill_form 触发日历 → 等日历渲染 → click 日期数字
5. **Textarea 清空**: 必须先 Ctrl+A → Delete，不能用 fill 覆盖
6. **弹窗优先**: 遇到弹窗必须先关闭才能继续推理后续操作
7. **空页处理**: 页面空白时重新 new_page 打开，不要关闭其他页签
8. **验证闭环**: 每个操作推理后必须包含验证步骤（take_snapshot 或截图）
