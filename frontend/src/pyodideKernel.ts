// TODO.md #64/PROPOSAL_pyscript_execution.md: client-side cell execution
// via Pyodide. Loads Pyodide once per page load from jsdelivr's public
// CDN, writes the real, unmodified deck.py/graph.py/cs.py/output.py/
// turtle.py into Pyodide's virtual filesystem as a real importable
// `codeslides` package (exactly the FS layout pyscript_spike/
// spike2_real_modules.html already proved works), and exposes
// functions shaped to drop straight into `CellState` (deckState.ts)
// with zero server round trip.
//
// Revisited (#64-v, once the structural-ops/tests-element/loading-
// indicator slices were all proven out): staying on the CDN rather
// than vendoring Pyodide into this repo's own static assets.
// PYODIDE_CDN_URL below pins an exact version (v0.29.4/full), so
// jsdelivr already gives version stability, not a moving target. The
// wasm runtime core alone is ~8.6MB (confirmed against the live CDN
// URL) -- self-hosting the full distribution would mean either
// committing tens of MB into this repo (the same "static/ bundle is
// committed, not gitignored" convention frontend/ already uses for its
// own build output, but at a very different scale) or standing up a
// separate asset pipeline/CDN of this project's own, plus an ongoing
// version-bump maintenance burden, for a widely-used, long-lived
// public CDN with its own global edge caching (likely faster for most
// students than anything this project could host itself) and no
// reported reliability/security incident motivating a change. Worth
// revisiting again only if a real problem with the CDN dependency
// actually surfaces (an outage, a corporate/school network that blocks
// jsdelivr, etc.) -- not proactively.
//
// TODO.md #64 (dependency-graph slice): mirrors kernel.py's
// _effective_graph/on_cell_edited/run_all/_run_cells shape, using the
// real graph.py (build_graph/DependencyGraph.topological_order/
// affected_by -- confirmed pure-stdlib, ported unmodified, per
// PROPOSAL_pyscript_execution.md section 1) rather than a
// reimplementation. Unlike the server, there is no persistent `Deck`
// object here to keep in sync incrementally -- the graph is rebuilt
// from scratch on every call from whatever `{cellName: source}` map the
// caller currently has (App.tsx's own `deck.cells`, the same "full
// current view" data the UI already maintains for other purposes), the
// same way `Kernel._effective_graph` already rebuilds from
// `session.source_overrides` on every call rather than caching an
// incrementally-patched graph. Only `name`/`source` are ever populated
// on the client-side `Cell`/`Deck` objects this constructs -- every
// other field on those dataclasses (elements, layout, is_main, etc.)
// has its own default and is irrelevant to graph-building (this slice
// doesn't touch element/kwarg binding at all yet -- a later slice's
// scope).
//
// The shared per-tab namespace (session.namespace's client-side
// equivalent) is kept entirely on the Python side, as a plain
// module-level dict in the runner module below -- only strings (cell
// names, sources, JSON) cross the JS/Pyodide boundary via
// `runPythonAsync`, the exact mechanism pyscript_spike/index.html
// already proved reliable, rather than round-tripping live Python
// object handles through pyodide's own JS<->Python proxy machinery.

const PYODIDE_CDN_URL = 'https://cdn.jsdelivr.net/pyodide/v0.29.4/full/pyodide.mjs'

// The modules confirmed (PYSCRIPT_SPIKE_FINDINGS.md,
// PROPOSAL_pyscript_execution.md section 1) to run unmodified inside
// Pyodide. deck.py/graph.py joined this list for the dependency-graph
// slice -- see sync-pyscript-modules.mjs's own comment.
const PYODIDE_MODULE_FILES = ['deck.py', 'graph.py', 'cs.py', 'output.py', 'turtle.py']

export interface PyodideElementWrite {
  elementName: string
  kind: string
  content: unknown
}

export interface PyodideCellResult {
  status: 'idle' | 'error'
  value: unknown
  kind: 'text' | 'markdown' | 'image' | 'dataframe' | null
  data: unknown
  error: string | null
  stdout: string
  stderr: string
  // kernel.py's execute_cell only ever returns element_writes for a
  // SUCCESSFUL run (ExecutionResult's own default is []); an error
  // result never carries any, matching that -- see this file's own
  // execute_cell docstring for why (a failed cell must not leave any
  // partial viewer-content change behind).
  elementWrites: PyodideElementWrite[]
}

// name/kind/config, matching ElementMeta (widgets/elementMeta.ts) --
// this is App.tsx's own per-cell deck.cells[id].elements, passed
// through unmodified so the Pyodide runner can bind input-element
// values as kwargs and know which elements exist for cs.*'s own
// "no such element" validation, exactly like kernel.py's execute_cell.
export interface PyodideElementMeta {
  name: string
  kind: string
  config: Record<string, unknown>
}

export interface PyodideCellInput {
  source: string
  elements: PyodideElementMeta[]
}

// A debug run's row-per-loop-iteration, snapshot-per-breakpoint-hit
// trace (_make_loop_tracer's own _new_loop_table/_new_iteration_row
// shapes, pyodideKernel.ts's shared Python runner) -- recursive:
// childTables under a given row index holds that SAME table shape
// again for a loop that ran during that one parent iteration, one
// entry per time that inner loop started fresh within that parent row
// (almost always one entry in practice, but never assumed -- see
// _new_loop_table's own docstring on why it's a list, not a single
// nested table). loopId is null only for the single synthetic root
// table every debug run starts with (never a real source line),
// letting TestsElementWidget.tsx/Cell.tsx render "no loop at all" and
// "inside a loop" through the one same component, rather than a
// separate branch for each.
export interface PyodideIterationTable {
  loopId: number | null
  startLine: number | null
  // Union of every variable name that appeared in ANY snapshot in ANY
  // row of this table, in first-seen order -- the iteration counter
  // itself is NEVER a member (it's PyodideIterationRow's own dedicated
  // `iteration` field, not a snapshot value), so a table with columns
  // === [] genuinely means "no breakpoint was ever hit in this loop
  // at all," not "only the counter was ever recorded."
  columns: string[]
  rows: PyodideIterationRow[]
  childTables: Record<string, PyodideIterationTable[]>
}

// One loop iteration's own trace. `snapshots` is an ORDERED list of
// {variable: repr string} objects, one per breakpoint hit during this
// iteration, in hit order -- this is what makes "one step per
// breakpoint hit within an iteration, not one step per iteration"
// possible (iterationSteps.ts/IterationTable.tsx): stepping through a
// row's own snapshots in order updates ITS displayed values live,
// without the step cursor moving to a different row. `snapshots` can
// be EMPTY -- an iteration that never hit any breakpoint inside the
// loop's body still gets a row (for iteration-counting purposes), it's
// just rendered blank (see IterationTable.tsx). A snapshot missing a
// given column entirely (rather than holding an empty string) is what
// tells the renderer to show a blank cell for a variable not yet
// assigned as of that specific breakpoint hit.
export interface PyodideIterationRow {
  iteration: number
  snapshots: Record<string, string>[]
}

// run_cell_with_breakpoints_b64's own result shape -- deliberately its
// own type, not PyodideCellResult, since a debug run never produces
// elementWrites (cs.image()/turtle canvas writes are still recorded
// server^Wclient-side but a debug run's whole point is inspecting the
// cell's own step-by-step state, not updating other elements) and adds
// iterationTable/truncated that an ordinary run has no use for.
export interface PyodideDebugRunResult {
  status: 'idle' | 'error'
  error: string | null
  stdout: string
  stderr: string
  iterationTable: PyodideIterationTable
  // True once _MAX_DEBUG_ITERATIONS (500) rows were recorded for some
  // one loop and tracing was turned off for the rest of the run -- the
  // cell's function still ran to completion either way (see
  // _debug_run_one's own docstring: this only stops RECORDING further
  // rows, never aborts execution), so truncated is purely an
  // informational flag for the UI to show a "stopped recording after
  // 500 iterations" notice.
  truncated: boolean
  finalValue?: unknown
  finalKind?: 'text' | 'markdown' | 'image' | 'dataframe' | null
  finalData?: unknown
}

// TODO.md #64/PROPOSAL_pyscript_execution.md section 7: kernel.py's own
// run_tests result shape (ARCHITECTURE.md section 3b) -- status is
// "pass"/"fail"/"error" (never "idle", unlike PyodideCellResult: a
// tests element's own status vocabulary has always been distinct from
// a cell's own run status, see TestsElementWidget's own TestResult
// type). turtleCommands mirrors PyodideElementWrite's own turtle
// content shape (a list of command dicts), present only when the
// owning cell has a turtle_canvas element, same "ambiguous means none"
// rule run_tests itself documents.
export interface PyodideTestResult {
  status: 'pass' | 'fail' | 'error'
  message: string
  stdout: string
  stderr: string
  turtleCommands: unknown[] | null
}

// run_test_with_breakpoints_b64's own result shape -- PyodideTestResult's
// status vocabulary ('pass'/'fail'/'error', not PyodideDebugRunResult's
// 'idle'/'error') plus PyodideDebugRunResult's own iterationTable/
// truncated, since a tests-element debug run is "the step-through
// debugger, but for test source" -- see _debug_run_test's own docstring
// for why its iterationTable never includes turtleCommands or a final
// value the way a cell's own debug run does (a test has no single
// "return value", and the debugger's own point here is inspecting the
// test's line-by-line state, not its drawing).
export interface PyodideTestDebugRunResult {
  status: 'pass' | 'fail' | 'error'
  message: string
  stdout: string
  stderr: string
  iterationTable: PyodideIterationTable
  truncated: boolean
}

// Minimal ambient shape for what this module actually calls on a
// loaded Pyodide instance -- not a full @types/pyodide surface (the
// full types package targets the npm-bundled runtime; this loads from
// a CDN script instead, per the hosting decision in the module
// docstring above), just enough to keep this file itself type-checked.
interface PyodideInterface {
  runPythonAsync(code: string): Promise<unknown>
  loadPackage(names: string | string[]): Promise<unknown>
  FS: {
    mkdirTree(path: string): void
    writeFile(path: string, data: string): void
  }
}

declare global {
  interface Window {
    __loadPyodideImpl?: (options?: Record<string, unknown>) => Promise<PyodideInterface>
  }
}

let pyodidePromise: Promise<PyodideInterface> | null = null

// TODO.md #64/PROPOSAL_pyscript_execution.md: cold-start loading state
// (PROPOSAL_pyscript_execution.md's own "measure and address cold-start
// latency" follow-up, first called out once the structural-ops/
// tests-element slices made it clear every cell run now genuinely
// depends on Pyodide's own ~several-second first-load). App.tsx has no
// other way to know whether Pyodide is still loading -- getPyodide's
// own pyodidePromise above is module-private, and nothing about the
// existing run*ClientSide functions' own Promise return value
// distinguishes "was already loaded, ran instantly" from "just spent 5
// seconds loading Pyodide before this call's own work even started."
// A plain module-level status + subscriber list (not a React hook
// itself -- this file has no framework dependency today, and adding
// one just for this would be a bigger change than the loading
// indicator itself needs) lets App.tsx subscribe via
// subscribePyodideStatus and mirror it into its own React state.
export type PyodideStatus = 'idle' | 'loading' | 'ready' | 'error'

