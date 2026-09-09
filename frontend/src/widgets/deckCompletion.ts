import type { Completion, CompletionContext, CompletionResult, CompletionSource } from '@codemirror/autocomplete'
import { getDeckSource } from './deckSource'
import { scanDeckImports, scanDeckSymbols } from './deckScan'
import { MODULE_MEMBERS } from './moduleCompletionData'
import { PYTHON_BUILTIN_METHODS } from './pythonCompletionData'

// Combines AUTOCOMPLETE_TODO.md items 3-4 (deck-wide symbols, import-
// gated module members) into the two CompletionSources CodeEditor wires
// up (item 5). Keyword/builtin completion (item 1) needs no source of
// its own -- `@codemirror/lang-python`'s `globalCompletion` is already
// registered as `pythonLanguage`'s default `autocomplete` data, so it
// (and `localCompletionSource`'s own single-document local-scope
// completions) activate automatically once `autocompletion()` is added
// to the extensions array; see CodeEditor.tsx.
//
// Two triggers, two sources, matching how a `.` genuinely changes what's
// being completed (a module/value's members, not a bare name):
//
// - `deckSymbolCompletion`: bare identifier prefix -> deck-wide
//   functions/classes/variables (scanDeckSymbols) plus any bare name
//   bound by a `from X import Y` anywhere in the deck (scanDeckImports'
//   `isModuleAlias: false` entries) -- both need a fresh parse of the
//   combined deck source (deckSource.ts) since neither is visible from
//   this one editor's own document.
// - `dotCompletion`: fires only right after a `.`, offering (a) the
//   flat type-blind builtin method list (pythonCompletionData.ts), (b)
//   the curated module member list (moduleCompletionData.ts) whenever
//   the name directly before the `.` textually matches one of its own
//   keys (random/math/turtle), and (c) that same curated list again for
//   any OTHER name that scanDeckImports resolves to one of those
//   modules (e.g. `import random as r` -> `r.` also offers `random`'s
//   members).
//
//   (b) is intentionally unconditional -- NOT gated on an import scan
//   finding the module anywhere in the deck's *cell* source, unlike
//   AUTOCOMPLETE_TODO.md item 4's original plan. Reason, found during
//   real-browser verification (item 6): this app's actual decks import
//   modules at FILE/module scope (e.g. `from codeslides import turtle`
//   at the top of a .py deck file, outside any `@app.cell` function),
//   which is never part of any cell's own `source` -- cells only ever
//   contain a function body. So a deck-wide scan of concatenated cell
//   sources structurally cannot see a real deck's actual imports; gating
//   on it would mean `turtle.forward` (this project's single most-used
//   module) never completes in practice, only in a synthetic test where
//   `import turtle` is typed directly inside a cell. Import-gating (c)
//   is kept for the general case (a name a user actually binds inside a
//   cell), but random/math/turtle specifically are always offered after
//   `.` since they're this app's de facto always-available modules.
export const deckSymbolCompletion: CompletionSource = (context: CompletionContext): CompletionResult | null => {
  const word = context.matchBefore(/[A-Za-z_][A-Za-z0-9_]*/)
  if (!word) return null
  if (word.from === word.to && !context.explicit) return null

  const deckSource = getDeckSource()
  const { names } = scanDeckSymbols(deckSource)
  const { boundNames } = scanDeckImports(deckSource)

  const options: Completion[] = []
  for (const name of names) {
    options.push({ label: name, type: 'variable' })
  }
  for (const [name, binding] of boundNames) {
    // Module aliases (`import random as r`) are offered as part of
    // dotCompletion's own module-name suggestions implicitly (typing
    // `r` and then `.` is just this same bare-identifier completion
    // followed by dotCompletion, no special-casing needed here) --
    // but they're also valid bare names in their own right (`r` by
    // itself refers to the module object), so both kinds are listed
    // here as plain variables/module names.
    options.push({ label: name, type: binding.isModuleAlias ? 'namespace' : 'function', detail: binding.module })
  }
  return { from: word.from, options, validFor: /^[A-Za-z_][A-Za-z0-9_]*$/ }
}

export const dotCompletion: CompletionSource = (context: CompletionContext): CompletionResult | null => {
  // Only fire immediately after `objectOrModule.partialName` -- matches
  // the identifier immediately preceding the cursor, requiring a `.`
  // right before it (and, before that, another identifier -- the
  // module/value being accessed).
  const match = context.matchBefore(/([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z0-9_]*)/)
  if (!match) return null
  const dotIndex = match.text.indexOf('.')
  const beforeDot = match.text.slice(0, dotIndex)
  const afterDotStart = match.from + dotIndex + 1

  const options: Completion[] = PYTHON_BUILTIN_METHODS.map((name) => ({ label: name, type: 'method' }))

  // (b): unconditional -- see this function's own docstring above for
  // why random/math/turtle specifically aren't import-gated.
  const directModule = MODULE_MEMBERS[beforeDot]
  if (directModule) {
    for (const name of directModule) options.push({ label: name, type: 'function', detail: beforeDot })
  } else {
    // (c): import-gated fallback for any other name a user has actually
    // bound (inside a cell) to one of the curated modules.
    const deckSource = getDeckSource()
    const { boundNames } = scanDeckImports(deckSource)
    const binding = boundNames.get(beforeDot)
    const members = binding && MODULE_MEMBERS[binding.module]
    if (binding && members) {
      for (const name of members) options.push({ label: name, type: 'function', detail: binding.module })
    }
  }
  return { from: afterDotStart, options, validFor: /^[A-Za-z0-9_]*$/ }
}
