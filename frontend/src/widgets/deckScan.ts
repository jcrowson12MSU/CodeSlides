import { pythonLanguage } from '@codemirror/lang-python'

// Deck-wide static analysis for autocomplete (AUTOCOMPLETE_TODO.md items
// 3-4): parses the deck's *combined* source (deckSource.ts) fresh with
// the same Lezer Python grammar CodeMirror already uses for syntax
// highlighting (`pythonLanguage.parser`, exposed by
// `@codemirror/lang-python`) and walks the resulting tree for two kinds
// of information a single cell's own document can't provide:
//
// - every function/class/variable name defined ANYWHERE in the deck
//   (`scanDeckSymbols`) -- deliberately flat/unscoped (item 3's "start
//   with the simple flat-list version" default): a name defined inside
//   one function is still offered while typing in a totally unrelated
//   cell, same tradeoff real lightweight (non-LSP) editors make.
// - every locally-visible name introduced by an `import`/`from ...
//   import` statement anywhere in the deck, and which module it came
//   from (`scanDeckImports`) -- so module-member completion (item 4)
//   can gate on "has this been imported anywhere in the deck" rather
//   than needing to run the code.
//
// Both intentionally ignore *where* in the deck a definition sits
// relative to the cursor (item 3/4's confirmed scope decision: whole-
// deck, not position-aware) -- this is a simpler, if less strictly
// "correct", model than a real language server, chosen to match how the
// rest of this deck's line-numbering (lineOffsets.ts) already treats
// cell order as informative but not gating.
//
// This module's own parser.parse() is intentionally NOT the same tree
// CodeMirror's `EditorView` keeps for syntax highlighting -- that tree
// only covers one cell's own document. Re-parsing the joined string here
// is the price of treating "the deck" as one file for completion
// purposes; see AUTOCOMPLETE_TODO.md item 2's own note on measuring
// whether this is cheap enough to do on every keystroke.

export interface DeckSymbols {
  /** Every def/class name and every assignment target found anywhere in the deck, deduplicated. */
  names: readonly string[]
}

// Node names verified against @lezer/python's actual parse output (not
// guessed from the grammar's own minified source, which is unreadable):
// FunctionDefinition/ClassDefinition's own name is the first VariableName
// child (immediately after the `def`/`class` keyword token, before
// ParamList/Body); a bare or annotated assignment (`x = ...` / `x: T =
// ...`) is an AssignStatement whose first child is the VariableName being
// assigned (a `TypeDef` child for the annotation, if present, comes
// after it and is not itself a definition).
export function scanDeckSymbols(source: string): DeckSymbols {
  const names = new Set<string>()
  const tree = pythonLanguage.parser.parse(source)
  const cursor = tree.cursor()
  do {
    if (cursor.name === 'FunctionDefinition' || cursor.name === 'ClassDefinition') {
      const child = cursor.node.firstChild
      // First child is the `def`/`class` keyword token itself; the name
      // is the next sibling.
      const nameNode = child?.nextSibling
      if (nameNode?.name === 'VariableName') names.add(source.slice(nameNode.from, nameNode.to))
    } else if (cursor.name === 'AssignStatement') {
      const nameNode = cursor.node.firstChild
      if (nameNode?.name === 'VariableName') names.add(source.slice(nameNode.from, nameNode.to))
    }
  } while (cursor.next())
  return { names: [...names] }
}

export interface DeckImports {
  /**
   * Every name locally bound by an import anywhere in the deck, mapped
   * to the module it came from. Two distinct shapes, told apart by
   * `isModuleAlias`:
   *  - `import random` / `import random as r` bind a name (`random` or
   *    `r`) that refers to the MODULE itself -- `isModuleAlias: true`,
   *    so `r.<member>` completions are valid (moduleCompletionData.ts's
   *    member list for `random`, offered after typing `r.`).
   *  - `from random import randint` / `... as ri` bind a name
   *    (`randint`/`ri`) that refers to the imported MEMBER directly --
   *    `isModuleAlias: false`, so the bound name itself is offered as a
   *    bare completion (not `.`-triggered) once `random` has appeared
   *    anywhere in the deck; `ri.<anything>` is not a module-member
   *    completion (whatever `ri` actually is at runtime, it's not the
   *    `random` module).
   */
  boundNames: ReadonlyMap<string, { module: string; isModuleAlias: boolean }>
}

