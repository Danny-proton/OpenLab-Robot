import { z } from "zod";
import { chromium } from "playwright";
import * as fs from "fs/promises";
import { taasClient } from "../api/taas-client.js";
import { queryProjects } from "./query-projects.js";
import { resolvePluginPath } from "../utils/path-utils.js";
const POLL_INTERVAL_MS = 2000;
const MAX_WAIT_MS = 5 * 60 * 1000; // 5 minutes
const VERIFICATION_INTERVAL_MS = 1000;
const MAX_VERIFICATION_WAIT_MS = 3 * 60 * 1000; // 3 minutes for phone verification
/**
 * 获取当前环境的 token 文件路径（跟随 taasClient 的配置）
 */
function getAuthTokenPath() {
    return taasClient.authTokenPath || ".auth_token";
}
/**
 * Launch a browser for user login and capture Authorization from session storage.
 * Since GitHub auth differs from TaaS, we mock the Authorization in session storage
 * after detecting a successful GitHub login (user lands on a non-login page).
 */
export async function getAuthToken(url) {
    let targetUrl;
    if (url) {
        targetUrl = url;
    }
    else {
        targetUrl = taasClient.loginUrl;
    }
    let browser = null;
    try {
        console.error(`[Auth] Launching browser, navigating to ${targetUrl}...`);
        browser = await chromium.launch({
            headless: false,
            channel: "msedge", // Use system-installed Edge; change to "chrome" if preferred
        });
        const context = await browser.newContext();
        const page = await context.newPage();
        await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
        console.error("[Auth] Waiting for user to complete login...");
        const token = await pollForAuthorization(page);
        if (!token) {
            return {
                success: false,
                message: "Timeout: failed to get Authorization within 5 minutes.",
            };
        }
        // 验证 token 是否可用
        console.error("[Auth] Verifying token validity...");
        const verifyStatus = await verifyToken(token);
        if (verifyStatus === 418) {
            // 需要手机验证
            console.error("[Auth] Token requires phone verification (418).");
            const verifyResult = await waitForPhoneVerification(page, token);
            if (!verifyResult.success) {
                return verifyResult;
            }
        }
        else if (verifyStatus !== 200) {
            // 其他错误
            return {
                success: false,
                message: `Token 验证失败，HTTP 状态码: ${verifyStatus}。请检查账号状态或重新登录。`,
            };
        }
        // Save token to file (跟随当前环境的配置)
        const tokenPath = resolvePluginPath(getAuthTokenPath());
        await fs.writeFile(tokenPath, token, "utf-8");
        console.error(`[Auth] Token saved to ${tokenPath}`);
        taasClient.refreshToken();
        return {
            success: true,
            message: `Authorization token 已保存至 ${tokenPath}，验证通过。`,
        };
    }
    catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        console.error(`[Auth] Error: ${errMsg}`);
        return { success: false, message: `Error: ${errMsg}` };
    }
    finally {
        if (browser) {
            await browser.close();
        }
    }
}
/**
 * Poll session storage for the Authorization field.
 * For GitHub (mock mode): after detecting login success (URL changes away from /login),
 * we inject a mock Authorization into session storage so the flow can be tested end-to-end.
 */
