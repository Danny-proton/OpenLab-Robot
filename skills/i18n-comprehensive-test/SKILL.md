---
name: i18n-comprehensive-test
description: 端到端中英文国际化综合测试全流程 - 从目标收集、语言包直测、网页冷启动、记忆整理到基于memory生成用例、自动化执行、英文语言质量综合评测和报告生成
version: 1.1
---

# 中英文国际化综合测试 Skill

端到端国际化测试全流程编排，串联 6 个子 Skill：
`需求收集 → language-pack-test（可选）→ test-web-memory-cold-start → test-memory-organizer → i18n-test-design → test-web-execution → english-quality-eval → test-report`

## 嵌套结构

```
i18n-comprehensive-test/
├── SKILL.md                          # 本文件 - 流程编排入口
├── sub/skills/
│   ├── test-web-memory-cold-start/   # Phase 2: 网页冷启动（含验证码处理）
│   ├── test-memory-organizer/        # Phase 3: 记忆整理
│   ├── i18n-test-design/             # Phase 4: 国际化用例设计（专用）
│   ├── test-web-execution/           # Phase 5: 自动化执行（含会话/重登修复）
│   ├── english-quality-eval/         # Phase 5.5: 英文语言质量综合评测（NEW）
│   └── language-pack-test/           # Phase 1.5: 语言包直测（NEW，可选）
```

## 阶段总览

```
Phase 1: 需求收集（本 Skill，含语言包询问与验证码知情确认）
  ↓ （若提供语言包）
Phase 1.5: 语言包直接测试（加载 sub/skills/language-pack-test/）
  ↓
Phase 2: 网页冷启动（加载 sub/skills/test-web-memory-cold-start/，含验证码处理）
  ↓ Phase 2.5 冷启动对齐
Phase 3: 记忆整理（加载 sub/skills/test-memory-organizer/）
  ↓
Phase 4: 基于 memory 生成用例（加载 sub/skills/i18n-test-design/）
  ↓ Phase 4.5 用例对齐
Phase 5: 自动化执行（加载 sub/skills/test-web-execution/）
  ↓
Phase 5.5: 英文语言质量综合评测（加载 sub/skills/english-quality-eval/）
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

### 1.2 询问语言包信息（NEW - Issue 5）

紧接着必选信息后，使用 AskUserQuestion 询问语言包情况：

```
**语言包询问:**
问题: "待测系统是否提供语言包/i18n 资源文件？若提供，将进行更彻底的翻译完整性直测。"
选项:
  - "有，提供路径与格式"   → 进入语言包路径格式收集
  - "无 / 不确定"          → 跳过 Phase 1.5，直接进入 Phase 2

若选择"有"，继续收集：
  - 语言包根目录路径（绝对或相对路径，如 ./src/locales/、./public/i18n/）
  - 文件格式（JSON / JS / YAML / PO / XLIFF / CSV / 其他）
  - 支持的语言列表（如 zh-CN、en-US）
  - 文件组织方式（按语言分文件 / 按模块分文件 / 单文件含多语言）
  - 示例文件路径（可选，用于格式校准）
```

> 收集到的语言包信息写入 `.memory/shared/environment.md` 的"语言包信息"章节，供 Phase 1.5 使用。

### 1.3 验证码知情确认（NEW - Issue 2）

使用 AskUserQuestion 确认登录验证码情况：

```
**验证码询问:**
问题: "待测系统登录是否涉及验证码（图形验证码 / 滑块 / 短信 / 邮件）？这将决定自动化登录策略。"
选项:
  - "无验证码"                 → 全自动登录
  - "有图形/滑块验证码"        → 自动登录到验证码步骤后暂停，等待人工介入
  - "有短信/邮件验证码"        → 自动登录到验证码步骤后暂停，等待人工输入验证码
  - "不确定"                   → 冷启动时按"有验证码"策略处理（检测到则暂停）
```

> 验证码策略写入 `.memory/shared/environment.md` 的"登录策略"章节。

### 1.4 存储环境信息

写入 `.memory/shared/environment.md`：

```markdown
---
system_url: <URL>
username: <账号>
password: <密码>
test_scope: <范围>
captcha_strategy: <none | graphic | sms | unknown>
language_pack:
  available: <true | false>
  root_path: <路径，若 available=true>
  format: <JSON | JS | YAML | PO | XLIFF | CSV | other>
  languages: [zh-CN, en-US]
  organization: <by_lang | by_module | single_file>
