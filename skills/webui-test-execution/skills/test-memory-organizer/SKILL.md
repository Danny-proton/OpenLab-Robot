---
name: test-memory-organizer
description: 在测试工作场景下，将调试过程中形成的原始经验（零散、混杂）按照分流规则结构化归档到项目记忆库。触发条件：用户说"整理经验"、"归档"、"memory-organize"、"沉淀知识"、"把经验整理到记忆库"。
version: 0.1.1
---
# Test Memory Organizer

## 核心职责

把调试过程中形成的原始经验（可能零散、混杂）整理到正确的位置，遵循设计文档定义的分流规则。

## 归档原则

1. **优先遵循项目约定**：归档前先读取 `.memory/README.md`，如果项目中已有记忆库且定义了特殊的归档规则、命名规范或模块划分方式，优先遵循项目约定。
2. **参考模板初始化**：如果项目尚无私有记忆库，参考 `.claude/skills/test-memory-organize/.memory-template/` 下的模板创建记忆库结构，同时将本 skill 目录下的 `CLAUDE.md` 与项目的 `CLAUDE.md` 合并。
3. **项目约定缺失时按本 skill 梳理**：如果项目中没有记忆库或约定不完整，再按照本 skill 定义的分流规则和模板进行归档。
4. **与用户确认**：对不确定的归类（如模块归属、跨项目通用性判断），主动与用户确认后再写入。

## 归档分流判断规则

按以下决策树判断每条经验应写入的位置：

```
问题 1：这条经验是否跨项目可复用？
  是 → 写入 .claude/skills/test-web-execution/ （通用执行规则）
  否 ↓

问题 2：它是否属于当前项目多个模块都要遵守？
  是 → 写入 .memory/shared/
  否 ↓

问题 3：它属于哪个业务模块？
  明确属于某模块 → 写入 .memory/modules/<module>/
  跨多个模块流程 → 写入 .memory/shared/cross_module_flows.md
  不确定 → 与用户确认模块归属

问题 4：它是什么类型的经验？
  模块入口、适用场景、前置条件 → <module>/README.md
  页面对象、字段、按钮、弹窗 → <module>/objects.md
  稳定操作流程 → <module>/guide.md
  失败原因、恢复方法 → <module>/known_issues.md
  单次执行过程 → <module>/cases/YYYYMMDD-HHMMSS_<topic>.md
  项目级全局规则 → shared/execution_rules.md
  环境、账号、地址 → shared/environment.md
  测试数据规则 → shared/data_rules.md
  跨模块业务流程 → shared/cross_module_flows.md
```

## 执行步骤

### Step 1：识别原始经验

收集以下来源中的经验：

- Claude Code memory（用户提到的调试记录）
- 用户修正记录
- 测试用例执行过程
- snapshot / screenshot 观察到的问题
- 原始的 reference 文件（如果还在）

### Step 2：分类判断

对每条经验执行分流判断（见上文决策树）。

### Step 3：写入对应文件

根据分类结果，写入对应文件：

**如果文件已存在**：追加内容或更新相应章节。
**如果文件不存在**：从 `.memory-template/` 复制模板并填充，或直接创建文件。

### Step 4：更新索引

- 新增 shared 文件 → 更新 `.memory/shared/README.md`
- 新增案例 → 更新 `.memory/modules/<module>/cases/INDEX.md`
- 新增模块 → 更新 `.memory/README.md`
- 新增通用规则 → 更新 `.claude/skills/test-execution/`

## 案例文件命名规范

```
YYYYMMDD-HHMMSS_<case-id>_<short-topic>.md
```

示例：

- `20260612-150000_TC-001_login-failure.md`
- `20260612-160000_RUN-001_dropdown-not-working.md`

## 记忆库模板

记忆库模板位于 `.memory-template/`，包含所有文件的参考结构和占位符。新建项目或归档新模块时，参考此模板创建目录和文件。

- 模块目录结构：`.memory-template/modules/<module>/`
- 案例文件模板：`.memory-template/modules/<module>/cases/case-template.md`

## 注意事项

1. **粒度控制**：每个文件控制在 50-100 行，避免过大文件。
2. **不写裸密码**：使用 secret 引用方式，不直接在正文中写密码。
3. **不重复写入**：如果某条经验已存在于目标文件，不要重复添加。
4. **模块名规范**：使用稳定、直观、业务含义明确的英文短名。
5. **验证写入结果**：写入后确认文件内容正确，无格式错误。

## 示例：从原始 reference 到记忆库

### 原始经验（来自 references.md）

```
# 问题：普通 click 点击"新建问题"按钮后，弹窗可能不会立即出现
# 解决：用 evaluate_script 遍历 document.querySelectorAll('button') 找到文本为"新建问题"的按钮并 click()

# 问题：编辑图标 `<i class="el-icon" title="编辑">` 在 snapshot 中不可见
# 解决：用 evaluate_script 获取并点击

# 问题：权限提示可能一闪而过，必须立即截图
# 解决：点击编辑他人模板后，立刻调用 take_screenshot 保存截图
```

### 归档结果

```text
.memory/
└── modules/
    ├── defect-management/
    │   ├── known_issues.md    ← 写入"新建问题按钮不生效"问题
    │   └── guide.md           ← 写入"编辑模板流程"
    └── template-management/
        └── known_issues.md    ← 写入"权限提示一闪而过"问题

.claude/skills/test-execution/
├── objects/
│   └── hidden_dom_object.md  ← 写入"隐藏元素必须用 evaluate_script 获取"通用规则
└── recovery/
    └── click_not_effective.md ← 写入"普通 click 不生效时用 JS 点击"恢复规则
```

## 完成确认

整理完成后，向用户报告：

1. 整理了多少条经验
2. 各条经验写入的位置
3. 是否有经验被提取到通用 skill
4. 是否需要用户确认或调整
