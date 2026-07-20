/**
 * Skin Service — Openlab Robot 皮肤定制
 *
 * 配置存储在 ~/.openlab-robot/skin.json：
 *   { "preset": "ocean", "accentColor": "#2563eb", "theme": "light" }
 *
 * - preset：预设皮肤 id（见桌面端 SKIN_PRESETS），'custom' 表示自定义强调色
 * - accentColor：自定义强调色（preset 为 custom 时生效）
 * - theme：基础主题（white/light/dark），与桌面端主题联动
 *
 * 构建期默认值：openlab.defaults.json 的 skin 段。
 */

import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import { getOpenlabDefaults } from '../../utils/openlabDefaults.js'

const OPENLAB_DIR = path.join(os.homedir(), '.openlab-robot')
const SKIN_FILE = path.join(OPENLAB_DIR, 'skin.json')

export interface SkinConfig {
  preset?: string
  accentColor?: string
  theme?: string
}

export interface SkinInfo {
  preset?: string
  accentColor?: string
  theme?: string
  /** 构建期默认皮肤（openlab.defaults.json） */
  buildDefaults?: SkinConfig
  skinFile: string
}

const HEX_COLOR_RE = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

function sanitize(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

function sanitizeColor(value: unknown): string | undefined {
  const v = sanitize(value)
  return v && HEX_COLOR_RE.test(v) ? v : undefined
}

export function getSkinConfig(): SkinConfig {
  try {
    const raw = fs.readFileSync(SKIN_FILE, 'utf-8')
    const parsed = JSON.parse(raw) as SkinConfig
    return {
      preset: sanitize(parsed.preset),
      accentColor: sanitizeColor(parsed.accentColor),
      theme: sanitize(parsed.theme),
    }
  } catch {
    return {}
  }
}

export function setSkinConfig(update: SkinConfig): SkinConfig {
  const current = getSkinConfig()
  const next: SkinConfig = {
    preset: update.preset !== undefined ? sanitize(update.preset) : current.preset,
    accentColor: update.accentColor !== undefined ? sanitizeColor(update.accentColor) : current.accentColor,
    theme: update.theme !== undefined ? sanitize(update.theme) : current.theme,
  }
  fs.mkdirSync(OPENLAB_DIR, { recursive: true })
  fs.writeFileSync(SKIN_FILE, JSON.stringify(next, null, 2) + '\n', 'utf-8')
  return next
}

export function getSkinInfo(): SkinInfo {
  const config = getSkinConfig()
  const build = getOpenlabDefaults().skin
  const buildDefaults: SkinConfig | undefined = build
    ? { preset: sanitize(build.preset), accentColor: sanitizeColor(build.accentColor), theme: sanitize(build.theme) }
    : undefined
  return {
    preset: config.preset ?? buildDefaults?.preset,
    accentColor: config.accentColor ?? buildDefaults?.accentColor,
    theme: config.theme ?? buildDefaults?.theme,
    buildDefaults,
    skinFile: SKIN_FILE,
  }
}
