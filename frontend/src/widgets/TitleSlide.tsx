import { useCallback, useRef, useState } from 'react'
import type { SlideLayout, TitleSlideTabId } from '../protocol'
import { CodeEditor } from './CodeEditor'
import type { CellMeta } from './Cell'
import type { SlideMeta } from './SlideShow'

const DEFAULT_COLUMN_FRACTION = 0.3

export interface TitleSlideProps {
  slides: SlideMeta[]
  activeIndex: number
  onIndexChange: (index: number) => void
  layout: SlideLayout | null | undefined
  onLayoutChange: (layout: SlideLayout) => void
  /** The deck's `is_setup`/`is_main` cells, if any (found by the caller
   * in `cellMeta` -- this component doesn't scan the whole deck itself,
   * it only knows about the two ids/metas it's handed). `undefined`
   * means that role doesn't exist in this deck at all -- distinct from
   * "exists but not currently added as a tab" (tracked in `layout.tabs`
   * instead), per the confirmed "Add Setup/Main tab only offered when
   * that cell role exists" availability rule. */
  setupCellId: string | undefined
  setupMeta: CellMeta | undefined
  mainCellId: string | undefined
  mainMeta: CellMeta | undefined
  lineOffsets: Record<string, number>
  onRunCell: (cellId: string, source: string) => void
  onRunAll: () => void
  onLineCountChange: (cellId: string, count: number) => void
}

