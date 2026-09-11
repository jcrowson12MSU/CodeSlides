import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'
import { useChatState } from './chatState'
import { useDeckState } from './deckState'
import { usePresenceState } from './presenceState'
import {
  onElementChangedClientSide,
  runAllClientSide,
  runCellClientSide,
  type PyodideCellInput,
  type PyodideCellResult,
} from './pyodideKernel'
import type { CellLayout, ServerMessage } from './protocol'
import { useCodeSlidesSocket } from './useCodeSlidesSocket'
import { Cell, type CellMeta } from './widgets/Cell'
import { ChatPanel } from './widgets/ChatPanel'
import { setDeckCellOrder } from './widgets/deckSource'
import { EditSlideDeckPanel } from './widgets/EditSlideDeckPanel'
import { JoinScreen } from './widgets/JoinScreen'
import { computeLineOffsets } from './widgets/lineOffsets'
import { PeerList } from './widgets/PeerList'
import { SlideShow, type SlideMeta } from './widgets/SlideShow'

interface DeckSummary {
  title: string
  cells: Record<string, CellMeta>
  slides: SlideMeta[]
}

type ViewMode = 'cells' | 'slides'

function initialViewMode(): ViewMode {
  // `codeslides present <file>` (cli.py) opens the browser at
  // /?mode=slides so an instructor lands directly in the presentation
  // view instead of having to click the toggle themselves; `edit` opens
  // plain `/`, defaulting to the flat Cells view. Purely a starting
  // point -- the toggle below still switches freely either way.
  return new URLSearchParams(window.location.search).get('mode') === 'slides' ? 'slides' : 'cells'
}

// TODO.md #46a-iv/#46d: `?document=<id>` in the URL means this is a
// collaborative connection to a shared document -- present only when a
// document link was explicitly opened (46e's join-link UI, `codeslides
// edit/present --collaborative`, is what actually generates these links;
// the param is read directly here, same "read it straight off
// window.location.search" pattern initialViewMode already uses for
// `?mode=`). `null` (the overwhelmingly common case: a plain `codeslides
// edit`/`present` open) means a solo, fully isolated connection exactly
// as before #46a -- no join-screen, no presence, nothing about this
// feature changes that path's behavior.
function documentIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get('document')
}

// TODO.md #46e-ii: `?role=viewer` in the URL (the viewer link
// `--collaborative` also prints) must reach the /ws connection URL, not
// just get silently dropped -- the server enforces this role
// server-side regardless of what the frontend does with it, but a
// viewer link that connects as an unrestricted editor because this
// param never made it onto the websocket URL would defeat the whole
// point of having a separate viewer link at all. Any value other than
// the literal "viewer" (including no ?role= at all -- true for every
// solo connection and every plain editor link) is editor, matching
// server.py's own "anything but literal 'viewer' is editor" fallback.
function roleFromUrl(): 'editor' | 'viewer' {
  return new URLSearchParams(window.location.search).get('role') === 'viewer' ? 'viewer' : 'editor'
}

