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
| 构建期默认值 | 应用根目录 `openlab.defaults.json`（示例见 `openlab.defaults.example.json`），可配置 brand/kernel/workspace/skin 默认值；用户运行时配置优先 |

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

2.6 **构建期默认值 / 默认工作区 / 皮肤定制**
   - [ ] `src/utils/openlabDefaults.ts` 存在；brandConfig / kernelService /
         workspaceService / skinService 的默认值均遵循
         `用户配置 > openlab.defaults.json > 硬编码默认`。
   - [ ] `src/server/services/workspaceService.ts` + `/api/workspace`；
         `sessionService.createSession` 未传 workDir 时使用
         `getDefaultWorkspaceDir()`。
   - [ ] 通用设置页含「默认工作区」（WorkspaceSettings）；
         `EmptySession.tsx` 预填默认工作区路径。
   - [ ] `src/server/services/skinService.ts` + `/api/skin`；
         桌面端 `skinStore`（SKIN_PRESETS + applyCurrent），
         通用设置页含「皮肤定制」（SkinSettings）；
         `App.tsx` 启动加载皮肤且主题切换时重新应用。
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
   - [ ] `desktop/src/App.tsx` 启动时调用 `useBrandStore.getState().fetchBrand()`。

4. **i18n 新增 key**（上游重写 locale 文件后需补回）
   - [ ] `settings.tab.kernel`、`settings.kernel.*`（14 个）、
         `settings.firstRun.*`（4 个）、`settings.about.ackCchaha`、
         `settings.tab.brand`、`settings.brand.*`（13 个）
         —— 五个 locale（en / zh / zh-TW / jp / kr）都要有。
   - [ ] 页面文案不得出现 cc-haha 字样（诊断页列出的真实 localStorage
         键名除外，那是功能性内容）。

5. **文档与致谢**
   - [ ] `ACKNOWLEDGEMENTS.md` 保留对 cc-haha（Claude Code 安全内核复现）
         与 jiuwenSwarm 的致谢（仓库级致谢保留；页面文案用「Claude Code
         安全修复版」指代默认内核，不出现 cc-haha）。
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

## 六、第 4 轮功能（账户/技能/Chrome use/Web 终端）

- 账户与云同步（mock）：`src/server/services/authService.ts`（登录、token 本地持久化、
  features 开关：运行时 app.json > openlab.defaults.json > 默认开启）、
  `syncService.ts`（四个 scope：agentConfig/skill/sessionHistory/memory，mock:// URL，
  历史上限 50 条）；REST：`/api/auth`、`/api/sync`；设置页"账户"选项卡。
- 对话框技能系统：`skillPrefsService.ts` + `/api/skill-prefs`；
  前端 `desktop/src/components/chat/SkillChips.tsx`（SkillPicker 本地+市场搜索、
  钉子常驻、拖动重排、分组、过长渐变、置入动效、双击改别名、气泡渲染）；
  ChatInput 加号菜单"置入技能"入口与 `/name` 前缀注入；
  通用设置中 `SkillPrefsSettings`（默认前缀技能 + 常驻默认值，构建期可用
  openlab.defaults.json 的 skillPrefs 段预置）。
- Chrome use 页签：`chromeUseService.ts`（chrome-devtools MCP 探测、Chrome>=144、
  9222 远程调试检查、`--remote-allow-origins=*` 启动）+ `/api/chrome-use`；
  前端 `ChromeUseSettings.tsx` 直连 CDP `Page.startScreencast` 串流画面。
- Web 部署终端：服务端 `src/server/ws/webTerminal.ts`（/ws/terminal/{id} 通道，
  Bun PTY 优先、pipe 回退，base64 输出）；前端 `desktop/src/api/terminal.ts`
  在无 Electron 宿主时自动走 WebSocket fallback，终端与文件系统（纯 HTTP API）在
  浏览器直连模式下均可用。
