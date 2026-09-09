// Static Python-language completion data (AUTOCOMPLETE_TODO.md item 1).
//
// Keywords and built-in functions/constants are NOT hand-listed here --
// `@codemirror/lang-python` already ships `globalCompletion` (keywords +
// builtins + exception classes + dunder names, each labeled with a
// `type` for the popup's icon) wired as `pythonLanguage`'s default
// `autocomplete` data. Adding `autocompletion()` to CodeEditor's
// extensions (item 5) activates it automatically -- reusing upstream's
// own list is more accurate and less code than re-deriving the same
// data by hand.
//
// What upstream does NOT cover: built-in *method* names offered after a
// `.` (str.upper, list.append, etc.), since that needs to key off
// whatever's before the `.`, not the global scope. Generated once
// against a real Python install (matching this project's
// `requires-python = ">=3.11"` from pyproject.toml -- this method
// surface hasn't changed across 3.11-3.13):
//
//   python3 -c "..." over str/list/dict/set/tuple/int/float's own
//   public dir()
//
// Regenerate by re-running the equivalent snippet against a newer
// interpreter if this project's minimum Python version ever moves past
// what's reflected here.

// Flat, type-blind method names offered after a `.` (AUTOCOMPLETE_TODO.md
// item 1's documented limitation: without real type inference, there's
// no way to know a value's runtime type from source text alone, so this
// offers the union of every builtin type's public methods regardless of
// what the value before the `.` actually is -- e.g. `"5".append` would
// still be offered even though only list has `append`. Standard
// behavior for a lightweight, non-language-server editor.
const METHODS_BY_TYPE: Record<string, readonly string[]> = {
  str: [
    'capitalize',
    'casefold',
    'center',
    'count',
    'encode',
    'endswith',
    'expandtabs',
    'find',
    'format',
    'format_map',
    'index',
    'isalnum',
    'isalpha',
    'isascii',
    'isdecimal',
    'isdigit',
    'isidentifier',
    'islower',
    'isnumeric',
    'isprintable',
    'isspace',
    'istitle',
    'isupper',
    'join',
    'ljust',
    'lower',
    'lstrip',
    'maketrans',
    'partition',
    'removeprefix',
    'removesuffix',
    'replace',
    'rfind',
    'rindex',
    'rjust',
    'rpartition',
    'rsplit',
    'rstrip',
    'split',
    'splitlines',
    'startswith',
    'strip',
    'swapcase',
    'title',
    'translate',
    'upper',
    'zfill',
  ],
  list: ['append', 'clear', 'copy', 'count', 'extend', 'index', 'insert', 'pop', 'remove', 'reverse', 'sort'],
  dict: ['clear', 'copy', 'fromkeys', 'get', 'items', 'keys', 'pop', 'popitem', 'setdefault', 'update', 'values'],
  set: [
    'add',
    'clear',
    'copy',
    'difference',
    'difference_update',
    'discard',
    'intersection',
    'intersection_update',
    'isdisjoint',
    'issubset',
    'issuperset',
    'pop',
    'remove',
    'symmetric_difference',
    'symmetric_difference_update',
    'union',
    'update',
  ],
  tuple: ['count', 'index'],
  int: [
    'as_integer_ratio',
    'bit_count',
    'bit_length',
    'conjugate',
    'denominator',
    'from_bytes',
    'imag',
    'is_integer',
    'numerator',
    'real',
    'to_bytes',
  ],
  float: ['as_integer_ratio', 'conjugate', 'fromhex', 'hex', 'imag', 'is_integer', 'real'],
}

export const PYTHON_BUILTIN_METHODS: readonly string[] = [...new Set(Object.values(METHODS_BY_TYPE).flat())].sort()
