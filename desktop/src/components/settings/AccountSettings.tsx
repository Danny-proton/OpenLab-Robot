import { useEffect, useState } from 'react'
import { useTranslation } from '../../i18n'
import { useAuthStore } from '../../stores/authStore'
import { syncApi, type SyncRecord, type SyncScope, type SyncState } from '../../api/sync'

const SYNC_SCOPES: Array<{ id: SyncScope; labelKey: string }> = [
  { id: 'agentConfig', labelKey: 'account.sync.scopeAgent' },
  { id: 'skill', labelKey: 'account.sync.scopeSkill' },
  { id: 'sessionHistory', labelKey: 'account.sync.scopeSession' },
  { id: 'memory', labelKey: 'account.sync.scopeMemory' },
]

/** 账户页：登录（mock）+ 云同步（mock） */
export function AccountSettings() {
  const t = useTranslation()
  const {
    enabled,
    loggedIn,
    username,
    tokenMask,
    loggedInAt,
    features,
    loaded,
    busy,
    error,
    fetchState,
    login,
    logout,
    setFeatures,
  } = useAuthStore()

  const [usernameDraft, setUsernameDraft] = useState('')
  const [passwordDraft, setPasswordDraft] = useState('')
  const [syncState, setSyncState] = useState<SyncState | null>(null)
  const [syncBusy, setSyncBusy] = useState<string | null>(null)

  useEffect(() => {
    if (!loaded) void fetchState()
  }, [loaded, fetchState])

  useEffect(() => {
    if (loggedIn) void syncApi.get().then(setSyncState).catch(() => setSyncState(null))
  }, [loggedIn])

  const refreshSync = () => {
    void syncApi.get().then(setSyncState).catch(() => undefined)
  }

  const toggleScope = (scope: SyncScope) => {
    if (!syncState) return
    const next = syncState.scopes.includes(scope)
      ? syncState.scopes.filter((s) => s !== scope)
      : [...syncState.scopes, scope]
    void syncApi.setScopes(next).then(setSyncState).catch(() => undefined)
  }

  const doSync = (direction: 'upload' | 'download', scope: SyncScope) => {
    const key = `${direction}:${scope}`
    setSyncBusy(key)
    const run = direction === 'upload' ? syncApi.upload(scope) : syncApi.download(scope)
    void run
      .catch(() => undefined)
      .finally(() => {
        setSyncBusy(null)
        refreshSync()
      })
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">{t('account.title')}</h1>
      <p className="text-sm text-[var(--color-text-tertiary)] mb-6">{t('account.subtitle')}</p>

      {/* 功能开关 */}
      <div className="mb-6">
        <div className="text-sm font-medium text-[var(--color-text-primary)] mb-2">{t('account.features')}</div>
        {([
          { key: 'auth' as const, labelKey: 'account.featureAuth' },
          { key: 'cloudSync' as const, labelKey: 'account.featureSync' },
        ]).map(({ key, labelKey }) => (
          <label key={key} className="mb-1.5 flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
            <input
              type="checkbox"
              checked={features[key]}
              onChange={(e) => void setFeatures({ [key]: e.target.checked })}
              className="accent-[var(--color-primary)]"
            />
            {t(labelKey as never)}
          </label>
        ))}
      </div>

      {enabled && (
        <div className="mb-6 rounded-xl border border-[var(--color-border)] p-4">
          <div className="text-sm font-medium text-[var(--color-text-primary)] mb-3">
            {t('account.loginTitle')}
          </div>
          {loggedIn ? (
            <div className="flex flex-col gap-2 text-sm text-[var(--color-text-secondary)]">
              <div>{username}</div>
              {tokenMask && <div className="font-mono text-xs text-[var(--color-text-tertiary)]">{tokenMask}</div>}
              {loggedInAt && (
                <div className="text-xs text-[var(--color-text-tertiary)]">
                  {t('account.loggedAt')}: {new Date(loggedInAt).toLocaleString()}
                </div>
              )}
              <button
                onClick={() => void logout()}
                disabled={busy}
                className="mt-1 w-fit rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-sm hover:bg-[var(--color-surface-hover)]"
              >
                {t('account.logout')}
              </button>
            </div>
          ) : (
            <form
              className="flex flex-col gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                void login(usernameDraft, passwordDraft).then((ok) => {
                  if (ok) {
                    setUsernameDraft('')
                    setPasswordDraft('')
                  }
                })
              }}
            >
              <input
                value={usernameDraft}
                onChange={(e) => setUsernameDraft(e.target.value)}
                placeholder={t('account.username')}
                autoComplete="username"
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
              />
              <input
                type="password"
                value={passwordDraft}
                onChange={(e) => setPasswordDraft(e.target.value)}
                placeholder={t('account.password')}
                autoComplete="current-password"
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)]"
              />
              {error && <div className="text-xs text-[var(--color-error)]">{error}</div>}
              <button
                type="submit"
                disabled={busy || !usernameDraft.trim() || !passwordDraft}
                className="w-fit rounded-lg bg-[var(--color-primary)] px-4 py-1.5 text-sm font-medium text-[var(--color-on-primary)] disabled:opacity-40"
              >
                {t('account.login')}
              </button>
            </form>
          )}
        </div>
      )}

      {/* 云同步 */}
      {enabled && features.cloudSync && (
        <div className="rounded-xl border border-[var(--color-border)] p-4">
          <div className="text-sm font-medium text-[var(--color-text-primary)] mb-3">
            {t('account.sync.title')}
          </div>
          {!loggedIn ? (
            <div className="text-sm text-[var(--color-text-tertiary)]">{t('account.sync.loginFirst')}</div>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                {SYNC_SCOPES.map(({ id, labelKey }) => (
                  <div key={id} className="flex items-center gap-3">
                    <label className="flex flex-1 items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                      <input
                        type="checkbox"
                        checked={syncState?.scopes.includes(id) ?? false}
                        onChange={() => toggleScope(id)}
                        className="accent-[var(--color-primary)]"
                      />
                      {t(labelKey as never)}
                    </label>
                    <button
                      onClick={() => doSync('upload', id)}
                      disabled={syncBusy !== null}
                      className="rounded-md border border-[var(--color-border)] px-2.5 py-1 text-xs hover:bg-[var(--color-surface-hover)] disabled:opacity-40"
                    >
                      {syncBusy === `upload:${id}` ? '…' : t('account.sync.upload')}
                    </button>
                    <button
                      onClick={() => doSync('download', id)}
                      disabled={syncBusy !== null}
                      className="rounded-md border border-[var(--color-border)] px-2.5 py-1 text-xs hover:bg-[var(--color-surface-hover)] disabled:opacity-40"
                    >
                      {syncBusy === `download:${id}` ? '…' : t('account.sync.download')}
                    </button>
                  </div>
                ))}
              </div>

              {syncState && syncState.history.length > 0 && (
                <div className="mt-4">
                  <div className="text-xs font-medium text-[var(--color-text-tertiary)] mb-1.5">
                    {t('account.sync.history')}
                  </div>
                  <div className="max-h-40 overflow-y-auto rounded-lg border border-[var(--color-border)]">
                    {syncState.history.map((record: SyncRecord) => (
                      <div
                        key={record.id}
                        className="flex items-center gap-2 border-b border-[var(--color-border)] px-3 py-1.5 text-xs text-[var(--color-text-tertiary)] last:border-b-0"
                      >
                        <span className="material-symbols-outlined text-[14px]">
                          {record.direction === 'upload' ? 'upload' : 'download'}
                        </span>
                        <span className="text-[var(--color-text-secondary)]">{record.scope}</span>
                        <span className="ml-auto">{new Date(record.at).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
