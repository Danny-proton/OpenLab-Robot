# PRD — 统一报告门户与进度管理（V1.1 新增）

> 本文档定义 V1.1 的**统一报告门户（Report Portal）**与**执行进度埋点（Progress Telemetry）**。
> 解决 v2.3.0 / v1.1.0 的两个缺口：
> 1. 报告分散：`test_report.html` / `case_iteration_*.html` / `dashboard.html` / `*_diagnosis.md` 各自孤立，无统一入口浏览、检索、管理。
> 2. 进度丢失：`sidecar.py` 只把状态 JSON 打到 stdout，不落盘，无法在网站上回看执行流程、无法度量阶段耗时、无法定位卡点。

## 1. 目标与非目标

### 1.1 目标
1. **统一报告管理**：一个自包含 HTML 门户聚合 `reports/index.jsonl` 全部报告，支持检索/过滤/分类/预览/导出，取代"挨个打开文件"。
2. **执行进度可视化**：把 sidecar 的瞬时状态落盘成 `data/progress.jsonl`，门户上渲染阶段时间线、当前进度、阶段耗时、卡点告警。
3. **专业级可视化**：报告与门户采用统一设计语言（深色玻璃态 + 渐变 + 微动效），鼠标悬浮有反馈，"一看就很专业"。
4. **零外部依赖**：单文件 HTML，数据内联为 JS 对象，本地双击即可打开，无需起服务。

