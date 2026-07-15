import { loadEnvironmentConfig } from "../config/environments.js";
/**
 * 注册查询可用环境工具
 */
export function registerListAvailableEnvironmentsTool(server) {
    server.registerTool("list_available_environments", {
        title: "查询可用环境",
        description: "查询 environments.json 配置文件中定义的所有可用环境",
        inputSchema: {},
    }, async () => {
        try {
            const config = await loadEnvironmentConfig();
            const environments = Object.entries(config).map(([key, value]) => ({
                name: key,
                displayName: value.displayName,
                baseUrl: value.baseUrl,
                authTokenPath: value.authTokenPath,
            }));
            return {
                content: [
                    {
                        type: "text",
                        text: `可用环境列表（共 ${environments.length} 个）:\n\n` +
                            environments.map((env, index) => `${index + 1}. **${env.name}** - ${env.displayName}\n` +
                                `   - Base URL: ${env.baseUrl}\n` +
                                `   - Token 文件：${env.authTokenPath}`).join("\n"),
                    },
                ],
                isError: false,
            };
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            console.error("[list_available_environments] Error:", errorMessage);
            return {
                content: [
                    {
                        type: "text",
                        text: `查询可用环境失败：${errorMessage}`,
                    },
                ],
                isError: true,
            };
        }
    });
}