// Walks ImportStatement's direct children in source order (verified
// against @lezer/python's actual parse output for every shape below,
// not guessed from its grammar source):
//
//   import X                    ->  import, VarName(X)
//   import X as Y                ->  import, VarName(X), as, VarName(Y)
//   import X, Y                  ->  import, VarName(X), ',', VarName(Y)
//   from X import Y              ->  from, VarName(X), import, VarName(Y)
//   from X import Y as Z         ->  from, VarName(X), import, VarName(Y), as, VarName(Z)
//   from X import Y, Z           ->  from, VarName(X), import, VarName(Y), ',', VarName(Z)
//   from X import (Y, Z)         ->  same as above, `(`/`)` tokens ignored
//
// So: the first VariableName is the module (always, for both forms --
// a bare `import X` has only one VariableName total, which doubles as
// "the module"). After a `from`, the *next* VariableName after the
// `import` keyword starts a sequence of one-or-more bound names, each
// optionally renamed by a following `as VariableName`. Without `from`,
// every VariableName after the first is itself a separately bound
// module (`import a, b` binds both `a` and `b` as module aliases), also
// optionally renamed by `as`.
export function scanDeckImports(source: string): DeckImports {
  const boundNames = new Map<string, { module: string; isModuleAlias: boolean }>()
  const tree = pythonLanguage.parser.parse(source)
  const cursor = tree.cursor()
  do {
    if (cursor.name !== 'ImportStatement') continue
    let child = cursor.node.firstChild
    let hasFrom = false
    let fromModule = ''
    let seenImportKeyword = false
    // The most recently seen import target: `pending` is the name that
    // will actually be bound (renamed by a following `as`, if any) and
    // `pendingModule` is the module it belongs to -- kept as two
    // separate fields because renaming only changes what name a program
    // uses to refer to the thing, never which module it came from (e.g.
    // `import random as r` must still record module: "random", not
    // "r" -- `pending` becomes "r" when the `as` is seen, but
    // `pendingModule` stays "random" throughout). Flushed into
    // `boundNames` either when a new target starts or at the end of the
    // statement.
    let pending: string | null = null
    let pendingModule = ''
    const flush = () => {
      if (pending === null) return
      boundNames.set(pending, { module: hasFrom ? fromModule : pendingModule, isModuleAlias: !hasFrom })
      pending = null
    }
    while (child) {
      const text = source.slice(child.from, child.to)
      if (child.name === 'from') {
        hasFrom = true
      } else if (child.name === 'import') {
        seenImportKeyword = true
      } else if (child.name === 'as') {
        // Nothing to do here -- `pending` stays set (not flushed), and
        // the VariableName branch below checks its own `prevSibling`
        // to notice it's immediately after `as` and treat itself as a
        // rename of `pending` rather than a new binding.
      } else if (child.name === 'VariableName') {
        const prev = child.prevSibling
        const renaming = prev?.name === 'as'
        if (hasFrom && !seenImportKeyword) {
          // The module name in `from X import ...` -- not itself a
          // bound name.
          fromModule = text
        } else if (renaming) {
          // Only the display/bound name changes; `pendingModule` (set
          // when this target first appeared, below) is left untouched.
          pending = text
          flush()
        } else {
          flush()
          pending = text
          pendingModule = text
        }
      }
      child = child.nextSibling
    }
    flush()
  } while (cursor.next())
  return { boundNames }
}
