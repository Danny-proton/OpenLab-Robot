/**
 * Sync Service — Openlab Robot 云同步（mock）
 *
 * 支持四个同步范围：agentConfig / skill / sessionHistory / memory。
 * mock 实现：上传/下载模拟网络延迟后返回 mock:// URL，
 * 同步历史（最多 50 条）持久化在 ~/.openlab-robot/sync.json。
 */

import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import * as crypto from 'crypto'
import { getFeatureFlags, getSession } from './authService.js'

const OPENLAB_DIR = path.join(os.homedir(), '.openlab-robot')
const SYNC_FILE = path.join(OPENLAB_DIR, 'sync.json')
const HISTORY_LIMIT = 50
const MOCK_LATENCY_MS = 300

export type SyncScope = 'agentConfig' | 'skill' | 'sessionHistory' | 'memory'
export type SyncDirection = 'upload' | 'download'

export const SYNC_SCOPES: SyncScope[] = ['agentConfig', 'skill', 'sessionHistory', 'memory']

export interface SyncRecord {
  id: string
  scope: SyncScope
  direction: SyncDirection
  at: string
  url: string
  detail?: string
}

interface SyncFileShape {
  enabledScopes?: SyncScope[]
  history?: SyncRecord[]
}

function readSyncFile(): SyncFileShape {
  try {
    return JSON.parse(fs.readFileSync(SYNC_FILE, 'utf-8')) as SyncFileShape
  } catch {
    return {}
  }
}

function writeSyncFile(shape: SyncFileShape) {
  fs.mkdirSync(OPENLAB_DIR, { recursive: true })
  fs.writeFileSync(SYNC_FILE, JSON.stringify(shape, null, 2) + '\n', 'utf-8')
}

export function isSyncScope(value: unknown): value is SyncScope {
  return typeof value === 'string' && (SYNC_SCOPES as string[]).includes(value)
}

export function getEnabledScopes(): SyncScope[] {
  const file = readSyncFile()
  const scopes = Array.isArray(file.enabledScopes) ? file.enabledScopes.filter(isSyncScope) : []
  return scopes.length > 0 ? scopes : [...SYNC_SCOPES]
}

export function setEnabledScopes(scopes: SyncScope[]): SyncScope[] {
  const file = readSyncFile()
  file.enabledScopes = scopes.filter(isSyncScope)
  writeSyncFile(file)
  return getEnabledScopes()
}

export function getSyncHistory(): SyncRecord[] {
  const file = readSyncFile()
  return Array.isArray(file.history) ? file.history : []
}

function appendHistory(record: SyncRecord) {
  const file = readSyncFile()
  const history = Array.isArray(file.history) ? file.history : []
  history.unshift(record)
  file.history = history.slice(0, HISTORY_LIMIT)
  writeSyncFile(file)
}

export function canUseSync(): { ok: boolean; reason?: string } {
  const features = getFeatureFlags()
  if (!features.cloudSync) return { ok: false, reason: 'Cloud sync is disabled.' }
  if (!features.auth || !getSession()) return { ok: false, reason: 'Sign in required.' }
  return { ok: true }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function upload(scope: SyncScope, detail?: string): Promise<SyncRecord> {
  const gate = canUseSync()
  if (!gate.ok) throw new Error(gate.reason)
  await delay(MOCK_LATENCY_MS)
  const record: SyncRecord = {
    id: crypto.randomUUID(),
    scope,
    direction: 'upload',
    at: new Date().toISOString(),
    url: `mock://sync.openlab/${scope}/${crypto.randomUUID()}`,
    detail,
  }
  appendHistory(record)
  return record
}

export async function download(scope: SyncScope): Promise<SyncRecord> {
  const gate = canUseSync()
  if (!gate.ok) throw new Error(gate.reason)
  await delay(MOCK_LATENCY_MS)
  const record: SyncRecord = {
    id: crypto.randomUUID(),
    scope,
    direction: 'download',
    at: new Date().toISOString(),
    url: `mock://sync.openlab/${scope}/latest`,
  }
  appendHistory(record)
  return record
}

export function getSyncState() {
  return {
    enabled: getFeatureFlags().cloudSync,
    scopes: getEnabledScopes(),
    history: getSyncHistory(),
  }
}
