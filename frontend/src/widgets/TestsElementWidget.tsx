import { CodeEditor } from './CodeEditor'
import type { TestResult } from './elementMeta'

// A `tests` element (ARCHITECTURE.md section 3b): a second, unittest-like
// code editor attached to a cell. Reuses the same CodeMirror-based
// CodeEditor as the cell's own source -- Python is Python, whether it's
// the code under test or the assertions checking it. Shift+Enter and
// Mod+Shift+Enter here both submit the *test* source (there's nothing to
// "run all" from inside a test editor), which the server runs immediately
// against the owning cell's current namespace and reports back as a
// pass/fail/error result -- never a re-run of the cell itself
// (ARCHITECTURE.md section 3b, distinct from set_ui_state's pure-no-op
// notes editing). The minimize toggle is applied by the caller (Cell.tsx),
// same as every other element kind -- this component only renders the
// editor + status badge + failure detail.
export interface TestsElementWidgetProps {
  elementId: string
  source: string
  result: TestResult | null
  onChangeSource: (source: string) => void
  // TODO.md #65 follow-up: on a review_mode document, `onChangeSource`
  // above is expected to be a no-op-until-reviewed staging function
  // (App.tsx wires push_cell here instead of set_test_source) rather
  // than immediately submitting -- this element needs the exact same
  // proposal banner/Accept/Reject/Withdraw/conflict UI Cell.tsx's own
  // primary-source path already has, since for many decks (every cell
  // hide_code=True) this editor is the *only* reachable editable
  // surface at all.
  reviewMode?: boolean
  ownUserId?: string | null
  proposals?: Record<string, { displayName: string; source: string; createdAt: string }>
  conflict?: string | null
  onWithdrawProposal?: () => void
  onAcceptProposal?: (proposerUserId: string) => void
  onRejectProposal?: (proposerUserId: string) => void
}

export function TestsElementWidget({
  elementId,
  source,
  result,
  onChangeSource,
  reviewMode = false,
  ownUserId = null,
  proposals = {},
  conflict = null,
  onWithdrawProposal,
  onAcceptProposal,
  onRejectProposal,
}: TestsElementWidgetProps) {
  // Printed output matters on every status, not just failure -- this box
  // is just as often a sample-input/sample-output demo (`print(f(3, 4))`,
  // no assertions at all) as it is an assert-only unittest-style check,
  // and a "pass" with silently-discarded stdout would be indistinguishable
  // from an empty box.
  const output = [result?.stdout, result?.stderr].filter(Boolean).join('')
  return (
    <div className="cs-element cs-element-viewer cs-tests-viewer">
      <div className="cs-tests-header">
        <span className="cs-element-label">{elementId}</span>
        {result && (
          <span className={`cs-tests-badge cs-tests-badge-${result.status}`}>{result.status}</span>
        )}
      </div>
      <div className="cs-tests-editor">
        <CodeEditor source={source} onRunCell={onChangeSource} onRunAll={onChangeSource} />
      </div>
      {result && result.status !== 'pass' && result.message && (
        <pre className={`cs-tests-message cs-tests-message-${result.status}`}>{result.message}</pre>
      )}
      {output && <pre className="cs-tests-output">{output}</pre>}
      {reviewMode && conflict != null && (
        <div className="cs-cell-proposal-conflict">
          <p>
            Someone else's change was accepted while your proposal was pending. The current test is now:
          </p>
          <pre className="cs-cell-proposal-diff">{conflict}</pre>
          <p>Re-push your change against the new version, or withdraw it.</p>
          {onWithdrawProposal && (
            <button type="button" onClick={onWithdrawProposal}>
              Withdraw my proposal
            </button>
          )}
        </div>
      )}
      {reviewMode &&
        Object.entries(proposals).map(([proposerUserId, proposal]) => {
          const isOwnProposal = ownUserId != null && proposerUserId === ownUserId
          return (
            <div className="cs-cell-proposal" key={proposerUserId}>
              <p className="cs-cell-proposal-header">
                <strong>{proposal.displayName}</strong> proposed a change to this test:
              </p>
              <pre className="cs-cell-proposal-diff">{proposal.source}</pre>
              <div className="cs-cell-proposal-actions">
                {isOwnProposal ? (
                  onWithdrawProposal && (
                    <button type="button" onClick={onWithdrawProposal}>
                      Withdraw
                    </button>
                  )
                ) : (
                  <>
                    {onAcceptProposal && (
                      <button type="button" onClick={() => onAcceptProposal(proposerUserId)}>
                        Accept
                      </button>
                    )}
                    {onRejectProposal && (
                      <button type="button" onClick={() => onRejectProposal(proposerUserId)}>
                        Reject
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          )
        })}
    </div>
  )
}
