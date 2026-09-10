import { useMemo } from 'react'
import type { ServerMessage } from './protocol'

// TODO.md #66: client-side chat history for a shared document, reduced
// from the same ordered ServerMessage stream presenceState.ts already
// reduces peer state from -- append-only, same as the server's own
// Session.chat_messages list (PROPOSAL_review_workflow.md section 2.2).
export interface ChatMessage {
  messageId: string
  userId: string
  displayName: string
  color: string
  text: string
  sentAt: string
  isSystem: boolean
}

export function reduceChatState(messages: ServerMessage[]): ChatMessage[] {
  const chat: ChatMessage[] = []

  for (const message of messages) {
    if (message.type !== 'chat_message_received') continue
    chat.push({
      messageId: message.message_id,
      userId: message.user_id,
      displayName: message.display_name,
      color: message.color,
      text: message.text,
      sentAt: message.sent_at,
      isSystem: message.is_system,
    })
  }

  return chat
}

export function useChatState(messages: ServerMessage[]): ChatMessage[] {
  return useMemo(() => reduceChatState(messages), [messages])
}
