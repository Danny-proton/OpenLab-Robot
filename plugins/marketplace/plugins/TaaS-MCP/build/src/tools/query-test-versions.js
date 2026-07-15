import { z } from "zod";
import { getProjectRootCaseDir, getCaseDirItems, } from "../utils/case-utils.js";
/**
 * 查询项目的测试版本列表。
 * @param projectId 项目 ID
 * @returns 测试版本列表
 */
export async function queryTestVersions(projectId) {
    try {
        // 步骤1：查询项目根目录ID
        const rootDirResult = await getProjectRootCaseDir(projectId);
        if (!rootDirResult.success) {
            return {
                success: false,
                message: rootDirResult.message,
            };
        }
        const rootDirId = rootDirResult.data?.rootDirId;
        if (!rootDirId) {
            return {
                success: false,
                message: "未找到项目测试用例根目录ID",
            };
        }
        // 步骤2：根据项目根目录ID查询子目录（即测试版本）
        const dirItemsResult = await getCaseDirItems(projectId, rootDirId, "TestVersion" // 只查询 TestVersion 类型
        );
        if (!dirItemsResult.success) {
            return {
                success: false,
                message: dirItemsResult.message,
            };
        }
        const dirItems = dirItemsResult.data || [];
        // 步骤3：过滤出测试版本并提取需要的信息
        const testVersions = dirItems
            .filter((item) => item.testVersion === true)
            .map((item) => ({
            name: item.name,
            nameEn: item.nameEn,
            realUri: item.realUri,
            featureNumber: item.featureNumber || "",
        }));
        if (testVersions.length === 0) {
            return {
                success: true,
                message: "该项目暂无测试版本",
                data: [],
            };
        }
        return {
            success: true,
            message: `测试版本列表查询成功，共 ${testVersions.length} 个版本`,
            data: testVersions,
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        return {
            success: false,
            message: `查询测试版本列表出错：${errMsg}`,
        };
    }
}
/**
 * 注册查询测试版本列表 MCP 工具。
 */
export function registerQueryTestVersionsTool(server) {
    server.registerTool("query_test_versions", {
        title: "查询项目测试版本列表",
        description: "查询指定项目的测试版本列表，用于批量导出测试用例",
        inputSchema: {
            projectId: z
                .string()
                .describe("项目 ID"),
        },
    }, async ({ projectId }) => {
        const result = await queryTestVersions(projectId);
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
