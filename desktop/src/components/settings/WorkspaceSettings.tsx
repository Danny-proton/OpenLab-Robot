import { useEffect, useState } from 'react'
import { workspaceApi, type WorkspaceInfo } from '../../api/workspace'
import { useTranslation } from '../../i18n'

/**
 * 新建会话默认工作区路径设置。
 */
export function WorkspaceSettings() {
  const t = useTranslation()
  const [info, setInfo] = useState<WorkspaceInfo | null>(null)
  const [draft, setDraft] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    workspaceApi.get()
      .then((data) => {
        setInfo(data)
        setDraft(data.defaultWorkspaceDir ?? '')
      })
      .catch(() => {})
  }, [])

  const save = async () => {
    setMessage(null)
    try {
      const data = await workspaceApi.update(draft)
      setInfo(data)
      setDraft(data.defaultWorkspaceDir ?? '')
      setMessage(t('settings.kernel.saved'))
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="mb-8">
      <h2 className="text-base font-semibold text-[var(--color-text-primary)] mb-1">{t('settings.workspace.title')}</h2>
      <p className="text-sm text-[var(--color-text-tertiary)] mb-3">{t('settings.workspace.description')}</p>
      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={info?.buildDefaultDir ?? t('settings.workspace.placeholder')}
          className="flex-1 rounded-md border border-[var(--color-border)] bg-transparent px-3 py-1.5 text-sm text-[var(--color-text-primary)]"
        />
        <button
          onClick={() => void save()}
          aria-label={t('settings.workspace.title')}
          className="rounded-md bg-[var(--color-accent,var(--color-brand))] px-3 py-1.5 text-sm text-white"
        >
          {t('settings.kernel.save')}
        </button>
      </div>
      {info && (
        <p className="mt-2 text-xs text-[var(--color-text-tertiary)]">
          {t('settings.workspace.effective', { dir: info.effectiveDefaultDir })}
        </p>
      )}
      {message && <p className="mt-1 text-xs text-[var(--color-text-secondary)]">{message}</p>}
    </div>
  )
}
