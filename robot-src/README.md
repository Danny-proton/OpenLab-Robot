# OpenLab Robot 源码

从 Docker 镜像 `openlab-robot-web.tar` 中提取的 TypeScript 源码。

## 目录结构

```
robot-src/
└── app/
    ├── src/                    # 主源码（2344 文件）
    │   ├── main.tsx            # 主入口
    │   ├── Tool.ts             # Tool 接口定义
    │   ├── Task.ts             # Task 接口
    │   ├── QueryEngine.ts      # 查询引擎
    │   ├── tools/              # 内置工具（Bash/Read/Write/Edit/Grep/Glob/...）
    │   ├── commands/           # 斜杠命令
    │   ├── entrypoints/        # CLI / 桌面端入口
    │   ├── server/             # HTTP/WebSocket 服务
    │   ├── services/           # 业务服务（mcp/cron/memory/...）
    │   ├── skills/             # Skill 系统
    │   ├── hooks/              # Hook 系统
    │   ├── plugins/            # Plugin 系统
    │   ├── agents/             # Agent 系统
    │   ├── adapters/           # IM 适配器（telegram/wechat/feishu/dingtalk）
    │   └── ...
    ├── adapters/               # IM 适配器源码（独立包）
    │   ├── common/             # 共享代码
    │   ├── telegram/
    │   ├── wechat/
    │   ├── feishu/
    │   └── dingtalk/
    ├── bin/                    # 可执行文件
    │   ├── claude-haha         # CLI 入口
    │   └── terminal-server
    ├── desktop/                # 桌面端（Electron + React 编译产物）
    ├── runtime/                # 运行时辅助（Python）
    └── entrypoint.sh           # Docker 入口
```

## 说明

- 这是编译前的 TypeScript 源码，不是编译后的 JS
- `node_modules` 已排除（体积太大）
- `desktop/dist/` 是前端编译产物（含 assets）
- 基于 Claude Code 源码修复而来，保留 CLI 协议 / Tool 接口 / MCP 支持
