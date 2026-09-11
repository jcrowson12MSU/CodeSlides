// TODO.md #64: copies the subset of src/codeslides/ that's proven
// (PYSCRIPT_SPIKE_FINDINGS.md, PROPOSAL_pyscript_execution.md section 1)
// to run unmodified inside Pyodide -- graph.py, cs.py, output.py,
// turtle.py -- into frontend/public/codeslides_pyscript/ so Vite serves
// them as static files the browser can fetch and write into Pyodide's
// virtual filesystem. Run before dev/build so these can never silently
// drift out of sync with the real server-side source (a hand-copied
// duplicate would be exactly that risk) -- this is a copy step, not a
// second copy of the source to maintain.
//
// deck.py is a dependency of graph.py (`from codeslides.deck import
// Cell, Deck`) but is NOT copied here yet -- the first implementation
// slice (one cell, no elements, no dependency graph) doesn't need
// graph.py itself loaded, only cs.py/output.py/turtle.py for a single
// cell's own execution. graph.py and its own dependency on deck.py join
// this list once the dependency-graph slice is built.
import { mkdirSync, copyFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const srcDir = join(__dirname, '..', '..', 'src', 'codeslides')
const destDir = join(__dirname, '..', 'public', 'codeslides_pyscript')

const MODULES = ['cs.py', 'output.py', 'turtle.py']

mkdirSync(destDir, { recursive: true })
for (const name of MODULES) {
  copyFileSync(join(srcDir, name), join(destDir, name))
}
// An empty __init__.py so these copy into Pyodide's virtual FS as a
// real importable `codeslides` package (see pyscript_spike/spike2_real_modules.html,
// which proved this exact FS layout works) -- not copied from src/
// (codeslides/__init__.py there is the real package's own non-empty
// init, which imports the rest of the package and its own real
// dependencies; the Pyodide-side package deliberately stays an empty
// marker file, only the four proven-portable modules above).
writeFileSync(join(destDir, '__init__.py'), '')

console.log(`Synced ${MODULES.length} Pyodide-target modules to ${destDir}`)
