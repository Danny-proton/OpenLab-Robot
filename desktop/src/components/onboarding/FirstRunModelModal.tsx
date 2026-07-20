import { useEffect, useState } from 'react'
import { useProviderStore } from '../../stores/providerStore'
import { useUIStore } from '../../stores/uiStore'
import { useTranslation } from '../../i18n'
import { Modal } from '../shared/Modal'

const DISMISS_KEY = 'openlab-model-setup-dismissed'

/**
 * Openlab Robot 首次使用引导：
 * 软件不内置默认模型，首次启动（无任何自定义大模型配置且未跳过）时
 * 弹出提示，引导用户前往「设置 → 大模型」配置 custom 模型。
 */
export function FirstRunModelModal() {
  const t = useTranslation()
  const providers = useProviderStore((s) => s.providers)
  const hasLoadedProviders = useProviderStore((s) => s.hasLoadedProviders)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!hasLoadedProviders) return
    let dismissed = false
    try {
      dismissed = localStorage.getItem(DISMISS_KEY) === '1'
    } catch { /* localStorage unavailable */ }
    if (!dismissed && providers.length === 0) {
      setVisible(true)
    }
  }, [hasLoadedProviders, providers.length])

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, '1')
    } catch { /* localStorage unavailable */ }
    setVisible(false)
  }

  const goConfigure = () => {
    dismiss()
    useUIStore.getState().setPendingSettingsTab('providers')
  }

  return (
    <Modal
      open={visible}
      onClose={dismiss}
      title={t('settings.firstRun.title')}
      width={480}
      footer={
        <div className="flex justify-end gap-2">
          <button
            onClick={dismiss}
            className="rounded-md px-3 py-1.5 text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]"
          >
            {t('settings.firstRun.dismiss')}
          </button>
          <button
            onClick={goConfigure}
            className="rounded-md bg-[var(--color-accent)] px-3 py-1.5 text-sm text-white"
          >
            {t('settings.firstRun.action')}
          </button>
        </div>
      }
    >
      <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
        {t('settings.firstRun.body')}
      </p>
    </Modal>
  )
}
