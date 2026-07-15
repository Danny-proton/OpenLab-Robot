import { z } from "zod";
import { taasClient } from "../api/taas-client.js";
/**
 * 查询用户所拥有的项目列表。
 * @param pageSize 每页数量
 * @param pageNum 页码
 * @returns 项目列表
 */
export async function queryProjects(pageSize, pageNum, raw_response) {
    try {
        const payload = {
            expression: {
                field: "status",
                value: [0, 1, 4, 5, 6, 8, 9],
                valueType: "int",
                symbol: "in",
            },
            joinSymbol: "and",
            listableExpression: {
                joinSymbol: "or",
                expressionList: [],
            },
            combinedExpressions: [
                {
                    joinSymbol: "or",
                    expressionList: [],
                },
                {
                    joinSymbol: "and",
                    expressionList: [],
                },
            ],
        };
        const params = new URLSearchParams({
            pageSize: (pageSize || 10).toString(),
            pageNum: (pageNum || 1).toString(),
        });
        const response = await taasClient.post(`/rest/optaasprojectmanagerservice/v1/project/list?${params}`, payload);
        // 处理 401 错误
        if (response.status === 401) {
            const result = {
                success: false,
                message: "鉴权已过期，请使用 get-auth-token 工具刷新鉴权",
            };
            if (raw_response)
                result.raw_response = response;
            return result;
        }
        if (response.status === 418) {
            const result = {
                success: false,
                message: "鉴权未认证，可能需要等待验证用户手机号",
            };
            if (raw_response)
                result.raw_response = response;
            return result;
        }
        // API 调用失败
        if (!response.success) {
            console.error(response);
            return {
                success: false,
                message: response.error || "查询项目列表失败",
            };
        }
        const data = response.data;
        const list = data?.result?.list || [];
        // 数据过滤和提取：只提取 projectId 和 projectName
        const projectList = list
            .filter((item) => {
            return (item !== null &&
                item !== undefined &&
                typeof item === "object" &&
                "projectId" in item &&
                "projectName" in item);
        })
            .map((item) => ({
            projectId: item.projectId,
            projectName: item.projectName,
        }));
        if (projectList.length === 0) {
            return {
                success: true,
                message: "当前页无项目数据",
                data: [],
            };
        }
        return {
            success: true,
            message: `项目列表查询成功，共 ${projectList.length} 个项目`,
            data: projectList,
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        return {
            success: false,
            message: `查询项目列表出错：${errMsg}`,
        };
    }
}
/**
 * 注册查询项目 MCP 工具。
 */
export function registerQueryProjectsTool(server) {
    server.registerTool("query_projects", {
        title: "查询TaaS测试项目",
        description: "查询用户所拥有的TaaS测试项目列表",
        inputSchema: {
            pageSize: z
                .number()
                .optional()
                .describe("每页显示的项目数量，默认为 10"),
            pageNum: z
                .number()
                .optional()
                .describe("页码，默认为 1"),
        },
    }, async ({ pageSize, pageNum }) => {
        const result = await queryProjects(pageSize, pageNum);
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
