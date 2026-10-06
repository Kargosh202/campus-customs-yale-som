import { matchPath, Route, Routes, useLocation } from 'react-router-dom'
import ChatProvider from './components/ChatProvider'
import ChatWidget from './components/ChatWidget'
import NavBar from './components/NavBar'
import ProductResultsPanel from './components/ProductResultsPanel'
import ScrollToTop from './components/ScrollToTop'
import { useChat } from './chatContext'
import About from './pages/About'
import CreateAccount from './pages/CreateAccount'
import Home from './pages/Home'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import ProductDetail from './pages/ProductDetail'
import Products from './pages/Products'

function Layout() {
  const { open } = useChat()
  const { pathname } = useLocation()
  // On a product page the detail view comes first and the chat's results move below it, so a
  // card clicked in the results always opens with its large image and full info in view.
  const onProductPage = matchPath('/products/:productId', pathname) !== null

  return (
    <div className={open ? 'app chat-open' : 'app'}>
      <ScrollToTop />
      <NavBar />
      <main className="page">
        {!onProductPage && <ProductResultsPanel />}
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<Login />} />
          <Route path="/create-account" element={<CreateAccount />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        {onProductPage && <ProductResultsPanel below />}
      </main>
      <footer className="footer">
        <p>Campus Customs · 57 Broadway, New Haven, CT 06511</p>
        <p>Officially Licensed Yale Merchandise</p>
      </footer>
      <ChatWidget />
    </div>
  )
}

export default function App() {
  return (
    <ChatProvider>
      <Layout />
    </ChatProvider>
  )
}
