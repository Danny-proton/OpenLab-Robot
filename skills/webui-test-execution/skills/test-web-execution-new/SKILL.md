---
name: test-web-execution-new
description: 基于 Chrome DevTools MCP 的新一代 Web 自动化测试执行框架。采用 dom-agent（感知-推理-调度-判定）和 verdict-heal（故障分类-自愈-重判）双层架构，支持 Excel 用例自动转换（xlsx-to-markdown）、测试记忆库读写和测试报告输出。
version: V1.0
---

# Test Web Execution (New Framework)

> 新一代 Web 自动化测试执行框架，将测试执行流程拆分为感知、推理、调度、判定四个阶段，并引入故障自愈机制。

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                     测试执行入口                              │
│                    (test_web_execution_new)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
┌─────────────┐              ┌──────────────────┐
│  dom-agent  │              │  verdict-heal    │
│ (测试执行主体)│              │  (故障自愈)       │
│             │              │                  │
│ 1. 多模态解析│────────────►│ 故障分类         │
│ 2. 意图推理  │              │  fault-classify  │
│ 3. 动作调度  │              │      ▼           │
│ 4. 结果判定  │              │ env/tool/script  │
│             │              │   remediate      │
│             │              │      ▼           │
│             │              │  重新判定 re-judge│
└─────────────┘              └──────────────────┘
      │                               │
      └──────────┬────────────────────┘
                 ▼
           测试报告输出
```

### 执行流

**正常流程** → multimodal-parse → intent-reason → action-schedule → verdict-judge → 报告

**异常流程** → verdict-judge 发现 FAIL → fault-classify → remediate → re-judge → 报告

---

## 二、子技能目录

### dom-agent（测试执行主体）

| 技能 | 职责 |
|------|------|
| `dom-agent/multimodal-parse` | 从 a11y 快照、截图、DOM 中提取结构化页面信息 |
| `dom-agent/intent-reason` | 根据用户意图和页面状态推理操作序列 + 特殊 UI 组件处理 |
| `dom-agent/action-schedule` | 将操作序列调度为 MCP 调用，管理执行与重试 |
| `dom-agent/verdict-judge` | 对比执行结果与预期，判定测试步骤通过/失败 |

### verdict-heal（故障自愈）

| 技能 | 职责 |
|------|------|
| `verdict-heal/fault-classify` | 分析失败原因，分类为 ENV/TOOL/SCRIPT/MISMATCH |
| `verdict-heal/env-remediate` | 修复环境故障（空白页、证书警告、会话过期） |
| `verdict-heal/tool-remediate` | 修复工具故障（元素定位失败、操作无响应） |
| `verdict-heal/script-remediate` | 修复脚本故障（填写错误、顺序错误、工具选择错误） |
| `verdict-heal/re-judge` | 修复后对原步骤重新判定，得出真实结果 |

### 辅助技能

| 技能 | 职责 |
|------|------|
| `xlsx-to-markdown/xlsx_to_markdown` | 将 Excel 测试用例文件 (.xlsx/.xls) 转换为 Markdown 格式 (.md) |
| `test-report` | 测试执行报告模板与输出规范 |

---

## 三、子技能使用指南

测试执行按以下流程组织，每个阶段对应一个子技能。主技能定义全局规则，子技能提供各阶段的具体操作指导。

### 3.1 执行流程与子技能对应关系

```
输入处理                    测试记忆库           dom-agent（4阶段）              verdict-heal（5阶段）           报告输出
┌──────────────┐     ┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐
│ xlsx-to-markdown │────►│ 记忆库读取   │───►│ multimodal-parse │───►│ fault-classify │───►│ test-report  │
│ (Excel转换)  │     │ (冷启动)   │    │ (页面解析)     │    │ (故障分类)     │    │ (报告模板)   │
└──────────────┘     └──────────────┘    │ intent-reason    │───►│ env-remediate  │    └──────────────┘
                                         │ (意图推理)     │    │ tool-remediate │
                                         │ action-schedule│───►│ script-remediate │
                                         │ (动作调度)     │    │ re-judge       │
                                         │ verdict-judge  │───►│ (以上修复)     │
                                         │ (结果判定)     │    └──────────────────┘
                                         └──────────────────┘           │
                                                                    verdict-judge 再判定
                                         └──────────────────────────────┘
