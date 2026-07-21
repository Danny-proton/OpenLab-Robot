import { create } from 'zustand'
import { skillPrefsApi, type PinnedSkill } from '../api/skillPrefs'

export type { PinnedSkill }

/** 输入框中已置入（待发送）的技能气泡 */
export type ComposerSkill = {
  name: string
  source?: string
  alias?: string
}

type SkillPrefsStore = {
  pinned: PinnedSkill[]
  defaultPrefixSkill?: string
  loaded: boolean

  fetchPrefs: () => Promise<void>
  savePinned: (pinned: PinnedSkill[]) => Promise<void>
  setDefaultPrefixSkill: (name?: string) => Promise<void>
  togglePinned: (skill: PinnedSkill) => Promise<void>
  setAlias: (name: string, alias?: string) => Promise<void>
}

export const useSkillPrefsStore = create<SkillPrefsStore>((set, get) => ({
  pinned: [],
  loaded: false,

  fetchPrefs: async () => {
    try {
      const prefs = await skillPrefsApi.get()
      set({ pinned: prefs.pinned, defaultPrefixSkill: prefs.defaultPrefixSkill, loaded: true })
    } catch {
      set({ loaded: true })
    }
  },

  savePinned: async (pinned) => {
    const prev = get().pinned
    set({ pinned }) // 乐观更新
    try {
      const saved = await skillPrefsApi.update({ pinned })
      set({ pinned: saved.pinned })
    } catch {
      set({ pinned: prev }) // 失败回滚
    }
  },

  setDefaultPrefixSkill: async (name) => {
    set({ defaultPrefixSkill: name })
    try {
      await skillPrefsApi.update({ defaultPrefixSkill: name ?? '' })
    } catch { /* 保持本地状态 */ }
  },

  togglePinned: async (skill) => {
    const pinned = get().pinned
    const exists = pinned.some((p) => p.name === skill.name)
    const next = exists ? pinned.filter((p) => p.name !== skill.name) : [...pinned, skill]
    await get().savePinned(next)
  },

  setAlias: async (name, alias) => {
    const next = get().pinned.map((p) => (p.name === name ? { ...p, alias } : p))
    await get().savePinned(next)
  },
}))
