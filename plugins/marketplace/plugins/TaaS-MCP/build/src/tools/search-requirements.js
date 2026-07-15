import { z } from "zod";
import { taasClient } from "../api/taas-client.js";
/**
 * 从 API 响应项转换为内部格式
 */
function convertAnalysisItem(apiItem) {
    return {
        requirementId: apiItem.requirementId,
        requirementTitle: apiItem.requirementTitle,
        requirementDesc: apiItem.requirementDesc,
        verificationPolicyDesc: apiItem.verificationPolicyDesc,
        childAnalyses: (apiItem.childAnalyses || []).map(convertAnalysisItem),
    };
}
/**
 * 分页查询需求列表
 * @param params 查询参数
 * @returns 所有页面的需求数据
 */
async function queryAllPages(params) {
    const allItems = [];
    let currentPage = params.pageNum;
    let hasMorePages = true;
    while (hasMorePages) {
        const payload = {
            projectId: params.projectId,
            pageSize: params.pageSize,
            pageNum: currentPage,
            param: params.searchParam || "",
            laissezPasser: [],
            priority: [],
            status: [],
            solution: [],
            scene: [],
            requirementType: [],
            requirementIds: [],
            requirementTitle: [],
            featureName: [],
            product: [],
            ownerName: [],
            createUser: [],
            caseResult: [],
            baseLine: [],
            progress: [],
            trustCategory: [],
            verificationPolicy: [],
            almUpdateTime: [],
            analysisTag: [],
            delivererOwner: [],
            piName: [],
            iterateName: [],
            sort: "",
            expand: true,
        };
        const response = await taasClient.post("/rest/optaasdesignservice/v1/analysis/view", payload);
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
                message: response.error || "查询需求失败",
            };
        }
        const apiData = response.data?.result;
        if (!apiData) {
            return {
                success: false,
                message: "响应数据格式错误",
            };
        }
        // 转换并添加当前页数据
        const convertedItems = (apiData.list || []).map(convertAnalysisItem);
        allItems.push(...convertedItems);
        // 检查是否还有下一页
        hasMorePages = apiData.pages > currentPage;
        currentPage++;
        // 防止无限循环
        if (currentPage > 100) {
            console.warn("已查询 100 页，停止分页查询");
            hasMorePages = false;
        }
    }
    return {
        success: true,
        message: `查询成功，共找到 ${allItems.length} 个需求`,
        data: allItems,
    };
}
/**
 * 搜索需求列表
 * @param projectId 项目 ID
 * @param searchParam 搜索字符串（留空则查询所有需求）
 * @param outputPath 可选的保存路径，如果提供则将结果保存为文件
 * @returns 搜索结果
 */
export async function searchRequirements(projectId, searchParam = "", outputPath) {
    try {
        // 分页查询所有需求
        const queryResult = await queryAllPages({
            projectId,
            pageNum: 1,
            pageSize: 100,
            searchParam: searchParam || undefined,
        });
        if (!queryResult.success) {
            return queryResult;
        }
        const data = queryResult.data || [];
        // 如果需要保存文件，写入文件系统
        if (outputPath) {
            const fs = await import("fs/promises");
            await fs.writeFile(outputPath, JSON.stringify(data, null, 2), "utf-8");
            return {
                success: true,
                message: `查询成功，共找到 ${data.length} 个需求，已保存到 ${outputPath}`,
            };
        }
        return {
            success: true,
            message: `查询成功，共找到 ${data.length} 个需求`,
            data,
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        return {
            success: false,
            message: `搜索需求出错：${errMsg}`,
        };
    }
}
/**
 * 注册搜索需求 MCP 工具。
 */
export function registerSearchRequirementsTool(server) {
    server.registerTool("search_requirements", {
        title: "搜索需求列表",
        description: "根据项目 ID 和搜索字符串查询需求列表。支持分页查询，自动获取所有页面的数据。结果包含需求 ID、标题、描述、验证策略描述和子需求。提供 outputPath 参数时可直接将结果保存为 JSON 文件下载到本地。",
        inputSchema: {
            projectId: z
                .string()
                .describe("项目 ID"),
            searchParam: z
                .string()
                .optional()
                .describe("搜索字符串（留空则查询所有需求）"),
            outputPath: z
                .string()
                .optional()
                .describe("可选的保存路径，如果提供则将结果保存为 JSON 文件；否则直接返回 JSON 数据"),
        },
    }, async ({ projectId, searchParam, outputPath }) => {
        const result = await searchRequirements(projectId, searchParam, outputPath);
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