// Two views over the same deck (ARCHITECTURE.md's "one tool, two modes"
// principle, VISION.md): a flat "Cells" edit view (every cell, always
// showing code -- TODO.md #6/#7) and a "Slides" presentation view
// (TODO.md #10) grouping cells by Slide, one at a time, with a
// reveal-code toggle. Both share the same websocket connection, cell
// state, and interaction handlers below -- switching modes never
// reconnects or re-runs anything, it's purely which cells are visible
// and how.
function App() {
  const [deck, setDeck] = useState<DeckSummary | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode)
  // Slides-view-only: collapses the entire header (title row + the
  // Prev/Next/Reveal-code toolbar rendered inside SlideShow) down to just
  // the toggle button itself, so presenting on a small/projected screen
  // doesn't lose ~250px of vertical space to chrome the audience doesn't
  // need to see. Prev/Next stay reachable while collapsed via the
  // existing Cmd+Control+Left/Right shortcut (SlideShow.tsx's window-
  // level listener doesn't depend on the toolbar being visible). Reset
  // whenever leaving Slides view so it never affects the Cells layout and
  // never surprises the user by starting collapsed next time they
  // present.
  const [headerCollapsed, setHeaderCollapsed] = useState(false)
  // The current slide's title, reported up by SlideShow (which owns slide
  // navigation) so the header row can show it in place of the collapsed
  // title row below -- see the header's own render for why it needs to
  // live here rather than just inside SlideShow.
  const [activeSlideTitle, setActiveSlideTitle] = useState('')
  // Slide navigation index -- lifted up from SlideShow's own useState so
  // the header row can render Prev/Next flanking the title slot
  // (`.cs-app-title`), per the user's request to move them there instead
  // of their own separate toolbar row inside SlideShow. SlideShow is
  // still the source of truth for *rendering* the slide at this index
  // (and still owns the Cmd+Control+Left/Right keyboard shortcut), but
  // no longer owns the index itself.
  const [slideIndex, setSlideIndex] = useState(0)
  // The title slide (index 0) shows the deck's own title here instead of
  // its own declared slide title -- per the user's request, matching
  // what Cells view's header always shows for the deck (`deck?.title`),
  // rather than whatever an author happened to name that one slide (e.g.
  // the literal string "Title" -- `examples/marchingSquares.py`'s own
  // `@app.slide('Title', ...)`). Every other slide still shows its own
  // title unchanged.
  const displayedSlideTitle = slideIndex === 0 ? (deck?.title ?? '') : activeSlideTitle
  // The "Edit slide deck" panel (rename of TODO's "+ New slide" button,
  // per the user's request): reorder existing slides and create new
  // ones, from the header row next to the Cells/Slides toggle.
  const [editSlideDeckOpen, setEditSlideDeckOpen] = useState(false)
  useEffect(() => {
    if (viewMode !== 'slides') {
      setHeaderCollapsed(false)
      setEditSlideDeckOpen(false)
      setSlideIndex(0)
    }
  }, [viewMode])
  // Guards against `slideIndex` pointing past the end of the deck's
  // slide list -- can't happen from reordering (a permutation never
  // changes the count) but is cheap, correct insurance against any
  // future slide-count change (e.g. deletion, not yet supported) landing
  // Prev/Next's `atEnd` check and SlideShow's `slides[index]` lookup on
  // an index that no longer exists.
  useEffect(() => {
    if (!deck) return
    setSlideIndex((i) => Math.min(i, Math.max(deck.slides.length - 1, 0)))
  }, [deck])
  // The header's "?" button (TODO.md #27, revised): the websocket
  // connection status it originally showed turned out not to matter day
  // to day (confirmed with the user), so it's now a real help popover
  // listing the keyboard shortcuts instead -- both the Cells-view-only
  // run shortcuts and the Slides-view-only navigation shortcut, since
  // there was previously no single place a user could see all of them
  // (the Cells-view hint text disappeared entirely in Slides view).
  const [helpOpen, setHelpOpen] = useState(false)
  const helpRef = useRef<HTMLDivElement | null>(null)
  // Feedback for the last save_deck round-trip (TODO.md #11). Cleared on
  // the next save attempt; not persisted -- purely a transient toast.
  // `saving` gates which `error` messages count as save feedback -- errors
  // are otherwise a generic, untagged message type shared with edit_cell/
  // set_element_value/etc, so without this an unrelated error (e.g. a
  // stale edit_cell for a since-renamed cell) would incorrectly surface as
  // a save failure.
  const [saveStatus, setSaveStatus] = useState<{ kind: 'saved' | 'error'; text: string } | null>(
    null,
  )
  const [saving, setSaving] = useState(false)
  const [elementValues, setElementValues] = useState<Record<string, Record<string, unknown>>>({})
  // Local-only override for notes content while editing: set_notes_source
  // produces no server reply on its own (ARCHITECTURE.md section 8 --
  // no re-run), so without this the editor would show stale content
  // until some unrelated cell_output happened to refresh it. In review
  // mode (handleStageNotesEdit) this is also the *only* place a staged-
  // but-not-yet-pushed edit is visible at all, since nothing reaches
  // deckState until accept_cell_bundle's notes_source_changed lands.
  const [notesOverrides, setNotesOverrides] = useState<Record<string, Record<string, string>>>({})
  // Same shape as notesOverrides, for a `tests` element's editable source
  // (ARCHITECTURE.md section 3b) -- set_test_source does get a server
  // reply (a fresh pass/fail result via element_output), but that reply
  // only carries the *result*, not an echo of the source itself, so the
  // editor still needs its own local echo the same way notes does.
  const [testSourceOverrides, setTestSourceOverrides] = useState<Record<string, Record<string, string>>>(
    {},
  )
  // TODO.md #64/PROPOSAL_pyscript_execution.md: a cell's own most recent
  // client-side (Pyodide) execution result -- this first implementation
  // slice's whole point. Unlike every other override above, this is not
  // an echo of something the server also knows about: the server never
  // executes anything and never sees this at all (the proposal's
  // section 2.1 axiom -- no execution result crosses a browser
  // boundary), so this is the ONLY source of a cell's status/output/
  // error now. Merged into mergedCellState below, same pattern as
  // notesOverrides, but replacing rather than layering onto
  // `cellState[cellId]` (there is no server-side execution state left
  // to layer on top of).
  const [clientExecutionState, setClientExecutionState] = useState<Record<string, PyodideCellResult>>({})
  // Collapse (ARCHITECTURE.md section 8): pure UI state, kept client-side
  // for the same reason notesOverrides/testSourceOverrides above are --
  // set_ui_state produces no server reply to sync from.
  const [collapsedCells, setCollapsedCells] = useState<Record<string, boolean>>({})
  // Feedback for a rejected rename_cell/add_element/remove_element (TODO.md
  // #22) -- e.g. renaming a cell another cell calls directly by name.
  // Keyed by cell_id since ErrorMessage carries one, so each cell's edit
  // panel only shows the error that's actually about it. Cleared on the
  // next edit-panel action for that cell.
  const [editErrors, setEditErrors] = useState<Record<string, string>>({})
  // TODO.md #68: on a review_mode document, which cells have any
  // un-pushed local change (a code/test/notes edit, or a hide-code/
  // hide-def/rename toggle) -- just a dirty flag, not a queue of
  // individual staged edits. Pushing always sends the cell's current
  // full state (read live from `notesOverrides`/`testSourceOverrides`/
  // `primarySourceDrafts`/the deck's own current hide/name fields at
  // push time, composed in `handlePushCellState` below), so there is
  // nothing to accumulate here beyond "this cell changed since the
  // last push/accept" -- replaces #65's `pendingActions` queue
  // entirely. Real classroom bug report: repeated Shift+Enter edits
  // before pushing used to append a new staged action every time,
  // replayed (and separately re-executed) one by one on Accept; there
  // is no longer anything to accumulate, so that can't recur.
  const [dirtyCells, setDirtyCells] = useState<Set<string>>(new Set())
  // TODO.md #68: the review_mode analogue of `notesOverrides`/
  // `testSourceOverrides` above, for a cell's primary source -- EditCell
  // is rejected outright on a review_mode document (same as before),
  // so nothing else remembers the last Shift+Enter'd primary source for
  // a cell client-side; needed so `handlePushCellState` has something
  // to read back when the user clicks Push.
  const [primarySourceDrafts, setPrimarySourceDrafts] = useState<Record<string, string>>({})
  // TODO.md #68: same shape, for a pending rename -- unlike hide_code/
  // hide_def (whose current-vs-pending value is read straight off
  // `deck.cells[cellId]` in handlePushCellState, since nothing else
  // ever changes it locally under review_mode), a rename's target name
  // has nowhere else to live: `deck.cells` is keyed by the cell's
  // *current* (pre-rename) name until the push is actually accepted.
  const [renameDrafts, setRenameDrafts] = useState<Record<string, string>>({})
  // Feedback for a rejected add_slide (e.g. no cells selected, or the
  // deck wasn't started from a file) -- same "clear on next attempt"
  // shape as editErrors, just not keyed by cell since a slide isn't one.
  const [addSlideError, setAddSlideError] = useState<string | undefined>(undefined)
  // The slide-order permutation staged so far, relative to the deck's
  // true on-disk order (what `set_slide_order`/`Session.
  // slide_order_override` actually expect) -- NOT relative to whatever
  // order is currently displayed. Reordering twice in a row must compose:
  // each `handleReorderSlides` call receives a permutation of the
  // *currently displayed* indices (what clicking an up/down arrow in
  // EditSlideDeckPanel naturally produces), but the message sent to the
  // server has to stay expressed against the original baseline, or a
  // second move silently discards the first (caught via a real browser
  // reorder-twice-then-save test: the file ended up scrambled relative
  // to what the UI showed). Cleared back to null on save success/failure
  // and whenever the deck's slide list changes for a reason other than
  // this composition (e.g. a fresh /api/deck fetch, or an add_slide) --
  // those all replace `deck.slides` with a new on-disk-order baseline.
  const pendingSlideOrder = useRef<number[] | null>(null)
  // TODO.md #46d: null for the overwhelmingly common solo case (no
  // `?document=` in the URL) -- the socket connects to plain `/ws`
  // exactly as before this feature existed. A non-null id connects to
  // `/ws?document=<id>[&role=viewer]` instead, joining (or creating)
  // that shared document's Session -- `role` (TODO.md #46e-ii) is
  // meaningless without a document, so it's only ever appended alongside
  // one, never on its own.
  const documentId = useMemo(documentIdFromUrl, [])
  const role = useMemo(roleFromUrl, [])
  // TODO.md #46e's own "not done" follow-on note: a UX improvement, not
  // the actual security boundary -- ws_handler.py's
  // VIEWER_ALLOWED_MESSAGE_TYPES already rejects every structural edit
  // server-side regardless of what this UI shows. Used to hide mutating
  // controls (Save, Add cell, Add slide, a cell's Edit button, move/
  // delete, the editor itself) so a viewer is never offered a control
  // that would just fail with a generic error. Deliberately does NOT
  // touch slider/text-input elements -- confirmed with the user those
  // should stay interactive for a viewer; see TODO.md #64 for the
  // separate, much larger client-side-execution work that would make
  // that interaction actually meaningful instead of a silent no-op.
  const isViewer = role === 'viewer'
  // TODO.md #64 (collaboration rework)/PROPOSAL_pyscript_execution.md
  // section 2.2: every collaborative document is now accept-gated --
  // the server's own `reviewMode` (session_created's `review_mode`,
  // tied to cli.py's `--review-mode` flag) is no longer what decides
  // this on the frontend, since always-live mode is retired entirely,
  // not just made optional. `documentId` (set only for a `--collaborative`
  // connection -- see documentIdFromUrl above) is the correct condition
  // now: a solo connection has no peer to push to at all, so it always
  // runs directly (handleRunCell, no staging); any collaborative
  // connection always stages+pushes, regardless of what the server
  // reports. useCodeSlidesSocket still returns the server's own
  // reviewMode (server.py/session.py's own review_mode field is
  // untouched by this frontend-only slice, see
  // PROPOSAL_pyscript_execution.md section 7's still-open "what happens
  // to review_mode as a stored field" question) -- no longer
  // destructured here at all, since nothing in this file reads it any
  // more.
  const { sessionId, messages, send } = useCodeSlidesSocket(
    documentId
      ? `/ws?document=${encodeURIComponent(documentId)}${role === 'viewer' ? '&role=viewer' : ''}`
      : undefined,
  )
  const acceptGated = Boolean(documentId)
  const cellState = useDeckState(messages)
  const presenceState = usePresenceState(messages)
  const chatMessages = useChatState(messages)
  const handleSendChatMessage = useCallback(
    (text: string) => {
      if (!sessionId) return
      send({ type: 'send_chat_message', session_id: sessionId, text })
    },
    [sessionId, send],
  )
  // TODO.md #66-iv: lifted here (not local to ChatPanel) so the expanded
  // panel's own right-padding on `.app` (below) can be applied -- see
  // ChatPanel.tsx's own comment on why the panel's fixed-position overlay
  // otherwise silently blocks clicks on real content underneath it.
  const [chatExpanded, setChatExpanded] = useState(false)
  // TODO.md #46d-ii: this connection's own identity, once join_ack
  // arrives -- null until then (and forever, for a solo connection,
  // which never sends Join in the first place per displayNamePrompt's
  // own gating below).
  const [ownIdentity, setOwnIdentity] = useState<{
    connectionId: string
    userId: string
    color: string
  } | null>(null)
  useEffect(() => {
    const lastJoinAck = [...messages].reverse().find((m) => m.type === 'join_ack')
    if (lastJoinAck && lastJoinAck.type === 'join_ack') {
      setOwnIdentity({
        connectionId: lastJoinAck.connection_id,
        userId: lastJoinAck.user_id,
        color: lastJoinAck.color,
      })
    }
  }, [messages])
  // TODO.md #46d-ii: the join-screen name prompt, shown only for a
  // collaborative connection (documentId set) that hasn't joined yet --
  // a solo connection never shows this at all, matching the decision
  // that presence/identity must not change the existing single-editor
  // experience. `null` display name = prompt still showing;
  // once set, Join is sent (below) and the prompt never reappears for
  // the life of this connection, even if display_name is later cleared
  // by some future "leave and rejoin" feature -- there is none today.
  const [displayName, setDisplayName] = useState<string | null>(null)
  const joinSentRef = useRef(false)
  useEffect(() => {
    if (!documentId || !sessionId || !displayName || joinSentRef.current) return
    joinSentRef.current = true
    send({ type: 'join', session_id: sessionId, display_name: displayName })
  }, [documentId, sessionId, displayName, send])
  // Each cell's own live line count, keyed by cellId -- updated on every
  // keystroke via CodeEditor's `onLineCountChange` (see lineOffsets.ts's
  // own docstring for why `deck.cells[cellId].source` alone isn't
  // enough: it's only as fresh as the last deck-shape event, not live
  // typing). Read, not written, by the `cellLineOffsets` memo below.
  const [liveLineCounts, setLiveLineCounts] = useState<Record<string, number>>({})
  const handleLineCountChange = useCallback((cellId: string, count: number) => {
    setLiveLineCounts((prev) => (prev[cellId] === count ? prev : { ...prev, [cellId]: count }))
  }, [])
  // Recomputed when the cells record's identity changes (a new cell
  // added/removed/reordered) or any cell's live count changes -- not on
  // every unrelated re-render (a slider drag, a cell's own output
  // updating) -- since it's an O(n) pass over the whole deck. Shared
  // between Cells view (below) and SlideShow.tsx's own Slides view,
  // which recomputes the same thing from the same `deck.cells`/live
  // counts it already receives as `cellMeta`, rather than needing this
  // passed in.
  const deckCells = deck?.cells
  const cellLineOffsets = useMemo(
    () => (deckCells ? computeLineOffsets(deckCells, liveLineCounts) : {}),
    [deckCells, liveLineCounts],
  )
  // Publishes this deck's cell ordering to the module-level deck-source
  // registry (deckSource.ts) so a CodeEditor anywhere in the tree can
  // scan "the whole deck" for autocomplete purposes (AUTOCOMPLETE_TODO.md
  // items 2-4) in the same order `cellLineOffsets` above already treats
  // as authoritative -- `Object.keys(deck.cells)`, not something this
  // effect needs to re-derive.
  useEffect(() => {
    if (deckCells) setDeckCellOrder(Object.keys(deckCells))
  }, [deckCells])

  useEffect(() => {
    fetch('/api/deck')
      .then((r) => r.json())
      .then(setDeck)
      .catch(() => setDeck(null))
  }, [])

  // TODO.md #28: in Slides view, the screen itself must not move --
  // only a cell's own code editor / elements column scrolls internally.
  // A class toggled on both `<html>` and `<body>` (App.css) is the
  // simplest way to change the page's overall scroll behavior for
  // exactly this one view without touching the Cells view's layout at
  // all -- same pattern Cell.tsx already uses for `cs-resizing` during a
  // divider drag. Both elements need the class, not just `body`:
  // confirmed by hand that `<html>` is the actual document scrolling
  // element in this browser, so locking `body` alone still let a wheel
  // event bubbling past an internal scroll container move the page.
  useEffect(() => {
    const locked = viewMode === 'slides'
    document.documentElement.classList.toggle('cs-slides-locked', locked)
    document.body.classList.toggle('cs-slides-locked', locked)
    if (!locked) return

    // `overflow: hidden`/`clip` on <html>/<body> (App.css) block wheel-
    // driven document scroll, but not this: clicking into a cell's code
    // editor to focus it still moves `document.documentElement.
    // scrollTop` by the sticky header's height, confirmed by hand --
    // the browser's own default focus-scroll-into-view behavior, which
    // isn't blocked by overflow on the scrolling element the way a
    // wheel/touch scroll is. Snapping it straight back to 0 on every
    // `scroll` event is the reliable fix regardless of what triggers it
    // (this fires for that focus-driven scroll same as any other).
    function snapBack() {
      if (document.documentElement.scrollTop !== 0) {
        document.documentElement.scrollTop = 0
      }
    }
    window.addEventListener('scroll', snapBack)
    return () => {
      document.documentElement.classList.remove('cs-slides-locked')
      document.body.classList.remove('cs-slides-locked')
      window.removeEventListener('scroll', snapBack)
    }
  }, [viewMode])

  // Shrinks the sticky header's title to 2/3 size once the page has
  // scrolled away from the top -- the title's landing-page-scale default
  // is meant to be seen once, at the top of the page; once you've
  // scrolled into the deck's content it's competing for space with a
  // sticky header row that stays pinned regardless (`.cs-app-header`'s
  // `position: sticky`). Only ever fires in Cells view in practice --
  // Slides view force-snaps scroll back to 0 (the effect above), so
  // `scrolled` would just never flip there, but the listener is kept
  // unconditional rather than gated on `viewMode` since it's harmless
  // (and correctly resets) either way.
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    function handleScroll() {
      setScrolled(document.documentElement.scrollTop > 0)
    }
    handleScroll()
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  // Cmd+Control+Left/Right advances between cells in Cells view -- same
  // modifier combo and same reasoning as SlideShow.tsx's own Slides-view
  // shortcut (see its own comment): plain Cmd+Left/Right is the standard
  // "move cursor to start/end of line" shortcut inside the code editor,
  // so using it unmodified for cell navigation would fight with normal
  // text editing every time a code editor has focus. Right advances
  // (down the page, to the next cell); left goes back (up, to the
  // previous cell) -- matching the user's own "right is down, left is
  // up" framing, and SlideShow's forward/backward convention.
  //
  // Unlike Slides view (which shows exactly one slide and so needs an
  // explicit `index` in state), Cells view is a single scrolling page --
  // there's no persistent "current cell" selection to move relative to,
  // so this finds whichever cell is nearest the top of the viewport
  // *at the moment the shortcut fires* and scrolls to its neighbor. This
  // stays correct even if the user free-scrolls the page by hand between
  // presses, which a stored index could otherwise drift out of sync with.
  useEffect(() => {
    if (viewMode !== 'cells' || !deckCells) return
    function handleKey(event: KeyboardEvent) {
      if (!event.metaKey || !event.ctrlKey) return
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
      event.preventDefault()
      const cellIds = Object.keys(deckCells ?? {})
      if (cellIds.length === 0) return
      const cellElements = cellIds.map((id) => document.getElementById(`cs-cell-${id}`)).filter((el): el is HTMLElement => el !== null)
      if (cellElements.length === 0) return
      // The topmost cell whose own top edge is still on-screen (or, if
      // every cell has already scrolled past the top, the last one) --
      // same "nearest to the top of the viewport" idea a reading-position
      // indicator would use, without needing to track scroll position in
      // React state.
      let currentIndex = cellElements.findIndex((el) => el.getBoundingClientRect().bottom > 0)
      if (currentIndex === -1) currentIndex = cellElements.length - 1
      const delta = event.key === 'ArrowRight' ? 1 : -1
      const targetIndex = Math.min(Math.max(currentIndex + delta, 0), cellElements.length - 1)
      cellElements[targetIndex].scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [viewMode, deckCells])

  useEffect(() => {
    if (!helpOpen) return
    function handlePointerDown(event: PointerEvent) {
      if (helpRef.current && !helpRef.current.contains(event.target as Node)) {
        setHelpOpen(false)
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setHelpOpen(false)
    }
    window.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('keydown', handleKey)
    return () => {
      window.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('keydown', handleKey)
    }
  }, [helpOpen])

  // TODO.md #64 (collaboration rework)/PROPOSAL_pyscript_execution.md
  // section 3: this used to send a `run_all` websocket message, back
  // when the server actually executed cells and broadcast the results.
  // The server no longer executes anything in response to any network
  // message (kernel.py's own run_all/on_cell_edited/on_element_changed
  // docstrings) -- sending it was already a no-op, just a pointless
  // round trip. Calls handleRunAll() (the same client-side path the Run
  // All button/shortcut already uses) instead, so opening a deck still
  // runs it automatically -- the one user-visible behavior this effect
  // exists for -- with zero server involvement. Gated on `deck` as well
  // as `sessionId` (not just `sessionId`, the original condition):
  // `deck` loads via its own independent `fetch('/api/deck')` effect
  // above, with no ordering relative to the websocket handshake that
  // produces `sessionId` -- `handleRunAll`'s own `currentCellInputs()`
  // silently returns `{}` for a still-null `deck` (see its own
  // docstring), which would otherwise mean "run nothing" if this effect
  // fired before the deck fetch resolved.
  useEffect(() => {
    if (sessionId && deck) {
      handleRunAll()
    }
    // run_all only needs to fire once per new session, once the deck is
    // also available -- not on every subsequent deck update thereafter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, Boolean(deck)])

  useEffect(() => {
    const last = messages[messages.length - 1]
    if (!last) return
    if (last.type === 'deck_saved') {
      setSaving(false)
      // The server's baseline now matches whatever it just wrote --
      // any further reorder must compose against a fresh
      // `deck.slides.map((_, i) => i)` identity, not whatever was
      // pending before this save (handleReorderSlides' own docstring).
      pendingSlideOrder.current = null
      // `last.slides` is only ever non-null when this save flushed a
      // pending slide reorder (DeckSaved's own docstring) -- splice the
      // deck's now-authoritative slide order in here rather than
      // trusting the optimistic order handleReorderSlides already
      // applied, since a concurrent conflict (SaveConflictError) could
      // in principle have left the two out of sync.
      if (last.slides) {
        const slides = last.slides
        setDeck((prev) => (prev ? { ...prev, slides: slides as DeckSummary['slides'] } : prev))
      }
      // Same shape as `last.slides` above, for `set_cell_layout` --
      // `last.cell_layouts` is only non-null when this save flushed at
      // least one pending layout override. Each cell already shows its
      // own layout optimistically (it's Cell.tsx's own local drag state,
      // never reset just because a save round-trips), so this is mostly
      // a defensive sync for `deck.cells[...].layout` specifically
      // (which nothing else keeps current once staged), not a visible
      // change to what's on screen.
      if (last.cell_layouts) {
        const cellLayouts = last.cell_layouts
        setDeck((prev) => {
          if (!prev) return prev
          const cells = { ...prev.cells }
          for (const [cellId, layout] of Object.entries(cellLayouts)) {
            if (cells[cellId]) cells[cellId] = { ...cells[cellId], layout }
          }
          return { ...prev, cells }
        })
      }
      const parts: string[] = []
      if (last.cells.length > 0) parts.push(`cells: ${last.cells.join(', ')}`)
      if (last.slides) parts.push('slide order')
      if (last.cell_layouts) parts.push('layout')
      setSaveStatus(
        parts.length > 0
          ? { kind: 'saved', text: `Saved: ${parts.join('; ')}` }
          : { kind: 'saved', text: 'Nothing to save' },
      )
    } else if (last.type === 'error') {
      // Not just a rejected save_deck -- a refused remove_cell/reorder_cells
      // (e.g. deleting a cell another cell still reads from) also lands
      // here, and those buttons live in the collapsed cell header with no
      // edit panel open to show `editErrors` in, so this banner is the
      // only place that failure is visible at all.
      setSaving(false)
      setSaveStatus({ kind: 'error', text: last.message })
    }
    // only re-check when a new message arrives
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages])

  // `cell_added`/`cell_renamed`/`element_added`/`element_removed`/
  // `elements_reordered`/`element_config_set` are never guaranteed to be
  // the *last* message in a batch -- the server also sends the affected
  // cell's own cell_status/cell_output (and element_output, if it has
  // viewer elements) right after it, all as separate websocket frames
  // that land in `messages` before this effect's next run. So this scans
  // every message added since the last run, not just
  // messages[messages.length - 1].
  const processedMessageCount = useRef(0)
  // Set right before sending `add_slide`, cleared by whatever response
  // (slide_added or a cell_id-less error) arrives for it -- same
  // "pending flag scopes the next generic response" shape `saving`
  // already uses for save_deck, needed here because AddSlide/its
  // ErrorMessage carry no cell_id for the message-scan loop below to key
  // an error off of the way editErrors does for cell-level actions.
  const addSlidePending = useRef(false)
  // TODO.md #64 (collaboration rework)/PROPOSAL_pyscript_execution.md
  // section 3: cell_added/title_slide_added/element_added/element_removed/
  // primary_editor_added/primary_editor_removed used to each also carry
  // a server-computed cell_status/cell_output/element_output tail (the
  // structural Kernel method's own re-run of the affected cell,
  // immediately after the disk write) -- removed now that none of those
  // 6 Kernel methods execute anything server-side any more (see each of
  // their own docstrings). What every one of them still needs is the
  // exact same "shows up immediately, not stale until an unrelated
  // future edit happens to trigger a run" behavior the server-side
  // re-run used to provide -- just achieved client-side now. This ref
  // collects the cell ids these 6 message types name, for the *separate*
  // effect below (keyed on `deck`, not `messages`) to actually run once
  // `deck.cells` reflects the new structure -- calling runCellClientSide
  // directly inside this effect's own `setDeck` updater isn't an option
  // (React state updaters must be pure, and `deck` here is still the
  // stale pre-update value until next render).
  const cellsNeedingClientRerun = useRef<Set<string>>(new Set())
  useEffect(() => {
    const newMessages = messages.slice(processedMessageCount.current)
    processedMessageCount.current = messages.length
    if (newMessages.length === 0) return

    for (const msg of newMessages) {
      if (
        msg.type === 'cell_added' ||
        msg.type === 'title_slide_added' ||
        msg.type === 'element_added' ||
        msg.type === 'element_removed' ||
        msg.type === 'primary_editor_added' ||
        msg.type === 'primary_editor_removed'
      ) {
        cellsNeedingClientRerun.current.add(msg.cell_id)
      }
    }

    setDeck((prev) => {
      if (!prev) return prev
      let cells = prev.cells
      let slides = prev.slides
      let changed = false
      for (const msg of newMessages) {
        if (
          msg.type === 'cell_added' ||
          msg.type === 'element_added' ||
          msg.type === 'element_removed' ||
          msg.type === 'elements_reordered' ||
          msg.type === 'element_config_set'
        ) {
          if (!changed) cells = { ...cells }
          changed = true
          cells[msg.cell_id] = {
            instance: msg.instance,
            source: msg.source,
            elements: msg.elements,
            layout: msg.layout,
            // None of these message types touch is_main/is_setup/
            // hide_code/hide_def (the backend preserves all four --
            // serialization.py's _detect_is_main/_detect_is_setup/
            // _detect_hide_code, same precedent as layout) -- carry the
            // existing local value forward rather than dropping to
            // `undefined`/false, which would make the UI show the
            // main/setup-cell/hide-code/hide-def checkboxes as
            // unchecked the moment an unrelated element edit landed.
            // cell_added is the one case with no existing cell to carry
            // forward from -- a brand-new cell is never main, setup, or
            // hidden.
            is_main: cells[msg.cell_id]?.is_main ?? false,
            is_setup: cells[msg.cell_id]?.is_setup ?? false,
            hide_code: cells[msg.cell_id]?.hide_code ?? false,
            hide_def: cells[msg.cell_id]?.hide_def ?? false,
            // Same carry-forward precedent -- none of these operations
            // touch whether this cell has a primary editor either.
            // Absent (a cell that's never been touched by
            // remove_primary_editor) defaults `true`: every existing
            // cell has a primary editor until this UI explicitly
            // removes it (CELL_QUADRANT_LAYOUT_TODO.md item 2b).
            has_primary_editor: cells[msg.cell_id]?.has_primary_editor ?? true,
          }
        } else if (msg.type === 'primary_editor_removed' || msg.type === 'primary_editor_added') {
          if (!changed) cells = { ...cells }
          changed = true
          cells[msg.cell_id] = {
            instance: msg.instance,
            source: msg.source,
            elements: msg.elements,
            layout: msg.layout,
            is_main: cells[msg.cell_id]?.is_main ?? false,
            is_setup: cells[msg.cell_id]?.is_setup ?? false,
            hide_code: cells[msg.cell_id]?.hide_code ?? false,
            hide_def: cells[msg.cell_id]?.hide_def ?? false,
            has_primary_editor: msg.type === 'primary_editor_added',
          }
        } else if (msg.type === 'cell_renamed') {
          if (!changed) cells = { ...cells }
          changed = true
          // has_primary_editor isn't part of CellRenamed's own payload
          // (unlike is_main/is_setup/hide_code, which rename_cell
          // detects and returns directly) -- carry it forward from the
          // pre-rename entry under its old key, same fallback-to-true
          // precedent as the cell_added/element_added block above.
          const hadPrimaryEditor = cells[msg.old_cell_id]?.has_primary_editor ?? true
          delete cells[msg.old_cell_id]
          cells[msg.cell_id] = {
            instance: msg.instance,
            source: msg.source,
            elements: msg.elements,
            layout: msg.layout,
            is_main: msg.is_main,
            is_setup: msg.is_setup,
            hide_code: msg.hide_code,
            hide_def: msg.hide_def,
            has_primary_editor: hadPrimaryEditor,
          }
        } else if (msg.type === 'main_cell_set') {
          if (!changed) cells = { ...cells }
          changed = true
          if (cells[msg.cell_id]) cells[msg.cell_id] = { ...cells[msg.cell_id], is_main: true }
          if (msg.previous_main_cell_id && cells[msg.previous_main_cell_id]) {
            cells[msg.previous_main_cell_id] = { ...cells[msg.previous_main_cell_id], is_main: false }
          }
        } else if (msg.type === 'setup_cell_set') {
          if (!changed) cells = { ...cells }
          changed = true
          if (cells[msg.cell_id]) cells[msg.cell_id] = { ...cells[msg.cell_id], is_setup: true }
          if (msg.previous_setup_cell_id && cells[msg.previous_setup_cell_id]) {
            cells[msg.previous_setup_cell_id] = { ...cells[msg.previous_setup_cell_id], is_setup: false }
          }
        } else if (msg.type === 'hide_code_set') {
          if (!changed) cells = { ...cells }
          changed = true
          if (cells[msg.cell_id]) {
            cells[msg.cell_id] = { ...cells[msg.cell_id], hide_code: msg.hide_code }
          }
        } else if (msg.type === 'hide_def_set') {
          if (!changed) cells = { ...cells }
          changed = true
          if (cells[msg.cell_id]) {
            // Unlike hide_code_set, hide_def changes what the backend's
            // display_source itself returns for this cell (whether the
            // `def name(...):` line is included) -- source must be
            // replaced too, or the editor keeps showing pre-toggle
            // content until some unrelated event happens to refresh it.
            cells[msg.cell_id] = { ...cells[msg.cell_id], hide_def: msg.hide_def, source: msg.source }
          }
        } else if (msg.type === 'cell_source_changed') {
          // TODO.md #46b-i: on a shared document, a peer's edit_cell
          // broadcasts this so every connection (including the sender,
          // harmlessly -- CodeEditor.tsx's remote-update effect is a
          // no-op when the incoming source already matches the live
          // doc) converges on the same source, matching the winning
          // last-write in Session.source_overrides server-side.
          if (!changed) cells = { ...cells }
          changed = true
          if (cells[msg.cell_id]) {
            cells[msg.cell_id] = { ...cells[msg.cell_id], source: msg.source }
          }
        } else if (msg.type === 'cell_removed') {
          if (!changed) cells = { ...cells }
          changed = true
          delete cells[msg.cell_id]
        } else if (msg.type === 'cells_reordered') {
          changed = true
          // Rebuild the object with keys re-inserted in the server's new
          // order -- both JS objects (string keys) and the Python dict
          // driving `msg.cell_order` preserve insertion order, and every
          // other cell-list render in this app (the `Object.entries(deck
          // .cells)` map below, `Object.keys` elsewhere) already relies
          // on that same convention for display order, so this is the
          // one place that convention needs to be actively re-asserted
          // rather than just inherited from however `cells` happened to
          // accumulate insertions so far.
          const reordered: Record<string, CellMeta> = {}
          for (const name of msg.cell_order) {
            if (name in cells) reordered[name] = cells[name]
          }
          cells = reordered
        } else if (msg.type === 'slide_added') {
          changed = true
          slides = [
            ...slides,
            { title: msg.title, cells: msg.cell_names, reveal_code: msg.reveal_code, notes: msg.notes },
          ]
          addSlidePending.current = false
          setAddSlideError(undefined)
        } else if (msg.type === 'slide_removed') {
          changed = true
          slides = slides.filter((_, i) => i !== msg.index)
        } else if (msg.type === 'title_slide_added') {
          if (!changed) cells = { ...cells }
          changed = true
          cells[msg.cell_id] = {
            instance: msg.instance,
            source: msg.source,
            elements: msg.elements,
            layout: msg.layout,
          }
          // Unlike slide_added (always appended -- see its own comment
          // above), a title slide is inserted first, so the server sends
          // the deck's whole, now-reordered slide list to replace
          // wholesale rather than a single slide to append.
          slides = msg.slides
        }
      }
      return changed ? { ...prev, cells, slides } : prev
    })

    const newErrors: Array<{ cell_id: string; message: string }> = []
    for (const m of newMessages) {
      if (m.type === 'error' && m.cell_id) {
        newErrors.push({ cell_id: m.cell_id, message: m.message })
      } else if (m.type === 'error' && !m.cell_id && addSlidePending.current) {
        addSlidePending.current = false
        setAddSlideError(m.message)
      }
    }
    if (newErrors.length > 0) {
      setEditErrors((prev) => {
        const next = { ...prev }
        for (const err of newErrors) {
          next[err.cell_id] = err.message
        }
        return next
      })
    }

    // TODO.md #65-xi/#68: test_source_changed must update
    // testSourceOverrides (the local echo TestsElementWidget's editor
    // actually renders from), the same state set_test_source's own
    // handleChangeTestSource already keeps in sync for the non-review-
    // mode path -- without this, every connection's test editor
    // (including the accepter's own) would keep showing pre-accept text
    // forever after an AcceptCellState applies a pushed test-source
    // field, having no other path that ever refreshes it (SetTestSource's
    // own reply is only ever the resulting ElementOutput result, never
    // an echo of the source itself).
    const acceptedTestSources = newMessages.filter(
      (m): m is Extract<ServerMessage, { type: 'test_source_changed' }> => m.type === 'test_source_changed',
    )
    if (acceptedTestSources.length > 0) {
      setTestSourceOverrides((prev) => {
        const next = { ...prev }
        for (const m of acceptedTestSources) {
          next[m.cell_id] = { ...next[m.cell_id], [m.element_id]: m.source }
        }
        return next
      })
    }

    // TODO.md #65-xiii/#68: same reasoning as acceptedTestSources above,
    // for a notes element -- SetNotesSource's own handler returns [], so
    // notes_source_changed is the only way any connection (including
    // the accepter's own) learns the newly-accepted markdown text after
    // an AcceptCellState application.
    const acceptedNotesSources = newMessages.filter(
      (m): m is Extract<ServerMessage, { type: 'notes_source_changed' }> => m.type === 'notes_source_changed',
    )
    if (acceptedNotesSources.length > 0) {
      setNotesOverrides((prev) => {
        const next = { ...prev }
        for (const m of acceptedNotesSources) {
          next[m.cell_id] = { ...next[m.cell_id], [m.element_id]: m.source }
        }
        return next
      })
    }
  }, [messages])

  // TODO.md #64 (collaboration rework)/PROPOSAL_pyscript_execution.md
  // section 3: drains `cellsNeedingClientRerun` (populated above,
  // whenever cell_added/title_slide_added/element_added/element_removed/
  // primary_editor_added/primary_editor_removed arrives) once `deck`
  // itself has actually been updated with the new structure -- a
  // separate effect, not inline in the one above, because `deck` there
  // is still last render's value until this component re-renders with
  // the `setDeck` call already applied. Each pending cell id is re-run
  // via the exact same client-side path Shift+Enter/Run All use
  // (runCellClientSide, currentCellInputs()) -- this is what makes a
  // freshly-added cell/element/primary-editor show real output
  // immediately instead of looking stale until an unrelated future edit
  // happens to trigger a run, the same "shouldn't look conspicuously
  // different" guarantee the removed server-side re-run used to provide.
  useEffect(() => {
    if (!deck) return
    const pending = cellsNeedingClientRerun.current
    if (pending.size === 0) return
    cellsNeedingClientRerun.current = new Set()
    for (const cellId of pending) {
      if (!deck.cells[cellId]) continue
      runCellClientSide(cellId, currentCellInputs())
        .then(applyClientExecutionResults)
        .catch((err: unknown) => reportClientExecutionError(cellId, err))
    }
    // currentCellInputs/applyClientExecutionResults/reportClientExecutionError
    // are plain function declarations recreated every render, not
    // memoized -- listing them would re-fire this effect on every
    // render instead of only when `deck` itself changes, same
    // "eslint-disable, not a real missing dependency" precedent the
    // sessionId/deck bootstrap effect above already uses.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deck])

  // TODO.md #64 (element/input-binding slice): mirrors handleRunCell/
  // handleRunAll below -- the value change runs entirely client-side via
  // Pyodide now (Kernel.on_element_changed's own re-run semantics,
  // replicated in pyodideKernel.ts's on_element_changed_b64), so the
  // set_element_value websocket message this used to send is dropped
  // entirely, same "no server round trip for execution" rule those two
  // already follow (PROPOSAL_pyscript_execution.md section 2.1 -- the
  // server never executes anything and never sees this value at all).
  // `elementValues` (local React state) stays the source of truth for
  // "what is this slider currently set to" exactly as it already was --
  // only the round-trip-to-server part is gone, not the local echo.
  function handleSetElementValue(cellId: string, elementId: string, value: unknown) {
    setElementValues((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: value },
    }))
    onElementChangedClientSide(cellId, elementId, value, currentCellInputs())
      .then(applyClientExecutionResults)
      .catch((err: unknown) => reportClientExecutionError(cellId, err))
  }

  // TODO.md #64/PROPOSAL_pyscript_execution.md: this tab's full current
  // view of the deck -- deck.cells' own last-known source/elements for
  // every OTHER cell, with `overrideCellId`'s own entry's source
  // overridden by whatever fresh source the caller was just given
  // (deck.cells[cellId].source only updates via server messages, which
  // no longer fire for a client-side-only edit -- see App.tsx's own
  // mergedCellState comment on why execution state is no longer
  // server-derived at all). This is the exact shape
  // runCellClientSide/runAllClientSide/onElementChangedClientSide need
  // to rebuild the dependency graph AND bind input-element kwargs fresh
  // on every call (there is no persistent client-side Deck object to
  // keep in sync incrementally -- see pyodideKernel.ts's own header
  // comment). `elements` always comes from `deck.cells[id].elements`
  // itself (name/kind/config, ElementMeta's own shape -- never
  // overridden per-call, since only source changes live-edit to live-
  // edit within this slice's scope), not `elementValues` -- those are a
  // SEPARATE per-tab value the Pyodide runner's own _element_values
  // dict tracks (see on_element_changed_b64), matching how
  // session.instances[cell].elements[el].value is a Session-side
  // concern kernel.py never threads through Cell/Deck either.
  function currentCellInputs(overrideCellId?: string, overrideSource?: string): Record<string, PyodideCellInput> {
    if (!deck) return {}
    const cells: Record<string, PyodideCellInput> = {}
    for (const [id, meta] of Object.entries(deck.cells)) {
      cells[id] = {
        source: id === overrideCellId && overrideSource !== undefined ? overrideSource : meta.source,
        elements: meta.elements,
      }
    }
    return cells
  }

  function applyClientExecutionResults(results: Record<string, PyodideCellResult>) {
    setClientExecutionState((prev) => ({ ...prev, ...results }))
  }

  function reportClientExecutionError(cellId: string, err: unknown) {
    setClientExecutionState((prev) => ({
      ...prev,
      [cellId]: {
        status: 'error',
        value: null,
        kind: null,
        data: null,
        error: err instanceof Error ? err.message : String(err),
        stdout: '',
        stderr: '',
        elementWrites: [],
      },
    }))
  }

  // TODO.md #64/PROPOSAL_pyscript_execution.md section 6: Shift+Enter
  // runs entirely client-side via Pyodide -- no edit_cell websocket
  // message at all. Marked "queued" immediately (so the UI shows
  // something changed right away, matching the old send-then-wait-for-
  // cell_status-broadcast feel) then replaced with the real result(s)
  // once Pyodide finishes -- `results` covers `cellId` itself plus
  // every dependent cell the graph says is affected (graph.py's own
  // `affected_by`), not just the one cell that was edited. Errors
  // thrown by runCellClientSide itself (Pyodide failed to load, a fetch
  // for one of the codeslides_pyscript/ files 404'd, etc.) are surfaced
  // as this cell's own error, same "never silently do nothing" rule the
  // rest of this file follows for a failed send.
  function handleRunCell(cellId: string, source: string) {
    setClientExecutionState((prev) => ({
      ...prev,
      [cellId]: {
        status: 'idle',
        value: prev[cellId]?.value ?? null,
        kind: prev[cellId]?.kind ?? null,
        data: prev[cellId]?.data ?? null,
        error: null,
        stdout: '',
        stderr: '',
        elementWrites: prev[cellId]?.elementWrites ?? [],
      },
    }))
    runCellClientSide(cellId, currentCellInputs(cellId, source))
      .then(applyClientExecutionResults)
      .catch((err: unknown) => reportClientExecutionError(cellId, err))
  }

  // TODO.md #65/#68/#64 (collaboration rework): the accept-gated
  // analogue of handleRunCell above -- used instead of running directly
  // whenever this is a collaborative document (Cell.tsx picks between
  // the two based on the reviewMode prop it is given, now driven by
  // acceptGated -- see this file's own documentId/acceptGated comment
  // above). Remembers the source locally (`primarySourceDrafts`, read
  // back by handlePushCellState below) and marks the cell dirty -- no
  // execution happens at all until the local Run/Run All the accepting
  // side eventually takes, per PROPOSAL_pyscript_execution.md section
  // 2.4's "no auto-rerun on incoming sync" rule.
  function handleStagePrimaryEdit(cellId: string, source: string) {
    if (!sessionId) return
    setPrimarySourceDrafts((prev) => ({ ...prev, [cellId]: source }))
    setDirtyCells((prev) => (prev.has(cellId) ? prev : new Set(prev).add(cellId)))
  }

  // TODO.md #65-xi/#68: same as handleStagePrimaryEdit, for a `tests`
  // element's own source -- many decks (anything with hide_code=True on
  // every cell) have no reachable primary editor at all, only a tests
  // element's editable source. Updates `testSourceOverrides` locally
  // (same local-echo role `handleChangeTestSource` plays in every other
  // mode) and marks the cell dirty, but never sends `set_test_source`
  // itself while review_mode is on.
  function handleStageTestEdit(cellId: string, elementId: string, source: string) {
    if (!sessionId) return
    setTestSourceOverrides((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: source },
    }))
    setDirtyCells((prev) => (prev.has(cellId) ? prev : new Set(prev).add(cellId)))
  }

  // TODO.md #64 (dependency-graph slice): Run All's client-side
  // equivalent -- every cell, full topological order, matching
  // Kernel.run_all's own unfiltered semantics (PROPOSAL_pyscript_execution.md
  // section 2.4) -- no more run_all websocket message at all.
  function handleRunAll() {
    runAllClientSide(currentCellInputs())
      .then(applyClientExecutionResults)
      .catch((err: unknown) => {
        if (!deck) return
        for (const cellId of Object.keys(deck.cells)) reportClientExecutionError(cellId, err)
      })
  }

  // TODO.md #46d-i/#46d-iv: which cell (if any) this connection's own
  // cursor is currently in -- tracked locally rather than only inferred
  // from the last set_presence sent, because `SetPresence` is NOT a
  // partial patch (ws_handler.py's `SessionRegistry.set_presence`
  // unconditionally overwrites both `cell_id` and `cursor_pos` together,
  // per its own docstring/implementation): sending a cursor-only update
  // with no `cell_id` would silently clobber this connection's own
  // already-broadcast `cell_id` back to `null` for every peer watching
  // it. Keeping this in local state (updated by handleCellFocusChange)
  // lets handleCursorChange always resend the *current* cell_id
  // alongside a new cursor_pos, rather than needing to omit it.
  const focusedCellIdRef = useRef<string | null>(null)
  // TODO.md #46d-iv: debounces cursor_pos updates (~200ms, confirmed
  // with the user) so a fast typist doesn't send one set_presence per
  // keystroke -- focus/blur (cell_id alone, no cursor_pos) is still sent
  // immediately below, since that's a much rarer event than every
  // keystroke/cursor move and the peer list should reflect "who's in
  // this cell" without a visible lag.
  const cursorDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // TODO.md #46d-i: only meaningful on a collaborative connection --
  // set_presence is ignored server-side for a connection that never sent
  // Join anyway (see ws_handler.py's SetPresence handling), so this is a
  // no-op for the overwhelmingly common solo case regardless, but the
  // documentId check avoids sending a message nobody will ever act on.
  function handleCellFocusChange(cellId: string, focused: boolean) {
    focusedCellIdRef.current = focused ? cellId : null
    if (!sessionId || !documentId) return
    send({
      type: 'set_presence',
      session_id: sessionId,
      cell_id: focused ? cellId : null,
    })
  }

  // TODO.md #46d-iv: fired on every cursor/selection move inside
  // whichever cell currently has focus -- always paired with
  // focusedCellIdRef's current value (see its own comment above for
  // why this must never be cursor_pos alone).
  function handleCursorChange(pos: number) {
    if (!sessionId || !documentId || !focusedCellIdRef.current) return
    const cellId = focusedCellIdRef.current
    if (cursorDebounceRef.current) clearTimeout(cursorDebounceRef.current)
    cursorDebounceRef.current = setTimeout(() => {
      send({ type: 'set_presence', session_id: sessionId, cell_id: cellId, cursor_pos: pos })
    }, 200)
  }

  // TODO.md #46d-iv: every *other* connected peer currently reporting
  // `cellId` as their own focused cell, with a known cursor position --
  // excludes this connection's own entry (ownIdentity.connectionId,
  // 46d-ii) since a person never needs to see their own cursor rendered
  // as a remote one, and excludes a peer with `cursorPos: null` (joined,
  // or in some other cell, but never actually reported a position in
  // this one) rather than rendering a decoration at a meaningless
  // fallback position like 0.
  function remotePeersForCell(cellId: string) {
    return Object.entries(presenceState)
      .filter(
        ([connectionId, peer]) =>
          connectionId !== ownIdentity?.connectionId && peer.cellId === cellId && peer.cursorPos !== null,
      )
      .map(([connectionId, peer]) => ({
        connectionId,
        color: peer.color,
        displayName: peer.displayName,
        cursorPos: peer.cursorPos as number,
      }))
  }

  function handleSaveDeck() {
    if (!sessionId) return
    setSaving(true)
    setSaveStatus(null)
    send({ type: 'save_deck', session_id: sessionId })
  }

  function handleAddCell() {
    if (!sessionId) return
    send({ type: 'add_cell', session_id: sessionId })
  }

  function handleAddSlide(title: string, cellNames: string[], revealCode: boolean) {
    if (!sessionId) return
    setAddSlideError(undefined)
    addSlidePending.current = true
    send({ type: 'add_slide', session_id: sessionId, title, cell_names: cellNames, reveal_code: revealCode })
  }

  function handleAddTitleSlide() {
    if (!sessionId) return
    send({ type: 'add_title_slide', session_id: sessionId })
  }

  // Removes slide `index` from the deck entirely, on disk immediately
  // (same write-now precedent as `handleAddSlide`/`handleRemoveCell`,
  // not staged behind Save the way `handleReorderSlides` is) --
  // deliberately does NOT delete the cell(s) that slide showed; see
  // `RemoveSlide`'s own docstring (protocol.py) for the distinction
  // from `handleRemoveCell`. Every slide after the removed one shifts
  // down by one position, so `slideIndex` needs adjusting: a slide
  // strictly before the removed one shifts its own index down by one
  // to keep tracking the same slide the user was looking at; a slide
  // strictly after stays put, its own index unaffected. Removing the
  // *currently-viewed* slide itself deliberately does NOT decrement --
  // per the user's own choice, staying at the same numeric index shows
  // whichever slide slides into that now-vacant spot (i.e. what used
  // to be the next slide), only clamped down by one if the removed
  // slide was the last one in the deck (nothing left to slide into
  // that spot).
  function handleRemoveSlide(index: number) {
    if (!sessionId) return
    const wasLastSlide = index === (deck?.slides.length ?? 1) - 1
    send({ type: 'remove_slide', session_id: sessionId, index })
    setSlideIndex((current) => {
      if (index < current) return current - 1
      if (index === current && wasLastSlide) return Math.max(0, current - 1)
      return current
    })
  }

  // Reorders the deck's slides to match `displayedOrder` -- a
  // permutation of indices into whatever's *currently displayed*
  // (`deck.slides`), which is what EditSlideDeckPanel's up/down arrows
  // naturally produce (same "local swap of an array built from current
  // state" shape App.tsx's own handleReorderCells already uses).
  // Applied optimistically to local state immediately, and staged
  // server-side via `set_slide_order` -- unlike `handleReorderCells`,
  // this does NOT write to disk yet; it's only persisted the next time
  // Save runs (`SaveDeck` flushes `Session.slide_order_override`), per
  // the user's request that slide reordering go through Save like a
  // cell-code edit does, not write immediately like every other slide/
  // cell mutation in this app.
  //
  // `set_slide_order`'s own `slide_order` must stay expressed relative
  // to the deck's true on-disk order, not the currently-displayed one --
  // composed here via `pendingSlideOrder`, since two reorders in a row
  // would otherwise silently discard the first (verified by hand: the
  // second move's raw indices, sent as-is, landed on the *original*
  // file order server-side, producing a result that didn't match what
  // the UI had shown after the first move).
  function handleReorderSlides(displayedOrder: number[]) {
    if (!sessionId || !deck) return
    const base = pendingSlideOrder.current ?? deck.slides.map((_, i) => i)
    const composed = displayedOrder.map((i) => base[i])
    pendingSlideOrder.current = composed
    setDeck((prev) => {
      if (!prev) return prev
      return { ...prev, slides: displayedOrder.map((i) => prev.slides[i]) }
    })
    send({ type: 'set_slide_order', session_id: sessionId, slide_order: composed })
  }

  function handleDeleteCell(cellId: string) {
    if (!sessionId) return
    send({ type: 'remove_cell', session_id: sessionId, cell_id: cellId })
  }

  // Stable identity (useCallback, not a plain function like its siblings
  // above) because Cell.tsx's stopResizing/stopPanelResizing list this as
  // a dependency of their own emitLayoutChange callback, which in turn is
  // a dependency of the window pointermove/pointerup listener-subscribing
  // effects -- a new function identity every App render would tear down
  // and re-subscribe those listeners mid-drag for no reason. Only stages
  // the layout (set_cell_layout); it's written to disk on the next Save,
  // same as handleReorderSlides' slide_order staging above.
  const handleLayoutChange = useCallback(
    (cellId: string, layout: CellLayout) => {
      if (!sessionId) return
      send({ type: 'set_cell_layout', session_id: sessionId, cell_id: cellId, layout })
    },
    [sessionId, send],
  )

  // Swaps `cellId` with its up/down neighbor in the deck's current
  // display order and sends the whole resulting permutation -- same
  // "local swap of an array built from current state, whole list sent
  // back" shape EditCellPanel.tsx's own `moveElement` already uses for
  // reordering one cell's *elements*, just at the deck level over
  // `Object.keys(deck.cells)` instead of one cell's own element list.
  function handleReorderCells(cellId: string, direction: -1 | 1) {
    if (!sessionId || !deck) return
    const order = Object.keys(deck.cells)
    const index = order.indexOf(cellId)
    const target = index + direction
    if (index === -1 || target < 0 || target >= order.length) return
    ;[order[index], order[target]] = [order[target], order[index]]
    send({ type: 'reorder_cells', session_id: sessionId, cell_order: order })
  }

  function clearEditError(cellId: string) {
    setEditErrors((prev) => {
      if (!(cellId in prev)) return prev
      const next = { ...prev }
      delete next[cellId]
      return next
    })
  }

  // TODO.md #68: the single interception point every one of the
  // accept-gated structural handlers below routes through -- on any
  // collaborative document (acceptGated -- TODO.md #64/
  // PROPOSAL_pyscript_execution.md section 2.2: every collaborative
  // document is accept-gated now, not just review_mode ones), mark
  // `cellId` dirty instead of sending `message` immediately; otherwise
  // (a solo connection, no peer to push to) send it right away exactly
  // as before this feature existed. Unlike #65's stageOrSend, `message`
  // itself is never kept -- rename/hide toggles are read fresh from
  // `deck.cells[cellId]`'s own current fields at push time (below),
  // same as every other pushed field.
  function stageOrSend(cellId: string, message: Record<string, unknown>) {
    if (!sessionId) return
    if (acceptGated) {
      setDirtyCells((prev) => (prev.has(cellId) ? prev : new Set(prev).add(cellId)))
      return
    }
    send(message as unknown as Parameters<typeof send>[0])
  }

  // TODO.md #68: composes cellId's entire current state from wherever
  // each field actually lives client-side -- `primarySourceDrafts`/
  // `notesOverrides`/`testSourceOverrides` for source-like fields (the
  // same local-echo state every mode already relies on), `deck.cells`
  // for hide_code/hide_def/the cell's current name (structural fields
  // this document's own deck metadata already reflects, since a rename/
  // hide toggle's own handler -- handleRenameCell/handleSetHideCode/
  // handleSetHideDef below -- only ever marks the cell dirty, it never
  // separately tracks a "pending" rename/hide value of its own) -- and
  // sends it as one push_cell_state message. There is deliberately no
  // separate draft-tracking for hide_code/hide_def/rename: `deck.cells`
  // already IS the student's own current view of those fields (nothing
  // else could have changed them locally, since review_mode rejects
  // those messages outright), so reading them straight from there at
  // push time is correct, not just convenient.
  function handlePushCellState(cellId: string) {
    if (!sessionId) return
    const meta = deck?.cells[cellId]
    if (!meta) return
    send({
      type: 'push_cell_state',
      session_id: sessionId,
      cell_id: cellId,
      new_cell_id: renameDrafts[cellId] ?? cellId,
      source: primarySourceDrafts[cellId] ?? meta.source,
      test_sources: testSourceOverrides[cellId] ?? {},
      notes_sources: notesOverrides[cellId] ?? {},
      hide_code: meta.hide_code ?? false,
      hide_def: meta.hide_def ?? false,
    })
    setDirtyCells((prev) => {
      if (!prev.has(cellId)) return prev
      const next = new Set(prev)
      next.delete(cellId)
      return next
    })
    setRenameDrafts((prev) => {
      if (!(cellId in prev)) return prev
      const next = { ...prev }
      delete next[cellId]
      return next
    })
  }

  function handleDiscardPendingChanges(cellId: string) {
    setDirtyCells((prev) => {
      if (!prev.has(cellId)) return prev
      const next = new Set(prev)
      next.delete(cellId)
      return next
    })
    setRenameDrafts((prev) => {
      if (!(cellId in prev)) return prev
      const next = { ...prev }
      delete next[cellId]
      return next
    })
  }

  function handleWithdrawPush(cellId: string) {
    if (!sessionId) return
    send({ type: 'withdraw_cell_state', session_id: sessionId, cell_id: cellId })
  }

  function handleAcceptPush(cellId: string, proposerUserId: string) {
    if (!sessionId) return
    send({ type: 'accept_cell_state', session_id: sessionId, cell_id: cellId, proposer_user_id: proposerUserId })
  }

  function handleRejectPush(cellId: string, proposerUserId: string) {
    if (!sessionId) return
    send({ type: 'reject_cell_state', session_id: sessionId, cell_id: cellId, proposer_user_id: proposerUserId })
  }

  // TODO.md #68: rename is part of the source+test+notes+hide+rename
  // push scope, so it stages (marks dirty + remembers the target name
  // in renameDrafts) rather than sending rename_cell immediately on any
  // collaborative (acceptGated) document.
  function handleRenameCell(cellId: string, newName: string) {
    if (!sessionId) return
    clearEditError(cellId)
    if (acceptGated) {
      setRenameDrafts((prev) => ({ ...prev, [cellId]: newName }))
      setDirtyCells((prev) => (prev.has(cellId) ? prev : new Set(prev).add(cellId)))
      return
    }
    send({ type: 'rename_cell', session_id: sessionId, cell_id: cellId, new_name: newName })
  }

  // TODO.md #68: main/setup-cell flags stayed out of the push scope
  // (see PushCellState's own comment) -- always sent immediately,
  // review_mode or not.
  function handleSetMainCell(cellId: string) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'set_main_cell', session_id: sessionId, cell_id: cellId })
  }

  function handleSetSetupCell(cellId: string) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'set_setup_cell', session_id: sessionId, cell_id: cellId })
  }

  // TODO.md #68: hide_code/hide_def ARE part of the push scope --
  // stage (mark dirty) rather than send immediately on a review_mode
  // document. No separate draft state needed: handlePushCellState
  // reads the *toggled-to* value straight back off `deck.cells`, since
  // nothing else changes hide_code/hide_def locally under review_mode
  // -- but that only works if the toggle's own UI reflects `hideCode`/
  // `hideDef` optimistically while dirty. Cell.tsx does this already
  // (its checkbox is controlled by the same prop either way); the
  // actual value only round-trips through the server once accepted.
  function handleSetHideCode(cellId: string, hideCode: boolean) {
    if (!sessionId) return
    clearEditError(cellId)
    stageOrSend(cellId, { type: 'set_hide_code', session_id: sessionId, cell_id: cellId, hide_code: hideCode })
  }

  function handleSetHideDef(cellId: string, hideDef: boolean) {
    if (!sessionId) return
    clearEditError(cellId)
    stageOrSend(cellId, { type: 'set_hide_def', session_id: sessionId, cell_id: cellId, hide_def: hideDef })
  }

  // TODO.md #68: element add/remove/reorder/config and primary-editor
  // add/remove all stayed out of the push scope (see PushCellState's
  // own comment) -- always sent immediately, review_mode or not.
  function handleAddElement(cellId: string, name: string, kind: string, config: Record<string, unknown>) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'add_element', session_id: sessionId, cell_id: cellId, element_name: name, kind, config })
  }

  function handleRemoveElement(cellId: string, elementName: string) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'remove_element', session_id: sessionId, cell_id: cellId, element_name: elementName })
  }

  // CELL_QUADRANT_LAYOUT_TODO.md item 2b: the primary code editor is
  // now a removable/addable tab, not a fixed always-present column --
  // same "write immediately, clear any stale edit error" shape as
  // handleAddElement/handleRemoveElement above, but hits its own
  // dedicated remove_primary_editor/add_primary_editor messages
  // (Element itself can never represent the primary editor -- its
  // `kind` has no matching entry in INPUT_KINDS/VIEWER_KINDS/
  // TEST_KINDS -- so this isn't just add_element/remove_element with a
  // synthetic kind).
  function handleRemovePrimaryEditor(cellId: string) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'remove_primary_editor', session_id: sessionId, cell_id: cellId })
  }

  function handleAddPrimaryEditor(cellId: string) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'add_primary_editor', session_id: sessionId, cell_id: cellId })
  }

  function handleReorderElements(cellId: string, elementOrder: string[]) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'reorder_elements', session_id: sessionId, cell_id: cellId, element_order: elementOrder })
  }

  function handleSetElementConfig(cellId: string, elementId: string, config: Record<string, unknown>) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'set_element_config', session_id: sessionId, cell_id: cellId, element_id: elementId, config })
  }

  function handleChangeNotesSource(cellId: string, elementId: string, source: string) {
    if (!sessionId) return
    setNotesOverrides((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: source },
    }))
    send({
      type: 'set_notes_source',
      session_id: sessionId,
      cell_id: cellId,
      element_id: elementId,
      source,
    })
  }

  // TODO.md #65-xiii/#68: notes-source used to bypass review mode
  // entirely (it rode on set_ui_state, shared with the genuinely-exempt
  // collapse/minimize flags, which never had a review_mode gate), a
  // real gap confirmed by direct user report. Fires on every keystroke
  // (Obsidian-style live preview, viewerElements.tsx's own docstring),
  // not just on an explicit Shift+Enter -- harmless now that pushing
  // just reads the latest `notesOverrides` value at push time rather
  // than accumulating one queued action per keystroke the way #65 did.
  function handleStageNotesEdit(cellId: string, elementId: string, source: string) {
    if (!sessionId) return
    setNotesOverrides((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: source },
    }))
    setDirtyCells((prev) => (prev.has(cellId) ? prev : new Set(prev).add(cellId)))
  }

  function handleChangeTestSource(cellId: string, elementId: string, source: string) {
    if (!sessionId) return
    setTestSourceOverrides((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: source },
    }))
    send({
      type: 'set_test_source',
      session_id: sessionId,
      cell_id: cellId,
      element_id: elementId,
      source,
    })
  }

  function handleToggleCollapse(cellId: string) {
    const next = !collapsedCells[cellId]
    setCollapsedCells((prev) => ({ ...prev, [cellId]: next }))
    if (sessionId) {
      send({ type: 'set_ui_state', session_id: sessionId, cell_id: cellId, collapsed: next })
    }
  }

  // Merge notes overrides and this cell's own client-side execution
  // result into cell state once, shared by both views. TODO.md #64: the
  // execution fields (status/value/kind/data/error) come ONLY from
  // clientExecutionState now -- cellState[cellId] (reduced from server
  // messages) never carries them any more, since the server never
  // executes anything (PROPOSAL_pyscript_execution.md section 2.1).
  // TODO.md #64 (element/input-binding slice): a run's elementWrites
  // (cs.image()/cs.iframe() calls, mirroring kernel.py's own
  // element_writes -> element_output translation, ws_handler.py's
  // _element_output_messages) are folded into elementContent here, the
  // same role that function plays server-side -- notes/tests fall
  // through to the server-derived value unchanged (notes is static
  // authored content, never re-computed by any run; tests has its own
  // separate, still-server-only execution path, out of this slice's
  // scope), matching _element_output_messages' own "notes/tests need a
  // fallback, viewer writes don't" split.
  const mergedCellState: Record<string, ReturnType<typeof useDeckState>[string] | undefined> = {}
  if (deck) {
    for (const cellId of Object.keys(deck.cells)) {
      const overrides = notesOverrides[cellId]
      const state = cellState[cellId]
      const execution = clientExecutionState[cellId]
      const withNotes = overrides
        ? { ...state, elementContent: { ...state?.elementContent, ...overrides } }
        : state
      const withElementWrites =
        execution && execution.elementWrites.length > 0
          ? {
              elementContent: {
                ...withNotes?.elementContent,
                ...Object.fromEntries(execution.elementWrites.map((w) => [w.elementName, w.content])),
              },
            }
          : null
      mergedCellState[cellId] = execution
        ? {
            ...withNotes,
            status: execution.status,
            value: execution.value,
            kind: execution.kind,
            data: execution.data,
            error: execution.error,
            elementContent: withElementWrites?.elementContent ?? withNotes?.elementContent ?? {},
            lastEditedBy: withNotes?.lastEditedBy ?? null,
            lastEditedAt: withNotes?.lastEditedAt ?? null,
            pendingPush: withNotes?.pendingPush ?? null,
          }
        : withNotes
    }
  }

  // TODO.md #46d-ii: the join-screen gate -- only ever shown for a
  // collaborative connection (documentId set) that hasn't sent Join yet.
  // A solo connection (documentId null) never renders this at all, so
  // the pre-#46d experience of `codeslides edit`/`present` is completely
  // unaffected -- this is the one thing that must never regress per the
  // scoping decision behind this whole feature.
  if (documentId && !displayName) {
    return <JoinScreen onJoin={setDisplayName} />
  }

  const slidesHeaderCollapsed = viewMode === 'slides' && headerCollapsed
  const slidesHeaderExpanded = viewMode === 'slides' && !headerCollapsed

  return (
    <main
      className={`app ${slidesHeaderCollapsed ? 'cs-header-is-collapsed' : ''} ${
        slidesHeaderExpanded ? 'cs-slides-header-expanded' : ''
      } ${documentId && chatExpanded ? 'cs-chat-is-open' : ''}`}
    >
      {slidesHeaderCollapsed && (
        <div className="cs-app-header cs-app-header-collapsed">
          <button
            type="button"
            className="cs-header-collapse-toggle"
            aria-pressed={headerCollapsed}
            aria-label="Show header"
            title="Show header"
            onClick={() => setHeaderCollapsed(false)}
          >
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path
                d="M4 6l4 4 4-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
          <button
            type="button"
            className="cs-slide-nav-button"
            aria-label="Previous slide"
            disabled={!deck || slideIndex === 0}
            onClick={() => setSlideIndex((i) => Math.max(i - 1, 0))}
          >
            &larr;
          </button>
          <h2 className="cs-slide-title cs-slide-title-in-header">{displayedSlideTitle}</h2>
          <button
            type="button"
            className="cs-slide-nav-button"
            aria-label="Next slide"
            disabled={!deck || slideIndex === deck.slides.length - 1}
            onClick={() => setSlideIndex((i) => Math.min(i + 1, (deck?.slides.length ?? 1) - 1))}
          >
            &rarr;
          </button>
          {deck && deck.slides.length > 0 && (
            <span className="cs-slideshow-position">
              {slideIndex + 1} / {deck.slides.length}
            </span>
          )}
        </div>
      )}
      {!slidesHeaderCollapsed && (
      <div className="cs-app-header">
        <div className="cs-app-title-group">
          {viewMode === 'slides' && (
            <button
              type="button"
              className="cs-header-collapse-toggle"
              aria-pressed={headerCollapsed}
              aria-label="Hide header"
              title="Hide header"
              onClick={() => setHeaderCollapsed(true)}
            >
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <path
                  d="M4 10l4-4 4 4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
          {/* Slides view: Prev/Next flank the title (per the user's
              request, moved here from their own toolbar row inside
              SlideShow) rather than sitting on a separate row -- the
              title itself doubles as the slide-position display's
              anchor, with the "N / total" count just after Next. */}
          {viewMode === 'slides' && deck && (
            <button
              type="button"
              className="cs-slide-nav-button"
              aria-label="Previous slide"
              disabled={slideIndex === 0}
              onClick={() => setSlideIndex((i) => Math.max(i - 1, 0))}
            >
              &larr; Prev
            </button>
          )}
          {/* Cells view: the deck's own title (its filename, server.py's
              /api/deck). Slides view: the current slide's title in this
              same spot instead (the title slide substituting the deck's
              own title too, per displayedSlideTitle's own docstring) --
              same content the collapsed header above already shows, just
              now also shown while the header is expanded. */}
          <h1 className={`cs-app-title ${scrolled ? 'cs-app-title-scrolled' : ''}`}>
            {viewMode === 'slides' ? displayedSlideTitle : (deck?.title ?? '')}
          </h1>
          {viewMode === 'slides' && deck && (
            <>
              <button
                type="button"
                className="cs-slide-nav-button"
                aria-label="Next slide"
                disabled={slideIndex === deck.slides.length - 1}
                onClick={() => setSlideIndex((i) => Math.min(i + 1, deck.slides.length - 1))}
              >
                Next &rarr;
              </button>
              {deck.slides.length > 0 && (
                <span className="cs-slideshow-position">
                  {slideIndex + 1} / {deck.slides.length}
                </span>
              )}
            </>
          )}
        </div>
        <div className="cs-header-controls">
          {deck && (
            <>
              {viewMode === 'cells' && !isViewer && (
                <button type="button" className="cs-add-cell-button" disabled={!sessionId} onClick={handleAddCell}>
                  + Add cell
                </button>
              )}
              {viewMode === 'slides' && !isViewer && (
                <>
                  <button
                    type="button"
                    className="cs-new-slide-button"
                    disabled={!sessionId}
                    onClick={() => setEditSlideDeckOpen((prev) => !prev)}
                  >
                    {editSlideDeckOpen ? 'Close' : 'Edit slide deck'}
                  </button>
                </>
              )}
              <button
                type="button"
                className="cs-view-mode-switch"
                role="switch"
                aria-checked={viewMode === 'slides'}
                aria-label={`Switch to ${viewMode === 'cells' ? 'Slides' : 'Cells'} view`}
                onClick={() => setViewMode(viewMode === 'cells' ? 'slides' : 'cells')}
              >
                <span className={`cs-view-mode-option ${viewMode === 'cells' ? 'cs-view-mode-option-active' : ''}`}>
                  Cells
                </span>
                <span className={`cs-view-mode-option ${viewMode === 'slides' ? 'cs-view-mode-option-active' : ''}`}>
                  Slides
                </span>
                <span
                  className="cs-view-mode-thumb"
                  style={{ transform: viewMode === 'slides' ? 'translateX(100%)' : 'translateX(0)' }}
                />
              </button>
              {!isViewer && (
                <button
                  type="button"
                  className="cs-save-button"
                  disabled={!sessionId || saving}
                  onClick={handleSaveDeck}
                >
                  {saving ? 'Saving…' : 'Save'}
                </button>
              )}
              {!isViewer && saveStatus && (
                <span className={`cs-save-status cs-save-status-${saveStatus.kind}`}>{saveStatus.text}</span>
              )}
            </>
          )}
          {documentId && (
            <PeerList peers={presenceState} ownConnectionId={ownIdentity?.connectionId ?? null} />
          )}
          <div className="cs-help" ref={helpRef}>
            <button
              type="button"
              className="cs-help-button"
              aria-haspopup="dialog"
              aria-expanded={helpOpen}
              aria-label="Keyboard shortcuts"
              onClick={() => setHelpOpen((prev) => !prev)}
            >
              ?
            </button>
            {helpOpen && (
              <div className="cs-help-popover" role="dialog" aria-label="Keyboard shortcuts">
                <h3>Keyboard shortcuts</h3>
                <dl>
                  <dt>Shift+Enter</dt>
                  <dd>Run the current cell</dd>
                  <dt>Mod+Shift+Enter</dt>
                  <dd>Run every cell</dd>
                  <dt>Cmd+Control+Left/Right</dt>
                  <dd>Previous/next slide (Slides view)</dd>
                  <dt>Cmd+Control+Left/Right</dt>
                  <dd>Previous/next cell (Cells view)</dd>
                </dl>
              </div>
            )}
          </div>
        </div>
      </div>
      )}
      {viewMode === 'cells' && (
        <p className="cs-hint">Shift+Enter: run cell &middot; Mod+Shift+Enter: run all</p>
      )}
      {deck && viewMode === 'cells' && (
        <section>
          {Object.entries(deck.cells).map(([cellId, meta], index, entries) => (
            <Cell
              key={cellId}
              cellId={cellId}
              meta={meta}
              lineOffset={cellLineOffsets[cellId] ?? 0}
              onLineCountChange={(count) => handleLineCountChange(cellId, count)}
              state={mergedCellState[cellId]}
              elementValues={elementValues[cellId] ?? {}}
              testSourceValues={testSourceOverrides[cellId] ?? {}}
              collapsed={collapsedCells[cellId] ?? false}
              onRunCell={(source) => handleRunCell(cellId, source)}
              onRunAll={handleRunAll}
              onFocusChange={(focused) => handleCellFocusChange(cellId, focused)}
              onCursorChange={handleCursorChange}
              remotePeers={remotePeersForCell(cellId)}
              onSetElementValue={(elementId, value) => handleSetElementValue(cellId, elementId, value)}
              onChangeNotesSource={(elementId, source) => handleChangeNotesSource(cellId, elementId, source)}
              onChangeTestSource={(elementId, source) => handleChangeTestSource(cellId, elementId, source)}
              onToggleCollapse={() => handleToggleCollapse(cellId)}
              onRenameCell={(newName) => handleRenameCell(cellId, newName)}
              onSetMainCell={() => handleSetMainCell(cellId)}
              onSetSetupCell={() => handleSetSetupCell(cellId)}
              onSetHideCode={(hideCode) => handleSetHideCode(cellId, hideCode)}
              onSetHideDef={(hideDef) => handleSetHideDef(cellId, hideDef)}
              onRemovePrimaryEditor={() => handleRemovePrimaryEditor(cellId)}
              onAddPrimaryEditor={() => handleAddPrimaryEditor(cellId)}
              onAddElement={(name, kind, config) => handleAddElement(cellId, name, kind, config)}
              onRemoveElement={(elementName) => handleRemoveElement(cellId, elementName)}
              onReorderElements={(elementOrder) => handleReorderElements(cellId, elementOrder)}
              onSetElementConfig={(elementId, config) => handleSetElementConfig(cellId, elementId, config)}
              onLayoutChange={(layout) => handleLayoutChange(cellId, layout)}
              editError={editErrors[cellId]}
              viewerMode={isViewer}
              reviewMode={acceptGated}
              ownUserId={ownIdentity?.userId ?? null}
              onStagePrimaryEdit={(source) => handleStagePrimaryEdit(cellId, source)}
              onStageTestEdit={(elementId, source) => handleStageTestEdit(cellId, elementId, source)}
              onStageNotesEdit={(elementId, source) => handleStageNotesEdit(cellId, elementId, source)}
              isDirty={dirtyCells.has(cellId)}
              onPushCellState={() => handlePushCellState(cellId)}
              onDiscardPendingChanges={() => handleDiscardPendingChanges(cellId)}
              onAcceptPush={(proposerUserId) => handleAcceptPush(cellId, proposerUserId)}
              onRejectPush={(proposerUserId) => handleRejectPush(cellId, proposerUserId)}
              onWithdrawPush={() => handleWithdrawPush(cellId)}
              onDeleteCell={isViewer ? undefined : () => handleDeleteCell(cellId)}
              onMoveCellUp={isViewer ? undefined : () => handleReorderCells(cellId, -1)}
              onMoveCellDown={isViewer ? undefined : () => handleReorderCells(cellId, 1)}
              isFirstCell={index === 0}
              isLastCell={index === entries.length - 1}
            />
          ))}
        </section>
      )}
      {deck && viewMode === 'slides' && !headerCollapsed && editSlideDeckOpen && (
        <EditSlideDeckPanel
          slides={deck.slides}
          cellIds={Object.keys(deck.cells)}
          onReorderSlides={handleReorderSlides}
          onAddSlide={handleAddSlide}
          onAddTitleSlide={handleAddTitleSlide}
          onRemoveSlide={handleRemoveSlide}
          addSlideError={addSlideError}
        />
      )}
      {deck && viewMode === 'slides' && (
        <SlideShow
          slides={deck.slides}
          headerCollapsed={headerCollapsed}
          onActiveSlideChange={setActiveSlideTitle}
          index={slideIndex}
          onIndexChange={setSlideIndex}
          cellMeta={deck.cells}
          liveLineCounts={liveLineCounts}
          onLineCountChange={handleLineCountChange}
          cellState={mergedCellState}
          elementValues={elementValues}
          testSourceValues={testSourceOverrides}
          onRunCell={handleRunCell}
          onRunAll={handleRunAll}
          onSetElementValue={handleSetElementValue}
          onChangeNotesSource={handleChangeNotesSource}
          onChangeTestSource={handleChangeTestSource}
          onToggleCollapse={handleToggleCollapse}
          onRenameCell={handleRenameCell}
          onSetMainCell={handleSetMainCell}
          onSetSetupCell={handleSetSetupCell}
          onSetHideCode={handleSetHideCode}
          onSetHideDef={handleSetHideDef}
          onRemovePrimaryEditor={handleRemovePrimaryEditor}
          onAddPrimaryEditor={handleAddPrimaryEditor}
          onAddElement={handleAddElement}
          onRemoveElement={handleRemoveElement}
          onReorderElements={handleReorderElements}
          onSetElementConfig={handleSetElementConfig}
          onLayoutChange={handleLayoutChange}
          editErrors={editErrors}
          viewerMode={isViewer}
          reviewMode={acceptGated}
          ownUserId={ownIdentity?.userId ?? null}
          onStagePrimaryEdit={handleStagePrimaryEdit}
          onStageTestEdit={handleStageTestEdit}
          onStageNotesEdit={handleStageNotesEdit}
          dirtyCells={dirtyCells}
          onPushCellState={handlePushCellState}
          onDiscardPendingChanges={handleDiscardPendingChanges}
          onAcceptPush={handleAcceptPush}
          onRejectPush={handleRejectPush}
          onWithdrawPush={handleWithdrawPush}
        />
      )}
      {documentId && (
        <ChatPanel
          messages={chatMessages}
          ownUserId={ownIdentity?.userId ?? null}
          onSendMessage={handleSendChatMessage}
          expanded={chatExpanded}
          onExpandedChange={setChatExpanded}
        />
      )}
    </main>
  )
}

export default App
