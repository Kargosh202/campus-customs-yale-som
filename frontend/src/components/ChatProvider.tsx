import { useEffect, useState, type ReactNode } from 'react'
import { matchPath, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import { fetchChatHistory, streamChatMessage, type ChatMessage, type ProductResults } from '../chat'
import { ChatContext, type ChatContextValue } from '../chatContext'

/** Handsome Dan's opening line in the chat. */
function greeting(firstName?: string, returning = false): ChatMessage {
  if (firstName && returning) {
    return {
      role: 'assistant',
      content: `Woof! Welcome back, ${firstName}! It's Handsome Dan. Our earlier chat is above. What can I help you find today?`,
    }
  }
  return {
    role: 'assistant',
    content: `Woof! I'm Handsome Dan${firstName ? `, and it's great to see you, ${firstName}` : ''}! I'm here to help you find the perfect Yale gear: just ask me about our hoodies, tees, sizes, or what's in stock.`,
  }
}

/** Holds the chat conversation so both the chat widget and the page can use it. */
export default function ChatProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  const currentProductId = matchPath('/products/:productId', location.pathname)?.params.productId ?? null

  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([greeting()])
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [latestResults, setLatestResults] = useState<ProductResults | null>(null)

  // Logging in loads that shopper's saved conversation; logging out starts a fresh one.
  useEffect(() => {
    if (loading) return
    let cancelled = false
    const load = user ? fetchChatHistory() : Promise.resolve([])
    load.then((saved) => {
      if (cancelled) return
      // A returning shopper sees their saved conversation, then a welcome-back note at the bottom.
      setMessages(saved.length > 0 ? [...saved, greeting(user?.first_name, true)] : [greeting(user?.first_name)])
      setLatestResults(null)
    })
    return () => {
      cancelled = true
    }
  }, [user, loading])

  async function send(text: string) {
    // Only used by the backend when logged out (then messages[0] is the greeting); logged-in
    // history is read from the database instead.
    const earlier = messages.slice(1)
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setSending(true)
    setStatus(null)
    try {
      const reply = await streamChatMessage(
        text,
        earlier,
        { path: location.pathname, product_id: currentProductId },
        setStatus,
      )
      setMessages((prev) => [...prev, reply])
      if (reply.results?.products.length) setLatestResults(reply.results)
    } catch (err) {
      const content = err instanceof Error ? err.message : 'Sorry, something went wrong. Please try again.'
      setMessages((prev) => [...prev, { role: 'assistant', content }])
    } finally {
      setSending(false)
      setStatus(null)
    }
  }

  const value: ChatContextValue = {
    open,
    setOpen,
    messages,
    sending,
    status,
    send,
    latestResults,
    dismissResults: () => setLatestResults(null),
  }
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>
}
