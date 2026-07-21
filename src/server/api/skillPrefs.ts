/**
 * Skill Prefs REST API — Openlab Robot 输入框技能偏好
 *
 * GET /api/skill-prefs — 获取常驻技能与默认前缀技能
 * PUT /api/skill-prefs — 更新 { pinned?, defaultPrefixSkill? }
 */

import { ApiError } from '../middleware/errorHandler.js'
import { getSkillPrefs, setSkillPrefs, type PinnedSkill } from '../services/skillPrefsService.js'

export async function handleSkillPrefsApi(
  req: Request,
  _url: URL,
  segments: string[],
): Promise<Response> {
  if (segments[2] !== undefined) throw new ApiError(404, 'Not found')

  if (req.method === 'GET') {
    return Response.json(getSkillPrefs())
  }

  if (req.method === 'PUT') {
    const body = (await req.json().catch(() => ({}))) as {
      pinned?: PinnedSkill[]
      defaultPrefixSkill?: string
    }
    const prefs = setSkillPrefs(body)
    return Response.json({ ok: true, ...prefs })
  }

  throw new ApiError(405, 'Method not allowed')
}