let pyodideStatus: PyodideStatus = 'idle'
const pyodideStatusListeners = new Set<(status: PyodideStatus) => void>()

function setPyodideStatus(status: PyodideStatus): void {
  pyodideStatus = status
  for (const listener of pyodideStatusListeners) listener(status)
}

export function getPyodideStatus(): PyodideStatus {
  return pyodideStatus
}

// Returns an unsubscribe function, the usual DOM/React-friendly
// listener contract (matches window.addEventListener's own
// removeEventListener-via-closure idiom) so a useEffect can clean up
// on unmount without needing to keep the original callback reference
// around separately.
export function subscribePyodideStatus(listener: (status: PyodideStatus) => void): () => void {
  pyodideStatusListeners.add(listener)
  return () => {
    pyodideStatusListeners.delete(listener)
  }
}

function loadPyodideScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.type = 'module'
    script.textContent = `import { loadPyodide } from '${src}'; window.__loadPyodideImpl = loadPyodide;`
    script.onerror = () => reject(new Error(`failed to load ${src}`))
    document.head.appendChild(script)
    // The module script above assigns window.__loadPyodideImpl
    // asynchronously (ES module evaluation) -- poll briefly rather
    // than relying on script.onload, which fires for the *script tag*
    // loading, not the module's own top-level code finishing.
    const start = Date.now()
    const check = () => {
      if (window.__loadPyodideImpl) {
        resolve()
        return
      }
      if (Date.now() - start > 30000) {
        reject(new Error('timed out waiting for Pyodide module script to load'))
        return
      }
      setTimeout(check, 50)
    }
    check()
  })
}

