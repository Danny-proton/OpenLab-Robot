import { z } from "zod";
import { taasClient } from "../api/taas-client.js";
/**
 * 查询用例内容工具
 * 根据用例 realUri 和项目 ID 获取用例的详细设计内容
 */
export function registerGetCaseContentTool(server) {
    server.registerTool("get_case_content", {
        title: "查询用例内容",
        description: "根据用例 realUri 和项目 ID 查询用例的详细内容（包括名称、编号、描述、预置条件、步骤和预期结果）",
        inputSchema: {
            projectId: z.string().describe("项目 ID"),
            realUri: z.string().describe("用例的 realUri (唯一标识符)"),
        },
    }, async ({ projectId, realUri }) => {
        try {
            // 接口地址：rest/case/v1/testcase/{realUri}
            // 查询参数：projectId
            const endpoint = `/rest/case/v1/testcase/${realUri}?projectId=${projectId}`;
            const response = await taasClient.get(endpoint);
            if (!response.success) {
                return {
                    content: [{ type: "text", text: `查询失败：${response.error}` }],
                    isError: true,
                };
            }
            const { data } = response;
            if (!data || data.status === "fail") {
                const errorMsg = data?.message || "用例不存在，请刷新重试";
                return {
                    content: [{ type: "text", text: `查询失败：${errorMsg}` }],
                    isError: true,
                };
            }
            const result = data.result;
            if (!result) {
                return {
                    content: [{ type: "text", text: "未能获取到用例内容" }],
                    isError: true,
                };
            }
            // 选出测试设计需要用到的字段
            const caseContent = {
                realUri: result.realUri || "",
                caseName: result.caseName || "",
                caseNumber: result.caseNumber || "",
                description: result.description || "",
                prerequisites: result.prerequisites || "",
                testSteps: result.testSteps || "",
                expectOutput: result.expectOutput || "",
            };
            return {
                content: [
                    {
                        type: "text",
                        text: JSON.stringify(caseContent, null, 2),
                    },
                ],
                isError: false,
            };
        }
        catch (error) {
            return {
                content: [
                    {
                        type: "text",
                        text: `发生异常：${error instanceof Error ? error.message : String(error)}`,
                    },
                ],
                isError: true,
            };
        }
    });
}
