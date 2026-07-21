/**
 * Sync REST API — Openlab Robot 云同步（mock）
 *
 * GET  /api/sync           — 同步状态（开关、scope、历史）
 * PUT  /api/sync/scopes    — 设置启用的同步范围 { scopes: [...] }
 * POST /api/sync/upload    — 上传 { scope, detail? }（需登录）
 * POST /api/sync/download  — 下载 { scope }（需登录）
 */

import { ApiError } from '../middleware/errorHandler.js'
import {
  download,
  getSyncState,
  isSyncScope,
  setEnabledScopes,
  upload,
} from '../services/syncService.js'

export async function handleSyncApi(
  req: Request,
  _url: URL,
  segments: string[],
): Promise<Response> {
  const action = segments[2]

  if (action === undefined && req.method === 'GET') {
    return Response.json(getSyncState())
  }

  if (action === 'scopes' && req.method === 'PUT') {
    const body = (await req.json().catch(() => ({}))) as { scopes?: unknown }
    if (!Array.isArray(body.scopes) || !body.scopes.every(isSyncScope)) {
      throw new ApiError(400, 'scopes must be an array of valid sync scopes')
    }
    setEnabledScopes(body.scopes)
    return Response.json({ ok: true, ...getSyncState() })
  }

  if (action === 'upload' && req.method === 'POST') {
    const body = (await req.json().catch(() => ({}))) as { scope?: unknown; detail?: unknown }
    if (!isSyncScope(body.scope)) throw new ApiError(400, 'Invalid scope')
    try {
      const record = await upload(body.scope, typeof body.detail === 'string' ? body.detail : undefined)
      return Response.json({ ok: true, record })
    } catch (err) {
      throw new ApiError(403, err instanceof Error ? err.message : String(err))
    }
  }

  if (action === 'download' && req.method === 'POST') {
    const body = (await req.json().catch(() => ({}))) as { scope?: unknown }
    if (!isSyncScope(body.scope)) throw new ApiError(400, 'Invalid scope')
    try {
      const record = await download(body.scope)
      return Response.json({ ok: true, record })
    } catch (err) {
      throw new ApiError(403, err instanceof Error ? err.message : String(err))
    }
  }

  throw new ApiError(404, 'Not found')
}