// TODO.md #64: mirrors kernel.py's execute_cell + Kernel._run_cells +
// output.py's resolve_output/wire_safe_value, and graph.py's own
// build_graph/affected_by/topological_order for real cross-cell
// reactivity. TODO.md #64 (element/input-binding slice) adds input-
// element (slider/text_input/button) kwargs binding and cs.*
// viewer-element writes (image/iframe), mirroring execute_cell's own
// params/cs.execution_context() handling. TODO.md #64 (turtle-canvas
// slice) adds turtle.execution_context() (codeslides.turtle -- already
// pure stdlib/contextvars, no changes needed, same as cs.py) for cells
// with exactly one turtle_canvas element, mirroring execute_cell's own
// _maybe_turtle_context/_find_turtle_canvas. Still deliberately without
// deck_imports or is_main handling (later slices).
// `_namespace` is one plain module-level dict, shared across every
// `run_cells`/`run_all` call for the life of this page load -- the
// client-side equivalent of session.namespace, scoped to this one
// browser tab (PROPOSAL_pyscript_execution.md section 2.1: no
// execution state of any kind is ever shared across tabs). `_element_values`
// is this tab's equivalent of session.instances[cell].elements[el].value
// -- also module-level and persistent across calls, so a slider's
// position (set via on_element_changed_b64) survives independently of
// whatever run_cell_and_dependents_b64/run_all_b64 call comes next,
// exactly like a Session's own ElementInstance.value does.
const RUNNER_MODULE_PYTHON = `
import ast
import base64
import io
import json
import contextlib
import sys
import textwrap
import traceback

from codeslides import cs, turtle
from codeslides import output as _output
from codeslides.deck import Cell, Deck, Element
from codeslides.graph import build_graph, extract_return_names

_namespace = {}

# kernel.py seeds every cell's __globals__ (session.namespace) with these
# two names before any execution (execute_cell/run_tests/run_all's own
# per-run seeding, kernel.py lines ~407/549/737) -- a plain "import
# codeslides as cs" isn't how a cell's source actually gets cs/turtle
# at all; the deck author's source never imports them itself (see
# examples/live_demo.py), the runtime injects them by name instead.
# deck_imports (the third thing kernel.py seeds alongside these) is
# handled separately, by set_deck_imports_b64 below -- unlike cs/turtle,
# it isn't known yet at this point (it comes from the deck's own .py
# file, fetched over /api/deck, which resolves after this module already
# finished loading), so it can't be seeded here.
_namespace["cs"] = cs
_namespace["turtle"] = turtle

# The exact key set of _namespace at this point -- before any cell or
# test has ever run in this tab -- is the stable "not a test's own
# variable" baseline _debug_run_test's own tracer filtering needs (see
# _make_snapshot_tracer's own exclude_keys docstring for why this must
# never be recomputed from _namespace's own CURRENT keys at debug-run
# time: cs/turtle only ever get added here, once, at this exact line,
# for the rest of this tab's whole lifetime -- capturing it now, and
# only now, is what makes it stable across every later cell definition/
# execution/test run this tab will ever do). Every cell name defined
# after this point is also excluded (see run_test_with_breakpoints_b64),
# but this constant only needs to cover what's seeded here, since a
# cell's own name is never a key in _namespace until _define_one/
# _execute_one actually runs it -- there's nothing else this baseline
# needs to capture.
_NAMESPACE_BASELINE_KEYS = frozenset(_namespace.keys())

# Cell names that have been executed at least once in this tab's session
# (i.e. are already bound into _namespace). Server-side, Kernel.on_cell_edited
# can assume every upstream cell already has a value in session.namespace,
# because that namespace persists across the whole session and run_all (or
# earlier edits) has always populated it first. A fresh browser tab has no
# such guarantee -- its first action might be editing a downstream cell
# that reads a name from a cell (e.g. "setup") the user never directly
# touched. _run_once tracks what's actually been executed here so we can
# detect and backfill missing upstream dependencies before running the
# edited cell itself.
_run_once = set()

# Every name any cell's own return name/return a, b has EVER bound
# into _namespace, across this tab's whole lifetime (_execute_one/
# _debug_run_one both add to this at the same point they write the
# value itself into _namespace) -- needed by _debug_run_test's own
# exclude_keys construction: a cell's return-named value (e.g. base
# from a setup cell returning base) is otherwise indistinguishable
# from a name a TEST itself assigned, since both are just plain
# top-level names in the one shared _namespace dict with no marker of
# which cell (if any) produced them. Deliberately never removed once
# added (even if that cell is later deleted/renamed) -- a stale
# leftover name being over-excluded from a future test's own variable
# snapshot is a far smaller cost than a genuinely different cell's
# return value being wrongly shown as if the test had assigned it.
_RETURN_NAMED_VALUES = set()

# cell_name -> {element_name: value}. Only ever holds entries for input
# elements (slider/button/text_input) that on_element_changed_b64 has
# actually set at least once -- an element never touched by the user yet
# simply isn't a key here, and _execute_one's kwargs binding below falls
# back to the element's own config["default"] in that case (Element's
# own config, not a separate seeding step -- see _build_deck).
_element_values = {}

def _decode(b64):
    return base64.b64decode(b64).decode("utf-8")

# Whether set_deck_imports_b64 (below) has already run once in this
# tab. deck.module_import_source (server.py's /api/deck) is static for
# the lifetime of a page load -- the same deck file's own top-level
# imports never change between an ordinary cell run and the next -- so
# there's nothing to gain by re-exec'ing the same statements on every
# single run_all/run_cell call the way App.tsx's callers already do for
# _build_deck's own cells_json_b64 (which genuinely does change on every
# call, as the user edits). Guarding this means the *caller* doesn't
# need its own bookkeeping for "have I already called this" -- it's
# always safe (and a no-op past the first call) to call
# set_deck_imports_b64 again, which matters because App.tsx fetches
# /api/deck (and so learns module_import_source) asynchronously,
# possibly interleaved with the very first run_all triggered by the
# same page load.
_deck_imports_applied = False

def set_deck_imports_b64(module_import_source_b64):
    """The client-side equivalent of kernel.py's deck_imports seeding
    (execute_cell/run_tests/run_all's own '**(deck_imports or {})'):
    exec module_import_source_b64 (deck.module_import_source, server.py's
    /api/deck -- the deck's own top-level import/from...import
    statements, exactly as written in its .py file, already stripped of
    any noop 'import turtle' by loader.py's own
    _module_level_import_source) directly into _namespace, so every cell
    sees the same names a deck-wide 'import random' at the top of the
    file would bind in an ordinary script -- instead of only whichever
    cell happens to import random itself (previously the ONLY way any
    cell got a deck-level import client-side, since this function didn't
    exist -- confirmed by hand: examples/marchingSquares.py's
    createMatrix reads random.randint(...) but never imports random
    itself, relying entirely on the file's own top-level 'import random'
    the same way any other cell already relies on cs/turtle being
    present without importing them).

    Also folds the newly-bound names into _NAMESPACE_BASELINE_KEYS (the
    "not a test's own variable" snapshot _debug_run_test's tracer
    filtering relies on) -- without this, a deck-level random would be
    wrongly reported as if a test itself had just assigned it, the exact
    failure mode that constant's own docstring already describes for
    cs/turtle, just reached through a different seeding path.

    Idempotent (via _deck_imports_applied) and safe to call with an
    empty string (an in-process-only Deck with no backing file, or the
    empty default before /api/deck resolves) -- exec("", ...) is a
    harmless no-op, so callers never need to special-case "nothing to
    import" themselves."""
    global _deck_imports_applied, _NAMESPACE_BASELINE_KEYS
    if _deck_imports_applied:
        return
    source = _decode(module_import_source_b64)
    before = set(_namespace.keys())
    exec(compile(source, "<deck-imports>", "exec"), _namespace)  # noqa: S102 - deck's own trusted source
    new_keys = set(_namespace.keys()) - before
    _NAMESPACE_BASELINE_KEYS = frozenset(_NAMESPACE_BASELINE_KEYS | new_keys)
    _deck_imports_applied = True

def _build_deck(cells_json_b64):
    """cells_json_b64 decodes to a JSON object of
    {cell_name: {"source": str, "elements": [{"name", "kind", "config"}]}}
    -- the caller's full current view of the deck (App.tsx's own
    deck.cells), same "rebuild fresh every call" shape
    Kernel._effective_graph already uses server-side. Only name/source/
    elements are populated on each Cell -- every other field defaults,
    and is irrelevant to graph-building or kwargs binding (this slice
    still doesn't touch layout/is_main/deck_imports)."""
    raw_cells = json.loads(_decode(cells_json_b64))
    cells = {}
    for name, raw in raw_cells.items():
        elements = [
            Element(name=e["name"], kind=e["kind"], config=e.get("config") or {})
            for e in raw.get("elements", [])
        ]
        cells[name] = Cell(name=name, source=raw["source"], elements=elements)
    return Deck(cells=cells)

def _return_names_for(source):
    """kernel.py's _compile_cell_function parses the cell's source to
    find its single function def and extract_return_names(func) from it
    -- replicated here (rather than re-deriving from graph.py's own
    parsed Cell.writes, which also folds in global-declared names and
    the cell's own implicit self-write) because only the return-name
    subset determines what execute_cell binds the call's result under."""
    tree = ast.parse(source)
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        raise ValueError(f"expected exactly one function definition, found {len(func_defs)}")
    return extract_return_names(func_defs[0])

def _strip_noop_turtle_imports(stmts):
    """Port of kernel.py's strip_noop_turtle_imports: drop every bare
    'import turtle' statement (not 'import turtle as t', not 'from
    turtle import forward') from a cell function's body before it's
    compiled/exec'd. _namespace["turtle"] (see above) already IS
    codeslides.turtle for every cell -- a real 'import turtle' executing
    here would try to import the actual stdlib module, which doesn't
    exist at all in this Pyodide runtime (no tkinter), turning any cell
    whose on-disk source keeps 'import turtle' for its OWN "also runs
    standalone via python3 my_lesson.py" purpose (examples/
    marchingSquares.py's setup cell, among others) into a guaranteed
    ModuleNotFoundError the moment it runs in-app. kernel.py's server-side
    _compile_cell_function already stripped this same statement before
    the client-side Pyodide port (TODO.md #64) replaced it; porting the
    exec call without also porting this step is exactly what let the
    ModuleNotFoundError back in here."""
    return [
        stmt
        for stmt in stmts
        if not (
            isinstance(stmt, ast.Import)
            and len(stmt.names) == 1
            and stmt.names[0].name == "turtle"
            and stmt.names[0].asname is None
        )
    ]

def _compile_cell(source, filename):
    """Parse a cell's source, strip any noop 'import turtle' from its
    one function's body (_strip_noop_turtle_imports), and compile the
    result -- the exact AST-level equivalent of what kernel.py's
    _compile_cell_function does server-side, replicated here (rather
    than reused) because that function also rebuilds a fresh
    types.FunctionType bound to a different __globals__ dict, a step
    every call site here already does its own way via plain
    exec(..., _namespace). Every site that exec(compile(source, ...))s
    a CELL's own source (never a test box's source -- kernel.py's own
    run_tests never strips this either, see its docstring) should call
    this instead of compile() directly."""
    tree = ast.parse(source)
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) == 1:
        func_defs[0].body = _strip_noop_turtle_imports(func_defs[0].body)
        ast.fix_missing_locations(tree)
    return compile(tree, filename, "exec")

_INPUT_KINDS = {"slider", "button", "text_input"}

def _kwargs_for(cell_name, fn, elements):
    """Bind each input element (slider/button/text_input) whose name is
    also one of fn's own declared parameters -- exactly execute_cell's
    own params = fn.__code__.co_varnames[:argcount] / "if element_name
    in params" filter, so a cell with elements the function doesn't
    actually take as arguments (e.g. only used inside the body via
    module-level input(), or not read at all) doesn't get a spurious
    TypeError from an unexpected kwarg. Falls back to the element's own
    declared config["default"] (ui.slider/ui.text_input's own default=,
    ui.button has none) when on_element_changed_b64 has never set this
    element for this cell -- same as a Session's ElementInstance.value
    starting at its seeded default until the user actually touches it."""
    params = set(fn.__code__.co_varnames[: fn.__code__.co_argcount])
    values = _element_values.get(cell_name, {})
    kwargs = {}
    for element in elements:
        if element.kind not in _INPUT_KINDS or element.name not in params:
            continue
        if element.name in values:
            kwargs[element.name] = values[element.name]
        else:
            kwargs[element.name] = element.config.get("default")
    return kwargs

def _find_turtle_canvas(elements):
    """kernel.py's own _find_turtle_canvas, unchanged: the cell's one
    turtle_canvas element, if it has exactly one -- codeslides.turtle
    calls have no way to name a target themselves (unlike cs.image/
    cs.iframe) without breaking stdlib turtle call syntax, so zero or
    more than one canvas is treated the same as none; turtle calls will
    raise from turtle._state() either way."""
    canvases = [e.name for e in elements if e.kind == "turtle_canvas"]
    return canvases[0] if len(canvases) == 1 else None

def _execute_one(cell_name, source, elements):
    """Mirrors kernel.py's execute_cell: run the cell's function against
    the shared _namespace (its real __globals__, via plain exec into
    _namespace itself -- so a global x write lands permanently, same
    guarantee _compile_cell_function documents), bind input-element
    values as kwargs (_kwargs_for), run the call inside
    cs.execution_context() (so cs.image()/cs.iframe() calls have
    somewhere to record their writes) and, when the cell has exactly one
    turtle_canvas element, also inside turtle.execution_context() (same
    "only establish it when there's a valid target" rule as kernel.py's
    _maybe_turtle_context -- a cell with zero or multiple canvases still
    runs, its turtle.* calls just raise from turtle._state(), reported
    as this cell's own error like any other exception), then --
    critically -- bind the call's result back into _namespace under its
    return-named name(s) (kernel.py lines ~471-485), exactly like a bare
    'return name' or 'return a, b' cell publishes name/a/b for any other
    cell to read by ordinary Python name resolution. Without that step,
    a downstream cell reading an upstream cell's returned value (not
    just calling its function directly) would always see a NameError,
    regardless of run order."""
    stdout, stderr = io.StringIO(), io.StringIO()
    turtle_element = _find_turtle_canvas(elements)
    try:
        return_names = _return_names_for(source)
        exec(_compile_cell(source, f"<cell:{cell_name}>"), _namespace)
        fn = _namespace[cell_name]
        kwargs = _kwargs_for(cell_name, fn, elements)
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            writes = stack.enter_context(cs.execution_context())
            turtle_commands = (
                stack.enter_context(turtle.execution_context()) if turtle_element is not None else None
            )
            value = fn(**kwargs)
        if len(return_names) == 1:
            _namespace[return_names[0]] = value
            _RETURN_NAMED_VALUES.add(return_names[0])
        elif len(return_names) > 1:
            values = value if isinstance(value, tuple) else (value,)
            if len(values) != len(return_names):
                raise ValueError(
                    f"cell {cell_name!r} returned {len(values)} values for {len(return_names)} names"
                )
            for name, item in zip(return_names, values):
                _namespace[name] = item
                _RETURN_NAMED_VALUES.add(name)
        # kernel.py's own execute_cell folds the turtle write into the
        # same writes list cs.image/cs.iframe populate (both go
        # through the identical "validate every element name, then
        # apply all-or-nothing" handling below) -- replicated here
        # rather than treated as a separate append after validation, so
        # an invalid turtle_canvas element name (impossible in practice
        # since _find_turtle_canvas only ever returns a name that's
        # actually in elements, but kept for exact parity) hits the
        # same check.
        if turtle_commands and turtle_element is not None:
            writes.append(cs.ElementWrite(element_name=turtle_element, kind="turtle", content=turtle_commands))
        element_names = {e.name for e in elements}
        for write in writes:
            if write.element_name not in element_names:
                raise RuntimeError(
                    f"cell {cell_name!r} called cs.{write.kind}({write.element_name!r}, ...) "
                    f"but has no element named {write.element_name!r}"
                )
    except Exception:
        return {
            "status": "error",
            "value": None,
            "kind": None,
            "data": None,
            "error": traceback.format_exc(),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "elementWrites": [],
        }
    resolved = _output.resolve_output(value)
    return {
        "status": "idle",
        "value": _output.wire_safe_value(value),
        "kind": resolved.kind,
        "data": resolved.data,
        "error": None,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "elementWrites": [
            {"elementName": w.element_name, "kind": w.kind, "content": w.content} for w in writes
        ],
    }

_MAX_DEBUG_SNAPSHOTS = 500

def _safe_repr(value):
    """Shared by every debug-run tracer below: a repr() that itself
    raises (a buggy __repr__) is caught per-variable so one bad object
    can't blow up an entire snapshot.

    A str containing a real newline is deliberately returned RAW here,
    never through repr() -- repr() would escape it to the two literal
    characters backslash-n (Python's own str.__repr__ behavior), which
    the frontend's variables table would then display exactly as typed,
    "line1\\nline2", rather than as two visually separate lines. The
    frontend's own CSS (.cs-cell-debugger-var-value, App.css) renders
    this raw value with white-space: pre-wrap, so an actual embedded
    newline character here becomes a real line break there -- this
    function's OWN job is only to make sure the character survives
    this far unescaped for a multi-line string specifically. A
    single-line str still goes through ordinary repr() (kept quoted,
    e.g. 'hello') so it stays visually distinct from a non-string value
    -- only a genuinely multi-line string trades that quoting away for
    readability, matching how a real Python REPL's own print(s) (not
    repr(s)) shows a multi-line string."""
    try:
        if isinstance(value, str) and "\\n" in value:
            return value
        return repr(value)
    except Exception as exc:
        return f"<repr() failed: {exc!r}>"

_MAX_DEBUG_ITERATIONS = 500

def _find_loops(source):
    """Statically maps every line of source to the ordered chain of
    while/for loops it's lexically nested inside (outermost first),
    keyed by loop identity ("loopId") -- the 1-based line number of the
    loop's own while/for statement, stable across the whole run
    since it's fixed by the source text, never by execution order.
    Built once per debug run via a single ast.walk, not per traced
    line, so the tracer's own per-line work stays O(1) lookups into
    the dicts this returns.

    Returns (line_to_loop_chain, loop_first_body_line, loop_header_line):
    - line_to_loop_chain: {line_no: [loopId, ...]} -- every line that
      is reachable from inside at least one loop, mapped to the full
      chain of loopIds it's nested in (outer to inner). A line outside
      any loop is simply absent (never an empty list), so checking
      "line in line_to_loop_chain" alone answers "is this line inside
      a loop at all" without a separate membership check.
    - loop_first_body_line: {loopId: line_no} -- the line number of the
      very FIRST statement in that loop's own body (not the while/for
      line itself). This is the line the tracer watches re-execution of
      to detect a new iteration: a while/for loop's condition check
      itself fires on every pass (including the one that exits the
      loop, which never re-enters the body), but the body's first
      statement only ever executes once per actual iteration, and
      always as that iteration's very first line -- true regardless of
      any if/else branching deeper in the body, since it's the one
      statement every iteration is guaranteed to reach before any
      branch point. A loop with an empty body (only pass) still has
      exactly one such line, pass itself.
    - loop_header_line: {loopId: line_no} -- the line number of the
      while/for statement itself (== loopId, returned as its own dict
      purely so the tracer doesn't need to remember "loopId IS a line
      number" as a separate fact). sys.settrace's own 'line' events fire
      BEFORE a line runs, so the truly final post-body state of a
      loop's LAST iteration is never directly observable at any body
      line -- it only becomes visible as the seed for a next iteration's
      row, which doesn't exist once the loop is exiting. The tracer
      additionally watches re-hits of this header line specifically to
      backfill that last row with its real final values right before
      the loop condition is re-evaluated and (assuming it's now False)
      the loop exits -- see _make_loop_tracer's own docstring.
    - loop_by_header_line: {line_no: loopId} -- the exact inverse of
      loop_header_line, so the tracer can go straight from "which line
      just fired" to "which loop's own last row does this backfill,"
      given the header line is deliberately NOT itself a member of any
      chain in line_to_loop_chain (see the "outer chain" comment below).
    - loop_parent_chain: {loopId: [loopId, ...]} -- the SAME chain a
      body line inside this loop would have, EXCLUDING the loop's own
      id (i.e. line_to_loop_chain[loop_first_body_line[loopId]] with
      the last element dropped) -- how the tracer descends root_table's
      own nesting to reach the correct table to append this loop's next
      row into, or backfill its last row, without needing a body line's
      chain as a stand-in for the header line's own position.

    A nested loop's own lines are included in both the outer loop's
    line_to_loop_chain entries (with the outer loop's id first) and the
    inner loop's own entries -- e.g. line 5 inside an inner loop nested
    in an outer loop starting at line 2 maps to [2, 5], not just [5]."""
    line_to_loop_chain = {}
    loop_first_body_line = {}
    loop_header_line = {}
    loop_parent_chain = {}

    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return line_to_loop_chain, loop_first_body_line, loop_header_line, {}, loop_parent_chain

    def walk(node, chain):
        is_loop = isinstance(node, (ast.While, ast.For, ast.AsyncFor))
        my_chain = chain
        if is_loop:
            loop_id = node.lineno
            my_chain = chain + [loop_id]
            loop_header_line[loop_id] = node.lineno
            loop_parent_chain[loop_id] = list(chain)
            if node.body:
                loop_first_body_line[loop_id] = node.body[0].lineno
        header_children = (getattr(node, "test", None), getattr(node, "iter", None), getattr(node, "target", None))
        for child in ast.iter_child_nodes(node):
            # A loop's own header expressions (While.test, For.iter/
            # target) belong to the OUTER chain, not the loop they
            # introduce -- "while x > 0:" itself isn't "inside" the loop
            # it opens, matching how Python only re-enters the BODY each
            # iteration, never re-executes the header line as a body
            # statement. Registered (and recursed into) using chain,
            # never my_chain, so the while/for line itself is never
            # marked as belonging to its own loop.
            child_chain = chain if (is_loop and child in header_children) else my_chain
            if hasattr(child, "lineno") and child_chain:
                line_to_loop_chain.setdefault(child.lineno, child_chain)
            walk(child, child_chain)

    for top in tree.body:
        walk(top, [])

    loop_by_header_line = {line: loop_id for loop_id, line in loop_header_line.items()}
    return line_to_loop_chain, loop_first_body_line, loop_header_line, loop_by_header_line, loop_parent_chain

def _new_loop_table(loop_id, start_line):
    """One loop's own trace: columns in first-seen order (union of
    every variable name that appeared in ANY snapshot anywhere in this
    table's own rows -- the counter itself is a dedicated per-row field,
    never a column, see _new_iteration_row's own docstring), rows one
    per iteration (_new_iteration_row), and childTables mapping a
    PARENT row's index (as a str, since this whole structure round-
    trips through json.dumps/JSON.parse) to the list of nested-loop
    tables that ran during that one parent iteration -- a list, not a
    single table, since the same inner loop can start fresh multiple
    times across different iterations of the outer loop, and each such
    run is its own independent set of rows, never appended onto a
    prior run's leftover rows from an earlier outer iteration."""
    return {"loopId": loop_id, "startLine": start_line, "columns": [], "rows": [], "childTables": {}}

def _new_iteration_row(iteration):
    """One loop iteration's own trace: iteration is the 1-based
    counter (previously stored as an ordinary column value under a
    caller-chosen key like "iteration" -- now a dedicated field, since
    it's the same for every snapshot within this one row and isn't
    itself a breakpoint-hit snapshot). snapshots is an ORDERED list
    of {variable: repr string} dicts, one per breakpoint hit that
    occurred during this iteration, in the order they were hit --
    empty if no breakpoint inside the loop's body was ever hit during
    this particular iteration (the row still exists, for iteration-
    counting purposes, it's just blank when rendered -- see the
    frontend's own IterationTable.tsx). This is the shape that makes
    "one step per breakpoint hit, not one step per iteration" possible:
    stepping through this row's own snapshots in order updates its
    displayed values live, without changing which ROW is showing."""
    return {"iteration": iteration, "snapshots": []}

def _make_loop_tracer(
    filename,
    line_to_loop_chain,
    loop_first_body_line,
    loop_header_line,
    loop_by_header_line,
    loop_parent_chain,
    breakpoint_lines,
    stdout,
    root_table,
    truncated,
    exclude_keys=frozenset(),
    exclude_dunders=False,
):
    """Builds a sys.settrace-compatible tracer recording a ROW-PER-
    ITERATION, SNAPSHOT-PER-BREAKPOINT-HIT trace: every loop iteration
    still gets its own row (_new_iteration_row), but a row's content is
    now an ORDERED LIST of snapshots -- one per breakpoint hit during
    that iteration, in hit order -- rather than one continuously-merged
    set of values. This is what lets the frontend step through each
    breakpoint hit individually within a single row (IterationTable.tsx/
    iterationSteps.ts), updating that row's displayed values live as
    the step cursor advances through its own snapshots, instead of
    jumping straight to the row's own final state.

    breakpoint_lines GATES snapshot recording specifically (a line only
    ever produces a snapshot if it's in this set) -- this reintroduces
    the precondition PR #55 removed ("no breakpoints set" now once again
    means "nothing to step through," matching the very original step-
    scrubber's own contract) -- but iteration-BOUNDARY detection below
    is intentionally NOT gated by it: every loop still gets a row for
    every iteration it actually ran, breakpoints or not, so the row/
    iteration COUNT stays accurate even when a particular iteration
    never hit a breakpoint at all (that row just ends up with an empty
    snapshots list -- still shown, just blank, per the accepted design;
    see IterationTable.tsx).

    root_table is the caller's own mutable dict (not created here, same
    "caller keeps a handle to read after sys.settrace(None)" pattern
    _make_snapshot_tracer already uses for snapshots/truncated) --
    ALWAYS a loop-table shape (_new_loop_table), even for code with no
    real loop at all: every line traced outside any loop lands in
    root_table's own single row (never a new row per line -- there's no
    iteration to delimit it), giving TestsElementWidget.tsx/Cell.tsx one
    consistent table shape to render regardless of whether the traced
    code has a loop, per the accepted "single-row fallback, not a
    separate no-loop view" design -- that one row can still accumulate
    multiple snapshots, one per breakpoint hit outside any loop.

    THE HARD PART -- detecting a genuine new iteration -- is NOT done
    by watching a loop's first body line, even though that sounds like
    the obvious signal. It breaks the moment a loop's first body
    statement is itself ANOTHER loop's header (e.g. "for row in
    range(3):" immediately followed by "for col in range(3):" with
    nothing else in the outer body) -- that inner header line then
    fires several times per OUTER iteration (once per inner iteration
    attempt), not once, so "first body line was hit" massively
    overcounts the outer loop's own rows. Reproduced and fixed while
    building this: see the git history/PR description for the
    intermediate broken attempts if you're touching this again.

    The actually-correct signal is a loop's own HEADER line
    (loop_by_header_line) -- Python's own sys.settrace fires a 'line'
    event there exactly once per iteration ATTEMPT: every time the
    condition is (re-)checked or the next item requested, whether or
    not the loop ends up continuing. confirmed[loop_id] (a dict local
    to this tracer's own closure, not part of the table structure
    itself) tracks whether the CURRENT speculative row -- the one
    started at this loop's most recent header hit -- has since been
    confirmed real by at least one actual body-line execution (this
    check is INDEPENDENT of breakpoints -- even a body line that's
    never a breakpoint still confirms the row is real, it just never
    contributes a snapshot to it). current_table[loop_id] caches the
    ACTUAL table dict object that row currently lives in -- see this
    closure's own comment just above its declaration for why re-
    deriving that object on every access (by re-descending root_table's
    own nesting from scratch) is unsound: an ancestor loop's own row
    count can advance in between two operations meant to target the
    SAME still-pending row, silently misdirecting a later pop onto the
    wrong (not-yet-existing) table:

    - On a header hit for loop_id: if confirmed.get(loop_id) is
      False, the PREVIOUS speculative row was never confirmed (the
      loop just exited without that attempted iteration ever really
      starting) -- pop it from current_table[loop_id] and clear that
      cache entry (the next line below re-derives it fresh, correctly
      landing under whatever the loop's parent row now is). Then
      (re-)descend to loop_id's own table, cache it into
      current_table[loop_id], append a fresh, empty row (_new_
      iteration_row -- no seeding from the prior row: unlike the old
      merged-values design, a snapshot-list row has nothing meaningful
      to inherit, it just starts empty and accumulates its OWN
      breakpoint hits from here), and set confirmed[loop_id] = False.
      No backfill: the old "capture the loop's true final post-body
      state right before it exits" step doesn't apply any more --
      there's no single "final state" to capture, only whichever
      breakpoints actually got hit during that iteration.
    - On any ordinary line, REGARDLESS of whether it's a breakpoint:
      for every loop_id in that line's own line_to_loop_chain, set
      confirmed[loop_id] = True (this line proves that loop's current
      speculative row is a real iteration). If (and only if) the line
      IS also in breakpoint_lines, additionally append a snapshot of
      the live locals to the DEEPEST such loop's own current row (or
      root_table's row, if line_to_loop_chain is empty), reusing
      current_table[innermost] if already cached (the ordinary case --
      still the same row a recent header hit started) or deriving and
      caching it fresh otherwise (the first line of a freshly-started
      row, which the header-hit branch above already created but this
      is the first line-event to see it).
    - On the traced function/module's own 'return' event: any loop
      still showing confirmed[loop_id] is False has a trailing
      speculative row from a header hit that was never followed by
      either a body line OR another header hit (the loop, and the
      function containing it, both ended together) -- pop it too, via
      the same current_table cache, then clear both dicts for the next
      debug run."""

    def _keep(k):
        if k in exclude_keys:
            return False
        if exclude_dunders and k.startswith("__") and k.endswith("__"):
            return False
        return True

    def _append_snapshot(table, variables):
        if not table["rows"]:
            return
        row = table["rows"][-1]
        snapshot = {}
        for name, value in variables.items():
            if name not in table["columns"]:
                table["columns"].append(name)
            snapshot[name] = value
        row["snapshots"].append(snapshot)

    def _descend(chain, create):
        """Walk root_table down through chain (a list of loopIds,
        outer to inner, INCLUDING the target loop's own id as the last
        element -- e.g. loop_parent_chain[loop_id] + [loop_id]),
        returning the table at the end -- creating any missing nested
        table along the way only if create is True. A freshly created
        table's own startLine is the loop's HEADER line (loop_header_
        line), matching what a person actually sees at that loop's own
        while/for statement in the editor -- NOT loop_first_body_line,
        which is one or more lines further down and, for a loop whose
        own first body statement is itself another loop, is a
        completely different loop's header entirely (the exact
        confusion this fix avoids: "Loop at line 4" pointing at
        print(seconds) instead of the while line 3 above it)."""
        table = root_table
        for loop_id in chain:
            parent_row_index = str(len(table["rows"]) - 1)
            children = table["childTables"].get(parent_row_index, [])
            child = children[-1] if children and children[-1]["loopId"] == loop_id else None
            if child is None:
                if not create:
                    return None
                child = _new_loop_table(loop_id, loop_header_line.get(loop_id))
                table["childTables"].setdefault(parent_row_index, []).append(child)
            table = child
        return table

    # current_table[loop_id]: the ACTUAL table dict object this loop's
    # rows are currently landing in -- a direct reference, cached at
    # creation time, deliberately NEVER re-derived by re-descending
    # root_table's own nesting on every access. This matters because a
    # loop's own "which parent row am I nested under" can change
    # WHILE that loop's most recent row is still only speculatively
    # pending: e.g. inner loop I's 3rd header hit (its exit-check for
    # outer iteration N) creates a speculative row in I's table-for-N;
    # before I's NEXT header hit ever arrives to judge that row
    # unconfirmed, outer loop O's OWN header fires first and advances
    # O to iteration N+1 -- if I's pop/backfill later tried to re-
    # descend via "parent's CURRENT last row index" at that point, it
    # would compute O's NEW row index (N+1's), landing on I's
    # not-yet-created table-for-(N+1) instead of the real target,
    # table-for-N -- silently doing nothing (create=False finds no
    # such child yet) while table-for-N's stale trailing row is left
    # corrupted by a later backfill that also mis-targets it. Caching
    # the real object once, when the row is actually appended,
    # sidesteps this entirely: every subsequent pop/backfill/merge for
    # that SAME speculative row operates on the exact same dict,
    # regardless of what any ancestor loop's own row count does in the
    # meantime.
    current_table = {}
    confirmed = {}

    def _pop_last_row(loop_id):
        table = current_table.get(loop_id)
        if table is not None and table["rows"]:
            table["rows"].pop()

    def _tracer(frame, event, arg):
        if frame.f_code.co_filename != filename:
            return None
        if event == "call":
            return _tracer

        if event == "return":
            for loop_id, is_confirmed in list(confirmed.items()):
                if not is_confirmed:
                    _pop_last_row(loop_id)
            confirmed.clear()
            current_table.clear()
            return _tracer

        if event != "line" or truncated["value"]:
            return _tracer

        line_no = frame.f_lineno
        is_breakpoint = line_no in breakpoint_lines
        variables = {k: _safe_repr(v) for k, v in frame.f_locals.items() if _keep(k)} if is_breakpoint else None

        if line_no in loop_by_header_line:
            loop_id = loop_by_header_line[line_no]
            if confirmed.get(loop_id) is False:
                _pop_last_row(loop_id)
                # This loop's row just got discarded -- its own cached
                # table may now be stale if an ancestor loop's row
                # advanced in the meantime (see this closure's own
                # current_table docstring above), so force a fresh
                # re-descend below rather than reusing it.
                current_table.pop(loop_id, None)
            table = _descend(loop_parent_chain[loop_id] + [loop_id], create=True)
            current_table[loop_id] = table
            if len(table["rows"]) >= _MAX_DEBUG_ITERATIONS:
                truncated["value"] = True
                return None
            table["rows"].append(_new_iteration_row(len(table["rows"]) + 1))
            confirmed[loop_id] = False
            return _tracer

        chain = line_to_loop_chain.get(line_no, [])
        for loop_id in chain:
            confirmed[loop_id] = True
        if not is_breakpoint:
            return _tracer
        if chain:
            innermost = chain[-1]
            table = current_table.get(innermost)
            if table is None:
                table = _descend(chain, create=True)
                current_table[innermost] = table
        else:
            table = root_table
        _append_snapshot(table, variables)
        return _tracer

    return _tracer

def _debug_run_one(cell_name, source, elements, breakpoint_lines):
    """Time-travel debugger run (step-through-via-arrows feature, not a
    live pause/resume debugger -- Pyodide's runPythonAsync can't suspend
    arbitrary synchronous Python mid-call and resume later on a JS event,
    see this file's own ensureMatplotlibIfNeeded comment for the same
    limitation hit elsewhere). The cell's function still runs exactly
    once, uninterrupted, to completion -- sys.settrace's own 'line'/
    'return' trace events (fired before each source line in the traced
    function/its own nested calls executes, and once when it returns)
    are used only to RECORD a ROW-PER-LOOP-ITERATION trace (see
    _make_loop_tracer's own docstring for the full algorithm), never to
    pause anything. The caller then scrubs through the recorded rows
    after the fact with plain array indexing (App.tsx/Cell.tsx) -- no
    worker, no Atomics, no suspend/resume bridge needed.

    Row/iteration-BOUNDARY detection still runs unconditionally over
    every traced line, regardless of breakpoint_lines -- a loop's row
    count must stay accurate even for an iteration that never hits a
    breakpoint. But actually RECORDING a snapshot into a row is gated
    on breakpoint_lines once again (see _make_loop_tracer's own
    docstring): with none set, every row ends up empty, and there's
    nothing to step through -- this restores breakpoints as a real
    precondition for inspecting anything, after PR #55 had turned them
    into pure highlights with no gating effect at all.

    Deliberately a separate function from _execute_one rather than a
    flag added to it: _execute_one is also used by the ordinary Shift+
    Enter/run-all/element-changed paths, none of which have any use for
    tracing overhead, and keeping this entirely separate means a normal
    run's performance/behavior is unaffected by this feature ever
    existing.

    Only ever called directly for the ONE cell the user asked to debug
    (Cell.tsx's own "Run with breakpoints" action) -- unlike
    run_cell_and_dependents_b64, this never computes or runs a
    dependency/upstream set; the caller is expected to have already run
    the deck normally (ordinary Shift+Enter/run-all) so every upstream
    name this cell's function reads already exists in _namespace, exactly
    the same precondition an ordinary function call in a Python REPL
    would need.

    Local variables are captured as repr() strings (never the live
    objects themselves): a row is a JSON-serializable record for the JS
    side to store and scroll through, not a live reference into a
    namespace that keeps mutating after the row was taken -- a repr
    also survives objects that plain JSON can't encode at all (a turtle
    Canvas, a DataFrame, a custom class instance) with a readable
    display value instead of an encoding error aborting the whole debug
    run. A repr() that itself raises (a buggy __repr__) is caught
    per-variable so one bad object can't blow up the entire row."""
    stdout, stderr = io.StringIO(), io.StringIO()
    turtle_element = _find_turtle_canvas(elements)
    cell_filename = f"<cell:{cell_name}>"
    line_to_loop_chain, loop_first_body_line, loop_header_line, loop_by_header_line, loop_parent_chain = _find_loops(
        source
    )
    iteration_table = _new_loop_table(None, 1)
    iteration_table["rows"].append(_new_iteration_row(0))
    truncated = {"value": False}
    _tracer = _make_loop_tracer(
        cell_filename,
        line_to_loop_chain,
        loop_first_body_line,
        loop_header_line,
        loop_by_header_line,
        loop_parent_chain,
        breakpoint_lines,
        stdout,
        iteration_table,
        truncated,
    )

    try:
        return_names = _return_names_for(source)
        exec(_compile_cell(source, cell_filename), _namespace)
        fn = _namespace[cell_name]
        kwargs = _kwargs_for(cell_name, fn, elements)
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            writes = stack.enter_context(cs.execution_context())
            turtle_commands = (
                stack.enter_context(turtle.execution_context()) if turtle_element is not None else None
            )
            sys.settrace(_tracer)
            try:
                value = fn(**kwargs)
            finally:
                sys.settrace(None)
        if len(return_names) == 1:
            _namespace[return_names[0]] = value
            _RETURN_NAMED_VALUES.add(return_names[0])
        elif len(return_names) > 1:
            values = value if isinstance(value, tuple) else (value,)
            if len(values) != len(return_names):
                raise ValueError(
                    f"cell {cell_name!r} returned {len(values)} values for {len(return_names)} names"
                )
            for name, item in zip(return_names, values):
                _namespace[name] = item
                _RETURN_NAMED_VALUES.add(name)
        if turtle_commands and turtle_element is not None:
            writes.append(cs.ElementWrite(element_name=turtle_element, kind="turtle", content=turtle_commands))
        element_names = {e.name for e in elements}
        for write in writes:
            if write.element_name not in element_names:
                raise RuntimeError(
                    f"cell {cell_name!r} called cs.{write.kind}({write.element_name!r}, ...) "
                    f"but has no element named {write.element_name!r}"
                )
    except Exception:
        return {
            "status": "error",
            "error": traceback.format_exc(),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "iterationTable": iteration_table,
            "truncated": truncated["value"],
        }
    resolved = _output.resolve_output(value)
    return {
        "status": "idle",
        "error": None,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "iterationTable": iteration_table,
        "truncated": truncated["value"],
        "finalValue": _output.wire_safe_value(value),
        "finalKind": resolved.kind,
        "finalData": resolved.data,
    }

def run_cell_with_breakpoints_b64(cell_name_b64, cells_json_b64, breakpoint_lines_json_b64):
    """App.tsx's entry point for the step-through debugger's "Run with
    breakpoints" action. breakpoint_lines_json_b64 decodes to a JSON
    array of 1-indexed line numbers (Cell.tsx's own breakpointLines Set,
    same shape as CodeEditor's highlightedLines), matching against
    frame.f_lineno inside the cell's own source exactly like a normal
    IDE gutter breakpoint would. Runs ONLY this one cell (via
    _debug_run_one) -- never its dependents/upstream, unlike
    run_cell_and_dependents_b64 -- since a debug run's purpose is
    inspecting how the CELL ITSELF gets from start to its return value,
    not re-propagating that value through the rest of the deck (the
    caller can always follow up with an ordinary run to do that)."""
    cell_name = _decode(cell_name_b64)
    deck = _build_deck(cells_json_b64)
    cell = deck.cells[cell_name]
    breakpoint_lines = set(json.loads(_decode(breakpoint_lines_json_b64)))
    result = _debug_run_one(cell_name, cell.source, cell.elements, breakpoint_lines)
    _run_once.add(cell_name)
    return json.dumps(result)

def _define_one(cell_name, source):
    """Mirrors kernel.py's define_cell: compile the cell's function and
    bind it into _namespace under its own name, but never actually CALL
    it -- unlike _execute_one, no kwargs binding, no cs/turtle execution
    context, no return-named value written back (nothing ran to produce
    one). This is what a cell with a tests element attached gets instead
    of _execute_one as its own "run" (kernel.py's own _run_cells: "a
    cell with a tests element is defined but never auto-run with no
    arguments the way a plain cell is"), needed here specifically so
    run_test_b64's own "run the owning cell first if this tab never has"
    step doesn't crash a cell like drawLineSegment(t, p1, p2, p3, p4) --
    real required parameters with no input elements to bind them, which
    _execute_one would call as drawLineSegment() and get a guaranteed
    TypeError from. A test's own call into the function (with whatever
    arguments IT chooses) is the only thing that ever actually invokes
    a tested cell's body, exactly like the server-side flow."""
    exec(_compile_cell(source, f"<cell:{cell_name}>"), _namespace)

_READABLE_INPUT_KINDS = ("text_input", "slider")

def _make_input_shim(cell_name, elements, element_values):
    """kernel.py's own _make_input_shim, unchanged in behavior: each
    successive input() call reads the next text_input/slider element's
    current value, in declaration order (the two kinds share one
    combined sequence -- see kernel.py's own docstring for why). Prompt
    and value are both echoed to stdout together (no real terminal here
    to echo the typed value back), same "plausible transcript" reasoning
    as the server-side version. element_values is this tab's own
    _element_values.get(cell_name, {}) -- a plain {element_name: value}
    dict, falling back to the element's own config["default"] exactly
    like _kwargs_for already does for input-element kwargs binding."""
    readable = [e for e in elements if e.kind in _READABLE_INPUT_KINDS]
    calls = {"count": 0}

    def shim(prompt=""):
        index = calls["count"]
        calls["count"] += 1
        if index >= len(readable):
            raise EOFError(
                f"input(): cell {cell_name!r} only has {len(readable)} ui.text_input/ui.slider "
                f"element(s), but input() was called a {index + 1}{'st' if index == 0 else 'th'} time -- "
                "add another ui.text_input or ui.slider to this cell's elements=[...] for this call to read from."
            )
        element = readable[index]
        raw = element_values.get(element.name, (element.config or {}).get("default"))
        value = "" if raw is None else str(raw)
        print(f"{prompt}{value}")
        return value

    return shim

def _run_test(test_source, cell_name, elements):
    """Mirrors kernel.py's run_tests + _run_and_apply_test: run a tests
    element's source as plain top-level Python (ordinary asserts, not
    unittest) against a shallow COPY of _namespace, not _namespace
    itself -- a test box's own top-level assignments must stay local to
    that one test run, never becoming silently readable from a
    different cell's main editor or a different cell's own tests box
    just because both share this one tab's _namespace. (Server-side
    equivalent: kernel.py's run_tests docstring, which documents the
    exact cross-cell leak this guards against and the accepted
    trade-off below.) The test can still call the owning cell's own
    function by name and read whatever global it already declared --
    that function's own __globals__ is still the real _namespace,
    fixed at compile time in _execute_one/_define_one, entirely
    independent of which dict this call's own top-level exec runs
    against. Trade-off, deliberately accepted (matches kernel.py's
    run_tests): a called cell's global mutation still reaches the
    real _namespace and persists for later cells/tests, but this same
    test's OWN subsequent lines still see their copy's pre-call
    snapshot, not that just-written value. cs/turtle are already seeded
    into _namespace once at runner-module init time (this file's own
    header comment) and thus already present in the copy too, since the
    copy starts from _namespace's current contents.

    input() is bound directly onto the copy (no save/restore needed --
    the copy is simply discarded when this call returns), reading from
    cell_name's own text_input/slider elements via _make_input_shim.

    turtle.execution_context() establishes a fresh canvas state (see
    turtle.py's own execution_context) whenever the owning cell has
    exactly one turtle_canvas element -- the test's own drawing, not
    layered on top of whatever the cell's own last run drew (same
    "replaces, doesn't layer" rule kernel.py's _run_and_apply_test
    documents), returned as turtleCommands for the caller to write into
    that same canvas element, forcing a resend even when the cell's own
    canvas write already happened in the same client-side run (the
    exact behavior ws_handler.py's old SetTestSource handler used to
    compute server-side, preserved here client-side instead)."""
    turtle_element = _find_turtle_canvas(elements)
    result = {"status": "pass", "message": "", "stdout": "", "stderr": "", "turtleCommands": None}
    if turtle_element is not None:
        result["turtleCommands"] = []
    if not test_source.strip():
        return result

    stdout, stderr = io.StringIO(), io.StringIO()
    test_globals = dict(_namespace)
    element_values = _element_values.get(cell_name, {})
    test_globals["input"] = _make_input_shim(cell_name, elements, element_values)
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            turtle_commands = (
                stack.enter_context(turtle.execution_context()) if turtle_element is not None else None
            )
            exec(compile(test_source, "<test>", "exec"), test_globals)
    except AssertionError as exc:
        result["status"] = "fail"
        result["message"] = str(exc) or "assertion failed"
    except Exception:
        result["status"] = "error"
        result["message"] = traceback.format_exc()

    result["stdout"] = stdout.getvalue()
    result["stderr"] = stderr.getvalue()
    if turtle_element is not None:
        result["turtleCommands"] = turtle_commands
    return result

def run_test_b64(cell_name_b64, test_source_b64, cells_json_b64):
    """App.tsx's client-side entry point for a tests-element edit
    (SetTestSource's former server-side execution, ARCHITECTURE.md
    section 3b). Unlike run_cell_and_dependents_b64/on_element_changed_b64,
    this never rebuilds/consults the dependency graph at all -- a
    test's source has no reads/writes of its own to the graph (kernel.py's
    on_tests_edited docstring: it only observes results other cells
    already produced), matching that method's own "no graph
    recomputation" rule exactly. cells_json_b64 is still needed (not just
    the one cell's elements) so the owning cell's own function is at
    least DEFINED first if this tab has never touched it yet --
    otherwise a test targeting a cell the user never directly touched
    would NameError against an empty _namespace, the same 'missing
    upstream' gap run_cell_and_dependents_b64 already handles for a
    plain cell edit. Deliberately _define_one, never _execute_one: a
    cell with a tests element attached is always define-only from a
    test's own perspective (kernel.py's _run_cells: "a cell with a
    tests element is defined but never auto-run with no arguments the
    way a plain cell is") -- _execute_one would call the function with
    no bound arguments, a guaranteed TypeError for any cell with a real
    required parameter and no matching input element (e.g.
    drawLineSegment(t, p1, p2, p3, p4)). Also deliberately never adds
    cell_name to _run_once: that set gates _missing_upstream's "already
    executed" check for run_cell_and_dependents_b64/
    on_element_changed_b64, and a define-only pass never writes any
    return-named value into _namespace the way a real execution does --
    marking it 'run' here would wrongly tell a LATER plain edit of some
    other cell that reads this one's return value that its upstream
    dependency is already satisfied, when it never actually ran."""
    cell_name = _decode(cell_name_b64)
    test_source = _decode(test_source_b64)
    deck = _build_deck(cells_json_b64)
    cell = deck.cells[cell_name]
    if cell_name not in _namespace:
        _define_one(cell_name, cell.source)
    return json.dumps(_run_test(test_source, cell_name, cell.elements))

def _debug_run_test(test_source, cell_name, elements, breakpoint_lines, all_cell_names):
    """The step-through debugger's "Run with breakpoints" action, for a
    tests element's own editor (TestsElementWidget) -- same time-travel
    "record a row-per-loop-iteration trace on one uninterrupted run,
    scrub through it after the fact" shape as _debug_run_one, sharing
    its exact tracer semantics via _make_loop_tracer, but wrapping
    _run_test's own "exec the test source as top-level statements"
    shape instead of a cell's "call the compiled function" shape --
    there is no function call to wrap here, so the traced lines are
    simply lines of test_source itself, traced under the SAME "<test>"
    filename _run_test already compiles under (kept in sync with that
    function deliberately: any change to how _run_test executes
    test_source -- the input() shim, the turtle context -- must be
    mirrored here too, or a debug run's rows would silently stop
    reflecting what an ordinary test run actually does).

    Like _run_test (see its own docstring for the full rationale), runs
    against a shallow COPY of _namespace, not _namespace itself -- so a
    test calling the cell's own function by name can still be traced
    through that function's body too (the tracer's own 'call' handling
    covers this: the cell's function was compiled under "<cell:NAME>",
    a different filename than "<test>", so its own lines are never
    captured as snapshots even though execution passes through them --
    a debug run here is scoped to the TEST's own lines, not the cell
    body it exercises; debugging the cell body itself is what Cell.tsx's
    own "Run with breakpoints" is for).

    all_cell_names (every cell in the current deck, not just this one)
    plus _NAMESPACE_BASELINE_KEYS (cs/turtle) plus _RETURN_NAMED_VALUES
    (every name any cell's own return has EVER bound, across every
    cell, this whole tab's lifetime) plus "input" together form the
    exclude_keys passed to _make_loop_tracer. This used to matter a
    great deal more: before test runs were isolated onto a fresh copy
    each time, a test's own prior-run locals (e.g. this test's own
    "total"/"i" loop variables) stayed sitting in the shared, persistent
    _namespace forever, so exclude_keys had to be computed from these
    four stable sources rather than "whatever _namespace already
    contains right now" -- otherwise a SECOND run of the same test would
    wrongly treat its own leftover locals as pre-existing and exclude
    them, rows coming back with an empty variables dict. Isolation
    means a fresh copy no longer carries that leftover state in the
    first place, so this exclude_keys computation is now more of a
    belt-and-suspenders guard than a load-bearing fix for that specific
    symptom -- kept exactly as-is regardless, since it's still correct
    and still needed for the OTHER thing it guards: a cell's own
    RETURN-named value (e.g. base from a setup cell returning base) is
    a DIFFERENT name from the cell itself, with nothing else marking
    which cell (if any) produced it, so _RETURN_NAMED_VALUES is what
    keeps an upstream cell's real, legitimate value from being
    misreported as if the test itself had just assigned it."""
    turtle_element = _find_turtle_canvas(elements)
    line_to_loop_chain, loop_first_body_line, loop_header_line, loop_by_header_line, loop_parent_chain = _find_loops(
        test_source
    )
    iteration_table = _new_loop_table(None, 1)
    iteration_table["rows"].append(_new_iteration_row(0))
    truncated = {"value": False}
    result = {
        "status": "pass",
        "message": "",
        "stdout": "",
        "stderr": "",
        "iterationTable": iteration_table,
        "truncated": False,
    }
    if not test_source.strip():
        return result

    stdout, stderr = io.StringIO(), io.StringIO()
    test_globals = dict(_namespace)
    element_values = _element_values.get(cell_name, {})
    test_globals["input"] = _make_input_shim(cell_name, elements, element_values)
    # See this function's own docstring for why this is every cell name
    # plus the permanently-seeded names, never _namespace's own current
    # key set. exec(compile(...), test_globals) below also implicitly
    # injects "__builtins__" into test_globals itself (a plain dict given
    # as exec's globals gets one added automatically if not already
    # present, same as any top-level module's own __builtins__) --
    # filtered here as "any dunder name" rather than one more name to
    # list by hand, since Python's own set of implicitly-injected dunder
    # globals isn't otherwise this function's concern to track.
    exclude_keys = frozenset(all_cell_names) | _NAMESPACE_BASELINE_KEYS | _RETURN_NAMED_VALUES | {"input"}
    _tracer = _make_loop_tracer(
        "<test>",
        line_to_loop_chain,
        loop_first_body_line,
        loop_header_line,
        loop_by_header_line,
        loop_parent_chain,
        breakpoint_lines,
        stdout,
        iteration_table,
        truncated,
        exclude_keys=exclude_keys,
        exclude_dunders=True,
    )
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(contextlib.redirect_stdout(stdout))
            stack.enter_context(contextlib.redirect_stderr(stderr))
            if turtle_element is not None:
                stack.enter_context(turtle.execution_context())
            sys.settrace(_tracer)
            try:
                exec(compile(test_source, "<test>", "exec"), test_globals)
            finally:
                sys.settrace(None)
    except AssertionError as exc:
        result["status"] = "fail"
        result["message"] = str(exc) or "assertion failed"
    except Exception:
        result["status"] = "error"
        result["message"] = traceback.format_exc()

    result["stdout"] = stdout.getvalue()
    result["stderr"] = stderr.getvalue()
    result["truncated"] = truncated["value"]
    return result

def run_test_with_breakpoints_b64(
    cell_name_b64, test_source_b64, cells_json_b64, breakpoint_lines_json_b64, all_cell_names_json_b64
):
    """TestsElementWidget's own "Run with breakpoints" entry point --
    same shape as run_cell_with_breakpoints_b64, but for a tests
    element's own source rather than the owning cell's. Defines (never
    executes) the owning cell first if this tab hasn't touched it yet,
    exactly like run_test_b64 already does, so a test targeting a cell
    the user never directly ran doesn't NameError against an empty
    _namespace.

    all_cell_names_json_b64 decodes to a JSON array of EVERY cell name in
    the current deck -- deliberately NOT derived from cells_json_b64/
    deck.cells.keys() here, since cells_json_b64 only ever contains the
    ONE owning cell (TestsElementWidget's own cellsInput, built from just
    cellSource/cellElements -- there is no persistent client-side Deck
    object to read the full cell list from some other way, see this
    file's own installModules/getPyodide docstrings). Passed straight
    through to _debug_run_test's own exclude_keys construction -- see
    its docstring for why this must be the deck's real, full cell list."""
    cell_name = _decode(cell_name_b64)
    test_source = _decode(test_source_b64)
    deck = _build_deck(cells_json_b64)
    cell = deck.cells[cell_name]
    breakpoint_lines = set(json.loads(_decode(breakpoint_lines_json_b64)))
    all_cell_names = json.loads(_decode(all_cell_names_json_b64))
    if cell_name not in _namespace:
        _define_one(cell_name, cell.source)
    return json.dumps(_debug_run_test(test_source, cell_name, cell.elements, breakpoint_lines, all_cell_names))

def _find_tests_element(elements):
    """kernel.py's own _find_tests_element, unchanged: the cell's one
    tests element, if it has exactly one -- same "ambiguous means none"
    rule as _find_turtle_canvas."""
    test_elements = [e.name for e in elements if e.kind == "tests"]
    return test_elements[0] if len(test_elements) == 1 else None

def _has_unbound_required_param(source, elements):
    """kernel.py's own _has_unbound_required_param, unchanged: True if
    the cell's function has a parameter with no default that isn't also
    bound by a matching input element -- see its own docstring for why
    this must be checked (via ast, never by compiling/calling) BEFORE
    choosing whether to _execute_one or _define_one a cell, the same
    "decide before running" ordering _run_cells needs server-side."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return False
    func_defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(func_defs) != 1:
        return False
    func = func_defs[0]

    element_names = {e.name for e in elements}
    args = func.args.posonlyargs + func.args.args
    positional_required = args[: len(args) - len(func.args.defaults)]
    kwonly_required = [a for a, default in zip(func.args.kwonlyargs, func.args.kw_defaults) if default is None]

    return any(a.arg not in element_names for a in (*positional_required, *kwonly_required))

def _run_names(names, cells):
    """Mirrors kernel.py's _run_cells' own execute-vs-define branch: a
    cell with a tests element attached, or an unbound required
    parameter (no default, no matching input element), is _define_one'd
    instead of _execute_one'd -- never auto-called with no arguments the
    way a plain cell is (kernel.py's own _run_cells docstring). Ported
    here specifically because runAllClientSide/runCellClientSide (via
    App.tsx's own "open a deck, run it automatically" effect -- the
    client-side replacement for the old run_all websocket message) hit
    exactly the TypeError this guards against for any tested cell with a
    real required parameter and no bound element (e.g.
    markCorners(cells, t), drawLineSegment(t, p1, p2, p3, p4)) -- a
    define-only cell still reports its own definition-time errors
    (CellDefinitionError/SyntaxError) as a real ExecutionResult, exactly
    like define_cell does, just never the call-time TypeError a forced
    zero-arg call would produce."""
    results = {}
    for name in names:
        cell = cells[name]
        if _find_tests_element(cell.elements) is not None or _has_unbound_required_param(cell.source, cell.elements):
            try:
                _define_one(name, cell.source)
                results[name] = {
                    "status": "idle",
                    "value": None,
                    "kind": None,
                    "data": None,
                    "error": None,
                    "stdout": "",
                    "stderr": "",
                    "elementWrites": [],
                }
            except Exception:
                results[name] = {
                    "status": "error",
                    "value": None,
                    "kind": None,
                    "data": None,
                    "error": traceback.format_exc(),
                    "stdout": "",
                    "stderr": "",
                    "elementWrites": [],
                }
        else:
            results[name] = _execute_one(name, cell.source, cell.elements)
        _run_once.add(name)
    return results

def _missing_upstream(graph, cell_name, all_names):
    """Cell names cell_name transitively depends on (directly or
    indirectly reads a name written by) that have never been executed in
    this tab -- i.e. are missing from _run_once. graph.py's
    DependencyGraph only stores forward edges (producer -> its
    dependents), so this walks that map in reverse rather than relying on
    a not-provided "dependencies of" query. Returned in the graph's own
    topological order, so running them in this order (before the edited
    cell itself) establishes correct values for each one's own upstream
    reads in turn."""
    dependency_of = {name: set() for name in all_names}
    for producer, consumers in graph.edges.items():
        for consumer in consumers:
            dependency_of.setdefault(consumer, set()).add(producer)

    missing: set = set()
    stack = [cell_name]
    seen = set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for dep in dependency_of.get(current, ()):
            if dep not in _run_once:
                missing.add(dep)
            if dep not in seen:
                stack.append(dep)
    order = graph.topological_order()
    return [name for name in order if name in missing]

def run_cell_and_dependents_b64(cell_name_b64, cells_json_b64):
    """Kernel.on_cell_edited's client-side equivalent: build the graph
    fresh from the caller's current sources, compute the minimal
    re-run set for an edit to cell_name (graph.py's own
    DependencyGraph.affected_by, in topological order), and run just
    those cells. A graph that fails to build (MultipleDefinitionError,
    GraphCycleError -- both ValueError subclasses -- or a SyntaxError
    from a cell that doesn't even parse, the ordinary expected state of
    live-typed code between keystrokes) is reported as the EDITED
    cell's own error, exactly like Kernel.on_cell_edited's own
    try/except ValueError|SyntaxError branch, rather than crashing or
    silently doing nothing.

    Unlike the server (whose session.namespace always already has every
    upstream value from a prior run_all/edit), a fresh browser tab may
    never have executed cell_name's own upstream dependencies at all --
    see _missing_upstream's docstring. Those are run first, in
    topological order, so ordinary Python name resolution in cell_name's
    own compiled function finds them already bound in _namespace exactly
    as it would server-side."""
    cell_name = _decode(cell_name_b64)
    try:
        deck = _build_deck(cells_json_b64)
        graph = build_graph(deck)
    except (SyntaxError, ValueError) as exc:
        return json.dumps({cell_name: {
            "status": "error",
            "value": None,
            "kind": None,
            "data": None,
            "error": str(exc),
            "stdout": "",
            "stderr": "",
            "elementWrites": [],
        }})
    prerequisites = _missing_upstream(graph, cell_name, deck.cells.keys())
    affected = graph.affected_by(cell_name)
    to_run = prerequisites + [name for name in affected if name not in prerequisites]
    return json.dumps(_run_names(to_run, deck.cells))

def run_all_b64(cells_json_b64):
    """Kernel.run_all's client-side equivalent: every cell, in full
    topological order -- no minimal-rerun-set filtering, matching
    run_all's own unfiltered graph.topological_order() call exactly."""
    try:
        deck = _build_deck(cells_json_b64)
        graph = build_graph(deck)
    except (SyntaxError, ValueError) as exc:
        return json.dumps({"__run_all_error__": {
            "status": "error",
            "value": None,
            "kind": None,
            "data": None,
            "error": str(exc),
            "stdout": "",
            "stderr": "",
            "elementWrites": [],
        }})
    return json.dumps(_run_names(graph.topological_order(), deck.cells))

def on_element_changed_b64(cell_name_b64, element_name_b64, value_json_b64, cells_json_b64):
    """Kernel.on_element_changed's client-side equivalent: record the new
    value (so _kwargs_for picks it up), then re-run exactly the same
    minimal set an edit to cell_name would -- cell_name itself plus any
    of its own never-yet-run upstream dependencies, plus its downstream
    dependents (graph.affected_by), same composition as
    run_cell_and_dependents_b64. value_json_b64 decodes to a JSON value
    (not a bare string) since an element's value can be a number
    (slider), int (button press count), or string (text_input) --
    JSON round-trips all three without the base64-string's own
    "everything is text" ambiguity."""
    cell_name = _decode(cell_name_b64)
    element_name = _decode(element_name_b64)
    value = json.loads(_decode(value_json_b64))
    _element_values.setdefault(cell_name, {})[element_name] = value
    try:
        deck = _build_deck(cells_json_b64)
        graph = build_graph(deck)
    except (SyntaxError, ValueError) as exc:
        return json.dumps({cell_name: {
            "status": "error",
            "value": None,
            "kind": None,
            "data": None,
            "error": str(exc),
            "stdout": "",
            "stderr": "",
            "elementWrites": [],
        }})
    prerequisites = _missing_upstream(graph, cell_name, deck.cells.keys())
    affected = graph.affected_by(cell_name)
    to_run = prerequisites + [name for name in affected if name not in prerequisites]
    return json.dumps(_run_names(to_run, deck.cells))
`

