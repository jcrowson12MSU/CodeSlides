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

# cell_name -> {element_name: value}. Only ever holds entries for input
# elements (slider/button/text_input) that on_element_changed_b64 has
# actually set at least once -- an element never touched by the user yet
# simply isn't a key here, and _execute_one's kwargs binding below falls
# back to the element's own config["default"] in that case (Element's
# own config, not a separate seeding step -- see _build_deck).
_element_values = {}

def _decode(b64):
    return base64.b64decode(b64).decode("utf-8")

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
        exec(compile(source, f"<cell:{cell_name}>", "exec"), _namespace)
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
        elif len(return_names) > 1:
            values = value if isinstance(value, tuple) else (value,)
            if len(values) != len(return_names):
                raise ValueError(
                    f"cell {cell_name!r} returned {len(values)} values for {len(return_names)} names"
                )
            for name, item in zip(return_names, values):
                _namespace[name] = item
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

def _run_names(names, cells):
    results = {}
    for name in names:
        cell = cells[name]
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
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const call = `run_cell_and_dependents_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(cellsB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as Record<string, PyodideCellResult>
}

export async function runAllClientSide(
  allCells: Record<string, PyodideCellInput>,
): Promise<Record<string, PyodideCellResult>> {
  const pyodide = await getPyodide()
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
  const cellsB64 = toBase64(JSON.stringify(allCells))
  const valueB64 = toBase64(JSON.stringify(value))
  const call = `on_element_changed_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(toBase64(elementName))}, ${JSON.stringify(valueB64)}, ${JSON.stringify(cellsB64)})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as Record<string, PyodideCellResult>
}
