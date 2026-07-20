/**
 * Workspace REST API — Openlab Robot 默认工作区
 *
 * GET /api/workspace   — 获取默认工作区配置
 * PUT /api/workspace   — 设置默认工作区路径（空字符串表示恢复默认）
 */

import { ApiError } from '../middleware/errorHandler.js'
import { getWorkspaceInfo, setAppConfig } from '../services/workspaceService.js'

export async function handleWorkspaceApi(
  req: Request,
  url: URL,
  segments: string[],
): Promise<Response> {
  if (segments[2] !== undefined) {
    throw new ApiError(404, 'Not found')
  }

  if (req.method === 'GET') {
    return Response.json(getWorkspaceInfo())
  }

  if (req.method === 'PUT') {
    const body = (await req.json().catch(() => ({}))) as { defaultWorkspaceDir?: string }
    if (body.defaultWorkspaceDir !== undefined && typeof body.defaultWorkspaceDir !== 'string') {
      throw new ApiError(400, 'defaultWorkspaceDir must be a string')
    }
    setAppConfig({ defaultWorkspaceDir: body.defaultWorkspaceDir })
    return Response.json({ ok: true, ...getWorkspaceInfo() })
  }

  throw new ApiError(405, 'Method not allowed')
}
