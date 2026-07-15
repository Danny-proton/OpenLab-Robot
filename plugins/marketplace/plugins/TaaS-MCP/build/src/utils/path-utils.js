import * as path from "path";
/**
 * 将相对路径解析到插件工作目录下（即 CLAUDE_PLUGIN_DATA 目录）。
 * 环境配置文件、用户鉴权 token 等保存在此目录下。
 * 环境变量: PLUGIN_PATH (由 .mcp.json 传入)
 */
export function resolvePluginPath(relativePath) {
    const basePath = process.env.PLUGIN_PATH || ".";
    return path.resolve(basePath, relativePath);
}
/**
 * 将相对路径解析到 Agent 工作目录下。
 * 用例导出、需求文档等 Agent 生成的文件保存在此目录下。
 * 环境变量: AGENT_WORKING_PATH (未设置时回退到 process.cwd())
 */
export function resolveAgentPath(relativePath) {
    const basePath = process.env.AGENT_WORKING_PATH || process.cwd();
    return path.resolve(basePath, relativePath);
}
export { path };
