---
name: test-web-memory-cold-start
description: 在正式批量执行测试用例前，对 Web 被测系统进行受控探索，初始化项目 memory。目标不是完整测试系统，也不是优先发现缺陷，而是建立后续测试执行 Agent 可复用的项目级记忆。
version: V1.0
---

# 项目记忆冷启动探索

本 skill 用于在正式批量执行测试用例前，对 Web 被测系统进行受控探索，初始化项目 memory。目标不是完整测试系统，也不是优先发现缺陷，而是建立后续测试执行 Agent 可复用的项目级记忆。

## 核心循环

主 Agent 通过“观察 → 规划 → 派发 → 回收 → 归档”的循环完成冷启动。

- 观察：访问系统入口，识别登录方式、导航结构、模块入口。
- 规划：生成 BOOT 任务队列。
- 派发：将模块扫描、页面对象采集、路径验证任务派给子 Agent。
- 回收：收集子 Agent 返回的结构化记忆片段。
- 归档：调用 test-memory-organizer skill 写入 project-memory。

## 铁律

1. 冷启动任务必须使用 BOOT 编号，例如 BOOT-001。
2. 每个 BOOT 任务必须对应一个明确采集目标。
3. 主 Agent 负责规划和归档，子 Agent 负责具体页面探索。
4. 子 Agent 不直接修改 project-memory，只返回结构化采集结果。
5. 每完成 1 个 BOOT 任务即更新 TODO.md。
6. 同一任务阻塞 3 次即标记 blocked，不再重试，记录原因并继续下一任务。
7. 默认只做非破坏性探索。
8. 涉及提交、审批、删除、生成正式结果等动作时，必须确认环境允许。
9. 发现可跨项目复用的经验时，标记为 test-web-execution skill 候选。
10. 所有历史执行记录写入 cases/，文件名必须包含时间戳和 BOOT 编号。

## 编号规则

- `BOOT-xxx` 代表冷启动规划中的任务编号（计划层）。
- `RUN-xxx` 代表实际执行的运行编号（执行层）。
- 案例文件命名格式：`YYYYMMDD-HHMMSS_BOOT-xxx_<topic>.md`，其中 `BOOT-xxx` 对应采集该案例的冷启动任务编号。
- 案例 YAML front matter 中：
  - `case_id` 填 BOOT-xxx（与采集任务关联）。
  - `run_id` 填实际运行序号（用于多次执行同一任务的区分）。
  - 二者通过 case_id/run_id 字段关联。

## 阶段一：初始侦察

1. navigate_page 访问目标 URL。
2. take_snapshot 获取页面结构。
3. 识别登录方式、全局导航、核心模块。
4. 生成 TODO.md。
5. 为 P0 任务创建 BOOT 任务。

## 阶段二：记忆采集循环

每个任务按以下流程执行：

1. 明确采集目标。
2. 派发子 Agent 探索页面。
3. 子 Agent 返回结构化采集结果。
4. 主 Agent 审核并判断归档位置。
5. 派发子 Agent 调用 test-memory-organizer 写入 memory。
6. 更新 TODO.md 和 cases/INDEX.md。

## 阶段三：记忆深化

仅对核心模块进行轻量路径验证：

- 模块入口是否稳定。
- 关键页面是否可打开。
- 表单必填字段是否可识别。
- 关键按钮是否可点击。
- 弹窗和 Toast 是否可捕捉。
- 失败恢复方式是否可复用。

## 阶段四：生成冷启动报告

生成 MEMORY_BOOTSTRAP_REPORT.md，包括：

- 系统概览
- 模块拓扑
- 已生成记忆文件
- 已采集对象
- 已验证路径
- 已知问题
- 通用 skill 候选
- 未覆盖范围
