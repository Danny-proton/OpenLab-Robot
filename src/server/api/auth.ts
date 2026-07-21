/**
 * Auth REST API — Openlab Robot 用户登录（mock）
 *
 * GET  /api/auth          — 登录状态与功能开关
 * POST /api/auth/login    — 登录 { username, password }
 * POST /api/auth/logout   — 退出登录
 * PUT  /api/auth/features — 设置功能开关 { auth?, cloudSync? }
 */

import { ApiError } from '../middleware/errorHandler.js'
import {
  getAuthState,
  login,
  logout,
  setFeatureFlags,
  verifyCredentials,
} from '../services/authService.js'

export async function handleAuthApi(
  req: Request,
  _url: URL,
  segments: string[],
): Promise<Response> {
  const action = segments[2]

  if (action === undefined && req.method === 'GET') {
    return Response.json(getAuthState())
  }

  if (action === 'login' && req.method === 'POST') {
    const body = (await req.json().catch(() => ({}))) as { username?: unknown; password?: unknown }
    if (!verifyCredentials(body.username, body.password)) {
      throw new ApiError(401, 'Invalid username or password')
    }
    login(body.username)
    return Response.json({ ok: true, ...getAuthState() })
  }

  if (action === 'logout' && req.method === 'POST') {
    logout()
    return Response.json({ ok: true, ...getAuthState() })
  }

  if (action === 'features' && req.method === 'PUT') {
    const body = (await req.json().catch(() => ({}))) as { auth?: unknown; cloudSync?: unknown }
    const update: { auth?: boolean; cloudSync?: boolean } = {}
    if (typeof body.auth === 'boolean') update.auth = body.auth
    if (typeof body.cloudSync === 'boolean') update.cloudSync = body.cloudSync
    setFeatureFlags(update)
    return Response.json({ ok: true, ...getAuthState() })
  }

  throw new ApiError(404, 'Not found')
}
