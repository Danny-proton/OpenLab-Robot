import { create } from 'zustand'
import { skinApi, type SkinInfo } from '../api/skin'

/**
 * 皮肤定制：预设皮肤 / 自定义强调色。
 * 皮肤以 inline CSS 变量形式覆盖到 :root（叠加在基础主题 white/light/dark 之上），
 * 即时生效并持久化到服务端（~/.openlab-robot/skin.json）。
 * 构建期默认值：openlab.defaults.json 的 skin 段。
 */

export type SkinPreset = {
  id: string
  labelKey: string
  /** 浅色主题下的强调色 */
  light: string
  /** 深色主题下的强调色 */
  dark: string
}

export const SKIN_PRESETS: SkinPreset[] = [
  { id: 'default', labelKey: 'settings.skin.presetDefault', light: '#8F482F', dark: '#FFB59F' },
  { id: 'ocean', labelKey: 'settings.skin.presetOcean', light: '#2563EB', dark: '#7DB4FF' },
  { id: 'forest', labelKey: 'settings.skin.presetForest', light: '#0F7B4D', dark: '#6FD9A6' },
  { id: 'violet', labelKey: 'settings.skin.presetViolet', light: '#7C3AED', dark: '#C4A8FF' },
  { id: 'rose', labelKey: 'settings.skin.presetRose', light: '#DB2777', dark: '#FF9FC6' },
  { id: 'amber', labelKey: 'settings.skin.presetAmber', light: '#B45309', dark: '#FFC97D' },
  { id: 'custom', labelKey: 'settings.skin.presetCustom', light: '', dark: '' },
]

/** 由强调色派生按钮渐变/容器色等配套变量 */
function derivePalette(accent: string, isDark: boolean): Record<string, string> {
  return isDark
    ? {
        '--color-primary': accent,
        '--color-brand': accent,
        '--color-on-primary': '#1A1C1A',
        '--color-primary-container': accent,
        '--color-on-primary-container': '#1A1C1A',
        '--color-primary-fixed': accent,
        '--color-primary-fixed-dim': accent,
        '--color-btn-primary-fg': '#1A1C1A',
      }
    : {
        '--color-primary': accent,
        '--color-brand': accent,
        '--color-on-primary': '#FFFFFF',
        '--color-primary-container': accent,
        '--color-on-primary-container': '#FFFFFF',
        '--color-primary-fixed': accent,
        '--color-primary-fixed-dim': accent,
        '--color-btn-primary-fg': '#FFFFFF',
      }
}

const APPLIED_VARS = [
  '--color-primary',
  '--color-brand',
  '--color-on-primary',
  '--color-primary-container',
  '--color-on-primary-container',
  '--color-primary-fixed',
  '--color-primary-fixed-dim',
  '--color-btn-primary-fg',
]

export function clearSkin(): void {
  const style = document.documentElement.style
  for (const key of APPLIED_VARS) style.removeProperty(key)
}

export function applySkinAccent(accent: string, isDark: boolean): void {
  const style = document.documentElement.style
  const palette = derivePalette(accent, isDark)
  for (const [key, value] of Object.entries(palette)) {
    style.setProperty(key, value)
  }
}

type SkinStore = {
  preset?: string
  accentColor?: string
  loaded: boolean
  fetchSkin: () => Promise<void>
  saveSkin: (update: { preset?: string; accentColor?: string }) => Promise<void>
  /** 按当前主题重新应用皮肤（主题切换时调用） */
  applyCurrent: (theme: string) => void
}

export const useSkinStore = create<SkinStore>((set, get) => ({
  preset: undefined,
  accentColor: undefined,
  loaded: false,

  fetchSkin: async () => {
    try {
      const info: SkinInfo = await skinApi.get()
      set({ preset: info.preset, accentColor: info.accentColor, loaded: true })
    } catch {
      set({ loaded: true })
    }
  },

  saveSkin: async (update) => {
    const info = await skinApi.update(update)
    set({ preset: info.preset, accentColor: info.accentColor })
  },

  applyCurrent: (theme) => {
    const { preset, accentColor } = get()
    const isDark = theme === 'dark'
    const resolved = preset ?? 'default'
    if (resolved === 'default') {
      clearSkin()
      return
    }
    if (resolved === 'custom' && accentColor) {
      applySkinAccent(accentColor, isDark)
      return
    }
    const found = SKIN_PRESETS.find((p) => p.id === resolved)
    if (found && found.id !== 'custom') {
      applySkinAccent(isDark ? found.dark : found.light, isDark)
      return
    }
    clearSkin()
  },
}))
