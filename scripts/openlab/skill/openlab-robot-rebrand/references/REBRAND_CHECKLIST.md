# Openlab Robot 品牌改造检查清单

> 用途：cc-haha 上游（NanmiCoder/cc-haha）每次版本更新合并后，按本清单重放
> Openlab Robot 品牌改造。配套自动化脚本：`scripts/openlab/apply_rebrand.py`。
> 对应 AI 技能：`openlab-robot-rebrand`（见 SKILL.md 分发包）。

## 品牌基线（必须保持一致）

| 项 | 值 |
|---|---|
| 软件名（用户可见，可在设置中自定义） | **Openlab Robot**（默认） |
| 内核显示名 | **Claude Code 安全修复版**（默认，内部 id `cc-haha`）、`jiuwen-Agent-core` |
| 页面上的 cc-haha 字样 | **不允许出现**（技术性存储键名除外） |
| 主启动命令 | `openlab-robot`（默认内核） |
| jiuwen 内核启动命令 | `jiuwen`（启动 vendor/jiuwenswarm 的 TUI） |
| appId / identifier | `com.openlab.robot` |
| 安装包文件名 | `Openlab-Robot-${version}-${os}-${arch}.${ext}` |
| 目标仓库 | https://gitee.com/HongKongJournalist/OpenLab-Robot |
| 外部文档链接 | https://atomgit.com/openJiuwen/jiuwenswarm |
| 品牌定制配置 | `~/.openlab-robot/brand.json`（appName/agentName/chatPlaceholder/systemPromptOverride） |

## 一、机械替换（脚本自动完成）

运行：

```bash
python3 scripts/openlab/apply_rebrand.py          # 应用
python3 scripts/openlab/apply_rebrand.py --check  # 只检查
```

覆盖：应用标识、包名、窗口标题、托盘/菜单、关于页、i18n「大模型」改名、
TUI 欢迎语、system prompt 身份、外部链接 → jiuwen。
脚本输出 `MISS` 说明上游改动了对应文本，需人工按下方条目核对新位置。

## 二、结构性改造（上游合并后逐项核对）

1. **启动脚本**
   - [ ] `bin/openlab-robot`：内核感知启动（读 `~/.openlab-robot/kernel.json`，
         按内核导出 `CLAUDE_CONFIG_DIR`）。
   - [ ] `bin/jiuwen`：启动 `vendor/jiuwenswarm` 的 TUI（Node dist 优先，
         回退 `python3 -m jiuwenswarm.cli.main`）。
   - [ ] `bin/claude-haha` 仅为转发别名。
   - [ ] 根 `package.json` 的 `bin` 映射包含 `openlab-robot` / `jiuwen`。

2. **内核切换机制**
   - [ ] `src/server/services/kernelService.ts` 存在（内核配置读写、默认目录：
         cc-haha → `~/.claude`，jiuwen-agent-core → `~/.jiuwenswarm`，
         支持 `configDir` 自定义覆盖）。
   - [ ] `src/server/api/kernel.ts` + `src/server/router.ts` 注册 `kernel` 路由。
   - [ ] `src/utils/envUtils.ts` 的 `getClaudeConfigHomeDir` 回退到
         `getKernelDefaultConfigDir()`（而非硬编码 `~/.claude`），
         且内核目录按 mtime+TTL 缓存（防止热路径频繁读盘导致卡顿）。
   - [ ] 桌面端 `desktop/src/components/settings/KernelSettings.tsx`（乐观更新）、
         `desktop/src/api/kernel.ts` 存在；设置页有「内核」选项卡；
         内核显示名为「Claude Code 安全修复版」（界面不得出现 cc-haha 字样）。
   - [ ] `src/components/LogoV2/KernelHint.tsx` 存在并在 `LogoV2.tsx`
         两种布局的返回 fragment 中渲染（提示 jiuwen 内核换用 `jiuwen` 命令）。

