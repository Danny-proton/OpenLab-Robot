/**
 * Kernel REST API — Openlab Robot 内核切换
 *
 * GET /api/kernel         — 获取当前内核配置（含生效配置目录、启动命令提示）
 * PUT /api/kernel         — 切换内核 / 自定义配置目录
 */

import { ApiError } from '../middleware/errorHandler.js'
import { getKernelInfo, setKernelConfig, KERNEL_IDS, type KernelId } from '../services/kernelService.js'

export async function handleKernelApi(
  req: Request,
  url: URL,
  segments: string[],
): Promise<Response> {
  if (segments[2] !== undefined) {
    throw new ApiError(404, 'Not found')
  }

  if (req.method === 'GET') {
    return Response.json({
      ...getKernelInfo(),
      availableKernels: KERNEL_IDS,
    })
  }

  if (req.method === 'PUT') {
    const body = (await req.json().catch(() => ({}))) as {
      kernel?: KernelId
      configDir?: string
    }
    if (body.kernel !== undefined && !(KERNEL_IDS as readonly string[]).includes(body.kernel)) {
      throw new ApiError(400, `Invalid kernel. Available: ${KERNEL_IDS.join(', ')}`)
    }
    if (body.configDir !== undefined && typeof body.configDir !== 'string') {
      throw new ApiError(400, 'configDir must be a string')
    }
    const next = setKernelConfig({ kernel: body.kernel, configDir: body.configDir })
    return Response.json({ ok: true, ...getKernelInfo(), kernel: next.kernel })
  }

  throw new ApiError(405, 'Method not allowed')
}
