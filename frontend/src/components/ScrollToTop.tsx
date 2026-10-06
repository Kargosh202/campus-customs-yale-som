import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

/** Start each new page at the top, so opening a product card shows its detail view right away. */
export default function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}
