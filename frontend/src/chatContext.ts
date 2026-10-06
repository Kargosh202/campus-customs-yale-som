import { createContext, useContext } from 'react'
import type { ChatMessage, ProductResults } from './chat'

export interface ChatContextValue {
  open: boolean
  setOpen: (open: boolean | ((open: boolean) => boolean)) => void
  messages: ChatMessage[]
  sending: boolean
  /** What the assistant is doing right now, e.g. "Checking stock…" (while sending). */
  status: string | null
  send: (text: string) => Promise<void>
  /** The newest product matches from this session, shown as cards on the page. */
  latestResults: ProductResults | null
  dismissResults: () => void
}

export const ChatContext = createContext<ChatContextValue | null>(null)

export function useChat(): ChatContextValue {
  const ctx = useContext(ChatContext)
  if (!ctx) throw new Error('useChat must be used inside <ChatProvider>')
  return ctx
}
