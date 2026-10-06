export interface SizeStock {
  size: string
  quantity: number
}

export interface ProductSummary {
  product_id: string
  name: string
  garment_type: string
  description: string
  price: number
  image_url: string
}

export interface Product extends ProductSummary {
  colors: string[]
  search_tags: string[]
  inventory: SizeStock[]
  total_stock: number
}

export class NotFoundError extends Error {}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (res.status === 404) throw new NotFoundError(path)
  if (!res.ok) throw new Error(`Request failed (${res.status})`)
  return res.json() as Promise<T>
}

export const fetchProducts = () => getJson<ProductSummary[]>('/api/products')

export const fetchProduct = (productId: string) =>
  getJson<Product>(`/api/products/${encodeURIComponent(productId)}`)

export const formatPrice = (price: number) =>
  price.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
