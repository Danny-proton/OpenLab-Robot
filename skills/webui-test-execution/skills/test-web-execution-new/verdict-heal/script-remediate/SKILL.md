---
name: verdict-heal/script-remediate
description: 脚本修复技能。处理脚本类故障（填写值错误、操作顺序错误、工具选择错误、步骤遗漏等），修正测试脚本后重新执行。
version: V1.0
---

# 脚本修复

> 针对脚本类故障进行修复，包括操作步骤、填写值、工具选择等修正。

---

## 一、修复场景

### 1.1 填写值错误

```
场景: 填写了错误的值或选了错误选项
修复:
  1. take_snapshot 确认当前页面状态和字段值
  2. 识别错误字段
  3. 如果是下拉框选错:
     - click 下拉框展开
     - 找到正确选项的 uid
     - click 正确选项
  4. 如果是文本填写错误:
     - fill_form 重新填写正确值
  5. take_snapshot 验证值已更正
```

### 1.2 工具选择错误

```
场景: 使用了不正确的操作工具导致操作失败
修复规则:
  下拉框（el-select）:
    - 错误做法: evaluate_script 设值 / fill 输入
    - 正确做法: click 展开 → click 选项 uid

  radio/checkbox:
    - 错误做法: evaluate_script 操作
    - 正确做法: click 直接点击 uid

  textarea 已有内容:
    - 错误做法: fill 覆盖
    - 正确做法: click 聚焦 → Ctrl+A → Delete → 输入新值

  日期选择器:
    - 错误做法: fill_form 后点关闭按钮
    - 正确做法: fill_form 触发日历 → click 日期数字 uid

  普通输入框:
    - 错误做法: type_text（逐字输入，效率低）
    - 正确做法: fill_form（批量写入）
```

### 1.3 操作顺序错误

```
场景: 操作步骤与页面逻辑不匹配
修复:
  1. 分析当前页面状态
  2. 识别缺失的前置步骤
  3. 补全前置步骤:
     - 未登录 → 先登录
     - 未导航到正确页面 → 先导航
     - 弹窗未关闭 → 先关闭弹窗
     - 父面板未展开 → 先展开面板
  4. 回到正确的操作步骤继续执行
```

### 1.4 步骤遗漏

```
场景: 缺少必要的操作步骤
常见遗漏:
  - 未关闭弹窗 → 补充关闭弹窗操作
  - 未填写必填字段 → 补充填写操作
  - 未等待加载完成 → 补充 wait_for
  - 未滚动到可见区域 → 补充滚动操作

修复:
  1. take_snapshot 分析当前页面缺失
  2. 识别遗漏步骤
  3. 补全遗漏步骤
  4. 回到原操作步骤继续执行
```

### 1.5 提交校验失败

```
场景: 点击提交后提示"必填字段不能为空"，但 snapshot 看起来已填写
修复:
  1. take_snapshot 逐个检查每个必填字段的 checked/value
  2. 重点关注:
     - 下拉框: 是否真的选中（检查 value 是否非空）
     - radio/checkbox: checked 是否为 true
     - 文本框: value 是否非空
     - 日期: 日期值是否已更新
  3. 如果某个字段 checked/value 不正确:
     - 关闭当前弹窗（Escape 或点击关闭按钮）
     - 重新打开弹窗/表单页
     - 重新检查并补填所有字段（关闭弹窗后 checkbox/radio 状态可能丢失）
  4. 重新提交

注意: 关闭弹窗后重新打开，checkbox/radio 的状态可能丢失，需重新检查并补选。
```

### 1.6 弹窗后状态丢失

```
场景: 关闭弹窗后重新打开，发现之前选中的 checkbox/radio 状态丢失
修复:
  1. take_snapshot 确认丢失了哪些状态
  2. 重新选中丢失的 checkbox/radio（用 click uid）
  3. 重新确认所有选项状态
```

---

## 二、修复流程

```
输入: fault-classify 输出的故障分类结果
输出: 修正后的操作步骤 + 验证结果

步骤:
  1. 读取故障分类结果
  2. 判断脚本故障类型
  3. 分析正确操作步骤
  4. 执行修正后的操作序列
  5. 验证操作结果
```

---

## 三、修复验证

```
修复后验证:
  1. take_snapshot 确认所有字段值正确
  2. 重点验证:
     - 下拉框选中值
     - radio/checkbox 选中状态
     - 文本字段填写值
     - 日期选择器选中日期
  3. 确认无未关闭弹窗
  4. 确认无错误提示
```

