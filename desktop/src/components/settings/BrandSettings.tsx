import { useEffect, useState } from 'react'
import { useBrandStore } from '../../stores/brandStore'
import { useTranslation } from '../../i18n'

/**
 * 品牌定制：应用名称 / 智能体名称 / 对话框占位提示 / 系统提示词。
 * 保存后界面各处文案实时跟随（例如 agentName 改为「金融智能体」）。
 */
export function BrandSettings() {
  const t = useTranslation()
  const { appName, agentName, chatPlaceholder, systemPromptOverride, loaded, fetchBrand, saveBrand } = useBrandStore()

  const [appNameDraft, setAppNameDraft] = useState('')
  const [agentNameDraft, setAgentNameDraft] = useState('')
  const [placeholderDraft, setPlaceholderDraft] = useState('')
  const [promptDraft, setPromptDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!loaded) void fetchBrand()
  }, [loaded, fetchBrand])

  useEffect(() => {
    setAppNameDraft(appName)
    setAgentNameDraft(agentName)
    setPlaceholderDraft(chatPlaceholder ?? '')
    setPromptDraft(systemPromptOverride ?? '')
  }, [appName, agentName, chatPlaceholder, systemPromptOverride])

  const saveAll = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await saveBrand({
        appName: appNameDraft,
        agentName: agentNameDraft,
        chatPlaceholder: placeholderDraft,
        systemPromptOverride: promptDraft,
      })
      setMessage(t('settings.brand.saved'))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">{t('settings.brand.title')}</h2>
        <p className="text-sm text-[var(--color-text-secondary)]">{t('settings.brand.subtitle')}</p>
      </div>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-[var(--color-text-primary)]">{t('settings.brand.appName')}</span>
        <span className="text-xs text-[var(--color-text-secondary)]">{t('settings.brand.appNameHint')}</span>
        <input
          value={appNameDraft}
          onChange={(e) => setAppNameDraft(e.target.value)}
          placeholder="Openlab Robot"
          className="rounded-md border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--color-text-primary)]"
        />
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-[var(--color-text-primary)]">{t('settings.brand.agentName')}</span>
        <span className="text-xs text-[var(--color-text-secondary)]">{t('settings.brand.agentNameHint')}</span>
        <input
          value={agentNameDraft}
          onChange={(e) => setAgentNameDraft(e.target.value)}
          placeholder={t('settings.brand.agentNamePlaceholder')}
          className="rounded-md border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--color-text-primary)]"
        />
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-[var(--color-text-primary)]">{t('settings.brand.chatPlaceholder')}</span>
        <span className="text-xs text-[var(--color-text-secondary)]">{t('settings.brand.chatPlaceholderHint')}</span>
        <input
          value={placeholderDraft}
          onChange={(e) => setPlaceholderDraft(e.target.value)}
          placeholder={t('settings.brand.chatPlaceholderDefault')}
          className="rounded-md border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--color-text-primary)]"
        />
      </label>

      <label className="flex flex-col gap-1.5">
        <span className="text-sm font-medium text-[var(--color-text-primary)]">{t('settings.brand.systemPrompt')}</span>
        <span className="text-xs text-[var(--color-text-secondary)]">{t('settings.brand.systemPromptHint')}</span>
        <textarea
          value={promptDraft}
          onChange={(e) => setPromptDraft(e.target.value)}
          placeholder="You are Openlab Robot, an AI coding assistant."
          rows={4}
          className="rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm text-[var(--color-text-primary)] font-mono"
        />
      </label>

      <div className="flex items-center gap-3">
        <button
          disabled={saving}
          onClick={() => void saveAll()}
          className="rounded-md bg-[var(--color-accent)] px-4 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {t('settings.kernel.save')}
        </button>
        {message && <span className="text-sm text-[var(--color-text-secondary)]">{message}</span>}
      </div>
    </div>
  )
}
