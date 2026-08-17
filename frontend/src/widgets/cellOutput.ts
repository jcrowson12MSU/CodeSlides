export type CellOutputKind = 'text' | 'markdown' | 'image' | 'dataframe' | null

export interface DataframeTable {
  columns: string[]
  rows: unknown[][]
}

export function isDataframeTable(data: unknown): data is DataframeTable {
  return (
    typeof data === 'object' &&
    data !== null &&
    Array.isArray((data as DataframeTable).columns) &&
    Array.isArray((data as DataframeTable).rows)
  )
}

// True when there's genuinely nothing worth rendering -- an empty/None
// return value (the common case for a side-effect-only cell, e.g. one
// that only calls turtle.forward()/cs.image() into its own elements),
// as opposed to a real value that just happens to be falsy (0, "",
// False are all still worth showing). Cell.tsx uses this to skip
// rendering CellOutputView's block entirely rather than showing an
// empty <pre>.
export function hasCellOutput(kind: CellOutputKind, data: unknown, value: unknown): boolean {
  if (kind === null) return false
  if (kind === 'text') return typeof data === 'string' && data !== ''
  if (kind === 'markdown') return typeof data === 'string' && data.trim() !== ''
  if (kind === 'image') return typeof data === 'string' && data !== ''
  if (kind === 'dataframe') return isDataframeTable(data) || data !== undefined
  return value !== undefined && value !== null
}
