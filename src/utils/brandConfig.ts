/**
 * Openlab Robot 品牌定制（CLI/服务端共享读取层，无服务端依赖）。
 * 配置见 ~/.openlab-robot/brand.json，由 src/server/services/brandService.ts 写入。
 */

import { homedir } from 'os'
import { join } from 'path'
import { readFileSync } from 'fs'
import { getOpenlabDefaults } from './openlabDefaults.js'

export interface BrandConfig {
  appName?: string
  agentName?: string
  chatPlaceholder?: string
  systemPromptOverride?: string
}

export const DEFAULT_APP_NAME = 'Openlab Robot'
export const DEFAULT_AGENT_NAME = 'Openlab Robot'

export const OPENLAB_DIR = join(homedir(), '.openlab-robot')
export const BRAND_FILE = join(OPENLAB_DIR, 'brand.json')

function sanitize(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

export function getBrandConfig(): BrandConfig {
  try {
    const raw = readFileSync(BRAND_FILE, 'utf-8')
    const parsed = JSON.parse(raw) as BrandConfig
    return {
      appName: sanitize(parsed.appName),
      agentName: sanitize(parsed.agentName),
      chatPlaceholder: sanitize(parsed.chatPlaceholder),
      systemPromptOverride: typeof parsed.systemPromptOverride === 'string'
        ? parsed.systemPromptOverride
        : undefined,
    }
  } catch {
    return {}
  }
}

export function getBrandAgentName(): string {
  return getBrandConfig().agentName
    ?? getOpenlabDefaults().brand?.agentName
    ?? DEFAULT_AGENT_NAME
}

export function getBrandAppName(): string {
  return getBrandConfig().appName
    ?? getOpenlabDefaults().brand?.appName
    ?? DEFAULT_APP_NAME
}

/**
 * 系统提示词身份：用户定制 > 构建期默认 > Openlab Robot 默认身份。
 */
export function getBrandSystemPromptPrefix(): string {
  const override = getBrandConfig().systemPromptOverride
    ?? getOpenlabDefaults().brand?.systemPromptOverride
  if (override && override.trim()) return override.trim()
  return `You are ${getBrandAgentName()}, an AI coding assistant.`
}