async function installModules(pyodide: PyodideInterface): Promise<void> {
  pyodide.FS.mkdirTree('/codeslides_pkg/codeslides')
  pyodide.FS.writeFile('/codeslides_pkg/codeslides/__init__.py', '')
  for (const name of PYODIDE_MODULE_FILES) {
    const res = await fetch(`/codeslides_pyscript/${name}`)
    if (!res.ok) throw new Error(`failed to fetch codeslides/${name}: ${res.status}`)
    const source = await res.text()
    pyodide.FS.writeFile(`/codeslides_pkg/codeslides/${name}`, source)
  }
}

// One shared Pyodide instance (and one shared runner namespace) per
// page load, matching the proposal's "loading Pyodide once per page
// load" -- section 5. Memoized so multiple cells' first runs don't
// each independently trigger a fresh ~10MB download/init.
async function getPyodide(): Promise<PyodideInterface> {
  if (!pyodidePromise) {
    setPyodideStatus('loading')
    pyodidePromise = (async () => {
      try {
        await loadPyodideScript(PYODIDE_CDN_URL)
        if (!window.__loadPyodideImpl) throw new Error('Pyodide script loaded but loadPyodide was not found')
        const pyodide = await window.__loadPyodideImpl()
        await installModules(pyodide)
        await pyodide.runPythonAsync(
          'import sys; sys.path.insert(0, "/codeslides_pkg") if "/codeslides_pkg" not in sys.path else None',
        )
        await pyodide.runPythonAsync(RUNNER_MODULE_PYTHON)
        setPyodideStatus('ready')
        return pyodide
      } catch (err) {
        // Reset pyodidePromise (not just the status) on failure -- a
        // transient network blip loading the CDN script shouldn't
        // permanently wedge every future cell run behind a Promise
        // that's already rejected; the NEXT getPyodide() call should
        // genuinely retry from scratch, matching how a failed
        // run*ClientSide call today already surfaces the error as
        // that one cell's own error and lets a later edit try again.
        pyodidePromise = null
        setPyodideStatus('error')
        throw err
      }
    })()
  }
  return pyodidePromise
}

