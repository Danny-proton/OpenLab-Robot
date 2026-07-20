import { useEffect, useState } from 'react'
import { useSkinStore, SKIN_PRESETS } from '../../stores/skinStore'
import { useUIStore } from '../../stores/uiStore'
import { useTranslation } from '../../i18n'
import type { TranslationKey } from '../../i18n/locales/en'

/**
 * 皮肤定制：预设皮肤 + 自定义强调色，点击即时生效。
 */
export function SkinSettings() {
  const t = useTranslation()
  const theme = useUIStore((s) => s.theme)
  const { preset, accentColor, loaded, fetchSkin, saveSkin, applyCurrent } = useSkinStore()
  const [customColor, setCustomColor] = useState('#2563EB')

  useEffect(() => {
    if (!loaded) void fetchSkin()
  }, [loaded, fetchSkin])

  useEffect(() => {
    if (accentColor) setCustomColor(accentColor)
  }, [accentColor])

  const resolvedPreset = preset ?? 'default'

  const choose = async (presetId: string, color?: string) => {
    const update = presetId === 'custom'
      ? { preset: presetId, accentColor: color ?? customColor }
      : { preset: presetId }
    try {
      await saveSkin(update)
      applyCurrent(theme)
    } catch { /* 保存失败时保持现状 */ }
  }

  return (
    <div className="mb-8">
      <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-1">{t('settings.skin.title')}</h2>
      <p className="text-sm text-[var(--color-text-tertiary)] mb-3">{t('settings.skin.description')}</p>
      <div className="flex flex-wrap gap-2">
        {SKIN_PRESETS.map((p) => {
          const active = resolvedPreset === p.id
          const swatch = p.id === 'custom' ? customColor : (theme === 'dark' ? p.dark : p.light)
          return (
            <button
              key={p.id}
              onClick={() => void choose(p.id)}
              aria-pressed={active}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition-all ${
                active
                  ? 'border-[var(--color-brand)] bg-[var(--color-surface-selected)] text-[var(--color-text-primary)]'
                  : 'border-[var(--color-border)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'
              }`}
            >
              <span
                className="inline-block h-4 w-4 rounded-full border border-black/10"
                style={p.id === 'default'
                  ? { background: 'linear-gradient(135deg, #8F482F 50%, #FFB59F 50%)' }
                  : { backgroundColor: swatch }}
              />
              {t(p.labelKey as TranslationKey)}
            </button>
          )
        })}
      </div>

      {resolvedPreset === 'custom' && (
        <div className="mt-3 flex items-center gap-3">
          <input
            type="color"
            value={customColor}
            onChange={(e) => setCustomColor(e.target.value)}
            onBlur={() => void choose('custom', customColor)}
            className="h-8 w-12 cursor-pointer rounded border border-[var(--color-border)] bg-transparent"
            aria-label={t('settings.skin.customColor')}
          />
          <span className="text-xs text-[var(--color-text-secondary)]">{t('settings.skin.customColor')}</span>
          <code className="text-xs text-[var(--color-text-tertiary)]">{customColor}</code>
        </div>
      )}
    </div>
  )
}
