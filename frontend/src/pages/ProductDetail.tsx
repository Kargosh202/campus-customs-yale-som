import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchProduct, formatPrice, NotFoundError, type Product } from '../api'

const LOW_STOCK = 5

export default function ProductDetail() {
  const { productId = '' } = useParams()
  // Tagged with the id it was loaded for, so a stale result isn't shown after navigating.
  const [result, setResult] = useState<{ id: string; product?: Product; error?: 'not-found' | 'failed' }>()

  useEffect(() => {
    fetchProduct(productId)
      .then((product) => setResult({ id: productId, product }))
      .catch((e) => setResult({ id: productId, error: e instanceof NotFoundError ? 'not-found' : 'failed' }))
  }, [productId])

  const current = result?.id === productId ? result : undefined
  const product = current?.product
  const error = current?.error

  const back = (
    <Link to="/products" className="back-link">
      ← All products
    </Link>
  )

  if (error) {
    return (
      <section>
        {back}
        <h1>{error === 'not-found' ? 'Product not found' : "We couldn't load this product"}</h1>
      </section>
    )
  }
  if (!product) {
    return (
      <section>
        {back}
        <p className="muted">Loading…</p>
      </section>
    )
  }

  return (
    <section>
      {back}
      <div className="product-detail">
        <img src={product.image_url} alt={product.name} className="product-detail-image" />
        <div className="product-detail-info">
          <p className="garment-type">{product.garment_type}</p>
          <h1>{product.name}</h1>
          <p className="price large">{formatPrice(product.price)}</p>
          <p>{product.description}</p>

          <h2>Colors</h2>
          <p>{product.colors.join(', ')}</p>

          <h2>Sizes</h2>
          {product.total_stock === 0 ? (
            <p className="muted">Currently out of stock in all sizes.</p>
          ) : (
            <ul className="size-list">
              {product.inventory.map(({ size, quantity }) => (
                <li key={size} className={quantity === 0 ? 'size sold-out' : 'size'}>
                  <span className="size-label">{size}</span>
                  <span className="size-stock">
                    {quantity === 0 ? 'Out of stock' : quantity <= LOW_STOCK ? `Only ${quantity} left` : 'In stock'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
