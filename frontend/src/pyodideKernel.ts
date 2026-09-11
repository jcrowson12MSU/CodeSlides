// TODO.md #64/PROPOSAL_pyscript_execution.md: client-side cell execution
// via Pyodide. Loads Pyodide once per page load (from a CDN, per the
// user's own explicit choice for this early slice -- see the
// proposal's section 1 note on Pyodide hosting; self-hosting the ~10MB
// runtime can be revisited once this slice is proven out), writes the
// real, unmodified deck.py/graph.py/cs.py/output.py/turtle.py into
// Pyodide's virtual filesystem as a real importable `codeslides`
// package (exactly the FS layout pyscript_spike/spike2_real_modules.html
// already proved works), and exposes functions shaped to drop straight
// into `CellState` (deckState.ts) with zero server round trip.
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

export interface PyodideCellResult {
  status: 'idle' | 'error'
  value: unknown
  kind: 'text' | 'markdown' | 'image' | 'dataframe' | null
  data: unknown
  error: string | null
  stdout: string
  stderr: string
}

// Minimal ambient shape for what this module actually calls on a
// loaded Pyodide instance -- not a full @types/pyodide surface (the
// full types package targets the npm-bundled runtime; this loads from
// a CDN script instead, per the hosting decision in the module
// docstring above), just enough to keep this file itself type-checked.
interface PyodideInterface {
  runPythonAsync(code: string): Promise<unknown>
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
// reactivity -- deliberately without elements/kwargs binding,
// deck_imports, or is_main handling yet (a later slice's scope).
// `_namespace` is one plain module-level dict, shared across every
// `run_cells`/`run_all` call for the life of this page load -- the
// client-side equivalent of session.namespace, scoped to this one
// browser tab (PROPOSAL_pyscript_execution.md section 2.1: no
// execution state of any kind is ever shared across tabs).
const RUNNER_MODULE_PYTHON = `
import ast
import base64
import io
import json
import contextlib
import traceback

from codeslides import cs, turtle
from codeslides import output as _output
from codeslides.deck import Cell, Deck
from codeslides.graph import build_graph, extract_return_names

_namespace = {}

# kernel.py seeds every cell's __globals__ (session.namespace) with these
# two names before any execution (execute_cell/run_tests/run_all's own
# per-run seeding, kernel.py lines ~407/549/737) -- a plain "import
# codeslides as cs" isn't how a cell's source actually gets cs/turtle
# at all; the deck author's source never imports them itself (see
# examples/live_demo.py), the runtime injects them by name instead.
# deck_imports (the third thing kernel.py seeds alongside these) isn't
# ported yet -- out of scope for this slice, same as elements/kwargs.
_namespace["cs"] = cs
_namespace["turtle"] = turtle

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

def _decode(b64):
    return base64.b64decode(b64).decode("utf-8")

def _build_deck(sources_json_b64):
    """sources_json_b64 decodes to a JSON object of {cell_name: source}
    -- the caller's full current view of the deck (App.tsx's own
    deck.cells), same "rebuild fresh every call" shape
    Kernel._effective_graph already uses server-side. Only name/source
    are populated on each Cell -- every other field defaults, and is
    irrelevant to graph-building (see this module's own header
    comment)."""
    sources = json.loads(_decode(sources_json_b64))
    cells = {name: Cell(name=name, source=source) for name, source in sources.items()}
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

def _execute_one(cell_name, source):
    """Mirrors kernel.py's execute_cell: run the cell's function against
    the shared _namespace (its real __globals__, via plain exec into
    _namespace itself -- so a global x write lands permanently, same
    guarantee _compile_cell_function documents), then -- critically --
    bind the call's result back into _namespace under its return-named
    name(s) (kernel.py lines ~471-485), exactly like a bare 'return
    name' or 'return a, b' cell publishes name/a/b for any other
    cell to read by ordinary Python name resolution. Without this step,
    a downstream cell reading an upstream cell's returned value (not
    just calling its function directly) would always see a NameError,
    regardless of run order."""
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        return_names = _return_names_for(source)
        exec(compile(source, f"<cell:{cell_name}>", "exec"), _namespace)
        fn = _namespace[cell_name]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            value = fn()
        if len(return_names) == 1:
            _namespace[return_names[0]] = value
        elif len(return_names) > 1:
            values = value if isinstance(value, tuple) else (value,)
            if len(values) != len(return_names):
                raise ValueError(
                    f"cell {cell_name!r} returned {len(values)} values for {len(return_names)} names"
                )
            for name, item in zip(return_names, values):
                _namespace[name] = item
    except Exception:
        return {
            "status": "error",
            "value": None,
            "kind": None,
            "data": None,
            "error": traceback.format_exc(),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
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
    }

def _run_names(names, sources):
    results = {}
    for name in names:
        results[name] = _execute_one(name, sources[name])
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

def run_cell_and_dependents_b64(cell_name_b64, sources_json_b64):
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
        deck = _build_deck(sources_json_b64)
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
        }})
    sources = {name: cell.source for name, cell in deck.cells.items()}
    prerequisites = _missing_upstream(graph, cell_name, sources.keys())
    affected = graph.affected_by(cell_name)
    to_run = prerequisites + [name for name in affected if name not in prerequisites]
    return json.dumps(_run_names(to_run, sources))

def run_all_b64(sources_json_b64):
    """Kernel.run_all's client-side equivalent: every cell, in full
    topological order -- no minimal-rerun-set filtering, matching
    run_all's own unfiltered graph.topological_order() call exactly."""
    try:
        deck = _build_deck(sources_json_b64)
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
        }})
    sources = {name: cell.source for name, cell in deck.cells.items()}
    return json.dumps(_run_names(graph.topological_order(), sources))
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
    pyodidePromise = (async () => {
      await loadPyodideScript(PYODIDE_CDN_URL)
      if (!window.__loadPyodideImpl) throw new Error('Pyodide script loaded but loadPyodide was not found')
      const pyodide = await window.__loadPyodideImpl()
      await installModules(pyodide)
      await pyodide.runPythonAsync(
        'import sys; sys.path.insert(0, "/codeslides_pkg") if "/codeslides_pkg" not in sys.path else None',
      )
      await pyodide.runPythonAsync(RUNNER_MODULE_PYTHON)
      return pyodide
    })()
  }
  return pyodidePromise
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

// Both entry points below take `allSources` -- the caller's full
// current view of every cell's source (own edits + whatever the
// document currently shows) -- since the graph must be rebuilt fresh
// each call (see this module's own header comment for why there's no
// persistent Deck object to keep in sync incrementally client-side).
export async function runCellClientSide(
  cellName: string,
  allSources: Record<string, string>,
): Promise<Record<string, PyodideCellResult>> {
  const pyodide = await getPyodide()
  const sourcesB64 = toBase64(JSON.stringify(allSources))
  const call = `run_cell_and_dependents_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(sourcesB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as Record<string, PyodideCellResult>
}

export async function runAllClientSide(
  allSources: Record<string, string>,
): Promise<Record<string, PyodideCellResult>> {
  const pyodide = await getPyodide()
  const sourcesB64 = toBase64(JSON.stringify(allSources))
  const call = `run_all_b64(${JSON.stringify(sourcesB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as Record<string, PyodideCellResult>
}