### 1.2 非目标
- 不做在线编辑报告（只读浏览 + 导出）。
- 不做多用户/鉴权（本地工作流）。
- 不做实时推送（生成时快照，非 WebSocket 流式）。

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│  数据层（.agent-eval/，全部 append-only / Git 可追踪）            │
│                                                                   │
│  reports/index.jsonl     ← report_manager 维护的报告索引          │
│  reports/*.html / *.md   ← 各报告生成器产出的报告文件             │
│  scores/*.json           ← 评测分数（门户 Overview 聚合）         │
│  data/progress.jsonl     ← 【新】progress_tracker 落盘的进度埋点  │
│  data/case_iterations.jsonl ← 用例自优化迭代历史                  │
└──────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
┌─────────────────────────┐      ┌─────────────────────────────┐
│ progress_tracker.py【新】│      │ report_portal.py【新】       │
│  - emit/list/latest/    │      │  - 聚合 index.jsonl          │
│    timeline/summary     │      │  - 聚合 progress.jsonl       │
│  - 被 sidecar.py 调用   │      │  - 聚合 scores/*.json        │
│  - 供门户查询           │      │  - 渲染单文件 portal.html    │
└─────────────────────────┘      └─────────────────────────────┘
              ▲                                │
              │                                ▼
┌─────────────────────────┐      ┌─────────────────────────────┐
│ sidecar.py【改】         │      │ reports/portal.html【新】    │
│  - --persist 默认开      │      │  统一门户（5 个页面）        │
│  - 调 progress_tracker   │      │  ① Overview ② Reports       │
│    落盘 + 仍打印 JSON    │      │  ③ Progress ④ Iterations    │
└─────────────────────────┘      │  ⑤ Quality                  │
                                 └─────────────────────────────┘
```

## 3. 进度埋点（Progress Telemetry）

### 3.1 痛点
`sidecar.py` 现状：`emit_status()` 把状态 JSON `print()` 到 stdout 就结束。orchestrator 每步调用它，但**没有任何脚本消费这个 stdout**，状态随终端滚走即丢失。无法回答："上一轮跑到第几步？哪步最慢？卡在哪？"

### 3.2 设计：progress_tracker.py（新脚本，零 LLM）

**职责**：进度事件的**持久化层** + **查询层**。sidecar 是事件**生产者**，progress_tracker 是**存储 + 查询**。

**存储**：`.agent-eval/data/progress.jsonl`（append-only，与 `case_iterations.jsonl` 同目录同风格）。

**事件 schema**（在 sidecar 现有字段上扩展）：
```json
{
  "event_id": "evt_20260717-014921_001",
  "tool": "agent-eval",
  "timestamp": "2026-07-17T01:49:21+08:00",
  "status": "running",            // pending | running | completed | failed | skipped
  "step": 3,
  "step_name": "用例执行",
  "total_steps": 9,
  "progress_pct": 33,
  "run_id": "20260717-014921-baseline-...",
  "session_id": "sess_...",        // 【新】区分多次运行
  "duration_ms": null,             // 【新】completed/failed 时填，阶段耗时
  "score": null,                   // 复用 sidecar 现有字段
  "extra": {}                      // 【新】任意附加（如 n_cases, n_diagnoses）
}
```

**CLI**：
```bash
# 落盘一条事件（sidecar 内部调用，也可直接用）
python progress_tracker.py --config .agent-eval/config.yaml emit \
  --status running --step 3 --step-name "用例执行" --run-id <run_id>

# 查询
python progress_tracker.py --config .agent-eval/config.yaml latest          # 最近一条
python progress_tracker.py --config .agent-eval/config.yaml list --limit 50 # 历史
python progress_tracker.py --config .agent-eval/config.yaml timeline        # 按阶段聚合
python progress_tracker.py --config .agent-eval/config.yaml summary         # 总览统计
```

**timeline 聚合输出**（供门户直接消费）：
```json
{
  "sessions": [
    {
      "session_id": "sess_...",
      "run_id": "20260717-...",
      "started_at": "...",
      "ended_at": "...",
      "current_step": 7,
      "current_status": "completed",
      "progress_pct": 78,
      "steps": [
        {"step": 1, "name": "启动前", "status": "completed", "duration_ms": 1200, "started_at": "...", "ended_at": "..."},
        {"step": 2, "name": "用例生成", "status": "completed", "duration_ms": 8500, "started_at": "...", "ended_at": "..."},
        {"step": 3, "name": "用例执行", "status": "failed", "duration_ms": 42000, "started_at": "...", "ended_at": "...", "error": "..."}
      ]
    }
  ]
}
```

**duration_ms 计算**：同一 step 的 `running` → `completed/failed` 两条事件的时间差。step 跨多条 running 事件取首条 running → 末条终态。

### 3.3 sidecar.py 改造（向后兼容）

- 新增 `--persist`（默认 `true`）：调 `progress_tracker.emit` 落盘。
- 新增 `--no-persist`：关闭落盘（CI 等场景）。
- **保留**原有 stdout JSON 输出（向后兼容现有 orchestrator 调用契约）。
- 新增 `--session-id`：可选，未传则自动生成（基于首次 running 的时间戳）。

### 3.4 埋点插入位置（更新 orchestrator / 各子 skill）

orchestrator/SKILL.md 已规定每步调 sidecar。本 PRD 不改调用点，只改 sidecar 行为（自动落盘）。额外在以下脚本的关键节点插入 sidecar 调用，使进度粒度更细：
- `eval_runner.py`：每个 case 执行后可选 `sidecar --status running --step 3 --extra '{"n_done": i}'`（轻量，可关）。
- `case_optimizer.py`：apply 前后 `sidecar --status running --step 4.5`。

## 4. 统一报告门户（Report Portal）

### 4.1 设计原则
1. **单文件 HTML**：CSS/JS/数据全内联，本地双击打开，可丢 Git。
2. **深色玻璃态**：与 dashboard.py 一致的 `#0f172a` 基底，但升级为玻璃态卡片 + 渐变描边。
3. **微动效**：所有可交互元素 hover 有 transition（transform/box-shadow/opacity），卡片悬浮上浮 + 发光。
4. **5 页结构**：Overview / Reports / Progress / Iterations / Quality。

### 4.2 页面设计

#### Page 1: Overview（总览）
- 顶部 6 张 KPI 卡片：总报告数、HTML 报告数、评测 Run 数、平均分、用例自优化迭代数、当前进度。
- 每张卡片 hover 上浮 + 渐变描边发光，点击跳转对应页。
- 最近 5 次 Run 分数趋势（mini SVG 折线，hover 点显示 run_id + 分数）。
- 最近 5 条报告列表（hover 高亮 + 显示路径 tooltip）。

#### Page 2: Reports（报告统一管理）★ 核心
- **检索栏**：关键词搜索（匹配 report_id/title/run_id/tags/notes）+ 类型过滤 + 格式过滤 + 日期范围。
- **报告卡片网格**：每张卡片显示 title / type 徽章 / format 图标 / run_id / 创建时间 / tags。
  - hover：卡片上浮 4px + 阴影加深 + 左侧渐变条点亮 + 显示完整路径 tooltip。
  - 点击：展开行内预览（md 报告渲染前 50 行；html 报告显示"在新标签打开"按钮）。
- **批量操作**：选中后可导出（复制路径）/ 加标签 / 删除（调 report_manager，需确认）。
- **空状态**：无报告时显示引导（"先跑 eval_runner.py 生成报告"）。
- 数据源：`report_manager.list_reports()` 的 JSON。

#### Page 3: Progress（执行进度管理）★ 核心
- **当前运行卡片**：大号进度环（SVG circle，渐变描边，hover 显示百分比 tooltip）+ 当前步骤名 + 状态徽章 + run_id。
- **阶段时间线**：横向 9 步时间线，每步一个节点。
  - 节点状态色：completed=绿 / running=蓝脉冲 / failed=红 / pending=灰。
  - hover 节点：弹出 tooltip 显示步骤名 + 耗时 + 起止时间 + extra。
  - running 节点带 CSS 脉冲动画。
- **阶段耗时条形图**：各步 duration_ms 横向条形，hover 显示精确耗时 + 占比。
- **历史会话列表**：每个 session 一行，可展开看该 session 的完整步骤。
- 数据源：`progress_tracker.timeline` 的 JSON。

#### Page 4: Iterations（用例自优化迭代历史）
- 消费 `data/case_iterations.jsonl`。
- 每次迭代一张卡片：proposal_id / run_id / 质量分前后对比（带 ↑↓ 箭头与颜色）/ 新增-修改-废弃计数 / mutation 检出率。
- hover 卡片展开看建议摘要。
- 质量分趋势 mini 折线。

#### Page 5: Quality（用例质量看板）
- 消费最近一次 `case_quality_*.json`。
- 12 维质量分雷达图（SVG，hover 维度显示权重 + 得分 + 状态）。
- 低分维度高亮卡片。

### 4.3 可视化设计规范（统一设计语言）

| 元素 | 规范 |
|------|------|
| 基底色 | `#0f172a`（slate-900）|
| 卡片 | `rgba(30,41,59,0.7)` + `backdrop-filter: blur(12px)` + `1px solid rgba(99,102,241,0.15)` |
| 主色 | `#6366f1`（indigo-500）渐变到 `#8b5cf6`（violet-500）|
| 成功 | `#22c55e`；失败 `#ef4444`；警告 `#fbbf24`；信息 `#3b82f6` |
| hover 动效 | `transition: all .2s cubic-bezier(.4,0,.2,1)`；卡片 `transform: translateY(-4px)` + `box-shadow: 0 12px 32px rgba(99,102,241,.25)` |
| 表格行 hover | 背景 `rgba(99,102,241,0.08)` + 左侧 2px 渐变条 |
| 徽章 | 圆角 999px + 半透明背景 + 对应色文字 |
| 进度环 | SVG `stroke-dasharray` + `stroke-dashoffset` + `linearGradient` |
| 字体 | `-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei"` |

## 5. 报告可视化重构（generate_report / case_iteration_report）

### 5.1 痛点
- `generate_report.py` 的 `data/test_report.html`：浅色 + 蓝色渐变头，卡片扁平，hover 仅表格行变色；且有 `output_path` 未定义 bug（line 66）。
- `case_iteration_report.py` 的 HTML：浅色 + indigo，表格为主，无 hover 动效，无图表。

### 5.2 重构目标
两份报告升级到与门户一致的**深色玻璃态 + 渐变 + 微动效**设计语言，并新增：
- `generate_report.py`：维度通过率横向条形图（hover 显示精确数）、优先级分布饼图、响应时间分布。
- `case_iteration_report.py`：质量分前后对比柱状图、mutation kill matrix 热力图、错误分布 Pareto 图。

### 5.3 共享样式
提取 `report_portal.py` 的 CSS 为 `PORTAL_CSS` 常量，两份报告生成器复用同一套类名（`.card` / `.stat` / `.badge` / `.progress-bar`），保证视觉一致。

## 6. 数据契约

### 6.1 progress_tracker.emit 输入
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | str | 是 | pending/running/completed/failed/skipped |
| step | int | 是 | 1-9 |
| step_name | str | 否 | 默认查 STEPS 表 |
| run_id | str | 否 | 关联评测 run |
| session_id | str | 否 | 未传自动生成 |
| extra | dict | 否 | 任意附加 |

### 6.2 report_portal 输入（聚合）
```python
{
  "reports": [...],          # report_manager.list_reports()
  "progress_timeline": {...},# progress_tracker.timeline
  "progress_latest": {...},  # progress_tracker.latest
  "iterations": [...],       # case_io.load_iterations
  "latest_quality": {...},   # 最近 case_quality_*.json
  "runs": [...],             # dashboard.collect_all_data 的 runs
  "generated_at": "..."
}
```

## 7. CLI

```bash
# 生成门户（聚合全部数据）
python report_portal.py --config .agent-eval/config.yaml
# → reports/portal.html，并自动 register_report

# 仅刷新进度数据（不重渲染门户）
python progress_tracker.py --config .agent-eval/config.yaml summary
```

## 8. 验收标准

- [ ] `progress_tracker.py emit` 落盘到 `data/progress.jsonl`，`list/latest/timeline/summary` 查询正确
- [ ] `sidecar.py --persist`（默认）调 progress_tracker 落盘；`--no-persist` 不落盘；stdout JSON 不变
- [ ] `report_portal.py` 生成单文件 `portal.html`，5 个页面均可切换，数据正确
- [ ] 门户 Reports 页检索/过滤/分类/预览均可用，hover 动效生效
- [ ] 门户 Progress 页进度环、阶段时间线、耗时条形图正确渲染，hover tooltip 生效
- [ ] `generate_report.py` 修复 `output_path` bug，HTML 升级到深色玻璃态 + hover 动效 + 维度图表
- [ ] `case_iteration_report.py` HTML 升级，新增质量分对比图 + mutation 热力图 + Pareto 图
- [ ] 端到端：mock 系统跑一轮 → 门户能同时展示报告 + 进度 + 迭代 + 质量
- [ ] 零外部依赖：portal.html 本地双击可打开

## 9. 与现有能力的关系

| 现有 | 本 PRD 的关系 |
|------|--------------|
| `report_manager.py` | **复用**：门户的 Reports 页直接调 `list_reports/search_reports`，不重造索引 |
| `sidecar.py` | **改造**：加 `--persist` 调 progress_tracker，向后兼容 |
| `dashboard.py` | **并存**：dashboard 是单 run 深度分析（10 页），门户是多 run/多报告统一管理（5 页），二者互补，门户 Overview 链接到 dashboard |
| `case_iteration_report.py` | **改造**：HTML 可视化升级 |
| `generate_report.py` | **改造**：HTML 可视化升级 + bug 修复 |
| `case_io.load_iterations` | **复用**：门户 Iterations 页数据源 |

## 10. 版本规划

| 版本 | 内容 | 状态 |
|------|------|------|
| v1.1.1 | progress_tracker + sidecar 改造 + report_portal + 两份报告可视化重构 | 本次开发 |
| v1.1.2 | 门户支持报告在线 diff（before/after cases）、进度实时刷新（轮询） | 待规划 |