async function pollForAuthorization(page) {
    const startTime = Date.now();
    while (Date.now() - startTime < MAX_WAIT_MS) {
        try {
            // Check if session storage already has Authorization (TaaS real scenario)
            const token = await page.evaluate(() => {
                return sessionStorage.getItem("Authorization");
            });
            if (token) {
                console.error("[Auth] Found Authorization in session storage.");
                return token;
            }
            // GitHub mock: detect login success by URL change
            const currentUrl = page.url();
            if (currentUrl.includes("github.com") &&
                !currentUrl.includes("/login") &&
                !currentUrl.includes("/session")) {
                console.error("[Auth] GitHub login detected, injecting mock Authorization...");
                // Get cookies/session info to build a mock token
                const cookies = await page.context().cookies();
                const sessionCookie = cookies.find((c) => c.name === "user_session" || c.name === "_gh_sess");
                const mockToken = `Bearer mock_github_${sessionCookie?.value?.substring(0, 16) || "token"}_${Date.now()}`;
                await page.evaluate((t) => {
                    sessionStorage.setItem("Authorization", t);
                }, mockToken);
                console.error("[Auth] Mock Authorization injected into session storage.");
                // Next iteration will pick it up
                continue;
            }
        }
        catch {
            // Page might be navigating, ignore errors and retry
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
    return null;
}
/**
 * 验证 token 是否可用（通过调用一个简单的 API 检查）
 * @returns 0 = 有效, 418 = 需要手机验证, 其他 = 无效
 */
async function verifyToken(token) {
    try {
        // 临时设置 token 用于验证
        const tokenPath = resolvePluginPath(getAuthTokenPath());
        await fs.writeFile(tokenPath, token, "utf-8");
        taasClient.refreshToken();
        const response = await queryProjects(10, 1, true);
        console.error(`[Auth] Verification response: ${response}`);
        if (response.success === true) {
            return 200;
        }
        if (response.raw_response === undefined) {
            throw Error(`Unexpected response: ${response.raw_response}`);
        }
        const raw_response = response.raw_response;
        // 如果验证失败，清除临时 token
        if (raw_response.status !== 200) {
            await fs.unlink(tokenPath).catch(() => { });
            taasClient.refreshToken();
        }
        return raw_response.status || -1;
    }
    catch (error) {
        console.error(`[Auth] Verification error: ${error}`);
        return -1;
    }
}
/**
 * 等待用户完成手机验证
 * 持续检查 token 是否变得可用（状态从 418 变为 200）
 */
async function waitForPhoneVerification(page, token) {
    const startTime = Date.now();
    let lastStatus = 418;
    console.error("[Auth] Token needs phone verification. Waiting for user to complete...");
    while (Date.now() - startTime < MAX_VERIFICATION_WAIT_MS) {
        // 检查 token 是否已经可用
        const status = await verifyToken(token);
        if (status === 200) {
            return { success: true, message: "手机验证完成，Token 已生效" };
        }
        if (status !== 418 && status !== lastStatus) {
            // 状态发生变化但不是成功
            console.error(`[Auth] Status changed from ${lastStatus} to ${status}`);
            lastStatus = status;
        }
        // 检查页面是否还在验证流程中
        try {
            const currentUrl = page.url();
            console.error(`[Auth] Current URL: ${currentUrl}`);
            // 检查页面上是否有验证相关的元素
            const hasVerificationDialog = await page.evaluate(() => {
                // 查找可能的验证相关元素
                const verificationKeywords = ["验证", "手机", "短信", "验证码", "code", "verify", "phone"];
                const bodyText = document.body?.innerText?.toLowerCase() || "";
                return verificationKeywords.some(kw => bodyText.includes(kw.toLowerCase()));
            });
            if (hasVerificationDialog) {
                console.error("[Auth] Phone verification dialog detected on page.");
            }
        }
        catch {
            // 页面可能在导航，忽略错误
        }
        await new Promise((resolve) => setTimeout(resolve, VERIFICATION_INTERVAL_MS));
    }
    return {
        success: false,
        message: "手机验证超时：请在 3 分钟内完成手机号验证",
    };
}
/**
 * 注册获取鉴权 Token MCP 工具。
 */
export function registerGetAuthTokenTool(server) {
    server.registerTool("get_auth_token", {
        title: "获取 TaaS 平台鉴权 Token",
        description: "打开浏览器，提示用户登录 TaaS 平台并自动获取用户鉴权 Token，用于后续 TaaS 平台接口调用操作",
        inputSchema: {
            url: z
                .string()
                .optional()
                .describe("需登录的平台链接，默认为当前环境的 loginUrl（environments.json 可配置完整 URL，不配置则默认为 baseUrl 拼接 /TaaS/scenario/?currentModule=0#/myProject）。"),
        },
    }, async ({ url }) => {
        const result = await getAuthToken(url);
        return {
            content: [
                {
                    type: "text",
                    text: result.message,
                },
            ],
            isError: !result.success,
        };
    });
}
