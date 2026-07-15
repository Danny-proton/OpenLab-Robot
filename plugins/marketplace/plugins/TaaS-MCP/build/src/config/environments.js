import * as fs from "fs/promises";
import { resolvePluginPath } from "../utils/path-utils.js";
/**
 * 平台环境定义
 */
export var Environment;
(function (Environment) {
    Environment["PRODUCTION"] = "production";
    Environment["BETA"] = "beta";
    Environment["UAT"] = "uat";
    Environment["ALPHA"] = "alpha";
})(Environment || (Environment = {}));
/**
 * 从 JSON 文件加载环境配置
 * 支持任意数量的环境配置，不需要在代码中固化
 * @returns 环境配置映射
 */
export async function loadEnvironmentConfig() {
    const configPath = resolvePluginPath("environments.json");
    const content = await fs.readFile(configPath, "utf-8");
    const rawConfig = JSON.parse(content);
    return rawConfig;
}
/**
 * 获取指定环境的配置
 * @param env 环境名称
 * @returns 环境配置
 */
let _configCache = null;
export async function getEnvironmentConfig(env) {
    // 延迟加载配置
    if (!_configCache) {
        _configCache = await loadEnvironmentConfig();
    }
    const config = _configCache[env];
    if (!config) {
        throw new Error(`未知的环境：${env}`);
    }
    return config;
}
/**
 * 强制重新加载配置（用于配置更新后）
 */
export function reloadEnvironmentConfig() {
    _configCache = null;
}
/**
 * 获取当前活跃的环境
 * @returns 当前环境，默认为 production
 */
export async function getCurrentEnvironment() {
    try {
        const fs = await import("fs/promises");
        const envFile = resolvePluginPath(".active_environment");
        return (await fs.readFile(envFile, "utf-8")).trim();
    }
    catch {
        return "production";
    }
}
/**
 * 设置当前活跃的环境
 * @param env 环境名称
 */
export async function setCurrentEnvironment(env) {
    const fs = await import("fs/promises");
    const envFile = resolvePluginPath(".active_environment");
    await fs.writeFile(envFile, env, "utf-8");
}
