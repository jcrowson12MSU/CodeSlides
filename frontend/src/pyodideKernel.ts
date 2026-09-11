// TODO.md #64/PROPOSAL_pyscript_execution.md: client-side cell execution
// via Pyodide -- the first implementation slice. Deliberately scoped
// per the proposal's own section 6: one cell, no elements, no
// dependency graph yet. Loads Pyodide once per page load (from a CDN,
// per the user's own explicit choice for this early slice -- see the
// proposal's section 1 note on Pyodide hosting; self-hosting the ~10MB
// runtime can be revisited once this slice is proven out), writes the
// real, unmodified cs.py/output.py/turtle.py into Pyodide's virtual
// filesystem as a real importable `codeslides` package (exactly the
// FS layout pyscript_spike/spike2_real_modules.html already proved
// works), and exposes a `runCellClientSide` function shaped to drop
// straight into `CellState` (deckState.ts) with zero server round trip.
//
// The shared per-tab namespace (session.namespace's client-side
// equivalent) is kept entirely on the Python side, as a plain
// module-level dict in `_codeslides_runner` below -- only strings
// (cell name, source) cross the JS/Pyodide boundary via
// `runPythonAsync`, the exact mechanism pyscript_spike/index.html
// already proved reliable, rather than round-tripping a live Python
// object handle through pyodide's own JS<->Python proxy machinery
// (unverified for this exact use case, and unnecessary complexity
// when the namespace never actually needs to leave Python at all).

const PYODIDE_CDN_URL = 'https://cdn.jsdelivr.net/pyodide/v0.29.4/full/pyodide.mjs'

// The four modules confirmed (PYSCRIPT_SPIKE_FINDINGS.md) to run
// unmodified inside Pyodide. graph.py/deck.py join this list once the
// dependency-graph slice is built (see the sync script's own comment
// for why they're not here yet).
const PYODIDE_MODULE_FILES = ['cs.py', 'output.py', 'turtle.py']

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

// TODO.md #64: mirrors kernel.py's execute_cell + output.py's
// resolve_output/wire_safe_value as closely as this first slice needs
// to -- deliberately without elements/kwargs binding, deck_imports, or
// is_main handling yet (PROPOSAL_pyscript_execution.md section 6's
// scoped-first-slice call). `_namespace` is one plain module-level
// dict, shared across every `run_cell` call for the life of this page
// load -- the client-side equivalent of session.namespace, scoped to
// this one browser tab (PROPOSAL_pyscript_execution.md section 2.1: no
// execution state of any kind is ever shared across tabs).
const RUNNER_MODULE_PYTHON = `
import base64
import io
import json
import contextlib
import traceback

from codeslides import output as _output

_namespace = {}

def run_cell_b64(cell_name_b64, source_b64):
    # Cell name/source cross the JS/Pyodide boundary as base64 rather
    # than as interpolated Python string literals, to sidestep any
    # JSON-vs-Python string-escaping mismatch entirely (backslashes,
    # embedded quotes, unicode edge cases) -- decoding here is the only
    # place that needs to get the exact original bytes back, so it's
    # the one spot worth being maximally conservative about.
    cell_name = base64.b64decode(cell_name_b64).decode("utf-8")
    source = base64.b64decode(source_b64).decode("utf-8")
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        exec(compile(source, f"<cell:{cell_name}>", "exec"), _namespace)
        fn = _namespace[cell_name]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            value = fn()
    except Exception:
        return json.dumps({
            "status": "error",
            "value": None,
            "kind": None,
            "data": None,
            "error": traceback.format_exc(),
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
        })
    resolved = _output.resolve_output(value)
    return json.dumps({
        "status": "idle",
        "value": _output.wire_safe_value(value),
        "kind": resolved.kind,
        "data": resolved.data,
        "error": None,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    })
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
  // encode step is required first for any non-ASCII cell source (a
  // comment/string literal with e.g. an em dash or emoji) to survive
  // the round trip correctly.
  const bytes = new TextEncoder().encode(text)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

export async function runCellClientSide(cellName: string, source: string): Promise<PyodideCellResult> {
  const pyodide = await getPyodide()
  const call = `run_cell_b64(${JSON.stringify(toBase64(cellName))}, ${JSON.stringify(toBase64(source))})`
  const resultJson = await pyodide.runPythonAsync(call)
  return JSON.parse(resultJson as string) as PyodideCellResult
}
