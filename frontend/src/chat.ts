// The chat API contract. These mirror ProductCard, ProductResults, and ChatMessage in backend/models.py.

/** One product card: built by the backend from the database, never written by the model. */
export interface ProductCard {
  product_id: string
  name: string
  garment_type: string
  price: number
  image_url: string
  short_description: string
  colors: string[]
  total_stock: number
}

/** The structured product matches attached to an assistant reply. */
export interface ProductResults {
  title: string
  products: ProductCard[]
}

/** Where the shopper is when they send a message (PageContext in backend/models.py). */
export interface PageContext {
  path: string
  product_id: string | null
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  results?: ProductResults | null
}

async function errorDetail(res: Response): Promise<string> {
  try {
    const { detail } = await res.json()
    if (typeof detail === 'string') return detail
  } catch {
    // fall through
  }
  return "The assistant couldn't answer just now. Please try again."
}

/**
 * Send one message to the Campus Customs agent (POST /api/chat).
 * `page` tells the agent which page (and product) the shopper is on. Who is chatting is never
 * sent: the backend reads it from the login session. `history` is only used when the shopper
 * is logged out; logged-in conversations are saved and reloaded on the server.
 */
export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
  page: PageContext,
): Promise<ChatMessage> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      page,
      history: history.slice(-20).map(({ role, content }) => ({ role, content })),
    }),
  })
  if (!res.ok) throw new Error(await errorDetail(res))
  return res.json()
}

/**
 * Like sendChatMessage, but uses POST /api/chat/stream (Server-Sent Events) so progress lines
 * ("Searching the catalogue for hoodies…") reach `onStatus` while the agent works. The reply
 * itself arrives whole at the end, after the backend's fact-check has approved it.
 */
export async function streamChatMessage(
  message: string,
  history: ChatMessage[],
  page: PageContext,
  onStatus: (text: string) => void,
): Promise<ChatMessage> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({
      message,
      page,
      history: history.slice(-20).map(({ role, content }) => ({ role, content })),
    }),
  })
  if (!res.ok || !res.body) throw new Error(await errorDetail(res))

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    // Events are separated by a blank line: "event: <name>\ndata: <json>\n\n"
    let end
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      const event = /^event: (.*)$/m.exec(block)?.[1]
      const data = /^data: (.*)$/m.exec(block)?.[1]
      if (!event || data === undefined) continue
      const payload = JSON.parse(data)
      if (event === 'status') onStatus(payload.text)
      else if (event === 'message') return payload as ChatMessage
      else if (event === 'error') throw new Error(payload.detail)
    }
  }
  throw new Error("The assistant couldn't answer just now. Please try again.")
}

/** The logged-in shopper's saved conversation (empty when logged out). */
export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const res = await fetch('/api/chat/history')
  return res.ok ? res.json() : []
}
