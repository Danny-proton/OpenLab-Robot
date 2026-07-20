---
name: openlab-robot-rebrand
description: Openlab Robot 品牌改造与上游同步。当需要把 cc-haha（NanmiCoder/cc-haha）的新版本合并进 Openlab Robot、或对合并后的代码重放品牌改造（去 Claude Code Haha 字样、恢复内核切换/大模型选项卡/首用引导等结构性改动）时使用。也适用于检查品牌基线是否被破坏。
---

# Openlab Robot Rebrand

## 品牌基线

- 软件名（用户可见，可在设置→品牌定制中自定义）：**Openlab Robot**（默认）；appId `com.openlab.robot`
- 内核显示名：**Claude Code 安全修复版**（默认，内部 id `cc-haha`）、`jiuwen-Agent-core`（vendor/jiuwenswarm）
- 页面不得出现 cc-haha 字样（诊断页真实存储键名除外）
- 启动命令：`openlab-robot`（默认内核）、`jiuwen`（jiuwen 内核）
- 品牌定制：`~/.openlab-robot/brand.json` 驱动（appName/agentName/chatPlaceholder/systemPromptOverride），
  界面文案经 brandStore.applyBrand 实时替换，系统提示词经 brandConfig 读取
- 仓库：https://gitee.com/HongKongJournalist/OpenLab-Robot
- 外部链接一律指向 jiuwen：https://atomgit.com/openJiuwen/jiuwenswarm
- 环境变量名（CLAUDE_*/CC_HAHA_*/ANTHROPIC_*）、docs/、release-notes/ 不改

## 工作流程

1. **合并上游**：将 cc-haha 上游更新合入 Openlab Robot 分支，解决冲突时
   优先保留上游逻辑，品牌差异交给后续步骤重放。
2. **机械替换**：在仓库根目录运行
   `python3 scripts/openlab/apply_rebrand.py`
   脚本幂等；输出 `MISS-RULE`/`MISS-FILE` 说明上游改动了对应文本，
   定位新文本后更新脚本的 RULES 表再重跑。
3. **结构核对**：对照 `scripts/openlab/REBRAND_CHECKLIST.md` 第二节逐项检查
   （启动脚本、内核切换、IM 适配器停用、默认模型清空、首用弹窗、
   i18n 新增 key、致谢）。
4. **验证**：
   - `python3 scripts/openlab/apply_rebrand.py --check` 无 PENDING/MISS
   - `cd desktop && npm install && npm run build` 通过
   - `bin/openlab-robot --version` 可启动
5. **用户可见字样扫描**：排除 docs/、release-notes/、tests/ 后 grep
   `Claude Code Haha`、`Claude Code`、`cc-haha`（内核名除外）、
   `code.claude.com`、`claude.ai`，确认无新增用户可见泄漏。

## 红线

- 不改环境变量名；不改 `CLAUDE.md`、`.claude/skills` 等生态路径约定。
- 模型 ID 常量（如 claude-opus-4-7）是功能标识，不替换。
- 保留 `ACKNOWLEDGEMENTS.md` 对 cc-haha（Claude Code 安全内核复现）的致谢。
