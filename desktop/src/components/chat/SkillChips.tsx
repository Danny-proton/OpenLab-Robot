import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from '../../i18n'
import { skillsApi } from '../../api/skills'
import { marketApi } from '../../api/market'
import { useSkillPrefsStore, type ComposerSkill, type PinnedSkill } from '../../stores/skillPrefsStore'

const STYLE_ID = 'openlab-skill-chips-style'

function ensureStyle() {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
@keyframes openlab-skill-pop {
  0% { transform: scale(0.7); opacity: 0; }
  60% { transform: scale(1.06); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
}
.openlab-skill-pop { animation: openlab-skill-pop 180ms ease-out; }
.openlab-skill-bar {
  mask-image: linear-gradient(to right, black calc(100% - 48px), transparent);
  -webkit-mask-image: linear-gradient(to right, black calc(100% - 48px), transparent);
}
.openlab-skill-bar.no-overflow { mask-image: none; -webkit-mask-image: none; }
.openlab-skill-chip.dragging { opacity: 0.4; }
`
  document.head.appendChild(style)
}

type LocalSkillItem = { name: string; description: string; source?: string }
type MarketSkillItem = { name: string; description: string; source: string }

/** 技能选择下拉框：本地技能 + 市场技能搜索，钉子切换常驻 */
export function SkillPicker({
  workDir,
  onPick,
  onClose,
}: {
  workDir?: string
  onPick: (skill: ComposerSkill) => void
  onClose: () => void
}) {
  const t = useTranslation()
  const [tab, setTab] = useState<'local' | 'market'>('local')
  const [query, setQuery] = useState('')
  const [localSkills, setLocalSkills] = useState<LocalSkillItem[]>([])
  const [marketSkills, setMarketSkills] = useState<MarketSkillItem[]>([])
  const [loading, setLoading] = useState(false)
  const pinned = useSkillPrefsStore((s) => s.pinned)
  const togglePinned = useSkillPrefsStore((s) => s.togglePinned)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    ensureStyle()
    void skillsApi
      .list(workDir)
      .then((res) =>
        setLocalSkills(
          res.skills
            .filter((s) => s.userInvocable)
            .map((s) => ({ name: s.name, description: s.description, source: s.source })),
        ),
      )
      .catch(() => setLocalSkills([]))
  }, [workDir])

  // 点击外部关闭
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [onClose])

  // 市场搜索防抖
  useEffect(() => {
    if (tab !== 'market') return
    setLoading(true)
    const timer = setTimeout(() => {
      void marketApi
        .list({ q: query || undefined, limit: 20 })
        .then((res) =>
          setMarketSkills(
            res.items.map((s) => ({ name: s.slug, description: s.summary, source: s.source })),
          ),
        )
        .catch(() => setMarketSkills([]))
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(timer)
  }, [tab, query])

  const filteredLocal = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return localSkills
    return localSkills.filter(
      (s) => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q),
    )
  }, [localSkills, query])

  const items = tab === 'local' ? filteredLocal : marketSkills

  return (
    <div
      ref={containerRef}
      className="absolute bottom-full left-0 z-30 mb-2 w-80 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl"
    >
      <div className="p-2 border-b border-[var(--color-border)]">
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('skills.picker.search')}
          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] px-2.5 py-1.5 text-sm outline-none focus:border-[var(--color-primary)]"
        />
        <div className="mt-2 flex gap-1">
          {(['local', 'market'] as const).map((key) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 rounded-md py-1 text-xs font-medium transition-colors ${
                tab === key
                  ? 'bg-[var(--color-surface-selected)] text-[var(--color-text-primary)]'
                  : 'text-[var(--color-text-tertiary)] hover:bg-[var(--color-surface-hover)]'
              }`}
            >
              {key === 'local' ? t('skills.picker.local') : t('skills.picker.market')}
            </button>
          ))}
        </div>
      </div>
      <div className="max-h-64 overflow-y-auto p-1">
        {items.length === 0 && !loading && (
          <div className="px-3 py-4 text-center text-xs text-[var(--color-text-tertiary)]">
            {t('skills.picker.empty')}
          </div>
        )}
        {items.map((skill) => {
          const isPinned = pinned.some((p) => p.name === skill.name)
          return (
            <div
              key={`${skill.source ?? 'local'}:${skill.name}`}
              className="group flex items-center gap-1 rounded-lg px-2 py-1.5 hover:bg-[var(--color-surface-hover)]"
            >
              <button
                className="min-w-0 flex-1 text-left"
                onClick={() => {
                  onPick({ name: skill.name, source: skill.source })
                  onClose()
                }}
              >
                <div className="truncate text-sm text-[var(--color-text-primary)]">/{skill.name}</div>
                <div className="truncate text-xs text-[var(--color-text-tertiary)]">{skill.description}</div>
              </button>
              <button
                title={isPinned ? t('skills.picker.unpin') : t('skills.picker.pin')}
                aria-label={isPinned ? t('skills.picker.unpin') : t('skills.picker.pin')}
                onClick={() => void togglePinned({ name: skill.name, source: skill.source })}
                className={`material-symbols-outlined shrink-0 rounded p-1 text-[16px] transition-opacity ${
                  isPinned
                    ? 'text-[var(--color-primary)]'
                    : 'text-[var(--color-text-tertiary)] opacity-0 group-hover:opacity-100'
                }`}
              >
                keep
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** 常驻技能栏 + 已置入技能气泡 */
export function SkillChips({
  composerSkills,
  onRemoveComposerSkill,
}: {
  composerSkills: ComposerSkill[]
  onRemoveComposerSkill: (name: string) => void
}) {
  const t = useTranslation()
  const pinned = useSkillPrefsStore((s) => s.pinned)
  const savePinned = useSkillPrefsStore((s) => s.savePinned)
  const setAlias = useSkillPrefsStore((s) => s.setAlias)
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [editingAlias, setEditingAlias] = useState<string | null>(null)
  const [aliasDraft, setAliasDraft] = useState('')
  const [overflow, setOverflow] = useState(false)
  const barRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    ensureStyle()
  }, [])

  // 过长时启用右端渐变隐藏
  useEffect(() => {
    const el = barRef.current
    if (!el) return
    const observer = new ResizeObserver(() => setOverflow(el.scrollWidth > el.clientWidth))
    observer.observe(el)
    setOverflow(el.scrollWidth > el.clientWidth)
    return () => observer.disconnect()
  }, [pinned.length])

  const onDrop = (targetIndex: number) => {
    if (dragIndex === null || dragIndex === targetIndex) return
    const next = [...pinned]
    const moved = next.splice(dragIndex, 1)[0]
    if (!moved) return
    next.splice(targetIndex, 0, moved)
    setDragIndex(null)
    void savePinned(next)
  }

  // 按 group 字段插入分组分隔标签
  const rows: Array<{ type: 'chip'; skill: PinnedSkill; index: number } | { type: 'group'; label: string }> = []
  let lastGroup: string | undefined
  pinned.forEach((skill, index) => {
    if (skill.group && skill.group !== lastGroup) {
      rows.push({ type: 'group', label: skill.group })
    }
    lastGroup = skill.group
    rows.push({ type: 'chip', skill, index })
  })

  if (pinned.length === 0 && composerSkills.length === 0) return null

  return (
    <div className="flex flex-col gap-1.5">
      {pinned.length > 0 && (
        <div
          ref={barRef}
          className={`openlab-skill-bar flex items-center gap-1.5 overflow-x-auto pb-0.5 ${overflow ? '' : 'no-overflow'}`}
        >
          {rows.map((row) =>
            row.type === 'group' ? (
              <span
                key={`group-${row.label}`}
                className="shrink-0 px-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-text-tertiary)]"
              >
                {row.label}
              </span>
            ) : (
              <span
                key={row.skill.name}
                draggable
                onDragStart={() => setDragIndex(row.index)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => onDrop(row.index)}
                onDragEnd={() => setDragIndex(null)}
                onDoubleClick={() => {
                  setEditingAlias(row.skill.name)
                  setAliasDraft(row.skill.alias ?? '')
                }}
                title={`/${row.skill.name}`}
                className={`openlab-skill-chip flex shrink-0 cursor-grab items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-hover)] px-2.5 py-1 text-xs text-[var(--color-text-secondary)] ${
                  dragIndex === row.index ? 'dragging' : ''
                }`}
              >
                <span className="material-symbols-outlined text-[13px]">auto_awesome</span>
                {editingAlias === row.skill.name ? (
                  <input
                    autoFocus
                    value={aliasDraft}
                    onChange={(e) => setAliasDraft(e.target.value)}
                    onBlur={() => {
                      void setAlias(row.skill.name, aliasDraft.trim() || undefined)
                      setEditingAlias(null)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                      if (e.key === 'Escape') setEditingAlias(null)
                    }}
                    className="w-20 bg-transparent text-xs outline-none"
                  />
                ) : (
                  <span>
                    {row.skill.alias ?? row.skill.name}
                    {row.skill.alias && (
                      <span className="ml-1 text-[var(--color-text-tertiary)]">/{row.skill.name}</span>
                    )}
                  </span>
                )}
              </span>
            ),
          )}
        </div>
      )}
      {composerSkills.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {composerSkills.map((skill) => (
            <span
              key={skill.name}
              className="openlab-skill-pop flex items-center gap-1 rounded-full bg-[var(--color-primary)] px-2.5 py-1 text-xs text-[var(--color-on-primary)]"
            >
              <span className="material-symbols-outlined text-[13px]">bolt</span>
              /{skill.alias ?? skill.name}
              <button
                aria-label={t('skills.chip.remove')}
                onClick={() => onRemoveComposerSkill(skill.name)}
                className="material-symbols-outlined text-[13px] opacity-70 hover:opacity-100"
              >
                close
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
