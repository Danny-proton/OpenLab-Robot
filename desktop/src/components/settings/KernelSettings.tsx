import { useCallback, useEffect, useState } from 'react'
import { kernelApi, type KernelId, type KernelInfo } from '../../api/kernel'
import { useTranslation } from '../../i18n'
import type { TranslationKey } from '../../i18n/locales/en'

const KERNEL_OPTIONS: { id: KernelId; label: string; descKey: TranslationKey }[] = [
  { id: 'cc-haha', label: 'cc-haha', descKey: 'settings.kernel.ccHahaDesc' },
  { id: 'jiuwen-agent-core', label: 'jiuwen-Agent-core', descKey: 'settings.kernel.jiuwenDesc' },
]

export function KernelSettings() {
  const t = useTranslation()
  const [info, setInfo] = useState<KernelInfo | null>(null)
  const [configDirDraft, setConfigDirDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await kernelApi.get()
      setInfo(data)
      setConfigDirDraft(data.configDir ?? '')
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const save = async (update: { kernel?: KernelId; configDir?: string }) => {
    setSaving(true)
    setMessage(null)
    try {
      const data = await kernelApi.update(update)
      setInfo(data)
      setConfigDirDraft(data.configDir ?? '')
      setMessage(t('settings.kernel.saved'))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  if (!info) {
    return <div className="text-sm text-[var(--color-text-secondary)]">{message ?? t('settings.kernel.loading')}</div>
  }

  return (
    <div className="max-w-2xl flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">{t('settings.kernel.title')}</h2>
        <p className="text-sm text-[var(--color-text-secondary)]">{t('settings.kernel.subtitle')}</p>
      </div>

      <div className="flex flex-col gap-3">
        {KERNEL_OPTIONS.map((option) => {
          const active = info.kernel === option.id
          return (
            <button
              key={option.id}
              disabled={saving}
              onClick={() => void save({ kernel: option.id })}
              className={`text-left rounded-lg border px-4 py-3 transition-colors ${
                active
                  ? 'border-[var(--color-accent)] bg-[var(--color-surface-selected)]'
                  : 'border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${active ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-border)]'}`} />
                <span className="text-sm font-medium text-[var(--color-text-primary)]">{option.label}</span>
                {active && <span className="text-xs text-[var(--color-accent)]">{t('settings.kernel.active')}</span>}
              </div>
              <div className="text-xs text-[var(--color-text-secondary)] mt-1 ml-5">{t(option.descKey)}</div>
            </button>
          )
        })}
      </div>

      <div className="rounded-lg border border-[var(--color-border)] px-4 py-3 flex flex-col gap-2">
        <div className="text-sm font-medium text-[var(--color-text-primary)]">{t('settings.kernel.configDirTitle')}</div>
        <div className="text-xs text-[var(--color-text-secondary)]">
          {t('settings.kernel.configDirHint', { dir: info.defaultConfigDir })}
        </div>
        <div className="flex gap-2 mt-1">
          <input
            value={configDirDraft}
            onChange={(e) => setConfigDirDraft(e.target.value)}
            placeholder={info.defaultConfigDir}
            className="flex-1 rounded-md border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--color-text-primary)]"
          />
          <button
            disabled={saving}
            onClick={() => void save({ configDir: configDirDraft })}
            className="rounded-md bg-[var(--color-accent)] px-3 py-1.5 text-sm text-white disabled:opacity-50"
          >
            {t('settings.kernel.save')}
          </button>
        </div>
        <div className="text-xs text-[var(--color-text-secondary)]">
          {t('settings.kernel.effectiveDir', { dir: info.effectiveConfigDir })}
        </div>
      </div>

      {info.kernel === 'jiuwen-agent-core' && (
        <div className="rounded-lg border border-[var(--color-warning,#d97706)]/50 bg-[var(--color-warning,#d97706)]/10 px-4 py-3 text-sm text-[var(--color-text-primary)]">
          {t('settings.kernel.jiuwenLaunchHint')}
          <code className="ml-1 rounded bg-[var(--color-surface-selected)] px-1.5 py-0.5 text-xs">jiuwen</code>
        </div>
      )}

      {message && <div className="text-sm text-[var(--color-text-secondary)]">{message}</div>}
    </div>
  )
}
