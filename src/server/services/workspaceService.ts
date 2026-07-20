/**
 * Workspace Service — Openlab Robot 默认工作区
 *
 * 配置存储在 ~/.openlab-robot/app.json：
 *   { "defaultWorkspaceDir": "/path/to/workspace" }
 *
 * 新建会话未指定目录时使用该默认路径；未设置时回退到
 * openlab.defaults.json 的 workspace.defaultDir，再回退到用户主目录。
 */

import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import { getOpenlabDefaults } from '../../utils/openlabDefaults.js'

const OPENLAB_DIR = path.join(os.homedir(), '.openlab-robot')
const APP_FILE = path.join(OPENLAB_DIR, 'app.json')

export interface AppConfig {
  defaultWorkspaceDir?: string
}

function sanitize(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : undefined
}

export function getAppConfig(): AppConfig {
  try {
    const raw = fs.readFileSync(APP_FILE, 'utf-8')
    const parsed = JSON.parse(raw) as AppConfig
    return { defaultWorkspaceDir: sanitize(parsed.defaultWorkspaceDir) }
  } catch {
    return {}
  }
}

export function setAppConfig(update: AppConfig): AppConfig {
  const current = getAppConfig()
  const next: AppConfig = {
    defaultWorkspaceDir: update.defaultWorkspaceDir !== undefined
      ? sanitize(update.defaultWorkspaceDir)
      : current.defaultWorkspaceDir,
  }
  fs.mkdirSync(OPENLAB_DIR, { recursive: true })
  fs.writeFileSync(APP_FILE, JSON.stringify(next, null, 2) + '\n', 'utf-8')
  return next
}

/**
 * 新建会话的默认工作目录：
 * 用户设置 > 构建期默认（openlab.defaults.json）> 用户主目录。
 */
export function getDefaultWorkspaceDir(): string {
  return getAppConfig().defaultWorkspaceDir
    ?? sanitize(getOpenlabDefaults().workspace?.defaultDir)
    ?? os.homedir()
}

export function getWorkspaceInfo() {
  return {
    defaultWorkspaceDir: getAppConfig().defaultWorkspaceDir,
    buildDefaultDir: sanitize(getOpenlabDefaults().workspace?.defaultDir),
    effectiveDefaultDir: getDefaultWorkspaceDir(),
    appFile: APP_FILE,
  }
}
