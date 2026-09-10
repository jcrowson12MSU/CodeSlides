import { useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../chatState'

// TODO.md #66-iv: collapsed to a small corner affordance by default;
// expands to a full-height overlay column on the right edge of the
// viewport (PROPOSAL_review_workflow.md section 2.1/2.2.5 -- a real
// layout surface once expanded, not a floating popover, though this
// overlays rather than reflows the existing cells/slides content to
// keep the change self-contained). Gated on `documentId` by the caller
// (App.tsx), same as `PeerList` -- there's nobody to chat with on a
// solo connection.
//
// `expanded`/`onExpandedChange` are controlled by App.tsx (not local
// state) so it can also add right-padding to the page's own content
// while the panel is open -- confirmed via a real browser that without
// this, the panel's `position: fixed` overlay silently intercepts
// clicks on whatever cell content happens to sit at that same
// horizontal position (e.g. a cell's own "Push"/header controls),
// rather than just visually covering it.
export function ChatPanel({
  messages,
  ownUserId,
  onSendMessage,
  expanded,
  onExpandedChange,
}: {
  messages: ChatMessage[]
  ownUserId: string | null
  onSendMessage: (text: string) => void
  expanded: boolean
  onExpandedChange: (expanded: boolean) => void
}) {
  const [draft, setDraft] = useState('')
  const listRef = useRef<HTMLDivElement | null>(null)
  const lastSeenCountRef = useRef(0)

  // TODO.md #66-iv: a small unread-count badge on the collapsed
  // affordance -- otherwise a message posted while the panel is
  // collapsed is silently invisible until someone happens to expand it.
  const unreadCount = expanded ? 0 : Math.max(0, messages.length - lastSeenCountRef.current)
  useEffect(() => {
    if (expanded) lastSeenCountRef.current = messages.length
  }, [expanded, messages.length])

  useEffect(() => {
    if (!expanded) return
    const el = listRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [expanded, messages.length])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return
    onSendMessage(text)
    setDraft('')
  }

  if (!expanded) {
    return (
      <button
        type="button"
        className="cs-chat-affordance"
        aria-label={unreadCount > 0 ? `Open chat (${unreadCount} new)` : 'Open chat'}
        title="Chat"
        onClick={() => onExpandedChange(true)}
      >
        <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
          <path
            d="M3 4h14a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H8l-4 3v-3H3a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
        </svg>
        {unreadCount > 0 && <span className="cs-chat-unread-badge">{unreadCount}</span>}
      </button>
    )
  }

  return (
    <div className="cs-chat-panel" role="complementary" aria-label="Chat">
      <div className="cs-chat-panel-header">
        <span className="cs-chat-panel-title">Chat</span>
        <button
          type="button"
          className="cs-chat-collapse-toggle"
          aria-label="Close chat"
          title="Close chat"
          onClick={() => onExpandedChange(false)}
        >
          <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path
              d="M4 4l8 8M12 4l-8 8"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
        </button>
      </div>
      <div className="cs-chat-message-list" ref={listRef}>
        {messages.length === 0 && <p className="cs-chat-empty">No messages yet.</p>}
        {messages.map((m) =>
          m.isSystem ? (
            <div key={m.messageId} className="cs-chat-system-message">
              {m.text}
            </div>
          ) : (
            <div key={m.messageId} className="cs-chat-message">
              <span
                className="cs-chat-message-avatar"
                style={{ backgroundColor: m.color }}
                aria-hidden="true"
              >
                {m.displayName.slice(0, 1).toUpperCase()}
              </span>
              <div className="cs-chat-message-body">
                <div className="cs-chat-message-meta">
                  <span className="cs-chat-message-author">
                    {m.userId === ownUserId ? 'You' : m.displayName}
                  </span>
                </div>
                <div className="cs-chat-message-text">{m.text}</div>
              </div>
            </div>
          ),
        )}
      </div>
      <form className="cs-chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          className="cs-chat-input"
          placeholder="Message..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="Chat message"
        />
        <button type="submit" className="cs-chat-send-button" disabled={!draft.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}
