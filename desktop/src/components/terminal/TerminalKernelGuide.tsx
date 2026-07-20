import { useEffect, useState } from 'react'
import { kernelApi, type KernelInfo } from '../../api/kernel'

const STYLE_ID = 'terminal-kernel-guide-styles'

const CSS = `
@keyframes openlab-guide-border-flow {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
@keyframes openlab-guide-slide-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes openlab-guide-dot {
  0%, 80%, 100% { opacity: 0.25; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}
.openlab-kernel-guide {
  position: relative;
  border-radius: 10px;
  padding: 1px;
  background: linear-gradient(120deg, var(--color-accent, #7c5cff), #38bdf8, #34d399, var(--color-accent, #7c5cff));
  background-size: 300% 300%;
  animation: openlab-guide-border-flow 6s ease infinite, openlab-guide-slide-in 0.35s ease-out;
}
.openlab-kernel-guide-inner {
  border-radius: 9px;
  background: var(--color-surface, #fff);
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.openlab-kernel-guide-dot {
  width: 6px; height: 6px; border-radius: 9999px;
  background: var(--color-accent, #7c5cff);
  animation: openlab-guide-dot 1.2s ease-in-out infinite;
}
`

/**
 * 终端页内核引导：根据当前内核显示不同的使用提示，带流动边框动画。
 */
export function TerminalKernelGuide() {
  const [info, setInfo] = useState<KernelInfo | null>(null)

  useEffect(() => {
    if (typeof document !== 'undefined' && !document.getElementById(STYLE_ID)) {
      const style = document.createElement('style')
      style.id = STYLE_ID
      style.textContent = CSS
      document.head.appendChild(style)
    }
    kernelApi.get().then(setInfo).catch(() => {})
  }, [])

  if (!info) return null

  const isJiuwen = info.kernel === 'jiuwen-agent-core'

  return (
    <div className="openlab-kernel-guide mb-2 shrink-0" data-testid="terminal-kernel-guide">
      <div className="openlab-kernel-guide-inner">
        <span className="flex items-center gap-1" aria-hidden="true">
          <span className="openlab-kernel-guide-dot" style={{ animationDelay: '0ms' }} />
          <span className="openlab-kernel-guide-dot" style={{ animationDelay: '150ms' }} />
          <span className="openlab-kernel-guide-dot" style={{ animationDelay: '300ms' }} />
        </span>
        {isJiuwen ? (
          <span className="text-xs text-[var(--color-text-secondary)]">
            当前内核：<strong className="text-[var(--color-text-primary)]">jiuwen-Agent-core</strong>
            <span className="mx-1.5 text-[var(--color-border)]">|</span>
            在下方终端输入 <code className="rounded bg-[var(--color-surface-selected)] px-1 py-0.5 font-mono text-[11px]">jiuwen</code> 启动蜂群协作 TUI
          </span>
        ) : (
          <span className="text-xs text-[var(--color-text-secondary)]">
            当前内核：<strong className="text-[var(--color-text-primary)]">Claude Code 安全修复版</strong>
            <span className="mx-1.5 text-[var(--color-border)]">|</span>
            在下方终端输入 <code className="rounded bg-[var(--color-surface-selected)] px-1 py-0.5 font-mono text-[11px]">openlab-robot</code> 启动交互式 Agent
          </span>
        )}
      </div>
    </div>
  )
}
