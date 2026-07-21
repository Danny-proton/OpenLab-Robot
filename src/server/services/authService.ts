/**
 * Auth Service — Openlab Robot 用户登录（mock）
 *
 * 用户名密码登录的后端 mock 实现：任意非空用户名/密码即可登录，
 * 签发的 token 持久化在 ~/.openlab-robot/auth.json。
 *
 * 功能开关（features）优先级：
 *   ~/.openlab-robot/app.json 的 features 段
 *   > openlab.defaults.json 的 features 段
 *   > 默认全部开启
 */

import * as os from 'os'
import * as path from 'path'
import * as fs from 'fs'
import * as crypto from 'crypto'
import { getOpenlabDefaults } from '../../utils/openlabDefaults.js'

const OPENLAB_DIR = path.join(os.homedir(), '.openlab-robot')
const AUTH_FILE = path.join(OPENLAB_DIR, 'auth.json')
const APP_FILE = path.join(OPENLAB_DIR, 'app.json')

export interface AuthSession {
  username: string
  token: string
  loggedInAt: string
}

export interface FeatureFlags {
  auth: boolean
  cloudSync: boolean
}

export interface AuthState {
  enabled: boolean
  loggedIn: boolean
  username?: string
  tokenMask?: string
  loggedInAt?: string
  features: FeatureFlags
}

function readJson<T>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf-8')) as T
  } catch {
    return null
  }
}

function writeJson(file: string, value: unknown) {
  fs.mkdirSync(OPENLAB_DIR, { recursive: true })
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n', 'utf-8')
}

export function verifyCredentials(username: unknown, password: unknown): username is string {
  // mock：任意非空用户名/密码即视为合法
  return (
    typeof username === 'string' &&
    username.trim().length > 0 &&
    typeof password === 'string' &&
    password.length > 0
  )
}

export function issueToken(): string {
  return `ol_mock_${crypto.randomBytes(24).toString('hex')}`
}

export function getSession(): AuthSession | null {
  const session = readJson<AuthSession>(AUTH_FILE)
  if (!session || typeof session.token !== 'string' || typeof session.username !== 'string') {
    return null
  }
  return session
}

export function login(username: string): AuthSession {
  const session: AuthSession = {
    username: username.trim(),
    token: issueToken(),
    loggedInAt: new Date().toISOString(),
  }
  writeJson(AUTH_FILE, session)
  return session
}

export function logout(): void {
  try {
    fs.unlinkSync(AUTH_FILE)
  } catch { /* 尚未登录 */ }
}

function defaultsFeatures(): Partial<FeatureFlags> {
  const raw = getOpenlabDefaults() as { features?: Partial<FeatureFlags> }
  return raw.features ?? {}
}

export function getFeatureFlags(): FeatureFlags {
  const d = defaultsFeatures()
  const app = readJson<{ features?: Partial<FeatureFlags> }>(APP_FILE)
  return {
    auth: app?.features?.auth ?? d.auth ?? true,
    cloudSync: app?.features?.cloudSync ?? d.cloudSync ?? true,
  }
}

export function setFeatureFlags(update: Partial<FeatureFlags>): FeatureFlags {
  const app = readJson<Record<string, unknown>>(APP_FILE) ?? {}
  const current = getFeatureFlags()
  const next: FeatureFlags = {
    auth: typeof update.auth === 'boolean' ? update.auth : current.auth,
    cloudSync: typeof update.cloudSync === 'boolean' ? update.cloudSync : current.cloudSync,
  }
  app.features = next
  writeJson(APP_FILE, app)
  return next
}

function maskToken(token: string): string {
  if (token.length <= 12) return `${token.slice(0, 4)}…`
  return `${token.slice(0, 12)}…${token.slice(-4)}`
}

export function getAuthState(): AuthState {
  const features = getFeatureFlags()
  const session = getSession()
  return {
    enabled: features.auth,
    loggedIn: features.auth && session !== null,
    username: session?.username,
    tokenMask: session ? maskToken(session.token) : undefined,
    loggedInAt: session?.loggedInAt,
    features,
  }
}