// CELL_QUADRANT_LAYOUT_TODO.md item 4: the title slide's own bespoke
// layout, replacing the old extraCodeAbove composition entirely -- a
// table of contents on the left (every slide's title, click to jump),
// and a tab strip on the right offering "Setup"/"Main" tabs (each an
// embed of that cell's actual primary editor) when those cell roles
// exist in the deck. Deliberately NOT a Cell/the 4-quadrant system --
// just a plain 2-column layout with one adjustable divider between
// them, per the confirmed design. The main cell's own notes/canvas/
// other elements no longer render here at all (confirmed behavior
// change from the old extraCodeAbove-composed-into-a-full-Cell
// rendering) -- they still show normally on whichever slide the author
// actually lists that cell on.
export function TitleSlide({
  slides,
  activeIndex,
  onIndexChange,
  layout,
  onLayoutChange,
  setupCellId,
  setupMeta,
  mainCellId,
  mainMeta,
  lineOffsets,
  onRunCell,
  onRunAll,
  onLineCountChange,
}: TitleSlideProps) {
  // Seeded once from the saved layout, then this component's own local
  // drag/tab state is authoritative -- same "local state, not re-
  // derived from props on every render" precedent Cell.tsx's own
  // columnFraction/tabQuadrant already set, so an in-progress drag or a
  // just-added tab doesn't get silently reset by an unrelated re-render
  // (e.g. a cell's status updating elsewhere on the page).
  const [columnFraction, setColumnFraction] = useState(() => layout?.column_fraction ?? DEFAULT_COLUMN_FRACTION)
  const [tabs, setTabs] = useState<TitleSlideTabId[]>(() => layout?.tabs ?? [])
  const [activeTabState, setActiveTabState] = useState<TitleSlideTabId | undefined>(() => layout?.active_tab)
  const activeTab = activeTabState !== undefined && tabs.includes(activeTabState) ? activeTabState : tabs[0]

  const containerRef = useRef<HTMLDivElement | null>(null)
  const draggingRef = useRef(false)

  const layoutRef = useRef({ columnFraction, tabs, activeTab })
  layoutRef.current = { columnFraction, tabs, activeTab }

  const emitLayoutChange = useCallback(() => {
    const current = layoutRef.current
    onLayoutChange({
      column_fraction: current.columnFraction,
      tabs: current.tabs,
      ...(current.activeTab !== undefined ? { active_tab: current.activeTab } : {}),
    })
  }, [onLayoutChange])

  const handleMove = useCallback((event: PointerEvent) => {
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    if (rect.width === 0) return
    const fraction = (event.clientX - rect.left) / rect.width
    setColumnFraction(fraction)
  }, [])

  const stopResizing = useCallback(() => {
    if (!draggingRef.current) return
    draggingRef.current = false
    document.body.classList.remove('cs-resizing')
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', stopResizing)
    emitLayoutChange()
  }, [handleMove, emitLayoutChange])

  const startResizing = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      draggingRef.current = true
      document.body.classList.add('cs-resizing')
      window.addEventListener('pointermove', handleMove)
      window.addEventListener('pointerup', stopResizing)
    },
    [handleMove, stopResizing],
  )

  function addTab(tab: TitleSlideTabId) {
    if (tabs.includes(tab)) return
    const nextTabs = [...tabs, tab]
    setTabs(nextTabs)
    setActiveTabState(tab)
    onLayoutChange({ column_fraction: columnFraction, tabs: nextTabs, active_tab: tab })
  }

  function removeTab(tab: TitleSlideTabId) {
    const nextTabs = tabs.filter((t) => t !== tab)
    setTabs(nextTabs)
    const nextActive = activeTab === tab ? nextTabs[0] : activeTab
    setActiveTabState(nextActive)
    onLayoutChange({
      column_fraction: columnFraction,
      tabs: nextTabs,
      ...(nextActive !== undefined ? { active_tab: nextActive } : {}),
    })
  }

  const availableToAdd: { id: TitleSlideTabId; label: string; cellId: string | undefined }[] = [
    ...(setupCellId ? [{ id: 'setup' as const, label: 'Setup', cellId: setupCellId }] : []),
    ...(mainCellId ? [{ id: 'main' as const, label: 'Main', cellId: mainCellId }] : []),
  ]
  const addableTabs = availableToAdd.filter((t) => !tabs.includes(t.id))

  function tabMeta(tab: TitleSlideTabId): { cellId: string; meta: CellMeta } | undefined {
    if (tab === 'setup' && setupCellId && setupMeta) return { cellId: setupCellId, meta: setupMeta }
    if (tab === 'main' && mainCellId && mainMeta) return { cellId: mainCellId, meta: mainMeta }
    return undefined
  }

  return (
    <div className="cs-title-slide" ref={containerRef}>
      <div className="cs-title-slide-toc" style={{ flexBasis: `${columnFraction * 100}%` }}>
        <ul className="cs-title-slide-toc-list">
          {slides.map((s, i) => (
            <li key={i}>
              <button
                type="button"
                className={`cs-title-slide-toc-entry ${i === activeIndex ? 'cs-title-slide-toc-entry-active' : ''}`}
                onClick={() => onIndexChange(i)}
              >
                {s.title || `Slide ${i + 1}`}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div
        className="cs-resize-handle"
        onPointerDown={startResizing}
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize the table of contents/tabs split"
      />

      <div className="cs-title-slide-tabs">
        <div className="cs-cell-tabs" role="tablist">
          {tabs.map((tab) => {
            const info = availableToAdd.find((t) => t.id === tab)
            return (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                className={`cs-cell-tab ${activeTab === tab ? 'cs-cell-tab-active' : ''}`}
                onClick={() => setActiveTabState(tab)}
              >
                {info?.label ?? tab}
                <span
                  className="cs-title-slide-tab-remove"
                  role="button"
                  aria-label={`Remove ${info?.label ?? tab} tab`}
                  onClick={(event) => {
                    event.stopPropagation()
                    removeTab(tab)
                  }}
                >
                  ×
                </span>
              </button>
            )
          })}
          {addableTabs.length > 0 && (
            <div className="cs-title-slide-add-tab">
              <select
                value=""
                aria-label="Add tab"
                onChange={(event) => {
                  const value = event.target.value as TitleSlideTabId
                  if (value) addTab(value)
                }}
              >
                <option value="" disabled>
                  + Add tab
                </option>
                {addableTabs.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
        <div className="cs-cell-tab-content">
          {activeTab &&
            (() => {
              const info = tabMeta(activeTab)
              if (!info) return null
              return (
                <CodeEditor
                  source={info.meta.source}
                  onRunCell={(source) => onRunCell(info.cellId, source)}
                  onRunAll={onRunAll}
                  readOnly={info.meta.instance === 'static'}
                  lineOffset={lineOffsets[info.cellId] ?? 0}
                  onLineCountChange={(count) => onLineCountChange(info.cellId, count)}
                />
              )
            })()}
        </div>
      </div>
    </div>
  )
}
