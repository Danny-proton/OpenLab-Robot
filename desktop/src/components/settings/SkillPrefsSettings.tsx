import { useEffect } from 'react'
import { useTranslation } from '../../i18n'
import { useSkillPrefsStore } from '../../stores/skillPrefsStore'

/**
 * 输入框技能偏好：默认输入前缀技能 + 常驻技能默认值配置。
 */
export function SkillPrefsSettings() {
  const t = useTranslation()
  const pinned = useSkillPrefsStore((s) => s.pinned)
  const defaultPrefixSkill = useSkillPrefsStore((s) => s.defaultPrefixSkill)
  const loaded = useSkillPrefsStore((s) => s.loaded)
  const fetchPrefs = useSkillPrefsStore((s) => s.fetchPrefs)
  const setDefaultPrefixSkill = useSkillPrefsStore((s) => s.setDefaultPrefixSkill)
  const togglePinned = useSkillPrefsStore((s) => s.togglePinned)

  useEffect(() => {
    if (!loaded) void fetchPrefs()
  }, [loaded, fetchPrefs])

  return (
    <div className="mb-8">
      <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-1">
        {t('skills.prefs.title')}
      </h2>
      <p className="text-sm text-[var(--color-text-tertiary)] mb-3">{t('skills.prefs.description')}</p>

      <div className="mb-4">
        <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1.5">
          {t('skills.prefs.prefixSkill')}
        </label>
        <select
          value={defaultPrefixSkill ?? ''}
          onChange={(e) => void setDefaultPrefixSkill(e.target.value || undefined)}
          className="w-full max-w-xs rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
        >
          <option value="">{t('skills.prefs.prefixNone')}</option>
          {pinned.map((skill) => (
            <option key={skill.name} value={skill.name}>
              /{skill.alias ?? skill.name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-[var(--color-text-tertiary)]">{t('skills.prefs.prefixHint')}</p>
      </div>

      {pinned.length > 0 && (
        <div>
          <div className="text-sm font-medium text-[var(--color-text-primary)] mb-1.5">
            {t('skills.prefs.pinnedLabel')}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {pinned.map((skill) => (
              <button
                key={skill.name}
                onClick={() => void togglePinned(skill)}
                title={`/${skill.name}`}
                className="flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-hover)] px-2.5 py-1 text-xs text-[var(--color-text-secondary)] hover:border-[var(--color-primary)]"
              >
                <span className="material-symbols-outlined text-[13px]">keep</span>
                {skill.alias ?? skill.name}
                <span className="material-symbols-outlined text-[13px] text-[var(--color-text-tertiary)]">close</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
