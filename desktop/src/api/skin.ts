import { api } from './client'

export type SkinInfo = {
  preset?: string
  accentColor?: string
  theme?: string
  buildDefaults?: { preset?: string; accentColor?: string; theme?: string }
  skinFile: string
}

export const skinApi = {
  get() {
    return api.get<SkinInfo>('/api/skin')
  },

  update(update: { preset?: string; accentColor?: string; theme?: string }) {
    return api.put<{ ok: true } & SkinInfo>('/api/skin', update)
  },
}
