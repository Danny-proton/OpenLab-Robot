import { taasClient } from "../api/taas-client.js";
/**
 * 获取项目测试用例根目录 ID。
 * 根目录 ID 用于进一步查询子目录以及测试用例。
 * @param projectId 项目 ID
 * @returns 项目测试用例根目录信息
 */
export async function getProjectRootCaseDir(projectId) {
    try {
        const response = await taasClient.get(`/rest/case/v1/projectmapping?projectId=${projectId}`);
        // 处理 401 错误
        if (response.status === 401) {
            return {
                success: false,
                message: "鉴权已过期，请使用 get-auth-token 工具刷新鉴权",
            };
        }
        // API 调用失败
        if (!response.success) {
            console.error(response);
            return {
                success: false,
                message: response.error || "获取项目测试用例根目录失败",
            };
        }
        const data = response.data;
        const result = data?.result;
        if (!result) {
            return {
                success: false,
                message: "未找到项目测试用例根目录",
            };
        }
        const rootDirId = result.targetRealUri;
        const rootDirName = result.name || "根目录";
        const yearMonth = result.yearMonth || "";
        if (!rootDirId) {
            return {
                success: false,
                message: "项目测试用例根目录 ID 为空",
            };
        }
        return {
            success: true,
            message: `项目测试用例根目录获取成功`,
            data: {
                projectId,
                rootDirId,
                rootDirName,
                yearMonth,
            },
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        return {
            success: false,
            message: `获取项目测试用例根目录出错：${errMsg}`,
        };
    }
}
/**
 * 根据目录 ID 获取子目录及用例。
 * @param projectId 项目 ID
 * @param realUri 目录真实 URI（目录 ID）
 * @param needType 需要获取的类型，逗号分隔，默认为"Folder,Cases,case,TestVersion"
 * @param baselineRealUri 基线真实 URI，默认为 null（不传）
 * @returns 子目录及用例列表
 */
export async function getCaseDirItems(projectId, realUri, needType = "Folder,Cases,case,TestVersion", baselineRealUri = null) {
    try {
        const payload = {
            needType,
            realUri,
            baselineRealUri: baselineRealUri || realUri, // 如果未提供基线 URI，则使用当前目录 URI
            projectId,
        };
        const response = await taasClient.post("/rest/case/v1/container/primary", payload);
        // 处理 401 错误
        if (response.status === 401) {
            return {
                success: false,
                message: "鉴权已过期，请使用 get-auth-token 工具刷新鉴权",
            };
        }
        // API 调用失败
        if (!response.success) {
            console.error(response);
            return {
                success: false,
                message: response.error || "获取目录及用例列表失败",
            };
        }
        const data = response.data;
        const result = data?.result || [];
        // 数据过滤和提取：只提取需要的字段
        const itemList = result
            .filter((item) => {
            return (item !== null &&
                item !== undefined &&
                typeof item === "object" &&
                "name" in item &&
                "realUri" in item);
        })
            .map((item) => ({
            name: item.name,
            nameEn: item.nameEn,
            realUri: item.realUri,
            uri: item.uri,
            sequence: item.sequence || 0,
            type: item.type,
            projectId: item.projectId,
            parentUri: item.parentUri,
            testVersion: item.testVersion,
            testVersionRealUri: item.testVersionRealUri,
            baselineRealUri: item.baselineRealUri,
        }));
        if (itemList.length === 0) {
            return {
                success: true,
                message: "该目录下无子目录或用例",
                data: [],
            };
        }
        return {
            success: true,
            message: `目录及用例列表获取成功，共 ${itemList.length} 项`,
            data: itemList,
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        return {
            success: false,
            message: `获取目录及用例列表出错：${errMsg}`,
        };
    }
}
