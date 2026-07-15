import * as fs from "fs/promises";
import { getEnvironmentConfig, setCurrentEnvironment } from "../config/environments.js";
import { resolvePluginPath } from "../utils/path-utils.js";
const DEFAULT_BASE_URL = "https://openlab.huawei.com";
const DEFAULT_AUTH_TOKEN_PATH = ".auth_token";
const DEFAULT_LOGIN_PATH = "/TaaS/scenario/?currentModule=0#/myProject";
/**
 * TaaS 平台接口调用封装客户端。
 * 自动读取 .auth_token 文件中的 Authorization 值，并附加到每个请求的请求头中。
 * 支持多环境切换（从 environments.json 动态读取）。
 */
export class TaasClient {
    _baseUrl;
    _authTokenPath;
    _loginUrl;
    cachedToken = null;
    currentEnvironment = null;
    constructor(options) {
        this._baseUrl = (options?.baseUrl ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
        this._authTokenPath = options?.authTokenPath ?? DEFAULT_AUTH_TOKEN_PATH;
        this._loginUrl = options?.loginUrl
            ? options.loginUrl
            : this._baseUrl + DEFAULT_LOGIN_PATH;
    }
    /** 当前环境的 baseUrl */
    get baseUrl() {
        return this._baseUrl;
    }
    /** 当前环境的 token 文件路径（相对插件根目录） */
    get authTokenPath() {
        return this._authTokenPath;
    }
    /** 当前环境的登录页面 URL */
    get loginUrl() {
        return this._loginUrl;
    }
    /**
     * 切换到指定环境
     * @param env 环境名称（从 environments.json 中读取）
     */
    async switchEnvironment(env) {
        const config = await getEnvironmentConfig(env);
        this._baseUrl = config.baseUrl.replace(/\/+$/, "");
        this._authTokenPath = config.authTokenPath;
        this._loginUrl = config.loginUrl
            ? config.loginUrl
            : this._baseUrl + DEFAULT_LOGIN_PATH;
        this.currentEnvironment = env;
        this.refreshToken(); // 清除 token 缓存
        console.log(`[TaasClient] 已切换到环境：${config.displayName} (${env})`);
        console.log(`[TaasClient] Base URL: ${this._baseUrl}`);
        console.log(`[TaasClient] Auth Token Path: ${this._authTokenPath}`);
        console.log(`[TaasClient] Login URL: ${this._loginUrl}`);
        // 同时设置全局活跃环境
        await setCurrentEnvironment(env);
    }
    /**
     * 获取当前环境配置
     * @returns 当前环境配置，如果未设置则返回 null
     */
    getCurrentEnvironment() {
        return this.currentEnvironment;
    }
    /**
     * 从 .auth_token 文件中读取 Authorization token。
     * 首次读取后缓存，后续调用直接返回缓存值。
     * 调用 refreshToken() 可清除缓存并重新读取。
     */
    async getToken() {
        if (this.cachedToken) {
            return this.cachedToken;
        }
        const tokenPath = resolvePluginPath(this._authTokenPath);
        try {
            const token = (await fs.readFile(tokenPath, "utf-8")).trim();
            if (!token) {
                throw new Error(`Auth token file is empty: ${tokenPath}`);
            }
            this.cachedToken = token;
            return token;
        }
        catch (error) {
            if (error.code === "ENOENT") {
                throw new Error(`Auth token file not found: ${tokenPath}. ` +
                    `Please run the get_auth_token tool first to obtain a token.`);
            }
            throw error;
        }
    }
    /**
     * 清除缓存的 token，下次请求时将重新从文件读取。
     */
    refreshToken() {
        this.cachedToken = null;
    }
    /**
     * 通用请求方法，封装对 TaaS 平台的 HTTP 调用。
     * @param endpoint - API 路径，如 "/api/v1/testcases"
     * @param method - HTTP 方法，如 "GET", "POST", "PUT", "DELETE"
     * @param payload - 可选的请求体（会被 JSON 序列化）
     * @returns TaasResponse<T> 包含 success 标志、数据或错误信息
     */
    async request(endpoint, method, payload) {
        const token = await this.getToken();
        const url = `${this.baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
        const headers = {
            Authorization: token,
            "Content-Type": "application/json",
            "Project-Type": "portal",
        };
        const fetchOptions = {
            method: method.toUpperCase(),
            headers,
        };
        if (payload !== undefined && method.toUpperCase() !== "GET") {
            fetchOptions.body = JSON.stringify(payload);
        }
        try {
            console.error(`[Fetch] ${method} ${url}`);
            console.error(`[Fetch] Headers: ${JSON.stringify(headers)}`);
            if (payload) {
                console.error(`[Fetch] Body: ${JSON.stringify(payload)}`);
            }
            const response = await fetch(url, fetchOptions);
            console.error(`[Fetch] Status: ${response.status} ${response.statusText}`);
            console.error(`[Fetch] Headers: ${JSON.stringify(Object.fromEntries(response.headers))}`);
            if (!response.ok) {
                const errorText = await response.text().catch(() => "Unknown error");
                console.error(`[Fetch] Error Response: ${errorText}`);
                return {
                    success: false,
                    error: `HTTP ${response.status}: ${errorText}`,
                    status: response.status,
                };
            }
            // 尝试解析 JSON 响应
            const contentType = response.headers.get("content-type");
            if (contentType?.includes("application/json")) {
                const data = (await response.json());
                console.error(`[Fetch] Response Data: ${JSON.stringify(data).substring(0, 200)}`);
                return { success: true, data, status: response.status };
            }
            // 非 JSON 响应，返回文本作为 data
            const text = await response.text();
            console.error(`[Fetch] Response Text: ${text.substring(0, 200)}`);
            return { success: true, data: text, status: response.status };
        }
        catch (error) {
            console.error(error);
            const errorObj = error instanceof Error ? error : new Error(String(error));
            const errMsg = errorObj.message;
            const errCode = error.code || "UNKNOWN";
            console.error(`[Fetch] Exception: ${errorObj.message}`);
            console.error(`[Fetch] Error Code: ${errCode}`);
            console.error(`[Fetch] Stack: ${errorObj.stack || "No stack"}`);
            // 诊断网络错误
            let diagnosticMsg = errMsg;
            if (errCode === "ENOTFOUND") {
                diagnosticMsg = `DNS 解析失败：无法解析主机名 "${url}"。请检查网络连接或域名是否正确。`;
            }
            else if (errCode === "ECONNREFUSED") {
                diagnosticMsg = `连接被拒绝：无法连接到 "${url}"。请检查服务是否正在运行或防火墙设置。`;
            }
            else if (errCode === "ETIMEDOUT") {
                diagnosticMsg = `连接超时：无法在限定时间内连接到 "${url}"。请检查网络延迟或服务器状态。`;
            }
            else if (errCode === "CERT_HAS_EXPIRED" || errCode === "UNABLE_TO_VERIFY_LEAF_SIGNATURE") {
                diagnosticMsg = `SSL 证书错误：${errMsg}。请检查服务器证书是否有效。`;
            }
            else if (errMsg.includes("network")) {
                diagnosticMsg = `网络错误：${errMsg}。请检查网络连接。`;
            }
            else if (errMsg.includes("getaddrinfo")) {
                diagnosticMsg = `DNS 解析错误：无法解析 "${url}" 的域名。请检查网络连接。`;
            }
            return { success: false, error: diagnosticMsg };
        }
    }
    /** GET 请求 */
    async get(endpoint) {
        return this.request(endpoint, "GET");
    }
    /** POST 请求 */
    async post(endpoint, payload) {
        return this.request(endpoint, "POST", payload);
    }
    /** PUT 请求 */
    async put(endpoint, payload) {
        return this.request(endpoint, "PUT", payload);
    }
    /** DELETE 请求 */
    async del(endpoint) {
        return this.request(endpoint, "DELETE");
    }
    /**
     * 通用请求方法，支持获取二进制响应数据。
     * @param endpoint - API 路径
     * @param method - HTTP 方法
     * @param payload - 可选的请求体
     * @param asBinary - 是否以二进制形式返回响应
     * @returns TaasResponse<T> 或包含二进制数据的响应
     */
    async requestWithBinary(endpoint, method, payload, asBinary = false) {
        const token = await this.getToken();
        const url = `${this.baseUrl}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
        const headers = {
            Authorization: token,
            "Content-Type": "application/json",
            "Project-Type": "baseline",
        };
        const fetchOptions = {
            method: method.toUpperCase(),
            headers,
        };
        if (payload !== undefined && method.toUpperCase() !== "GET") {
            fetchOptions.body = JSON.stringify(payload);
        }
        try {
            console.error(`[Fetch] ${method} ${url}`);
            if (payload) {
                console.error(`[Fetch] Body: ${JSON.stringify(payload)}`);
            }
            const response = await fetch(url, fetchOptions);
            console.error(`[Fetch] Status: ${response.status} ${response.statusText}`);
            if (!response.ok) {
                const errorText = await response.text().catch(() => "Unknown error");
                console.error(`[Fetch] Error Response: ${errorText}`);
                return {
                    success: false,
                    error: `HTTP ${response.status}: ${errorText}`,
                    status: response.status,
                };
            }
            // 如果需要二进制响应
            if (asBinary) {
                const buffer = Buffer.from(await response.arrayBuffer());
                console.error(`[Fetch] Binary Response: ${buffer.length} bytes`);
                return { success: true, data: buffer, status: response.status };
            }
            // 尝试解析 JSON 响应
            const contentType = response.headers.get("content-type");
            if (contentType?.includes("application/json")) {
                const data = (await response.json());
                console.error(`[Fetch] Response Data: ${JSON.stringify(data).substring(0, 200)}`);
                return { success: true, data, status: response.status };
            }
            // 非 JSON 响应，返回文本作为 data
            const text = await response.text();
            console.error(`[Fetch] Response Text: ${text.substring(0, 200)}`);
            return { success: true, data: text, status: response.status };
        }
        catch (error) {
            const errorObj = error instanceof Error ? error : new Error(String(error));
            const errMsg = errorObj.message;
            const errCode = error.code || "UNKNOWN";
            console.error(`[Fetch] Exception: ${errorObj.message}`);
            console.error(`[Fetch] Error Code: ${errCode}`);
            console.error(`[Fetch] Stack: ${errorObj.stack || "No stack"}`);
            let diagnosticMsg = errMsg;
            if (errCode === "ENOTFOUND") {
                diagnosticMsg = `DNS 解析失败：无法解析主机名 "${url}"。请检查网络连接或域名是否正确。`;
            }
            else if (errCode === "ECONNREFUSED") {
                diagnosticMsg = `连接被拒绝：无法连接到 "${url}"。请检查服务是否正在运行或防火墙设置。`;
            }
            else if (errCode === "ETIMEDOUT") {
                diagnosticMsg = `连接超时：无法在限定时间内连接到 "${url}"。请检查网络延迟或服务器状态。`;
            }
            else if (errCode === "CERT_HAS_EXPIRED" || errCode === "UNABLE_TO_VERIFY_LEAF_SIGNATURE") {
                diagnosticMsg = `SSL 证书错误：${errMsg}。请检查服务器证书是否有效。`;
            }
            else if (errMsg.includes("network")) {
                diagnosticMsg = `网络错误：${errMsg}。请检查网络连接。`;
            }
            else if (errMsg.includes("getaddrinfo")) {
                diagnosticMsg = `DNS 解析错误：无法解析 "${url}" 的域名。请检查网络连接。`;
            }
            return { success: false, error: diagnosticMsg };
        }
    }
}
/**
 * 导出一个默认的 TaasClient 实例，方便直接使用。
 */
export const taasClient = new TaasClient();
