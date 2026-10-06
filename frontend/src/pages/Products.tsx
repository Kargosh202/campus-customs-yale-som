import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, type ProductSummary } from '../api'
import ProductCardView from '../components/ProductCardView'

const SORT_OPTIONS = {
  name: 'Name (A to Z)',
  'price-asc': 'Price: Low to High',
  'price-desc': 'Price: High to Low',
} as const

type SortKey = keyof typeof SORT_OPTIONS

const isSortKey = (value: string | null): value is SortKey => value !== null && value in SORT_OPTIONS

function sortProducts(products: ProductSummary[], sort: SortKey): ProductSummary[] {
  const byName = (a: ProductSummary, b: ProductSummary) => a.name.localeCompare(b.name)
  const sorted = [...products]
  if (sort === 'price-asc') sorted.sort((a, b) => a.price - b.price || byName(a, b))
  else if (sort === 'price-desc') sorted.sort((a, b) => b.price - a.price || byName(a, b))
  else sorted.sort(byName)
  return sorted
}

export default function Products() {
  const [products, setProducts] = useState<ProductSummary[] | null>(null)
  const [error, setError] = useState(false)
  // Kept in the URL (?sort=price-asc) so it survives opening a product and coming back.
  const [searchParams, setSearchParams] = useSearchParams()
  const sortParam = searchParams.get('sort')
  const sort: SortKey = isSortKey(sortParam) ? sortParam : 'name'

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch(() => setError(true))
  }, [])

  const sorted = useMemo(() => (products ? sortProducts(products, sort) : null), [products, sort])

  function changeSort(value: string) {
    setSearchParams(value === 'name' ? {} : { sort: value }, { replace: true })
  }

  return (
    <section>
      <h1>Products</h1>
      {error && <p className="muted">We couldn't load the catalogue. Please try again later.</p>}
      {!error && sorted === null && <p className="muted">Loading products…</p>}
      {sorted && (
        <>
          <div className="products-toolbar">
            <p className="muted">{sorted.length} items</p>
            <label className="sort-control">
              Sort by
              <select value={sort} onChange={(e) => changeSort(e.target.value)}>
                {Object.entries(SORT_OPTIONS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ul className="product-grid">
            {sorted.map((p) => (
              <li key={p.product_id}>
                <ProductCardView
                  productId={p.product_id}
                  name={p.name}
                  price={p.price}
                  imageUrl={p.image_url}
                  info={p.description}
                />
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
