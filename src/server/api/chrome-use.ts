/**
 * Chrome Use REST API — Openlab Robot Chrome use
 *
 * GET  /api/chrome-use/status  — 环境检查（MCP / Chrome 版本 / 远程调试）
 * GET  /api/chrome-use/targets — 枚举调试目标页签
 * POST /api/chrome-use/launch  — 启动调试 Chrome 实例
 */

import { ApiError } from '../middleware/errorHandler.js'
import {
  getChromeUseStatus,
  launchDebugChrome,
  listDebugTargets,
} from '../services/chromeUseService.js'

export async function handleChromeUseApi(
  req: Request,
  _url: URL,
  segments: string[],
): Promise<Response> {
  const action = segments[2]

  if (action === 'status' && req.method === 'GET') {
    return Response.json(await getChromeUseStatus())
  }

  if (action === 'targets' && req.method === 'GET') {
    return Response.json({ targets: await listDebugTargets() })
  }

  if (action === 'launch' && req.method === 'POST') {
    const result = launchDebugChrome()
    if (!result.ok) throw new ApiError(500, result.error ?? 'Failed to launch Chrome')
    return Response.json(result)
  }

  throw new ApiError(404, 'Not found')
}
