import { z } from "zod";
import { taasClient } from "../api/taas-client.js";
import { getEnvironmentConfig } from "../config/environments.js";
/**
 * 注册平台环境切换工具
 */
export function registerSwitchEnvironmentTool(server) {
    server.registerTool("switch_environment", {
        title: "切换平台环境",
        description: "切换 TaaS 平台的环境（生产/测试等），同时切换对应的域名和认证 token",
        inputSchema: {
            environment: z.string().describe("要切换到的环境名称，可通过 list_available_environments 查询可用环境"),
        },
    }, async ({ environment }) => {
        try {
            // 执行环境切换
            await taasClient.switchEnvironment(environment);
            const config = await getEnvironmentConfig(environment);
            return {
                content: [
                    {
                        type: "text",
                        text: `成功切换到 ${config.displayName}。\n\n` +
                            `环境信息：\n` +
                            `- 环境：${environment}\n` +
                            `- 域名：${config.baseUrl || "未设置"}\n` +
                            `- 登录页：${config.loginUrl || "默认（baseUrl + /TaaS/scenario/?currentModule=0#/myProject）"}\n` +
                            `- Token 文件：${config.authTokenPath}\n\n` +
                            `请注意：已切换到对应的认证 token 文件，请确保已登录目标环境。`,
                    },
                ],
                isError: false,
            };
        }
        catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            console.error("[switch_environment] Error:", errorMessage);
            return {
                content: [
                    {
                        type: "text",
                        text: `切换环境失败：${errorMessage}`,
                    },
                ],
                isError: true,
            };
        }
    });
}