// TODO.md #64 (matplotlib slice): output.py's own resolve_output/
// _figure_to_data_uri already duck-type a matplotlib Figure by class
// name and call figure.savefig(...) -- pure stdlib, no changes needed,
// same "already portable" story as cs.py/turtle.py. What's missing is
// matplotlib ITSELF: unlike codeslides' own modules, it isn't bundled
// into codeslides_pyscript/ (it's a large, genuinely optional runtime
// dependency for lesson authors, matching pyproject.toml's own
// "matplotlib is a dev extra, not a hard dependency" stance), so it has
// to be loaded from Pyodide's own curated package index
// (pyodide.loadPackage('matplotlib'), confirmed against a real browser
// in pyscript_spike/spike3_matplotlib.html -- ~1s to fetch, savefig()
// works unmodified regardless of the auto-selected backend) -- but only
// for a session that actually uses it, not unconditionally at Pyodide
// startup, the same "pay only for what you use" reasoning the whole
// Pyodide-over-self-hosted-runtime tradeoff already follows.
//
// Detection is a plain source-text scan for "import matplotlib"/"from
// matplotlib" across every cell this run touches, rather than trying to
// catch a ModuleNotFoundError mid-execution and retry -- the actual
// exec() call happens deep inside one synchronous Python call
// (_execute_one, inside run_cell_and_dependents_b64/run_all_b64/
// on_element_changed_b64), and loadPackage is itself async, so
// detecting and loading BEFORE that call starts avoids needing to
// suspend Python execution mid-cell and resume after an awaited JS
// call -- which Pyodide's runPythonAsync doesn't support for arbitrary
// synchronous code anyway. A plain text scan can't be fooled by e.g. a
// cell that builds the string "import matplotlib" without meaning it,
// but that's a vanishingly unlikely false positive to worry about (the
// cost of a false positive is one extra ~1s package load, never a
// correctness problem) -- much cheaper than actually parsing imports.
const MATPLOTLIB_IMPORT_RE = /\b(import\s+matplotlib\b|from\s+matplotlib\b)/

