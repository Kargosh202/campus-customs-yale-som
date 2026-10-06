import { Link } from 'react-router-dom'
import { formatPrice } from '../api'

interface Props {
  productId: string
  name: string
  price: number
  imageUrl: string
  info: string
  outOfStock?: boolean
}

/** A product card (image, name, price, short info) linking to the product page. */
export default function ProductCardView({ productId, name, price, imageUrl, info, outOfStock }: Props) {
  return (
    <Link to={`/products/${productId}`} className="product-card">
      <img src={imageUrl} alt={name} loading="lazy" />
      <div className="product-card-body">
        <h3>{name}</h3>
        <p className="price">
          {formatPrice(price)}
          {outOfStock && <span className="out-of-stock-tag"> · Out of stock</span>}
        </p>
        <p className="product-card-desc">{info}</p>
      </div>
    </Link>
  )
}