---

- **系统入口**: <URL>
- **登录账号**: <账号>
- **登录密码**: <密码>
- **测试范围**: <范围>
- **记录时间**: <YYYY-MM-DD HH:MM:SS>

## 登录策略
- **验证码类型**: <none/graphic/sms/unknown>
- **登录方式**: <自动 / 半自动（验证码处暂停等待人工）>

## 语言包信息
- **是否提供**: <是/否>
- **根目录路径**: <路径>
- **文件格式**: <格式>
- **支持语言**: <语言列表>
- **文件组织方式**: <按语言/按模块/单文件>
```

## Phase 1.5: 语言包直接测试（NEW - Issue 5）

> **触发条件**：Phase 1.2 中用户确认存在语言包。否则跳过本阶段，直接进入 Phase 2。

加载 `sub/skills/language-pack-test/`，对语言包进行直接测试（不依赖 UI）：

1. **解析语言包**：按收集到的格式与路径，加载所有语言资源文件
2. **键完整性检查**：对比不同语言之间的键集合，找出缺失/多余的键
3. **未翻译值检测**：在英文包中查找中文残留，在中文包中查找英文残留
4. **占位符一致性**：校验 `{0}`、`%s`、`{{name}}` 等占位符在各语言间是否一致
5. **英文质量直测**：对英文包中的所有值调用 `english-quality-eval` 子 Skill 进行语言质量评测
6. **生成语言包测试报告**：输出 `LANGUAGE_PACK_TEST_REPORT.md`

> 语言包直测的优势：覆盖全部字符串（含 UI 未展示的）、不依赖页面渲染、可批量精确分析。其结果将作为 Phase 5.5 综合评测的重要输入。

## Phase 2: 网页冷启动

加载 `sub/skills/test-web-memory-cold-start/`，执行四阶段冷启动：

1. **初始侦察**: 打开 URL → 截图 → 识别登录 → **按验证码策略执行登录**（见 1.3）→ 登录成功截图
2. **内存采集循环**: 识别导航/模块 → 逐页记录页面元素 → 识别语言切换功能
3. **内存深化**: 验证核心路径 → 识别所有可交互元素 → 记录页面跳转关系
4. **生成报告**: 输出 `MEMORY_BOOTSTRAP_REPORT.md`

### 登录与验证码处理（NEW - Issue 2）

冷启动登录按以下策略执行：

```
策略 A（无验证码）:
  fill 用户名 → fill 密码 → click 登录 → 等待跳转 → 验证登录成功

策略 B（图形/滑块验证码）:
  fill 用户名 → fill 密码 → 检测验证码元素 →
  暂停并通过 AskUserQuestion 通知用户："检测到验证码，请在浏览器中完成验证后点击继续" →
  用户完成验证码并确认 → click 登录 → 验证登录成功

策略 C（短信/邮件验证码）:
  fill 用户名 → fill 密码 → click 登录/发送验证码 →
  通过 AskUserQuestion 请求用户输入收到的验证码 →
  fill 验证码 → click 登录 → 验证登录成功

策略 D（不确定）:
  按策略 A 尝试 → 若点击登录后仍停留在登录页或检测到验证码元素 → 切换为策略 B/C
