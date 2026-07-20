import { AppShell } from './components/layout/AppShell'
import { FirstRunModelModal } from './components/onboarding/FirstRunModelModal'
import { useBrandStore } from './stores/brandStore'
import { useSkinStore } from './stores/skinStore'
import { useUIStore } from './stores/uiStore'
import { useScheduledTaskDesktopNotifications } from './hooks/useScheduledTaskDesktopNotifications'
import { installDesktopNotificationNavigation } from './lib/desktopNotificationNavigation'
import { useEffect } from 'react'

export function App() {
  useScheduledTaskDesktopNotifications()
  // 启动时加载品牌定制（appName / agentName 驱动全局文案替换）
  useEffect(() => {
    void useBrandStore.getState().fetchBrand()
  }, [])
  // 启动时加载皮肤定制，并在主题切换时重新应用
  const theme = useUIStore((s) => s.theme)
  const skinLoaded = useSkinStore((s) => s.loaded)
  useEffect(() => {
    void useSkinStore.getState().fetchSkin()
  }, [])
  useEffect(() => {
    if (skinLoaded) useSkinStore.getState().applyCurrent(theme)
  }, [theme, skinLoaded])
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
