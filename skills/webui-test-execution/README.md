# Test Web Execution Skills

基于 Chrome DevTools MCP 的 Web 自动化测试执行工具集，包含测试执行、故障自愈、记忆库管理三大核心能力。

---

## Skills 总览

| Skill                                                             | 版本   | 用途                | 适用场景                                       |
| ----------------------------------------------------------------- | ------ | ------------------- | ---------------------------------------------- |
| [test-web-execution-new](skills/test-web-execution-new/SKILL.md)  | V1.0   | 新一代 Web 测试框架 | 复杂测试场景，需要故障自愈和记忆库             |
| [test-web-memory-cold-start](skills/test-web-memory-cold-start/SKILL.md) | V1.0 | 记忆冷启动探索 | 批量执行测试前，受控探索被测系统并初始化项目记忆 |
| [test-memory-organizer](skills/test-memory-organizer/SKILL.md)     | v1.0   | 测试经验归档整理    | 将调试经验结构化沉淀到记忆库                   |

> **推荐使用 `test-web-execution-new`**：新一代框架，支持故障自愈、记忆库读写、分层截图等完整能力。

---

## 一、test-web-execution-new（推荐）

### 架构

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

### 子技能

| 类别         | 子技能                          | 职责                                 |
| ------------ | ------------------------------- | ------------------------------------ |
| dom-agent    | `dom-agent/multimodal-parse`    | 页面解析（快照/截图/DOM）            |
| dom-agent    | `dom-agent/intent-reason`       | 意图推理 + 特殊 UI 组件处理          |
| dom-agent    | `dom-agent/action-schedule`     | 动作调度 + 重试管理                  |
| dom-agent    | `dom-agent/verdict-judge`       | 结果判定（PASS/FAIL）                |
| verdict-heal | `verdict-heal/fault-classify`   | 故障分类（ENV/TOOL/SCRIPT/MISMATCH） |
| verdict-heal | `verdict-heal/env-remediate`    | 环境修复（空白页/证书/会话）         |
| verdict-heal | `verdict-heal/tool-remediate`   | 工具修复（元素定位/操作无响应）      |
| verdict-heal | `verdict-heal/script-remediate` | 脚本修复（填写值/顺序/工具选择）     |
| verdict-heal | `verdict-heal/re-judge`         | 修复后重新判定                       |
| 辅助         | `xlsx-to-markdown`              | Excel 用例 → Markdown                |
| 辅助         | `test-report`                   | 测试报告输出                         |
| 辅助         | `chrome-devtools-plugins`       | 32 个 DevTools 工具参考              |

### 输入格式

| 格式               | 处理方式     |
| ------------------ | ------------ |
| 纯文本 / 自然语言  | 直接执行     |
| Markdown (.md)     | 直接执行     |
| Excel (.xlsx/.xls) | 先转换再执行 |

### 快速开始

```bash
# 执行 Excel 用例
use skill: test_web_execution_new
# 输入: 参考 references.md 执行用例 test_case.xlsx
```

---

## 二、test-web-memory-cold-start（记忆冷启动）

在正式批量执行测试用例前，对 Web 被测系统进行受控探索，初始化项目 memory。

### 核心循环

观察 → 规划 → 派发（子 Agent） → 回收 → 归档（调用 test-memory-organizer）

### 阶段

1. **初始侦察**：访问入口、识别登录/导航/模块、生成 TODO.md
2. **记忆采集循环**：派发子 Agent 探索页面、收集结构化记忆片段、归档
3. **记忆深化**：核心模块轻量路径验证（入口稳定性、表单/按钮/弹窗/Toast）
4. **生成冷启动报告**：MEMORY_BOOTSTRAP_REPORT.md

### 铁律

- 冷启动任务必须使用 BOOT 编号
- 子 Agent 不直接修改 project-memory，只返回结构化采集结果
- 默认只做非破坏性探索
- 涉及提交/审批/删除等破坏性动作时必须确认环境允许

---

## 三、test-memory-organizer

测试经验归档整理技能。将调试过程中形成的原始经验结构化沉淀到项目记忆库。

### 触发条件

用户说"整理经验"、"归档"、"memory-organize"、"沉淀知识"时触发。

### 归档分流

```
是否跨项目可复用？
  ├─ 是 → 写入 test-web-execution skill 通用规则
  └─ 否 ↓
      是否多个模块共用？
        ├─ 是 → 写入 .memory/shared/
        └─ 否 ↓
            属于哪个模块？
              ├─ 明确模块 → 写入 .memory/modules/<module>/
              └─ 跨模块流程 → 写入 .memory/shared/cross_module_flows.md
```

### 经验类型映射

| 类型                 | 归档位置                                    |
| -------------------- | ------------------------------------------- |
| 模块入口、适用场景   | `<module>/README.md`                        |
| 页面对象、字段、按钮 | `<module>/objects.md`                       |
| 稳定操作流程         | `<module>/guide.md`                         |
| 失败原因、恢复方法   | `<module>/known_issues.md`                  |
| 单次执行过程         | `<module>/cases/YYYYMMDD-HHMMSS_<topic>.md` |
| 项目全局规则         | `shared/execution_rules.md`                 |
| 环境、账号、地址     | `shared/environment.md`                     |

---

## 四、使用流程

```
1. 准备用例
   └─ Excel 文件 (.xlsx) 或 Markdown 文件 (.md)
   └─ 可选: references.md（登录信息、模块导航、经验笔记）

2. 执行测试
   └─ 调用 test-web-execution-new
   └─ 自动读取记忆库 → 执行用例 → 输出报告

3. 整理经验
   └─ 调用 test-memory-organizer
   └─ 将调试经验按分流规则归档到 .memory/
```

---

## 五、目录结构

```
├── test-web-execution-new/        # 新一代测试框架
│   ├── SKILL.md                   # 主技能入口
│   ├── dom-agent/                 # 测试执行主体（4个子技能）
│   ├── verdict-heal/              # 故障自愈（5个子技能）
│   ├── xlsx-to-markdown/          # Excel 转换工具
│   ├── test-report/               # 报告模板
│   ├── chrome-devtools-plugins/   # DevTools 工具参考
│   └── get-timestamp/             # 时间戳工具
├── test-web-memory-cold-start/    # 记忆冷启动探索
│   ├── SKILL.md
│   └── CLAUDE.md
├── test-memory-organizer/         # 经验归档
│   ├── SKILL.md
│   └── .memory-template/          # 记忆库模板
└── references.md                  # 参考信息（按需提供）
```