let matplotlibLoadedPromise: Promise<void> | null = null

async function ensureMatplotlibIfNeeded(
  pyodide: PyodideInterface,
  allCells: Record<string, PyodideCellInput>,
): Promise<void> {
  const needsMatplotlib = Object.values(allCells).some((cell) => MATPLOTLIB_IMPORT_RE.test(cell.source))
  if (!needsMatplotlib) return
  if (!matplotlibLoadedPromise) {
    matplotlibLoadedPromise = Promise.resolve(pyodide.loadPackage('matplotlib')).then(() => undefined)
  }
  await matplotlibLoadedPromise
}

function toBase64(text: string): string {
  // btoa operates on a byte string (one char = one byte), so a UTF-8
  // encode step is required first for any non-ASCII text (a
  // comment/string literal with e.g. an em dash or emoji, or a cell
  // name -- unlikely but not disallowed) to survive the round trip
  // correctly.
  const bytes = new TextEncoder().encode(text)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

// Applies the deck's own top-level import/from...import statements
// (server.py's /api/deck, deck.module_import_source -- see loader.py's
// _module_level_import_source and this module's own Python-side
// set_deck_imports_b64 for the full story) into this tab's shared
// _namespace, exactly once -- the client-side equivalent of kernel.py
// seeding deck_imports into every cell's globals. App.tsx calls this
// right after its own fetch('/api/deck') resolves, before the first
// runAllClientSide it triggers, so a cell reading a deck-level name
// (examples/marchingSquares.py's createMatrix reading `random`, bound by
// the file's own top-level `import random`, never its own) resolves it
// correctly on the very first run, not just on some later re-run.
// set_deck_imports_b64 is itself idempotent and safe to call with an
// empty string, so this can be called unconditionally on every /api/deck
// fetch (including a later reload) with no extra bookkeeping here.
export async function setDeckImportsClientSide(moduleImportSource: string): Promise<void> {
  const pyodide = await getPyodide()
  const sourceB64 = toBase64(moduleImportSource)
  await pyodide.runPythonAsync(`set_deck_imports_b64(${JSON.stringify(sourceB64)})`)
}

// Every entry point below takes `allCells` -- the caller's full current
// view of every cell (source + elements: name/kind/config, own edits +
// whatever the document currently shows) -- since the graph and kwargs
// binding must be rebuilt fresh each call (see this module's own header
// comment for why there's no persistent Deck object to keep in sync
// incrementally client-side).
export async function runCellClientSide(
  cellName: string,
  allCells: Record<string, PyodideCellInput>,
): Promise<Record<string, PyodideCellResult>> {
  const pyodide = await getPyodide()
  await ensureMatplotlibIfNeeded(pyodide, allCells)
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const call = `run_cell_and_dependents_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(cellsB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as Record<string, PyodideCellResult>
}

export async function runAllClientSide(
  allCells: Record<string, PyodideCellInput>,
): Promise<Record<string, PyodideCellResult>> {
  const pyodide = await getPyodide()
  await ensureMatplotlibIfNeeded(pyodide, allCells)
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const call = `run_all_b64(${JSON.stringify(cellsB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as Record<string, PyodideCellResult>
}

// value is JSON-encoded (not base64-of-a-string) since an element's
// value can be a number (slider), int (button press count), or string
// (text_input) -- see on_element_changed_b64's own docstring.
export async function onElementChangedClientSide(
  cellName: string,
  elementName: string,
  value: unknown,
  allCells: Record<string, PyodideCellInput>,
): Promise<Record<string, PyodideCellResult>> {
  const pyodide = await getPyodide()
  await ensureMatplotlibIfNeeded(pyodide, allCells)
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const valueB64 = toBase64(JSON.stringify(value))
  const call = `on_element_changed_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(toBase64(elementName))}, ${JSON.stringify(valueB64)}, ${JSON.stringify(cellsB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as Record<string, PyodideCellResult>
}

// TODO.md #64/PROPOSAL_pyscript_execution.md section 7: kernel.py's
// on_tests_edited client-side equivalent -- runs `testSource` against
// cellName's own namespace (running cellName itself first, if this tab
// has never executed it), preserving the exact turtle-forced-resend/
// input-shim/stdout-capture behavior run_tests already has server-side
// (this file's own run_test_b64/_run_test docstrings). Does not re-run
// cellName itself if it's already been executed in this tab -- same
// "test source has no reads/writes of its own to the graph" rule
// on_tests_edited's own docstring gives for skipping any graph
// recomputation.
// Step-through debugger's "Run with breakpoints" action (Cell.tsx). Runs
// only `cellName` itself (never its dependents/upstream -- see
// run_cell_with_breakpoints_b64's own docstring for why); the caller is
// expected to have already run the deck normally at least once so this
// cell's own upstream reads already resolve, exactly the same
// precondition runCellClientSide's own missing-upstream backfill exists
// for on an ordinary run, just not replicated here since a debug run's
// whole point is a single cell's own internal step-by-step state, not
// full-deck reactivity.
export async function runCellWithBreakpointsClientSide(
  cellName: string,
  allCells: Record<string, PyodideCellInput>,
  breakpointLines: ReadonlySet<number>,
): Promise<PyodideDebugRunResult> {
  const pyodide = await getPyodide()
  await ensureMatplotlibIfNeeded(pyodide, allCells)
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const breakpointLinesB64 = toBase64(JSON.stringify([...breakpointLines]))
  const call = `run_cell_with_breakpoints_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(cellsB64)}, ${JSON.stringify(breakpointLinesB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as PyodideDebugRunResult
}

export async function runTestClientSide(
  cellName: string,
  testSource: string,
  allCells: Record<string, PyodideCellInput>,
): Promise<PyodideTestResult> {
  const pyodide = await getPyodide()
  await ensureMatplotlibIfNeeded(pyodide, allCells)
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const call = `run_test_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(toBase64(testSource))}, ${JSON.stringify(cellsB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as PyodideTestResult
}

// The step-through debugger's "Run with breakpoints" action, for a
// tests element's own editor (TestsElementWidget) -- same shape as
// runCellWithBreakpointsClientSide, but targets a tests element's own
// source/breakpoints rather than the owning cell's. Defines (never
// executes) the owning cell first if this tab hasn't touched it yet,
// same precondition runTestClientSide already has.
export async function runTestWithBreakpointsClientSide(
  cellName: string,
  testSource: string,
  allCells: Record<string, PyodideCellInput>,
  breakpointLines: ReadonlySet<number>,
  // Every cell name in the deck (TestsElementWidget's own allCellNames
  // prop) -- see run_test_with_breakpoints_b64's own docstring for why
  // this must be the DECK's full cell list, never just Object.keys(allCells)
  // (allCells here only ever contains the ONE owning cell, not the whole
  // deck -- see this file's own installModules/getPyodide docstrings for
  // why there's no persistent client-side Deck object to read the full
  // list from some other way).
  allCellNames: string[],
): Promise<PyodideTestDebugRunResult> {
  const pyodide = await getPyodide()
  await ensureMatplotlibIfNeeded(pyodide, allCells)
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const breakpointLinesB64 = toBase64(JSON.stringify([...breakpointLines]))
  const allCellNamesB64 = toBase64(JSON.stringify(allCellNames))
  const call = `run_test_with_breakpoints_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(toBase64(testSource))}, ${JSON.stringify(cellsB64)}, ${JSON.stringify(breakpointLinesB64)}, ${JSON.stringify(allCellNamesB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as PyodideTestDebugRunResult
}