```

### 3.2 子技能调用时机

| 阶段 | 子技能 | 何时调用 |
|------|--------|---------|
| **输入转换** | `xlsx-to-markdown` | 仅当输入为 `.xlsx`/`.xls` 文件时 |
| **记忆库读取** | 内联于主技能 | 每次执行用例前自动进行 |
| **页面解析** | `dom-agent/multimodal-parse` | 每次操作前获取页面状态 |
| **意图推理** | `dom-agent/intent-reason` | 确定下一步操作序列时 |
| **动作调度** | `dom-agent/action-schedule` | 执行具体浏览器操作时 |
| **结果判定** | `dom-agent/verdict-judge` | 每个操作完成后验证结果 |
| **故障分类** | `verdict-heal/fault-classify` | verdict-judge 判定 FAIL 时 |
| **环境修复** | `verdict-heal/env-remediate` | fault-classify 分类为 ENV 时 |
| **工具修复** | `verdict-heal/tool-remediate` | fault-classify 分类为 TOOL 时 |
| **脚本修复** | `verdict-heal/script-remediate` | fault-classify 分类为 SCRIPT 时 |
| **重新判定** | `verdict-heal/re-judge` | 任意修复成功后重新验证 |
| **报告输出** | `test-report` | 用例执行完成后 |

### 3.3 子技能详细内容

各子技能的详细规则、操作步骤和避坑指南见对应子技能文件。主技能中的**执行策略**、**全局规范**、**记忆库**、**任务管理**为所有阶段通用规则，优先级高于子技能中的具体指导。

---

## 四、测试用例输入处理

本 Skill 接受三种格式的输入，按以下优先级处理：

| 输入格式 | 处理方式 |
|---------|---------|
| **纯文本 / 自然语言指令** | 直接解析并执行，**无需转换** |
| **Markdown 文件（`.md`）** | 直接读取并执行，**无需转换** |
| **Excel 文件（`.xlsx` / `.xls`）** | 需先使用 xlsx-to-markdown 转换 |

### Excel 用例处理流程（仅当输入为 `.xlsx`/`.xls` 时）

**步骤 1：使用 xlsx-to-markdown 子技能转换**

```bash
python "${CLAUDE_SKILL_DIR}/xlsx-to-markdown/xlsx_to_markdown.py" --input "<Excel文件路径>"
```

该子技能会自动生成对应的 `.md` 文件，并输出"转换完成!"。

**步骤 2：读取生成的 Markdown 文件**

使用 Read 工具读取 `<Excel文件名>.md` 文件，获取测试用例内容。

**步骤 3：按 Markdown 中的测试用例执行浏览器自动化操作**

**禁止**使用其他任何方式读取 Excel 文件（如 pandas CLI、openpyxl 直接操作、LibreOffice 等）。

---

## 五、测试记忆库

执行测试用例前及执行过程中，必须优先参考项目测试记忆库 `.memory/` 中的内容。记忆库中沉淀了系统结构、页面元素、操作流程、已知问题等经验，能显著提升执行效率和准确性。

### 记忆库读取流程

#### 1. 冷启动：执行前必读

在开始执行任何测试用例前，依次读取以下内容：

| 文件                                  | 用途                             | 读取时机   |
| ------------------------------------- | -------------------------------- | ---------- |
| `.memory/README.md`                 | 了解系统概览和目录结构           | 首次执行时 |
| `.memory/shared/environment.md`     | 获取当前环境、域名映射、登录状态 | 每次执行前 |
| `.memory/shared/execution_rules.md` | 获取通用导航、页面模式、注意事项 | 每次执行前 |

#### 2. 按用例定位模块记忆

根据用例中涉及的系统、菜单、页面、业务对象，定位 `.memory/modules/<module-name>/`，按顺序读取：

| 文件                | 用途                                         | 读取时机         |
| ------------------- | -------------------------------------------- | ---------------- |
| `README.md`       | 了解模块用途、入口 URL、导航结构             | 首次接触该模块时 |
| `objects.md`      | 了解页面对象、字段、按钮、弹窗、关键业务对象 | 首次接触该模块时 |
| `guide.md`        | 了解稳定执行流程                             | 遇到流程不清晰时 |
| `known_issues.md` | 了解已知问题和规避方案                       | 执行失败或异常时 |
| `cases/INDEX.md`  | 查看历史执行经验                             | 遇到类似场景时   |

#### 3. 跨模块流程

如果用例涉及多个模块的交互操作（如跨系统跳转、跨域名导航），额外读取：

- `.memory/shared/cross_module_flows.md`（如果存在）

### 记忆优先原则

执行过程中遇到问题时，按以下优先级依次尝试：

1. **当前用例上下文** — 优先使用用例中已有的信息和步骤
2. **模块记忆库** — 查阅对应模块的 `objects.md`、`guide.md`、`known_issues.md`
3. **共享规则** — 查阅 `.memory/shared/execution_rules.md`、`.memory/shared/environment.md`
4. **通用 skill 规则** — 查阅本技能全局规范中的操作对象规则
5. **用户询问** — 只有记忆库中无相关信息时，才向用户提问

> **关键要求**：在点击按钮、填写表单、处理弹窗、导航跳转等操作前，**先检查记忆中是否有相关经验**。遇到元素找不到、点击无响应、页面不匹配等问题时，**立即查阅** `known_issues.md` 和 `objects.md`，不要盲目重试。

### 记忆优先级

用户当前指令 > 当前测试用例 > 项目模块记忆 > .memory/shared > 通用 test-web-execution skill > 模型常识。

### 经验沉淀

执行完成后，将新发现的稳定经验沉淀回记忆库：

- 当前模块特有经验 → 写入 `.memory/modules/<module>/`
- 跨模块通用经验 → 写入 `.memory/shared/`
- 可跨项目复用的 Web 操作经验 → 调用 `test-memory-organizer` skill 按分流规则归档到 test-web-execution skill 通用规则章节

---

## 六、执行策略（最高优先级）

> **重要提醒：任务可能非常多且复杂，涉及大量用例的连续执行。以下规则必须严格遵守。**

### 6.1 全局连续执行

- 用例之间默认连续执行，绝不主动暂停
- 若用户未明确指示暂停，整个测试流程必须一气呵成执行到底
- 多条用例必须**串行执行**，禁止并行

### 6.2 单用例内连续执行

- 单用例内多步骤之间不得无故暂停，按"执行 → 截图 → 验证 → 下一步"闭环推进
- 必须连续执行到该用例完成，禁止在过程中插入无关操作或无故中断

### 6.3 禁止在单用例中询问用户（最高优先级）

- 严禁在执行过程中向用户提问、请求确认或输出状态等待回复
- 每一步操作完成后直接进入下一步，不需要用户确认
- 只有在整个用例完全执行完毕后，才输出测试结果和报告

### 6.4 禁止自主关闭页签（最高优先级）

- 严禁调用 `close_page` 关闭任何页签
- `close_page` 仅在用户明确要求时才调用
- 需要切换页签时用 `select_page`，需要回到上一步时用 `navigate_page` 的 `back`/`reload`

**Why:** 页签关闭后不可恢复，可能丢失关键页面状态和上下文信息。

### 6.5 异常处理

- 用例信息缺失、操作连续失败、页面异常等，必须退出当前用例并在报告中说明原因
- 退出当前用例后，继续执行后续用例，不得影响其他用例

### 6.6 调试模式

若输入不是以用例 Excel 启动的正式测试任务（即用户通过自然语言发起的浏览、抓取数据、点击操作等），视为**调试模式**。

- **调试模式下无须保存截图**
- **无须输出测试报告**
- 按需操作即可，灵活执行

---

## 七、任务管理

### 7.1 任务创建

为每个用例创建独立任务，将用例完整详情带入 `description`。

| 字段 | 格式 |
|------|------|
| `subject` | `TC-序号: 用例名称（简写）` |
| `description` | 包含用例编号、名称、描述、预置条件、测试步骤、预期结果 |

### 7.2 禁止使用 subagent

测试执行任务必须在本 agent 中顺序完成，**不要**使用 `Agent` 工具派生子代理处理单个用例。Web 测试涉及浏览器状态管理（页签、DOM 等），subagent 无法共享浏览器上下文，会导致执行失败。

### 7.3 用例编号与目录规则

1. 用例中明确包含编号的，**直接使用**，如 `FRS07_CSZSQ_01_002_001`
2. **禁止**自行编造或修改用例编号（添加前缀后缀、替换字符、截断、合并）
3. 没有明确编号时，使用 `TC-序号` 作为编号

#### 目录结构

同一个项目下多次执行的结果按**时间戳文件夹**区分存放，每个时间戳文件夹内包含该次执行的所有用例截图（**不按用例再分子文件夹**）。

```
项目-执行目录/
├── 20260623_143000/          ← 时间戳文件夹（本次执行）
│   ├── TC01-Step01.png
│   ├── TC01-Step02.png
│   ├── TC01-Step03-01.png    ← Step03第1次截图（若某步骤有多个关键操作）
│   ├── TC01-Step03-02.png    ← Step03第2次截图（若某步骤有多个关键操作）
│   ├── TC01-Step04.png
│   ├── TC01-Step05.png
│   ├── TC01-Step06.png
│   ├── TC02-Step01.png
│   └── test_report.md
├── 20260623_150000/          ← 时间戳文件夹（下次执行）
│   └── ...
└── ...
```

**创建执行目录：** 首次执行时用 `YYYYMMDD_HHmmss` 格式创建时间戳文件夹。获取时间戳的方法：

```bash
python "${CLAUDE_SKILL_DIR}/get-timestamp/get_timestamp.py"
```

返回如 `20260623_143000`，然后用此值创建目录（如 `mkdir 20260623_143000`）。所有截图和报告统一保存在 `<时间戳>/` 目录下。

---

## 八、全局规范

### 8.1 工具选择铁律

| 场景 | 首选工具 | 禁止操作 |
|------|---------|---------|
| 定位页面元素 | `take_snapshot` | 跳过快照直接操作 |
| 点击按钮/链接 | `click` (uid) | - |
| 填写文本框 | `fill_form` | - |
| 下拉框选择 | `click` 展开 → `click` 选项 | evaluate_script 设值、fill 输入 |
| 单选/复选框 | `click` uid | evaluate_script 操作 |
| 日期选择 | fill_form 触发 → click 日期数字 | 点关闭按钮 |
| Textarea 已有内容 | Ctrl+A → Delete → 输入新值 | fill 覆盖、evaluate_script 清空 |
| 页面滚动 | `evaluate_script` 执行 JS | press_key（SPA 应用中可能无效） |
| 文件上传 | `upload_file` (uid, filePath) | fill 输入路径、evaluate_script |
| 弹窗处理 | `handle_dialog` / Escape / click 关闭按钮 | 不关闭继续操作 |
| 对话框 alert/confirm | `handle_dialog` | 直接 click 关闭按钮替代 |
| 鼠标悬停 | `hover` (uid) | 不hover导致菜单不出现 |
| 拖拽操作 | `drag` (from_uid → to_uid) | evaluate_script 模拟 |
| 关闭页签 | `close_page` (pageId) | 操作完成后清理冗余页签 |
| 排查 DOM | `evaluate_script` | 直接操作隐藏元素 |
| 视觉验证 | `take_screenshot` + 截图分析 | 仅依赖快照/文本判断 |

### 8.2 截图规范（最高优先级）

> ⚠️ **每个操作执行后必须同时调用 take_snapshot 和 take_screenshot，只执行其中一项视为违规。**

1. **每步必截**: 每个操作执行后必须立即截图，不得合并或跳步
2. **必须指定 filePath**: 不带 filePath 的截图视为无效
3. **命名格式**: `<用例编号>/step_<序号>_<操作类型>_<关键词>.png`
4. **操作闭环**: 操作 → take_screenshot(截图保存) → take_snapshot(结构化验证) → 下一步

### 8.3 指令模糊处理原则

> **核心：可尝试操作，禁止发散。**

当用户指令不够明确时：

1. **有限尝试**: 基于已有上下文选择最合理的操作路径
2. **每步验证**: 每次操作后截图，通过视觉反馈确认
3. **及时止损**: 连续 2 次操作偏离预期则停止，向用户澄清
4. **禁止发散**: 不主动探索无关元素，不自行增加额外步骤
5. **保守优先**: 多选一时选视觉上最显著、最符合直觉的元素

**示例**：
- 用户说"点击添加节点"→ 找到按钮并点击 ✅
- 用户说"添加节点"→ 点击按钮打开面板后停止，等待下一步指令 ✅
- 错误示范：打开面板后自动选中某个节点并配置参数 ❌

### 8.4 操作前必须取最新 uid

uid 每次操作后可能变化，操作前必须重新 `take_snapshot` 获取最新 uid。

### 8.5 不合并操作

每个操作独立执行、独立截图，禁止在一个批次中连续执行多个操作再截图。

### 8.6 不同系统间导航用 new_page

不同系统间导航时，使用 `new_page` 打开新页签，禁止用 `navigate_page` 覆盖已有页签。

### 8.7 检查新页签

点击登录、提交表单、打开链接等可能触发新页签的操作后，执行 `list_pages` 确认，如有新页签则用 `select_page` 切换。

---

## 九、截图层级定义与执行流程

### 9.1 截图层级定义

| 层级 | 截图 | Read 读图 | 适用场景 |
|------|------|-----------|---------|
| **L0** | ❌ 不截图 | 不需要 | 同一连续操作链中的细微调整：连续点击多个按钮、重复点击同一类元素、操作失败后的重试 |
| **L0.5** | ✅ 截图 | ❌ 按需 Read | 同页面内的关键操作：填写输入框后、点击导航按钮后、打开/关闭下拉框后 |
| **L1** | ✅ 截图 | ✅ 必须 Read | 页面跳转、新弹窗/对话框出现、用例预期结果验证、错误/成功提示 |

**截图覆盖原则（最高优先级）：**
- 每个测试用例的关键操作步骤都必须有截图，这是 test-report 子技能的强制要求
- **宁可多截，不可少截**：截图是测试执行的证据，比执行效率更重要
- 如果某一步操作后无法确认预期结果是否达成，必须截图

### 9.2 各层级执行流程

**L0 — 细微调整（最少使用）：**
```
take_snapshot → Grep找uid → Read确认uid → 执行操作 → 直接找下一个元素
```
- 仅当操作失败时才使用 L1 截图诊断，L0 操作本身不截图

**L0.5 — 同页面关键操作：**
```
take_snapshot → Grep找uid → Read确认uid → 执行操作 → take_screenshot 保存
```
- 操作后保存截图，但不强制 Read 读图确认
- 如果操作结果需要验证，则 Read 截图；如果只是记录操作，则直接继续

**L1 — 关键验证点：**
```
take_screenshot + take_snapshot（可异步）
→ Read 读取截图确认
→ Grep找uid → Read确认uid
→ 执行操作
→ 操作结果需要验证时：再次 take_screenshot + Read
```

**L1 验证强制规则（最高优先级）：**
- **截图不是终点，Read 读图才是验证步骤**：`take_screenshot` 后必须用 `Read` 工具读取截图文件
- **结果判定必须基于截图证据**：根据 Read 读取的截图内容来判断用例步骤是否达成预期，禁止臆断或假设
- 不要假设"操作成功=预期达成"，要看到实际 UI 变化

### 9.3 整体流程

> **⚠️ 核心规则：L1 级别的截图必须配合 Read 读取（验证断言）；L0.5 级别的截图仅记录操作结果，不强制 Read；L0 不截图。**

```
[定位] take_snapshot → Grep → Read 提取 uid → 确认
[操作] click/fill/type_text（直接执行，不截图）
[记录] 操作完成后根据层级决定截图：
  - L0 细微调整：不截图，直接回到 [定位] 找下一个元素
  - L0.5 同页面关键操作：take_screenshot 保存（不强制 Read）
  - L1 页面导航/弹窗/断言验证：take_screenshot + Read 确认结果
