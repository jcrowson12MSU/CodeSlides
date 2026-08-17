import { isDataframeTable, type CellOutputKind } from './cellOutput'
import { renderMarkdown } from './markdown'

export interface CellOutputViewProps {
  kind: CellOutputKind
  data: unknown
  value: unknown
}

// Renders a cell's own returned value, resolved server-side into the
// tagged output union (ARCHITECTURE.md section 6,
// codeslides.output.resolve_output): plain text, markdown (cs.md()),
// an image (including matplotlib figures converted server-side to a
// data URI), or a DataFrame as an HTML table. Rendered by Cell.tsx as
// an always-visible block under the header -- no Output tab anymore,
// per the user's own explicit request -- right alongside the cell's
// own error block (a separate, always-shown-on-error element; this
// component only ever handles the happy path). Callers should gate on
// `hasCellOutput` (cellOutput.ts) first so a cell with nothing to show
// renders no block at all, rather than an empty one.
export function CellOutputView({ kind, data, value }: CellOutputViewProps) {
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
