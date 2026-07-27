import { renderMarkdown } from './markdown'

export interface CellOutputViewProps {
  error: string | null
  kind: 'text' | 'markdown' | 'image' | 'dataframe' | null
  data: unknown
  value: unknown
}

interface DataframeTable {
  columns: string[]
  rows: unknown[][]
}

function isDataframeTable(data: unknown): data is DataframeTable {
  return (
    typeof data === 'object' &&
    data !== null &&
    Array.isArray((data as DataframeTable).columns) &&
    Array.isArray((data as DataframeTable).rows)
  )
}

// Renders a cell's output per its resolved kind (ARCHITECTURE.md section
// 6, codeslides.output.resolve_output server-side): plain text, markdown
// (cs.md()), an image (including matplotlib figures converted server-side
// to a data URI), or a DataFrame as an HTML table. Falls back to
// JSON.stringify(value) for a null kind (no successful run yet) or an
// unrecognized shape, so a still-loading or unusual cell never renders
// blank.
export function CellOutputView({ error, kind, data, value }: CellOutputViewProps) {
  if (error) {
    return <pre className="cs-cell-output cs-cell-output-error">{error}</pre>
  }

  switch (kind) {
    case 'markdown':
      return (
        <div
          className="cs-cell-output cs-cell-output-markdown"
          dangerouslySetInnerHTML={{ __html: renderMarkdown(typeof data === 'string' ? data : '') }}
        />
      )
    case 'image':
      return (
        <div className="cs-cell-output cs-cell-output-image">
          {typeof data === 'string' && <img src={data} alt="cell output" />}
        </div>
      )
    case 'dataframe':
      if (isDataframeTable(data)) {
        return (
          <div className="cs-cell-output cs-cell-output-dataframe">
            <table>
              <thead>
                <tr>
                  {data.columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  // eslint-disable-next-line react/no-array-index-key -- rows have no stable id
                  <tr key={i}>
                    {row.map((cell, j) => (
                      // eslint-disable-next-line react/no-array-index-key -- cells have no stable id
                      <td key={j}>{JSON.stringify(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      }
      return <pre className="cs-cell-output">{JSON.stringify(data)}</pre>
    case 'text':
      return <pre className="cs-cell-output">{typeof data === 'string' ? data : JSON.stringify(data)}</pre>
    default:
      return <pre className="cs-cell-output">{JSON.stringify(value)}</pre>
  }
}
