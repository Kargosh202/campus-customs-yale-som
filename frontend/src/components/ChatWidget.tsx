import { useEffect, useRef, useState, type FormEvent } from 'react'
import Markdown from 'react-markdown'
import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { useChat } from '../chatContext'

// On wide screens the page shows every match of the latest reply, so that reply's chat cards
// are trimmed to the first few (see .chat-products.compact in index.css).
const CHAT_CARDS_WIDE = 4

export default function ChatWidget() {
  const { open, setOpen, messages, sending, status, send, latestResults } = useChat()
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, sending, status, open])

  // On narrow screens the chat panel covers the page, so close it when a product card is opened.
  function closeIfCovering() {
    if (window.matchMedia('(max-width: 999px)').matches) setOpen(false)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    await send(text)
    inputRef.current?.focus()
  }

  return (
    <div className="chat-widget">
      {open && (
        <section
          id="chat-panel"
          className="chat-panel"
          aria-label="Chat with Handsome Dan"
          onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
        >
          <header className="chat-header">
            <span className="dan-avatar large" aria-hidden="true" />
            <div className="chat-header-text">
              <h2>Handsome Dan</h2>
              <p>Campus Customs shopping assistant</p>
            </div>
            <button type="button" className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
              ×
            </button>
          </header>

          <div className="chat-messages" aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`chat-message ${m.role}`}>
                {m.role === 'assistant' ? (
                  <div className="chat-dan-row">
                    <span className="dan-avatar" aria-hidden="true" />
                    <div className="chat-bubble assistant">
                      <Markdown>{m.content}</Markdown>
                    </div>
                  </div>
                ) : (
                  <div className="chat-bubble user">{m.content}</div>
                )}
                {m.results && m.results.products.length > 0 && (
                  <>
                    <ul
                      className={m.results === latestResults ? 'chat-products compact' : 'chat-products'}
                      aria-label={m.results.title}
                    >
                      {m.results.products.map((p) => (
                        <li key={p.product_id}>
                          <Link to={`/products/${p.product_id}`} className="chat-product" onClick={closeIfCovering}>
                            <img src={p.image_url} alt="" loading="lazy" />
                            <span className="chat-product-name">{p.name}</span>
                            <span className="chat-product-price">
                              {formatPrice(p.price)}
                              {p.total_stock === 0 && <span className="chat-product-soldout"> · Out of stock</span>}
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                    {m.results === latestResults && m.results.products.length > CHAT_CARDS_WIDE && (
                      <p className="chat-more-note">+{m.results.products.length - CHAT_CARDS_WIDE} more on the page</p>
                    )}
                  </>
                )}
              </div>
            ))}
            {sending && (
              <div className="chat-dan-row">
                <span className="dan-avatar" aria-hidden="true" />
                <p className="chat-bubble assistant typing" role="status">
                  <span className="typing-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  {status ?? 'Thinking…'}
                </p>
              </div>
            )}
            <div ref={endRef} />
          </div>

          <form className="chat-input" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask Handsome Dan…"
              aria-label="Message"
              maxLength={2000}
            />
            <button type="submit" className="button" disabled={!draft.trim() || sending}>
              Send
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        className="chat-toggle"
        aria-expanded={open}
        aria-controls="chat-panel"
        onClick={() => setOpen((o) => !o)}
      >
        {!open && <span className="dan-avatar" aria-hidden="true" />}
        {open ? 'Close chat' : 'Ask Handsome Dan'}
      </button>
    </div>
  )
}
