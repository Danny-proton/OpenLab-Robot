/**
 * Skill Prefs Service — Openlab Robot 输入框技能偏好
 *
 * 存储在 ~/.openlab-robot/skill-prefs.json。
 * 构建期默认值从 openlab.defaults.json 的 skillPrefs 段读取。
 */

import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import { getOpenlabDefaults } from '../../utils/openlabDefaults.js'

const OPENLAB_DIR = path.join(os.homedir(), '.openlab-robot')
const PREFS_FILE = path.join(OPENLAB_DIR, 'skill-prefs.json')

export interface PinnedSkill {
  name: string
  source?: string
  alias?: string
  group?: string
}

export interface SkillPrefs {
  pinned: PinnedSkill[]
  defaultPrefixSkill?: string
}

function sanitizePinned(value: unknown): PinnedSkill[] {
  if (!Array.isArray(value)) return []
  const out: PinnedSkill[] = []
  for (const item of value) {
    if (!item || typeof item !== 'object') continue
    const raw = item as Record<string, unknown>
    if (typeof raw.name !== 'string' || raw.name.trim().length === 0) continue
    out.push({
      name: raw.name.trim(),
      source: typeof raw.source === 'string' && raw.source.trim() ? raw.source.trim() : undefined,
      alias: typeof raw.alias === 'string' && raw.alias.trim() ? raw.alias.trim() : undefined,
      group: typeof raw.group === 'string' && raw.group.trim() ? raw.group.trim() : undefined,
    })
  }
  return out
}

function sanitizePrefix(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : undefined
}

function defaultsPrefs(): SkillPrefs {
  const raw = getOpenlabDefaults() as { skillPrefs?: { pinned?: unknown; defaultPrefixSkill?: unknown } }
  return {
    pinned: sanitizePinned(raw.skillPrefs?.pinned),
    defaultPrefixSkill: sanitizePrefix(raw.skillPrefs?.defaultPrefixSkill),
  }
}

export function getSkillPrefs(): SkillPrefs {
  try {
    const parsed = JSON.parse(fs.readFileSync(PREFS_FILE, 'utf-8')) as {
      pinned?: unknown
      defaultPrefixSkill?: unknown
    }
    const d = defaultsPrefs()
    return {
      pinned: parsed.pinned !== undefined ? sanitizePinned(parsed.pinned) : d.pinned,
      defaultPrefixSkill:
        parsed.defaultPrefixSkill !== undefined
          ? sanitizePrefix(parsed.defaultPrefixSkill)
          : d.defaultPrefixSkill,
    }
  } catch {
    return defaultsPrefs()
  }
}

export function setSkillPrefs(update: Partial<SkillPrefs>): SkillPrefs {
  const current = getSkillPrefs()
  const next: SkillPrefs = {
    pinned: update.pinned !== undefined ? sanitizePinned(update.pinned) : current.pinned,
    defaultPrefixSkill:
      update.defaultPrefixSkill !== undefined
        ? sanitizePrefix(update.defaultPrefixSkill)
        : current.defaultPrefixSkill,
  }
  fs.mkdirSync(OPENLAB_DIR, { recursive: true })
  fs.writeFileSync(PREFS_FILE, JSON.stringify(next, null, 2) + '\n', 'utf-8')
  return next
}
