import { useEffect, useRef, useState } from 'react'
import type { ClientMessage, ServerMessage } from './protocol'

// Connects to the /ws endpoint (ARCHITECTURE.md section 5), tracks the
// session_id the server assigns on connect (session_created), and exposes
// a `send` function plus every ServerMessage received, in order, for
// callers to reduce over. One hook instance = one browser-tab Session.
export function useCodeSlidesSocket(url = '/ws') {
  const socketRef = useRef<WebSocket | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ServerMessage[]>([])
  const [connected, setConnected] = useState(false)

  useEffect(() => {
    const wsUrl = url.startsWith('ws')
      ? url
      : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}${url}`
    const socket = new WebSocket(wsUrl)
    socketRef.current = socket

    socket.onopen = () => setConnected(true)
    socket.onclose = () => setConnected(false)
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data) as ServerMessage
      if (message.type === 'session_created') {
        setSessionId(message.session_id)
      }
      setMessages((prev) => [...prev, message])
    }

    return () => socket.close()
  }, [url])

  function send(message: ClientMessage) {
    socketRef.current?.send(JSON.stringify(message))
  }

  return { sessionId, connected, messages, send }
}