2.5 **品牌定制机制（Openlab Robot 核心能力）**
   - [ ] `src/utils/brandConfig.ts`（共享读取层）与
         `src/server/services/brandService.ts`、`src/server/api/brand.ts` 存在，
         路由注册 `brand`。
   - [ ] 系统提示词身份可定制：`src/constants/system.ts` 的
         `getCLISyspromptPrefix` 优先使用 `systemPromptOverride`；
         `src/constants/prompts.ts` 使用 `getBrandSystemPromptPrefix()` /
         `getDefaultAgentPrompt()`。
   - [ ] 桌面端 `desktop/src/stores/brandStore.ts`：`applyBrand()` 替换引擎
         （Claude Code Haha→appName、Claude Code→appName、单独 Claude→agentName、
         ~/.claude→内核生效目录；保护「Claude Code 安全修复版」短语），
         `translate()` 与 `useTranslation()` 已接入。
   - [ ] 设置页有「品牌定制」选项卡（BrandSettings），可编辑
         应用名/智能体名/对话框占位提示/系统提示词。
   - [ ] `ChatInput.tsx` 占位提示优先使用 `chatPlaceholder` 定制值。
   - [ ] 侧边栏标题、通知标题（chatStore）使用 `appName`。
   - [ ] 终端页 `TerminalKernelGuide`（按内核显示不同引导 + 流动边框动画），
         TerminalSettings 激活/spawn 后自动 `terminal.focus()`。

3. **界面**
   - [ ] `desktop/src/pages/Settings.tsx`：IM 适配器选项卡与内容保持注释停用；
         「内核」选项卡已注册；关于页显示 Openlab Robot + 致谢区块。
   - [ ] `desktop/src/stores/uiStore.ts`：`SETTINGS_TABS` 与 `SettingsTab`
         类型包含 `'kernel'`。
   - [ ] `desktop/src/constants/modelCatalog.ts` /
         `openaiOfficialProvider.ts` / `grokOfficialProvider.ts`：
         `OFFICIAL_MODELS` / `OPENAI_OFFICIAL_MODELS` / `GROK_OFFICIAL_MODELS`
         均为空数组（不内置默认模型）。
   - [ ] `BUILT_IN_PROVIDER_IDS` 为空数组（隐藏内置官方供应商，仅 custom）。
   - [ ] `desktop/src/components/onboarding/FirstRunModelModal.tsx` 存在，
         且 `desktop/src/App.tsx` 中已挂载（首次使用弹出配置 custom 模型提示）。
   - [ ] `src/components/LogoV2/KernelHint.tsx` 存在并在 `LogoV2.tsx`
         两种布局的返回 fragment 中渲染。

4. **i18n 新增 key**（上游重写 locale 文件后需补回）
   - [ ] `settings.tab.kernel`、`settings.kernel.*`（14 个）、
         `settings.firstRun.*`（4 个）、`settings.about.ackCchaha`
         —— 五个 locale（en / zh / zh-TW / jp / kr）都要有。

5. **文档与致谢**
   - [ ] `ACKNOWLEDGEMENTS.md` 保留对 cc-haha（Claude Code 安全内核复现）
         与 jiuwenSwarm 的致谢。
   - [ ] docs/、release-notes/ 不改动（按需求保持上游原文）。

## 三、保持不变项（切勿"顺手优化"）

- 环境变量名：`CLAUDE_*` / `CC_HAHA_*` / `ANTHROPIC_*` 一律不改。
- `CLAUDE.md`、`.claude/skills` 等项目级约定路径不改（生态兼容）。
- 模型 ID 常量（如 `claude-opus-4-7`）为功能标识，不属于品牌文案。

## 四、验证步骤

```bash
python3 scripts/openlab/apply_rebrand.py --check   # 无 PENDING/MISS
cd desktop && npm install && npm run build          # 前端构建通过
bun test src/server/__tests__ 2>/dev/null || true   # 服务端测试（可选）
bin/openlab-robot --version                          # CLI 可启动
```

## 五、jiuwenSwarm 内核更新

`vendor/jiuwenswarm` 为 jiuwenSwarm（openJiuwen-ai/jiuwenswarm，v0.2.3）的
源码快照（剔除 .git/node_modules/__pycache__/dist）。更新时整目录替换，
并确认 `bin/jiuwen` 的两个启动入口仍存在：
`jiuwenswarm/channels/tui/frontend/dist/index.js` 与
`python3 -m jiuwenswarm.cli.main`。
