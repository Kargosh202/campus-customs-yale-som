import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const MAIN_LINKS = [
  { to: '/', label: 'Home' },
  { to: '/products', label: 'Products' },
  { to: '/about', label: 'About Us' },
]

const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? 'nav-link active' : 'nav-link')

export default function NavBar() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <header className="navbar">
      <Link to="/" className="brand">
        Campus Customs
      </Link>
      <nav aria-label="Main">
        <ul className="nav-links">
          {MAIN_LINKS.map(({ to, label }) => (
            <li key={to}>
              <NavLink to={to} end={to === '/'} className={linkClass}>
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="nav-account">
        {loading ? null : user ? (
          <>
            <span className="nav-greeting">Hi, {user.first_name}</span>
            <button type="button" className="button" onClick={handleLogout}>
              Log Out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login" className={linkClass}>
              Log In
            </NavLink>
            <NavLink to="/create-account" className="button">
              Create Account
            </NavLink>
          </>
        )}
      </div>
    </header>
  )
}