---

## 四、输出格式

```json
{
  "fault_category": "SCRIPT",
  "sub_category": "工具选择错误",
  "original_action": "evaluate_script 设置下拉框值",
  "corrected_action": "click 展开 → click 选项 uid",
  "remediation_steps": [
    "重新 click 下拉框展开",
    "找到选项 uid: 3_25",
    "click 选项 uid",
    "take_snapshot 验证"
  ],
  "verification": "PASS",
  "retry_operation": {
    "tool": "click",
    "target_uid": "3_25"
  }
}
```

---

## 五、调试排查思路

```
提交报错"必填字段不能为空"？
  → take_snapshot 逐个检查 checked/value 是否为 true/有值
  → checked 为 true 但仍报错？→ 用 click 重新点击该 uid
  → 没值？→ 重新 fill_form 或 click 展开选择
  → 关闭弹窗后重新打开 → 重新填完所有字段

下拉框填了值但校验仍报 "cannot be empty"？
  → 检查是否用了 evaluate_script / fill() 强行设值
  → 改回 click 展开 → click 选项 uid

radio/checkbox 用 JS 操作不生效？
  → 停止用 JS，改用 click 直接点击 uid

日期选择器卡住/不生效？
  → fill_form 填值后，多次 take_snapshot
  → 等日历中目标日期数字出现在快照中
  → click 日期数字 uid

Textarea 内容异常 / 文本累积？
  → 停止用 fill() 覆盖
  → 改为 Ctrl+A → Delete → 输入新值

弹窗未关闭导致操作异常？
  → take_snapshot 检查是否仍有 dialog modal 在 DOM 中
  → 按 Escape 或点击 Close 按钮关闭弹窗
```

---

## 六、避坑速查表

| # | 坑 | 解决方法 |
|---|-----|---------|
| 1 | `evaluate_script` 操作 radio/checkbox 不生效 | 改用 `click` 直接点击 uid |
| 2 | 手动 dispatch 事件但表单仍校验失败 | 依赖 `click` 触发原生点击 |
| 3 | 日期选择器反复弹出/卡住 | fill_form 后 take_snapshot，等日历中出现日期数字后再 click |
| 4 | 日期填值后点关闭按钮取消选择 | 必须 click 日期数字 uid，不能点关闭 |
| 5 | 下拉框选错选项 | 重新点击下拉框展开 → 确认上下文正确 → 选择正确选项 |
| 6 | 快照刷新后 uid 变化 | 操作前 `take_snapshot` 获取最新 uid |
| 7 | 提交校验失败但看起来已填 | take_snapshot 逐个检查 checked/value，关闭弹窗重新打开 → 重新填完 |
| 8 | iframe 内元素无法定位 | click/fill_form 会自动跨 iframe，无需手动处理 |
| 9 | 用 evaluate_script 给下拉框设值 | 必须 click 展开 → click 选项 uid |
| 10 | 用 fill() 给 readonly 下拉框输入 | 必须 click 展开 → click 选项 uid |
| 11 | 用 fill() 覆盖 textarea 已有内容 | 必须 Ctrl+A → Delete → 输入新值 |
| 12 | 用 evaluate_script 清空 textarea | 必须键盘操作 Ctrl+A → Delete → 输入 |
| 13 | 日期选择后未确认 value 更新 | 每次必须 take_snapshot / take_screenshot 确认 |
| 14 | 关闭弹窗后 checkbox 状态丢失 | 关闭弹窗后重新打开，检查并补选 checkbox/radio |
| 15 | 模态弹窗未关闭继续操作 | 操作型弹窗必须用 Escape 或 Close 按钮关闭后再继续 |

---

## 七、关键规则

1. **工具选择铁律**:
   - 下拉框: 永远用 click 展开 → click 选项，禁用 evaluate_script/fill
   - radio/checkbox: 永远用 click uid，禁用 JS 操作
   - textarea: 已有内容必须 Ctrl+A → Delete → 输入
   - 日期: 先 fill_form 触发日历 → click 日期数字
2. **顺序修复**: 操作顺序错误时补全前置步骤，不跳过任何必要步骤
3. **修复验证**: 每次修复后必须 take_snapshot 验证所有字段值
4. **修复重试**: 脚本修复可重试 2 次，仍失败则返回 fault-classify 重新分类
5. **不跳过步骤**: 补全步骤时不跳过任何必要操作
