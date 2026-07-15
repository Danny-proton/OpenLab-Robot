import { z } from "zod";
import { taasClient } from "../api/taas-client.js";
/**
 * 编辑用例内容工具
 * 根据用例 realUri 和项目 ID 修改用例的内容
 */
export function registerEditCaseContentTool(server) {
    server.registerTool("edit_case_content", {
        title: "编辑用例内容",
        description: "根据用例 realUri 和项目 ID 编辑用例的内容（包括名称、编号、描述、预置条件、步骤和预期结果）",
        inputSchema: {
            projectId: z.string().describe("项目 ID"),
            realUri: z.string().describe("用例的 realUri (唯一标识符)"),
            caseName: z.string().optional().describe("用例名称"),
            caseNumber: z.string().optional().describe("用例编号"),
            description: z.string().optional().describe("用例描述"),
            prerequisites: z.string().optional().describe("预置条件"),
            testSteps: z.string().optional().describe("测试步骤"),
            expectOutput: z.string().optional().describe("预期结果"),
        },
    }, async ({ projectId, realUri, caseName, caseNumber, description, prerequisites, testSteps, expectOutput }) => {
        try {
            // 先查询获取用例的完整内容
            // 接口地址：rest/case/v1/testcase/{realUri}
            const getEndpoint = `/rest/case/v1/testcase/${realUri}?projectId=${projectId}`;
            const getResponse = await taasClient.get(getEndpoint);
            if (!getResponse.success) {
                return {
                    content: [{ type: "text", text: `查询用例失败：${getResponse.error}` }],
                    isError: true,
                };
            }
            const { data: getData } = getResponse;
            if (!getData || getData.status === "fail") {
                const errorMsg = getData?.message || "用例不存在，请刷新重试";
                return {
                    content: [{ type: "text", text: `查询失败：${errorMsg}` }],
                    isError: true,
                };
            }
            const result = getData.result;
            if (!result) {
                return {
                    content: [{ type: "text", text: "未能获取到用例内容" }],
                    isError: true,
                };
            }
            // 检查用例是否被锁定
            if (result.isLocked === true) {
                return {
                    content: [{ type: "text", text: "该用例已被锁定，无法编辑" }],
                    isError: true,
                };
            }
            // 构建更新负载：使用原有用例内容并合并修改字段
            const updatePayload = {
                ...result,
                caseName: caseName ?? result.caseName,
                caseNameEn: caseName ?? result.caseNameEn,
                caseNumber: caseNumber ?? result.caseNumber,
                prerequisites: prerequisites ?? result.prerequisites,
                prerequisitesEn: prerequisites ?? result.prerequisitesEn,
                testSteps: testSteps ?? result.testSteps,
                testStepsEn: testSteps ?? result.testStepsEn,
                expectOutput: expectOutput ?? result.expectOutput,
                expectOutputEn: expectOutput ?? result.expectOutputEn,
                description: description ?? result.description,
                descriptionEn: description ?? result.descriptionEn,
            };
            // 更新用例
            // 接口地址：rest/case/v1/testcase
            const updateEndpoint = `/rest/case/v1/testcase?projectId=${projectId}`;
            const updateResponse = await taasClient.put(updateEndpoint, updatePayload);
            if (!updateResponse.success) {
                return {
                    content: [{ type: "text", text: `更新用例失败：${updateResponse.error}` }],
                    isError: true,
                };
            }
            const { data: updateData } = updateResponse;
            if (!updateData || updateData.status === "fail") {
                return {
                    content: [{ type: "text", text: `更新失败：${updateData?.message || "未知错误"}` }],
                    isError: true,
                };
            }
            // 构建返回的成功信息
            let successMessage = "用例更新成功！\n\n";
            if (caseName !== undefined)
                successMessage += `- 用例名称：${caseName}\n`;
            if (caseNumber !== undefined)
                successMessage += `- 用例编号：${caseNumber}\n`;
            if (description !== undefined)
                successMessage += `- 用例描述：${description}\n`;
            if (prerequisites !== undefined)
                successMessage += `- 预置条件：${prerequisites}\n`;
            if (testSteps !== undefined)
                successMessage += `- 测试步骤：${testSteps}\n`;
            if (expectOutput !== undefined)
                successMessage += `- 预期结果：${expectOutput}\n`;
            return {
                content: [{ type: "text", text: successMessage }],
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
