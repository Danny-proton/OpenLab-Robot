import { useEffect, useRef, useState } from 'react'
import { useTranslation } from '../../i18n'
import { chromeUseApi, type ChromeUseStatus, type DebugTarget } from '../../api/chromeUse'

type StreamState = 'idle' | 'connecting' | 'streaming' | 'error'

function StatusRow({ ok, label, detail }: { ok: boolean; label: string; detail?: string }) {
  return (
    <div className="flex items-center gap-2 py-1.5 text-sm">
      <span
        className={`material-symbols-outlined text-[18px] ${
          ok ? 'text-[var(--color-success,#0F7B4D)]' : 'text-[var(--color-error)]'
        }`}
      >
        {ok ? 'check_circle' : 'cancel'}
      </span>
      <span className="text-[var(--color-text-primary)]">{label}</span>
      {detail && <span className="text-xs text-[var(--color-text-tertiary)]">{detail}</span>}
    </div>
  )
}

/** Chrome use 设置页：环境检查 + 调试 Chrome 画面 CDP 串流 */
export function ChromeUseSettings() {
  const t = useTranslation()
  const [status, setStatus] = useState<ChromeUseStatus | null>(null)
  const [checking, setChecking] = useState(false)
  const [targets, setTargets] = useState<DebugTarget[]>([])
  const [selectedTarget, setSelectedTarget] = useState<string>('')
  const [streamState, setStreamState] = useState<StreamState>('idle')
  const [frame, setFrame] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const sessionIdRef = useRef<string | null>(null)

  const recheck = () => {
    setChecking(true)
    void chromeUseApi
      .status()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setChecking(false))
    void chromeUseApi
      .targets()
      .then((res) => {
        const pages = res.targets.filter((target) => target.type === 'page')
        setTargets(pages)
        setSelectedTarget((prev) => prev || (pages[0]?.id ?? ''))
      })
      .catch(() => setTargets([]))
  }

  useEffect(() => {
    recheck()
    return () => stopStream()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const sendCdp = (method: string, params: Record<string, unknown> = {}) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN || !sessionIdRef.current) return
    ws.send(JSON.stringify({ id: Date.now(), sessionId: sessionIdRef.current, method, params }))
  }

  const connectTarget = (target: DebugTarget) => {
    if (!target.webSocketDebuggerUrl) {
      setStreamState('error')
      return
    }
    stopStream()
    setStreamState('connecting')
    const ws = new WebSocket(target.webSocketDebuggerUrl)
    wsRef.current = ws
    ws.onopen = () => {
      // 浏览器级 WS：用 Target.attachToTarget 建立会话
      ws.send(
        JSON.stringify({
          id: 1,
          method: 'Target.attachToTarget',
          params: { targetId: target.id, flatten: true },
        }),
      )
    }
    ws.onmessage = (event) => {
      let msg: {
        id?: number
        method?: string
        params?: { sessionId?: string; data?: string }
        result?: { sessionId?: string }
      }
      try {
        msg = JSON.parse(String(event.data))
      } catch {
        return
      }
      if (msg.id === 1 && msg.result?.sessionId) {
        sessionIdRef.current = msg.result.sessionId
        sendCdp('Page.enable')
        sendCdp('Page.startScreencast', { format: 'jpeg', quality: 60, maxWidth: 1280, maxHeight: 800 })
        setStreamState('streaming')
        return
      }
      if (msg.method === 'Page.screencastFrame' && msg.params?.data) {
        setFrame(`data:image/jpeg;base64,${msg.params.data}`)
        const frameSessionId = (msg.params as { sessionId?: unknown }).sessionId
        sendCdp('Page.screencastFrameAck', { sessionId: frameSessionId })
      }
    }
    ws.onerror = () => setStreamState('error')
    ws.onclose = () => {
      setStreamState((prev) => (prev === 'streaming' || prev === 'connecting' ? 'idle' : prev))
    }
  }

  const stopStream = () => {
    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) sendCdp('Page.stopScreencast')
      wsRef.current.close()
      wsRef.current = null
    }
    sessionIdRef.current = null
    setFrame(null)
    setStreamState('idle')
  }

  const startStream = () => {
    const target = targets.find((item) => item.id === selectedTarget)
    if (target) {
      connectTarget(target)
      return
    }
    // 无目标时尝试启动调试 Chrome 后重连
    void chromeUseApi
      .launch()
      .then(() => new Promise((resolve) => setTimeout(resolve, 1500)))
      .then(() => chromeUseApi.targets())
      .then((res) => {
        const pages = res.targets.filter((item) => item.type === 'page')
        setTargets(pages)
        const first = pages[0]
        if (!first) {
          setStreamState('error')
          return
        }
        setSelectedTarget(first.id)
        connectTarget(first)
      })
      .catch(() => setStreamState('error'))
  }

  const streamStatusText =
    streamState === 'idle'
      ? t('chromeUse.streamIdle')
      : streamState === 'connecting'
        ? t('chromeUse.streamConnecting')
        : streamState === 'error'
          ? t('chromeUse.streamError')
          : null

  return (
    <div className="max-w-3xl">
      <h1 className="text-lg font-semibold text-[var(--color-text-primary)] mb-1">{t('chromeUse.title')}</h1>
      <p className="text-sm text-[var(--color-text-tertiary)] mb-6">{t('chromeUse.subtitle')}</p>

      {/* 环境检查 */}
      <div className="mb-6 rounded-xl border border-[var(--color-border)] p-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm font-medium text-[var(--color-text-primary)]">{t('chromeUse.checks')}</div>
          <button
            onClick={recheck}
            disabled={checking}
            className="rounded-md border border-[var(--color-border)] px-2.5 py-1 text-xs hover:bg-[var(--color-surface-hover)] disabled:opacity-40"
          >
            {checking ? t('chromeUse.checking') : t('chromeUse.recheck')}
          </button>
        </div>
        <StatusRow ok={status?.mcpInstalled ?? false} label="chrome-devtools MCP" />
        <StatusRow
          ok={status?.chromeVersionOk ?? false}
          label={t('chromeUse.chromeVersion')}
          detail={
            status?.chromeVersion
              ? status.chromeVersionOk
                ? status.chromeVersion
                : `${status.chromeVersion} — ${t('chromeUse.versionTooOld')}`
              : t('chromeUse.chromeMissing')
          }
        />
        <StatusRow
          ok={status?.remoteDebugging ?? false}
          label={t('chromeUse.remoteDebugging')}
          detail={status ? `127.0.0.1:${status.debugPort}` : undefined}
        />
        {status && !status.remoteDebugging && status.chromeVersionOk && (
          <button
            onClick={() => void chromeUseApi.launch().then(() => setTimeout(recheck, 1500))}
            className="mt-2 rounded-lg bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-[var(--color-on-primary)]"
          >
            {t('chromeUse.launch')}
          </button>
        )}
      </div>

      {/* 画面串流 */}
      <div className="rounded-xl border border-[var(--color-border)] p-4">
        <div className="mb-3 flex items-center gap-2">
          <div className="flex-1 text-sm font-medium text-[var(--color-text-primary)]">
            {t('chromeUse.stream')}
          </div>
          {targets.length > 0 && (
            <select
              value={selectedTarget}
              onChange={(e) => setSelectedTarget(e.target.value)}
              aria-label={t('chromeUse.pickTarget')}
              className="max-w-[280px] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-xs outline-none"
            >
              {targets.map((target) => (
                <option key={target.id} value={target.id}>
                  {target.title || target.url}
                </option>
              ))}
            </select>
          )}
          {streamState === 'streaming' ? (
            <button
              onClick={stopStream}
              className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs hover:bg-[var(--color-surface-hover)]"
            >
              {t('chromeUse.streamStop')}
            </button>
          ) : (
            <button
              onClick={startStream}
              disabled={streamState === 'connecting'}
              className="rounded-lg bg-[var(--color-primary)] px-3 py-1.5 text-xs font-medium text-[var(--color-on-primary)] disabled:opacity-40"
            >
              {t('chromeUse.streamStart')}
            </button>
          )}
        </div>
        <div className="flex aspect-[8/5] items-center justify-center overflow-hidden rounded-lg bg-black">
          {frame ? (
            <img src={frame} alt={t('chromeUse.stream')} className="h-full w-full object-contain" />
          ) : (
            <div className="px-6 text-center text-xs text-white/60">
              {streamStatusText ?? t('chromeUse.streamHint')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
