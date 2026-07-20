import { AppShell } from './components/layout/AppShell'
import { FirstRunModelModal } from './components/onboarding/FirstRunModelModal'
import { useBrandStore } from './stores/brandStore'
import { useScheduledTaskDesktopNotifications } from './hooks/useScheduledTaskDesktopNotifications'
import { installDesktopNotificationNavigation } from './lib/desktopNotificationNavigation'
import { useEffect } from 'react'

export function App() {
  useScheduledTaskDesktopNotifications()
  // 启动时加载品牌定制（appName / agentName 驱动全局文案替换）
  useEffect(() => {
    void useBrandStore.getState().fetchBrand()
  }, [])
  useEffect(() => {
    let cleanup: (() => void) | undefined
    let cancelled = false
    installDesktopNotificationNavigation()
      .then((fn) => {
        if (cancelled) {
          fn()
        } else {
          cleanup = fn
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
      cleanup?.()
    }
  }, [])
  return (
    <>
      <AppShell />
      <FirstRunModelModal />
    </>
  )
}
