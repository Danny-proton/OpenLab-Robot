# OpenLab Robot


---

Openlab-Robot（曾用名AgentBus）是一个原生集成了桌面执行、网页执行能力的，方便内源扩展及二次开发，基于 2026-03-31 从 Anthropic npm registry 泄露的 Claude Code 源码修复而来。

把网页录制回放、智能执行（BrowserUse）、桌面智能执行（ComputerUse）、会话、多项目、分支 / Worktree、右侧代码改动、代码 Diff、权限审批、模型提供商、Computer Use、H5 远程访问、welink接入和定时任务集中到一个Windows APP 里。支持多AI模型集成、技能系统、插件框架、渠道管理、记忆系统等企业级功能。

定位是一款面向公司内部研发团队的 AI 通用CoWorker 执行助手。本项目由行解团队牵头研发，旨在为开发者提供一个安全、高效的本地化 AI自闭环本地执行环境。


## 项目核心能力

**全场景执行终端：** 一套桌面应用内集中了桌面智能执行（Computer Use）、网页录制回放与智能执行（BrowserUse）、H5 远程访问和定时任务等能力，支持Windows、Linux 两大平台。

**多AI模型与企业级功能：** 支持多 AI 模型集成，原生接入支持Openlab绿区官方提供的模型内置 Provider，同时兼容 Anthropic-compatible、OpenAI-compatible、DeepSeek 等第三方 API方便蓝区使用，支持 OAuth 登录、模型目录浏览和运行时环境自动注入。内置会话管理、多项目支持、分支/Worktree、代码 Diff、权限审批、IM 接入（WeLink）和跨会话记忆系统。

**高度可扩展框架：** 提供技能系统（Skills）、插件框架（Plugin）与标准化 MCP 工具接口，便于内部团队进行二次开发和能力扩展。

---


## 桌面端亮点

- **多会话工作台**：标签页、项目切换、终端入口和会话历史集中管理。
- **分支 / Worktree 启动**：新会话可以选择仓库分支，并决定使用当前工作树还是隔离 Worktree。
- **右侧代码改动面板**：聊天时直接在右侧查看已更改文件、增删行和当前工作区状态。
- **代码修改可视化**：直接查看 AI 对文件的编辑、Diff 和执行过程。
- **权限与确认流**：危险命令、工具调用和 AI 反问可以在桌面端集中审批。
- **多模型提供商**：支持 Anthropic 兼容 API、第三方模型、WebSearch fallback 和本地配置。
- **Robot Browser Use**：让 Agent 在授权后通过MCP控制Chrome浏览器。
- **Robot Computer Use**：让 Agent 在授权后截图、点击、输入并控制桌面应用。
- **H5 远程访问**：用一次性令牌在手机或其他设备上接入当前桌面端会话。
- **IM 接入**：通过 Welink 远程对话、切换项目和审批权限，也可以控制Welink对话、邮件。
- **定时任务与用量统计**：在桌面端创建计划任务，并查看本机 Token 使用趋势。

---

## 更多文档

