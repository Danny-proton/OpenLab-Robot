import { api } from './client'

export type PinnedSkill = {
  name: string
  source?: string
  alias?: string
  group?: string
}

export type SkillPrefs = {
  pinned: PinnedSkill[]
  defaultPrefixSkill?: string
}

export const skillPrefsApi = {
  get() {
    return api.get<SkillPrefs>('/api/skill-prefs')
  },

  update(update: Partial<SkillPrefs>) {
    return api.put<{ ok: true } & SkillPrefs>('/api/skill-prefs', update)
  },
}