```

> 详细登录流程与会话管理规则见 `sub/skills/test-web-execution/SKILL.md` 的"登录与会话管理"章节。

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

> **用例格式规范**：遵循内置的 `**字段名**:` 换行格式。详细格式由 `i18n-test-design` 子 Skill 管理。

> **Checklist 内容**：由 `i18n-test-design` 子 Skill 内置维护，共 11 项（8 必选 + 3 可选）。**注意：原"英文残留于中文界面"检查项已按需求移除，仅保留"中文残留于英文界面"检查方向。**

### Phase 4.5: 用例对齐

向用户展示生成的用例清单，确认：
- 用例覆盖是否完整（必选 Checklist 项是否每页至少 1 条）
- 用例步骤是否可执行（基于 memory 中实际页面/元素）
- 是否需要补充特定场景

有意见 → 补充用例 → 再次对齐；确认无误 → Phase 5。

## Phase 5: 自动化执行

加载 `sub/skills/test-web-execution/`，按用例顺序执行。

### 国际化执行模式（每个用例）

```
1. 导航到目标页面
2. 截图（切换语言前）
3. 切换语言到英文界面
4. 等待页面加载
5. 截图（切换到英文界面后）
6. 检查中文残留于英文界面（仅此方向，不再反向检查）
7. 检查布局对齐、字体协调
8. 检查功能可用性
9. 收集英文文本样本（供 Phase 5.5 英文质量评测使用）
10. 记录检查结果
```

**执行规则**：逐个执行、持续不停顿、截图留证、记录 PASS/FAIL/BLOCKED、异常先记录后继续。

### 会话与重登修复（NEW - Issue 4）

执行过程中若检测到会话失效（被重定向到登录页、出现登录表单、接口返回 401），按 `sub/skills/test-web-execution/SKILL.md` 的"会话失效与重登修复"流程处理：

1. **检测**：操作前/后检查当前 URL 与页面是否为登录页
2. **重读凭证**：从 `.memory/shared/environment.md` 重新读取账号密码（**禁止再次询问用户**）
3. **重新快照**：`take_snapshot` 获取登录表单的最新 uid（旧 uid 在页面重载后失效，这是"输入后无效"的根因）
4. **等待就绪**：确保页面 `readyState=complete` 且表单元素可交互后再 `fill`
5. **重新登录**：按 Phase 2 的验证码策略执行（验证码出现则再次走人工介入流程）
6. **验证成功**：登录后确认 URL 跳转离开登录页、且用户菜单/头像等登录态元素出现
7. **恢复执行**：回到原用例中断点继续执行

## Phase 5.5: 英文语言质量综合评测（NEW - Issue 3）

加载 `sub/skills/english-quality-eval/`，对 Phase 5 中收集的英文文本样本（以及 Phase 1.5 语言包直测结果，若存在）进行综合语言质量评测。

### 评测维度（7 维）

| 维度 | 检查内容 |
|------|----------|
| 词汇准确性 | 选词是否准确、专业术语是否正确 |
| 语法正确性 | 时态、单复数、主谓一致、句法结构 |
| 语义表达 | 含义是否清晰准确、是否存在歧义 |
| 场合规范 | 正式/非正式场合匹配、UI 上下文适配 |
| 一致性 | 同一术语在多处是否一致使用 |
| 拼写与大小写 | 拼写错误、Title Case 规范、专有名词大小写 |
| 标点符号 | 标点使用规范、中英文标点混用 |

### 输出

- 每条文本样本的逐维评分（0-10 分）与问题描述
- 维度级汇总评分
- 综合质量等级（A/B/C/D）
- 问题清单与修复建议
- 保存为 `ENGLISH_QUALITY_EVAL_REPORT.md`

> 详细评测方法与报告模板见 `sub/skills/english-quality-eval/SKILL.md`。

## Phase 6: 报告生成

加载 `sub/skills/test-web-execution/test-report/`，按 `test-report/SKILL.md` 中的报告模板生成每个用例的执行报告，保存为 `<用例编号>/test_report.md`。

此外汇总生成：
- `I18N_TEST_SUMMARY.md`：国际化测试总报告（含残留检查、布局、功能、英文质量评测结论、语言包直测结论）

> 报告格式全部遵循 `test-report/SKILL.md` 中的规范。

## 注意事项

1. **隐私保护**: 账号密码仅保存在 .memory/shared/environment.md，不输出到对话
2. **循环对齐**: Phase 2.5 和 Phase 4.5 支持循环对齐
3. **渐进式**: 先从必选项开始，可选项按需求补充
4. **截图留证**: 所有检查项执行过程都要截图
5. **语言切换验证（更新）**: 每个用例切换到英文界面后，**仅检查英文界面是否存在中文残留**，不再反向检查中文界面的英文残留（按需求裁剪）
6. **持续执行**: 用例执行阶段不停顿，批量完成后统一报告
7. **验证码人工介入（NEW）**: 涉及验证码时通过 AskUserQuestion 暂停等待人工，不得强行绕过
8. **会话保持（NEW）**: 全程不关闭已登录页签；检测到会话失效时按"重登修复"流程处理，凭证从 memory 重读，禁止再次询问用户
9. **英文质量评测（NEW）**: Phase 5 执行时同步收集英文文本样本，Phase 5.5 统一评测；若存在语言包，Phase 1.5 直测结果合并纳入综合评测
10. **语言包优先（NEW）**: 若用户提供语言包，Phase 1.5 直测可覆盖 UI 未展示的字符串，是 UI 检查的重要补充