```

**核心原则：每个关键操作步骤至少 L0.5 级别截图记录，L1 级别必须 Read 验证。**

---

## 十、快照管理

| 规则 | 说明 |
|------|------|
| 保存位置 | `take_snapshot` 固定保存为 `temp/snapshot.txt`（覆盖写入） |
| 优先默认 | 优先使用默认 snapshot（verbose=false），元素找不到时再切换到 verbose=true |
| 大文件处理 | 快照文件很大时禁止整体读取，必须用 Grep 搜索后用 Read 读取局部 |
| 复用策略 | 同一页面未操作时可复用已有快照，多次 Grep 搜索不同元素 |
| 刷新策略 | 每次交互操作（click/fill/submit 等）后必须重新调用 `take_snapshot` |

### 定位元素 uid 方法

核心原则：**Grep 只能用来找到匹配行，Read 才是提取 uid 的唯一途径。**

1. **保存快照**：`take_snapshot` 固定保存为 `temp/snapshot.txt`
2. **Grep 搜索关键字**：用 `Grep` 从快照文件中搜索关键字，拿到匹配行号
3. **Read 提取 uid**：用 `Read` 读取匹配行附近范围（如 `offset=行号-5, limit=15`），提取目标元素的 uid
4. **确认上下文**：通过 Read 返回的上下文确认该 uid 确实对应目标元素

> Grep 只返回匹配的那一行，但 uid 可能位于相邻行。必须通过 Read 读取上下文才能拿到正确的 uid。

**清理：** 每条用例执行完毕后，必须删除 `temp/` 目录下的 `snapshot.txt`

---

## 十一、测试报告输出

每次测试执行完成后必须输出结构化报告并保存到文件：

```
保存路径: <时间戳>/test_report.md
```

报告模板和规则见 `test-report` 子技能。

---

## 十二、页面滚动操作

> **规则**: 优先使用 `evaluate_script` 执行 JS，详见 `dom-agent/action-schedule` §三。

```javascript
// 向下滚动 600px / 滚到底部 / 回到顶部 / 滚动到指定元素
function() { return window.scrollBy(0, 600) }
```

---

## 十三、参考链接

| 文件 | 用途 |
|------|------|
| `dom-agent/multimodal-parse/SKILL.md` | 页面解析指南 |
| `dom-agent/intent-reason/SKILL.md` | 意图推理 + 工具选择规则 |
| `dom-agent/action-schedule/SKILL.md` | 调度执行 + 重试策略 |
| `dom-agent/verdict-judge/SKILL.md` | 判定标准 |
| `verdict-heal/fault-classify/SKILL.md` | 故障分类体系 |
| `verdict-heal/env-remediate/SKILL.md` | 环境修复策略 |
| `verdict-heal/tool-remediate/SKILL.md` | 工具修复策略 |
| `verdict-heal/script-remediate/SKILL.md` | 脚本修复策略 |
| `verdict-heal/re-judge/SKILL.md` | 重新判定流程 |
| `xlsx-to-markdown/xlsx_to_markdown.py` | Excel 测试用例 → Markdown 格式转换 |
| `test-report/SKILL.md` | 测试执行报告模板与输出规范 |
| `chrome-devtools-plugins/SKILL.md` | Chrome DevTools 32 个工具指令参考 + 通用操作模式 + 常用 JS 代码片段 |
