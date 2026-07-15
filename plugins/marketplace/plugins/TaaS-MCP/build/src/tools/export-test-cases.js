import { z } from "zod";
import { taasClient } from "../api/taas-client.js";
import * as fs from "fs/promises";
import * as path from "path";
import { resolveAgentPath } from "../utils/path-utils.js";
/**
 * 导出测试用例为 Excel 文件。
 * @param projectId 项目 ID
 * @param realUri 测试版本目录 ID
 * @param outputPath 可选的输出文件路径，默认为 {项目名}+{测试版本名}.xlsx
 * @param projectName 可选的项目名称，用于生成默认文件名
 * @param versionName 可选的测试版本名称，用于生成默认文件名
 * @returns 导出结果
 */
export async function exportTestCases(projectId, realUri, outputPath, projectName, versionName) {
    try {
        // 构造 API 端点
        const endpoint = `/rest/case/v1/testcase/exportExcel/${realUri}?type=2`;
        // 构造请求负载
        const payload = {
            projectId,
            fromBaseline: false,
            lists: [realUri],
        };
        // 调用 API，获取二进制响应
        const response = await taasClient.requestWithBinary(endpoint, "POST", payload, true // asBinary = true
        );
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
                message: response.error || "导出测试用例失败",
            };
        }
        // 获取二进制数据
        const buffer = response.data;
        if (!buffer || buffer.length === 0) {
            return {
                success: false,
                message: "导出测试用例失败：未收到有效数据",
            };
        }
        // 确定输出文件路径
        let filePath;
        if (outputPath) {
            filePath = outputPath;
        }
        else {
            // 生成默认文件名
            const safeProjectName = (projectName || "project").replace(/[\\/:*?"<>|]/g, "_");
            const safeVersionName = (versionName || "version").replace(/[\\/:*?"<>|]/g, "_");
            const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
            const fileName = `${safeProjectName}_${safeVersionName}_${timestamp}.xlsx`;
            filePath = resolveAgentPath(fileName);
        }
        // 确保目录存在
        const dir = path.dirname(filePath);
        await fs.mkdir(dir, { recursive: true });
        // 写入文件
        await fs.writeFile(filePath, buffer);
        return {
            success: true,
            message: `success`,
            filePath,
            bytesWritten: buffer.length,
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        return {
            success: false,
            message: `Error: ${errMsg}`,
        };
    }
}
/**
 * 注册导出测试用例 MCP 工具。
 */
export function registerExportTestCasesTool(server) {
    server.registerTool("export_test_cases", {
        title: "导出测试用例",
        description: "根据指定的项目和测试版本，导出测试版本下的所有测试用例为 Excel 文件并保存到本地",
        inputSchema: {
            projectId: z
                .string()
                .describe("项目 ID"),
            realUri: z
                .string()
                .describe("测试版本目录的 realUri（即测试版本的 ID）"),
            outputPath: z
                .string()
                .optional()
                .describe("可选的输出文件路径，如果未指定则自动生成文件名（格式：{项目名}_{测试版本名}_{日期}.xlsx）"),
            projectName: z
                .string()
                .optional()
                .describe("可选的项目名称，用于生成默认文件名"),
            versionName: z
                .string()
                .optional()
                .describe("可选的测试版本名称，用于生成默认文件名"),
        },
    }, async ({ projectId, realUri, outputPath, projectName, versionName }) => {
        const result = await exportTestCases(projectId, realUri, outputPath, projectName, versionName);
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
