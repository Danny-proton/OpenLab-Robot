/**
 * Kernel Service — Openlab Robot 内核切换
 *
 * 支持两个内核：
 *   - cc-haha：默认内核（Claude Code 安全内核复现，本地 Bun TUI）
 *   - jiuwen-agent-core：九问 Agent 内核（jiuwenSwarm 蜂群协作，vendor/jiuwenswarm）
 *
 * 配置存储在 ~/.openlab-robot/kernel.json：
 *   { "kernel": "cc-haha" | "jiuwen-agent-core", "configDir": "/custom/path"? }
 *
 * 用户数据目录跟随内核切换默认配置，也可通过 configDir 自定义覆盖。
 * 环境变量机制不变（CLAUDE_CONFIG_DIR / JIUWENSWARM_DATA_DIR 仍优先生效）。
 */

import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'

export type KernelId = 'cc-haha' | 'jiuwen-agent-core'

export const KERNEL_IDS: readonly KernelId[] = ['cc-haha', 'jiuwen-agent-core']

export interface KernelConfig {
  kernel: KernelId
  /** 用户自定义配置目录（可选，优先级高于内核默认目录） */
  configDir?: string
}

export interface KernelInfo extends KernelConfig {
  /** 当前生效的配置目录（configDir 覆盖 > 内核默认） */
  effectiveConfigDir: string
  /** 内核默认配置目录 */
  defaultConfigDir: string
  /** 内核配置文件路径 */
  kernelFile: string
  /** 对应的启动命令提示 */
  launchCommand: string
}

const OPENLAB_DIR = path.join(os.homedir(), '.openlab-robot')
const KERNEL_FILE = path.join(OPENLAB_DIR, 'kernel.json')

export const DEFAULT_KERNEL: KernelId = 'cc-haha'

/** 各内核的默认用户数据目录 */
export function defaultConfigDirFor(kernel: KernelId): string {
  return kernel === 'jiuwen-agent-core'
    ? path.join(os.homedir(), '.jiuwenswarm')
    : path.join(os.homedir(), '.claude')
}

/** 各内核对应的推荐启动命令 */
export function launchCommandFor(kernel: KernelId): string {
  return kernel === 'jiuwen-agent-core' ? 'jiuwen' : 'openlab-robot'
}

function isKernelId(value: unknown): value is KernelId {
  return typeof value === 'string' && (KERNEL_IDS as readonly string[]).includes(value)
}

/** 读取内核配置（不存在时返回默认 cc-haha） */
export function getKernelConfig(): KernelConfig {
  try {
    const raw = fs.readFileSync(KERNEL_FILE, 'utf-8')
    const parsed = JSON.parse(raw) as Partial<KernelConfig>
    return {
      kernel: isKernelId(parsed.kernel) ? parsed.kernel : DEFAULT_KERNEL,
      configDir: typeof parsed.configDir === 'string' && parsed.configDir.trim()
        ? parsed.configDir.trim()
        : undefined,
    }
  } catch {
    return { kernel: DEFAULT_KERNEL }
  }
}

/** 写入内核配置 */
export function setKernelConfig(update: Partial<KernelConfig>): KernelConfig {
  const current = getKernelConfig()
  const next: KernelConfig = {
    kernel: update.kernel !== undefined && isKernelId(update.kernel) ? update.kernel : current.kernel,
    configDir: update.configDir !== undefined
      ? (update.configDir.trim() ? update.configDir.trim() : undefined)
      : current.configDir,
  }
  fs.mkdirSync(OPENLAB_DIR, { recursive: true })
  fs.writeFileSync(KERNEL_FILE, JSON.stringify(next, null, 2) + '\n', 'utf-8')
  return next
}

/** 获取完整内核信息（含生效目录与启动命令提示） */
export function getKernelInfo(): KernelInfo {
  const config = getKernelConfig()
  const defaultDir = defaultConfigDirFor(config.kernel)
  return {
    ...config,
    defaultConfigDir: defaultDir,
    effectiveConfigDir: config.configDir ?? defaultDir,
    kernelFile: KERNEL_FILE,
    launchCommand: launchCommandFor(config.kernel),
  }
}
