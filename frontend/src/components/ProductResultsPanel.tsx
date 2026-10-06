import { useEffect, useRef } from 'react'
import { useChat } from '../chatContext'
import ProductCardView from './ProductCardView'

/**
 * Shows the assistant's latest product matches as cards on the page, next to the chat.
 * Every card links to its product page (/products/:id), the same as on the Products page.
 * `below` places it under a product's detail view instead of at the top of the page.
 */
export default function ProductResultsPanel({ below = false }: { below?: boolean }) {
  const { latestResults, dismissResults } = useChat()
  const ref = useRef<HTMLElement>(null)

  // Scroll to new results when they arrive (not when this panel just moved to another page).
  const shownResults = useRef(latestResults)
  useEffect(() => {
    if (latestResults && latestResults !== shownResults.current) {
      ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
    shownResults.current = latestResults
  }, [latestResults])

  if (!latestResults) return null
  const { title, products } = latestResults

  return (
    <section
      ref={ref}
      className={below ? 'results-panel below' : 'results-panel'}
      aria-labelledby="results-heading"
      aria-live="polite"
    >
      <header className="results-header">
        <div>
          <p className="results-eyebrow">From your chat</p>
          <h2 id="results-heading">{title}</h2>
          <p className="muted">
            {products.length} {products.length === 1 ? 'product' : 'products'}
          </p>
        </div>
        <button type="button" className="results-close" onClick={dismissResults}>
          Clear
        </button>
      </header>
      <ul className="product-grid">
        {products.map((p) => (
          <li key={p.product_id}>
            <ProductCardView
              productId={p.product_id}
              name={p.name}
              price={p.price}
              imageUrl={p.image_url}
              info={p.short_description}
              outOfStock={p.total_stock === 0}
            />
          </li>
        ))}
      </ul>
    </section>
  )
}
