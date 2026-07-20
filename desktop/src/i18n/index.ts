import { useCallback } from 'react'
import { useSettingsStore } from '../stores/settingsStore'
import { useBrandStore, applyBrand } from '../stores/brandStore'
import { en, type TranslationKey } from './locales/en'
import { zh } from './locales/zh'
import { zh as zhTW } from './locales/zh-TW'
import { jp } from './locales/jp'
import { kr } from './locales/kr'

export type Locale = 'en' | 'zh' | 'zh-TW' | 'jp' | 'kr'

const translations: Record<Locale, Record<string, string>> = {
  en,
  zh,
  'zh-TW': zhTW,
  jp,
  kr,
}

/**
 * Translate a key with optional interpolation params.
 * Falls back to the key itself if no translation is found.
 *
 * @example
 * translate('en', 'settings.providers.connected', { latency: '42' })
 * // => "Connected (42ms)"
 */
export function translate(
  locale: Locale,
  key: TranslationKey,
  params?: Record<string, string | number>,
): string {
  let text = translations[locale]?.[key] ?? translations.en[key] ?? key
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v))
    }
  }
  // Openlab Robot 品牌定制：翻译结果统一经过品牌替换引擎
  return applyBrand(text)
}

/**
 * React hook that returns a `t()` function bound to the current locale.
 * Re-renders when the locale changes.
 *
 * @example
 * const t = useTranslation()
 * t('sidebar.newSession')  // => "New session" or "新建会话"
 */
export function useTranslation() {
  const locale = useSettingsStore((s) => s.locale)
  // 订阅品牌定制变化，appName/agentName 更新后所有文案自动刷新
  const appName = useBrandStore((s) => s.appName)
  const agentName = useBrandStore((s) => s.agentName)
  return useCallback(
    (key: TranslationKey, params?: Record<string, string | number>) =>
      translate(locale, key, params),
    [locale, appName, agentName],
  )
}

/**
 * Get a translation outside of React (e.g. in stores).
 * Reads the current locale from the Zustand store directly.
 */
export function t(key: TranslationKey, params?: Record<string, string | number>): string {
  const locale = useSettingsStore.getState().locale
  return translate(locale, key, params)
}

export type { TranslationKey }
