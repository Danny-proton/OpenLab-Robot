/**
 * Brand Service — Openlab Robot 品牌定制
 *
 * 配置存储在 ~/.openlab-robot/brand.json：
 *   {
 *     "appName": "Openlab Robot",            // 软件名称（关于页、通知、标题等）
 *     "agentName": "Openlab Robot",          // 智能体名称（界面文案中的“Claude”位）
 *     "chatPlaceholder": "让 Openlab Robot 编辑、调试或解释代码...",  // 对话框占位提示（可单独设置）
 *     "systemPromptOverride": "You are ..."  // 系统提示词身份（可单独定制）
 *   }
 *
 * 例如把 agentName 改为「金融智能体」并保存后，界面各处（对话框提示、
 * 新建会话引导、诊断、Token 用量、技能/Agents/MCP 页提示等）都会显示
 * 「金融智能体」。
 *
 * 读取层见 src/utils/brandConfig.ts（CLI 侧系统提示词也走这里）。
 */

import * as fs from 'fs'
import {
  BRAND_FILE,
  OPENLAB_DIR,
  getBrandConfig,
  DEFAULT_APP_NAME,
  DEFAULT_AGENT_NAME,
  type BrandConfig,
} from '../../utils/brandConfig.js'
import { getOpenlabDefaults } from '../../utils/openlabDefaults.js'

export type { BrandConfig } from '../../utils/brandConfig.js'
export { DEFAULT_APP_NAME, DEFAULT_AGENT_NAME, getBrandConfig } from '../../utils/brandConfig.js'

export interface BrandInfo {
  appName: string
  agentName: string
  chatPlaceholder?: string
  systemPromptOverride?: string
  brandFile: string
}

function sanitize(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

/** 写入品牌配置（空字符串表示清除该项，恢复默认） */
export function setBrandConfig(update: BrandConfig): BrandConfig {
  const current = getBrandConfig()
  const next: BrandConfig = {
    appName: update.appName !== undefined ? sanitize(update.appName) : current.appName,
    agentName: update.agentName !== undefined ? sanitize(update.agentName) : current.agentName,
    chatPlaceholder: update.chatPlaceholder !== undefined ? sanitize(update.chatPlaceholder) : current.chatPlaceholder,
    systemPromptOverride: update.systemPromptOverride !== undefined
      ? (update.systemPromptOverride.trim() ? update.systemPromptOverride : undefined)
      : current.systemPromptOverride,
  }
  fs.mkdirSync(OPENLAB_DIR, { recursive: true })
  fs.writeFileSync(BRAND_FILE, JSON.stringify(next, null, 2) + '\n', 'utf-8')
  return next
}

/** 获取完整品牌信息（用户配置 > 构建期默认 > 硬编码默认） */
export function getBrandInfo(): BrandInfo {
  const config = getBrandConfig()
  const buildDefaults = getOpenlabDefaults().brand
  return {
    appName: config.appName ?? buildDefaults?.appName ?? DEFAULT_APP_NAME,
    agentName: config.agentName ?? buildDefaults?.agentName ?? DEFAULT_AGENT_NAME,
    chatPlaceholder: config.chatPlaceholder ?? buildDefaults?.chatPlaceholder,
    systemPromptOverride: config.systemPromptOverride ?? buildDefaults?.systemPromptOverride,
    brandFile: BRAND_FILE,
  }
}