| 文档                                            | 说明                                                         |
| ----------------------------------------------- | ------------------------------------------------------------ |
| [环境变量](docs/guide/env-vars.md)              | 完整环境变量参考和配置方式                                   |
| [第三方模型](docs/guide/third-party-models.md)  | 默认接入Openlab官方，支持接入 OpenAI / DeepSeek / Ollama 等OpenAI及Anthropic格式模型 |
| [贡献与质量门禁](docs/guide/contributing.md)    | 本地测试、真实模型 baseline、PR 和 release 门禁              |
| [记忆系统](docs/memory/01-usage-guide.md)       | 跨会话持久化记忆的使用与实现                                 |
| [多 Agent 系统](docs/agent/01-usage-guide.md)   | 多代理编排、并行任务执行与 Teams 协作                        |
| [Skills 系统](docs/skills/01-usage-guide.md)    | 可扩展能力插件、自定义工作流与条件激活                       |
| [IM 接入](docs/im/)                             | 通过 Welink（绿区）远程对话、切换项目和审批权限              |
| [Computer Use](docs/features/computer-use.md)   | 桌面控制功能（截屏、鼠标、键盘）— [架构解析](docs/features/computer-use-architecture.md) |
| [桌面端](docs/desktop/)                         | Tauri 2 + React 图形化客户端 — [快速上手](docs/desktop/01-quick-start.md) \| [架构设计](docs/desktop/02-architecture.md) \| [安装指南](docs/desktop/04-installation.md) |
| [全局使用](docs/guide/global-usage.md)          | 在任意目录启动OpenLab-Robot或TUI启动ClaudeCode               |
| [常见问题](docs/guide/faq.md)                   | 常见错误排查                                                 |
| [源码修复记录](docs/reference/fixes.md)         | 相对于原始泄露源码的修复内容                                 |
| [项目结构](docs/reference/project-structure.md) | 代码目录结构说明                                             |
| [核心机制](http://10.246.136.104:3004/zh/)      | 手把手拆解CLaudeCode/OpenlabRobot最核心原理                  |

---

## 快速开始

**OpenLab AI Robot Client客户端 及 环境一键安装部署包**

具有如下特点：

• ✅ 离线安装 Node.js 24+

• ✅ 自动配置 npm 内网镜像 + 忽略证书 + D盘缓存

• ✅ 自动安装 OpenLab AI Robot 客户端

• ✅ 自动探测 Git 安装路径并设置 CLAUDE_CODE_GIT_BASH_PATH

• ✅ 若未找到 Git，自动执行安装程序

• ✅ 自动配置 Claude 启动所需要环境变量 API Key + Openlab 大模型 Base URL

• ✅ 复制默认 ~/.claude.json 和 ~/.claude/settings.json

• ✅ 自动配置 C:\Windows\System32\drivers\etc\hosts 来过滤 statsig.anthropic.com 等请求。

• ✅ 日志记录 + 容错提示



绿区包获取地址：https://openx.huawei.com/Openlab-Robot/dynamics

蓝区包获取地址：请进群用户群咨询，群号：926199585930793702

-----

### 安装步骤：（请阅读后再进行安装）

1. 解压本OpenlabRobot-RuntimeInstaller压缩包到一个固定目录（如：D:/OpenLabRobot）

2. 双击运行 install1.bat

3. 提示***Please run install2.bat to continue***，双击运行install2.bat

4. 等待脚本执行完成 （如果没有安装过Git需要手动操作弹出的安装程序，选项均默认即可）

5. 若遇到报错，可以重新执行bat文件

6. 关闭当前终端，重新打开新终端（在开始菜单搜索：“终端”或“Powershell”，普通模式运行无需管理员模式）

7. 验证：输入claude并按回车，若显示聊天界面说明TUI内核安装成功，可以启动客户端开始使用。

8. 客户端安装：运行Openlab Robot MSI安装程序，选择当前目录作为安装目录，等待安装完成。

9. 客户端启动：在桌面找到OpenlabRobot快捷方式，双击打开

-----


### 针对测试用户的插件安装指导：

前置要求：

Claude Code 已安装并能正常运行
安装步骤：

打开安装包目录，右键空白处打开终端


输入
claude plugin marketplace add ./

安装插件，输入

-   TaaS-MCP（TaaS操作插件）：

> claude plugin install taas-mcp

- Chrome-devtools-mcp（Chrome操作插件）:

> claude plugin install chrome-devtools-mcp

- website-traversing（自主遍历Skill）

> claude plugin install website-traversing


**TaaS-MCP 插件 - 使用指南：**
参考如下博客：https://3ms.huawei.com/km/blogs/details/22268761
也可以参考附件中的指导视频


**OpenlabRobot客户端设置里配置服务商：**

请进群用户群咨询，群号：926199585930793702

-----

### Chrome 版本升级及 Debugging 模式


**1、检查当前 Chrome 版本**

- 打开 Chrome 浏览器
- 点击地址栏右侧的 三个点 菜单图标
- 选择 帮助 > 关于 Google Chrome
- 查看当前版本号，确认 版本大于 144

-----

**2、 版本低于 144 时在HIS找到最新Chrome安装升级**



**蓝区检查Chrome版本：**

若当前版本低于 144，请按以下步骤升级：

打开系统 应用管理（设置 > 应用 > 应用和功能）
找到 Google Chrome，点击 卸载
注意：卸载后用户数据（书签、密码、扩展等）会被保留
点击 Chrome 一键安装包，按提示完成安装
**绿区检查Chrome版本：**

HIS市场找到 > 144的chrome版本，下载并安装，无需卸载

-------------------

**3. 开启远程调试模式**

打开高版本 Chrome 浏览器

在地址栏输入：

> chrome://inspect/#remote-debugging

按 Enter 回车

勾选 Allow remote debugging for this browser instance

完成以上步骤即表示浏览器设置完毕，可正常进行远程调试。





测试设计/执行相关：

• 安装包内置了robotskill技能，用于连接Openlab技能市场RobotSkill（可在浏览器访问：RobotSkill - 软件工程技能目录 ）；内置了TaaS-MCP插件用于Agent自主操作TaaS平台，具体安装指导可查看plugins文件夹内容。

• Openlab技能市场内置了测试设计/执行相关的Skill，可以直接向Agent提出安装相关技能的要求即可安装。例如输入：“请在robotskill市场里找出测试设计、测试执行相关的技能安装”。

=======

• ✅ 自动安装 OpenLab AI Robot 客户端

• ✅ 自动探测 Git 安装路径并设置 CLAUDE_CODE_GIT_BASH_PATH

• ✅ 若未找到 Git，自动执行安装程序

• ✅ 自动配置 Claude 启动所需要环境变量 API Key + Openlab 大模型 Base URL

• ✅ 复制默认 ~/.claude.json 和 ~/.claude/settings.json

• ✅ 自动配置 C:\Windows\System32\drivers\etc\hosts 来过滤 statsig.anthropic.com 等请求。

• ✅ 日志记录 + 容错提示



绿区包获取地址：https://openx.huawei.com/Openlab-Robot/dynamics

蓝区包获取地址：请进群用户群咨询，群号：926199585930793702

-----

### 安装步骤：（请阅读后再进行安装）

1. 解压本OpenlabRobot-RuntimeInstaller压缩包到一个固定目录（如：D:/OpenLabRobot）

2. 双击运行 install1.bat

3. 提示***Please run install2.bat to continue***，双击运行install2.bat

4. 等待脚本执行完成 （如果没有安装过Git需要手动操作弹出的安装程序，选项均默认即可）

5. 若遇到报错，可以重新执行bat文件

6. 关闭当前终端，重新打开新终端（在开始菜单搜索：“终端”或“Powershell”，普通模式运行无需管理员模式）

7. 验证：输入claude并按回车，若显示聊天界面说明TUI内核安装成功，可以启动客户端开始使用。

8. 客户端安装：运行Openlab Robot MSI安装程序，选择当前目录作为安装目录，等待安装完成。

9. 客户端启动：在桌面找到OpenlabRobot快捷方式，双击打开

-----


### 针对测试用户的插件安装指导：

前置要求：

Claude Code 已安装并能正常运行
安装步骤：

打开安装包目录，右键空白处打开终端


输入
claude plugin marketplace add ./

安装插件，输入

-   TaaS-MCP（TaaS操作插件）：

> claude plugin install taas-mcp

- Chrome-devtools-mcp（Chrome操作插件）:

> claude plugin install chrome-devtools-mcp

- website-traversing（自主遍历Skill）

> claude plugin install website-traversing


**TaaS-MCP 插件 - 使用指南：**
参考如下博客：https://3ms.huawei.com/km/blogs/details/22268761
也可以参考附件中的指导视频


**OpenlabRobot客户端设置里配置服务商：**

请进群用户群咨询，群号：926199585930793702

-----

### Chrome 版本升级及 Debugging 模式


**1、检查当前 Chrome 版本**

- 打开 Chrome 浏览器
- 点击地址栏右侧的 三个点 菜单图标
- 选择 帮助 > 关于 Google Chrome
- 查看当前版本号，确认 版本大于 144

-----

**2、 版本低于 144 时在HIS找到最新Chrome安装升级**



**蓝区检查Chrome版本：**

若当前版本低于 144，请按以下步骤升级：

打开系统 应用管理（设置 > 应用 > 应用和功能）
找到 Google Chrome，点击 卸载
注意：卸载后用户数据（书签、密码、扩展等）会被保留
点击 Chrome 一键安装包，按提示完成安装
**绿区检查Chrome版本：**

HIS市场找到 > 144的chrome版本，下载并安装，无需卸载

-------------------

**3. 开启远程调试模式**

打开高版本 Chrome 浏览器

在地址栏输入：

> chrome://inspect/#remote-debugging

按 Enter 回车

勾选 Allow remote debugging for this browser instance

完成以上步骤即表示浏览器设置完毕，可正常进行远程调试。





测试设计/执行相关：

• 安装包内置了robotskill技能，用于连接Openlab技能市场RobotSkill（可在浏览器访问：RobotSkill - 软件工程技能目录 ）；内置了TaaS-MCP插件用于Agent自主操作TaaS平台，具体安装指导可查看plugins文件夹内容。

• Openlab技能市场内置了测试设计/执行相关的Skill，可以直接向Agent提出安装相关技能的要求即可安装。例如输入：“请在robotskill市场里找出测试设计、测试执行相关的技能安装”。

---

## 早期问题单管理

'''
https://onebox.huawei.com/v/5c4ca65e8eb38c10dd9077de5deb06d6?type=1&sheet=%E5%AE%A2%E6%88%B7%E7%AB%AF%E9%97%AE%E9%A2%98-%E6%94%BF%E5%8A%A1%20
'''

>>>>>>> acbac314d41e8a73a9695e096d0072bb92dfb300

---

## 技术栈

| 类别       | 技术                                               |
| ---------- | -------------------------------------------------- |
| 语言       | TypeScript                                         |
| 桌面 APP   | Tauri 2                                            |
| 桌面 UI    | React + Vite                                       |
| 本地运行时 | [Bun](https://bun.sh)                              |
| 终端 UI    | React + [Ink](https://github.com/vadimdemedes/ink) |
| CLI 解析   | Commander.js                                       |
| API        | Anthropic SDK                                      |
| 协议       | MCP, LSP                                           |

## 感谢

感谢以下开源项目和社区实践为本项目提供参考与启发：

- [React](https://github.com/facebook/react)：前端工程与组件化 UI 生态。
- [Tauri](https://github.com/tauri-apps/tauri)：跨端桌面应用能力与工程实践。
- [cc-switch](https://github.com/farion1231/cc-switch)：模型供应商配置能力参考。
