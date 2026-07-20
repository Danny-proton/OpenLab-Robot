/**
 * Brand REST API — Openlab Robot 品牌定制
 *
 * GET /api/brand   — 获取品牌定制配置
 * PUT /api/brand   — 更新品牌定制（appName / agentName / chatPlaceholder / systemPromptOverride）
 */

import { ApiError } from '../middleware/errorHandler.js'
import { getBrandInfo, setBrandConfig, type BrandConfig } from '../services/brandService.js'

const ALLOWED_FIELDS = ['appName', 'agentName', 'chatPlaceholder', 'systemPromptOverride'] as const

export async function handleBrandApi(
  req: Request,
  url: URL,
  segments: string[],
): Promise<Response> {
  if (segments[2] !== undefined) {
    throw new ApiError(404, 'Not found')
  }

  if (req.method === 'GET') {
    return Response.json(getBrandInfo())
  }

  if (req.method === 'PUT') {
    const body = (await req.json().catch(() => ({}))) as Record<string, unknown>
    const update: BrandConfig = {}
    for (const field of ALLOWED_FIELDS) {
      if (body[field] !== undefined) {
        if (typeof body[field] !== 'string') {
          throw new ApiError(400, `${field} must be a string`)
        }
        update[field] = body[field] as string
      }
    }
    setBrandConfig(update)
    return Response.json({ ok: true, ...getBrandInfo() })
  }

  throw new ApiError(405, 'Method not allowed')
}
