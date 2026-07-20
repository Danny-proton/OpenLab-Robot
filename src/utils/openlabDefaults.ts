/**
 * Openlab Robot 构建期默认值（CLI/服务端共享读取层）。
 *
 * 构建/打包时可在仓库根目录放置 openlab.defaults.json，为各项设置提供默认值：
 *   {
 *     "brand":     { "appName": "...", "agentName": "...",
 *                    "chatPlaceholder": "...", "systemPromptOverride": "..." },
 *     "kernel":    { "kernel": "cc-haha", "configDir": "..." },
 *     "workspace": { "defaultDir": "/path/to/workspace" },
 *     "skin":      { "theme": "light", "preset": "ocean", "accentColor": "#2563eb" }
 *   }
 *
 * 优先级：用户运行时配置（~/.openlab-robot/*.json）> openlab.defaults.json > 硬编码默认。
 * 不放置该文件时，一切按当前硬编码默认值。
 *
 * 文件查找顺序：
 *   1. 环境变量 OPENLAB_DEFAULTS_FILE 指定的路径
 *   2. 当前工作目录 /openlab.defaults.json
 *   3. 包根目录（本文件上溯三级）/openlab.defaults.json
 */

import { readFileSync, existsSync } from 'fs'
import { join, dirname } from 'path'
import { fileURLToPath } from 'url'

export interface OpenlabDefaults {
  brand?: {
    appName?: string
    agentName?: string
    chatPlaceholder?: string
    systemPromptOverride?: string
  }
  kernel?: {
    kernel?: string
    configDir?: string
  }
  workspace?: {
    defaultDir?: string
  }
  skin?: {
    theme?: string
    preset?: string
    accentColor?: string
  }
}

const PACKAGE_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..')

let cache: OpenlabDefaults | null | undefined

export function getOpenlabDefaults(): OpenlabDefaults {
  if (cache !== undefined) return cache
  const candidates = [
    process.env.OPENLAB_DEFAULTS_FILE,
    join(process.cwd(), 'openlab.defaults.json'),
    join(PACKAGE_ROOT, 'openlab.defaults.json'),
  ].filter((p): p is string => typeof p === 'string' && p.length > 0)

  for (const candidate of candidates) {
    try {
      if (!existsSync(candidate)) continue
      const parsed = JSON.parse(readFileSync(candidate, 'utf-8')) as OpenlabDefaults
      cache = parsed && typeof parsed === 'object' ? parsed : {}
      return cache
    } catch {
      // 读取失败则尝试下一个候选
    }
  }
  cache = {}
  return cache
}

/** 测试或热更新场景下重置缓存 */
export function resetOpenlabDefaultsCache(): void {
  cache = undefined
}
