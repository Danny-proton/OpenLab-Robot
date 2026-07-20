/**
 * Skin REST API — Openlab Robot 皮肤定制
 *
 * GET /api/skin   — 获取皮肤配置
 * PUT /api/skin   — 更新皮肤（preset / accentColor / theme）
 */

import { ApiError } from '../middleware/errorHandler.js'
import { getSkinInfo, setSkinConfig, type SkinConfig } from '../services/skinService.js'

const ALLOWED_FIELDS = ['preset', 'accentColor', 'theme'] as const

export async function handleSkinApi(
  req: Request,
  url: URL,
  segments: string[],
): Promise<Response> {
  if (segments[2] !== undefined) {
    throw new ApiError(404, 'Not found')
  }

  if (req.method === 'GET') {
    return Response.json(getSkinInfo())
  }

  if (req.method === 'PUT') {
    const body = (await req.json().catch(() => ({}))) as Record<string, unknown>
    const update: SkinConfig = {}
    for (const field of ALLOWED_FIELDS) {
      if (body[field] !== undefined) {
        if (typeof body[field] !== 'string') {
          throw new ApiError(400, `${field} must be a string`)
        }
        update[field] = body[field] as string
      }
    }
    setSkinConfig(update)
    return Response.json({ ok: true, ...getSkinInfo() })
  }

  throw new ApiError(405, 'Method not allowed')
}
