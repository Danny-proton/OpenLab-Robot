---
name: i18n-comprehensive-test
description: 端到端中英文国际化综合测试全流程 - 从目标收集、网页冷启动、记忆整理到基于memory生成用例、自动化执行和报告生成
---

# 中英文国际化综合测试 Skill

端到端国际化测试全流程编排，串联 4 个子 Skill：
`需求收集 → test-web-memory-cold-start → test-memory-organizer → i18n-test-design → test-web-execution → test-report`

## 嵌套结构

```
i18n-comprehensive-test/
├── SKILL.md                        # 本文件 - 流程编排入口
├── sub/skills/
│   ├── test-web-memory-cold-start/ # Phase 2: 网页冷启动
│   ├── test-memory-organizer/      # Phase 3: 记忆整理
│   ├── i18n-test-design/           # Phase 4: 国际化用例设计（专用）
│   ├── test-web-execution/         # Phase 5: 自动化执行
```

## 阶段总览

```
Phase 1: 需求收集（本 Skill）
  ↓
Phase 2: 网页冷启动（加载 sub/skills/test-web-memory-cold-start/）
  ↓ Phase 2.5 冷启动对齐
Phase 3: 记忆整理（加载 sub/skills/test-memory-organizer/）
  ↓
Phase 4: 基于 memory 生成用例（加载 sub/skills/i18n-test-design/）
  ↓ Phase 4.5 用例对齐
Phase 5: 自动化执行（加载 sub/skills/test-web-execution/）
  ↓
Phase 6: 报告生成（加载 sub/skills/test-web-execution/test-report/）
```

## Phase 1: 需求收集

### 1.1 询问用户测试目标

使用 AskUserQuestion 收集：

```
**必选信息:**
1. 待测系统 URL
2. 登录账号和密码
3. 主要用户旅程/业务场景
4. 测试范围

**可选信息:**
5. 重点关注的国际化维度（界面多语言 / 多时区 / 多货币 / 配置项）
6. 是否有已有测试用例
7. 目标浏览器和分辨率
```

### 1.2 存储环境信息

写入 `.memory/shared/environment.md`：

```markdown
---
system_url: <URL>
username: <账号>
password: <密码>
test_scope: <范围>
---
- **系统入口**: <URL>
- **登录账号**: <账号>
- **登录密码**: <密码>
- **测试范围**: <范围>
- **记录时间**: <YYYY-MM-DD HH:MM:SS>
```

## Phase 2: 网页冷启动

加载 `sub/skills/test-web-memory-cold-start/`，执行四阶段冷启动：

1. **初始侦察**: 打开 URL → 截图 → 识别登录 → 输入账号密码 → 登录成功截图
2. **内存采集循环**: 识别导航/模块 → 逐页记录页面元素 → 识别语言切换功能
3. **内存深化**: 验证核心路径 → 识别所有可交互元素 → 记录页面跳转关系
4. **生成报告**: 输出 `MEMORY_BOOTSTRAP_REPORT.md`

### Phase 2.5: 冷启动对齐

向用户展示扫描总结，确认：
- 模块是否遗漏
- 页面是否完整
- 是否需要补充特定路径

有意见 → 补充扫描 → 再次对齐；确认无误 → Phase 3。

## Phase 3: 记忆整理

加载 `sub/skills/test-memory-organizer/`，将冷启动数据归档到 `.memory/`：

1. 页面信息 → `.memory/modules/<module>/objects.md`
2. 导航结构 → `.memory/modules/<module>/README.md`
3. 操作流 → `.memory/modules/<module>/guide.md`
4. 环境配置 → `.memory/shared/environment.md`
5. 更新 `.memory/README.md` 索引

## Phase 4: 基于 memory 生成国际化测试用例

加载 `sub/skills/i18n-test-design/`，读取 `.memory/` 中已整理的模块/页面信息，结合国际化 Checklist 生成用例。

> **用例格式规范**：遵循内置的 `**字段名**:` 换行格式（`**用例编号**:`、`**用例名称**:`、`**预置条件**:`、`**测试步骤**:`、`**预期结果**:`、`**设计描述**:`）。详细格式由 `i18n-test-design` 子 Skill 管理。

> **Checklist 内容**：由 `i18n-test-design` 子 Skill 内置维护，共 12 项（9 必选 + 3 可选）。

## Phase 5: 自动化执行

加载 `sub/skills/test-web-execution/`，按用例顺序执行。

### 国际化执行模式（每个用例）

```
1. 导航到目标页面
2. 截图（切换语言前）
3. 切换语言到目标语言
4. 等待页面加载
5. 截图（切换语言后）
6. 检查翻译残留（中文/英文）
7. 检查布局对齐、字体协调
8. 检查功能可用性
9. 记录检查结果
```

**执行规则**：逐个执行、持续不停顿、截图留证、记录 PASS/FAIL/BLOCKED、异常先记录后继续。

## Phase 6: 报告生成

加载 `sub/skills/test-web-execution/test-report/`，按 `test-report/SKILL.md` 中的报告模板生成每个用例的执行报告，保存为 `<用例编号>/test_report.md`。

> 报告格式全部遵循 `test-report/SKILL.md` 中的规范（用例编号、测试目标、执行步骤与结果表、断言验证、附加信息、结论）。

## 注意事项

1. **隐私保护**: 账号密码仅保存在 .memory/shared/environment.md，不输出到对话
2. **循环对齐**: Phase 2.5 和 Phase 4.5 支持循环对齐
3. **渐进式**: 先从必选项开始，可选项按需求补充
4. **截图留证**: 所有检查项执行过程都要截图
5. **语言切换验证**: 每个用例执行双向验证（中→英，英→中）
6. **持续执行**: 用例执行阶段不停顿，批量完成后统一报告
