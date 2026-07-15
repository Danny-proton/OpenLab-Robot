import { z } from "zod";
import { taasClient } from "../api/taas-client.js";
import { getProjectRootCaseDir } from "../utils/case-utils.js";
/**
 * 搜索用例
 * @param projectId 项目ID
 * @param realUri 起始目录 realUri，可选，默认为项目根目录
 * @param fieldName 搜索模式（CASE_NAME 用例名称 / CASE_NUMBER 用例编号）
 * @param value 搜索字符串
 * @returns 搜索结果
 */
export async function searchTestCases(projectId, realUri, fieldName, value) {
    try {
        // 如果未提供 realUri，使用项目根目录
        const searchUri = realUri || (await getProjectRootCaseDir(projectId)).data?.rootDirId;
        if (!searchUri) {
            return {
                success: false,
                message: "未找到有效的搜索目录",
            };
        }
        const params = new URLSearchParams({
            projectId,
            fieldName,
            realUri: searchUri,
            value,
        });
        const response = await taasClient.get(`/rest/case/v1/testcase/baseLine/quickQuery?${params}`);
        // 处理 401 错误
        if (response.status === 401) {
            return {
                success: false,
                message: "鉴权已过期，请使用 get-auth-token 工具刷新鉴权",
            };
        }
        // API 调用失败
        if (!response.success) {
            return {
                success: false,
                message: response.error || "搜索用例失败",
            };
        }
        const responseData = response.data;
        const paths = responseData?.result || [];
        if (paths.length === 0) {
            return {
                success: true,
                message: "未找到匹配的测试用例",
                data: [],
            };
        }
        // 提取 realUri（路径最后一段）
        const results = paths.map((path) => {
            const segments = path.split("/");
            const realUriPart = segments[segments.length - 1] || "";
            return realUriPart;
        });
        return {
            success: true,
            message: `搜索成功，找到 ${results.length} 个匹配的测试用例`,
            data: results,
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        return {
            success: false,
            message: `搜索用例出错：${errMsg}`,
        };
    }
}
/**
 * 注册搜索用例 MCP 工具。
 */
export function registerSearchTestCasesTool(server) {
    server.registerTool("search_test_cases", {
        title: "搜索TaaS测试用例",
        description: "根据用例名称或编号搜索测试用例。可指定搜索模式：按用例名称（CASE_NAME）或用例编号（CASE_NUMBER）进行搜索。",
        inputSchema: {
            projectId: z
                .string()
                .describe("项目ID"),
            fieldName: z
                .enum(["CASE_NAME", "CASE_NUMBER"])
                .describe("搜索模式：CASE_NAME 按用例名称搜索，CASE_NUMBER 按用例编号搜索"),
            value: z
                .string()
                .describe("搜索字符串"),
            realUri: z
                .string()
                .optional()
                .describe("起始目录的realUri，搜索将在此目录及其子目录中进行；如未提供则默认搜索项目根目录"),
        },
    }, async ({ projectId, fieldName, value, realUri }) => {
        const result = await searchTestCases(projectId, realUri, fieldName, value);
        return {
            content: [
                {
                    type: "text",
                    text: JSON.stringify(result, null, 2),
                },
            ],
            isError: !result.success,
        };
    });
}
