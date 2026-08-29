import { useEffect, useState } from 'react'
import type { PropsWithChildren } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { destinationForRealm, useAuth } from '../context/AuthContext'
import { MenuIcon } from './Icons'

export function Brand() {
  return (
    <Link className="brand" to="/" aria-label="ScholarSaathi home">
      <img src="/logo.png" alt="ScholarSaathi Logo" style={{ height: '40px' }} />
    </Link>
  )
}

export function Layout({ children }: PropsWithChildren) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!menuOpen) return
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [menuOpen])

  async function handleLogout() {
    await logout()
    navigate('/')
  }

  return (
    <div className="site-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className="topbar">
        <Brand />
        <button
          className="menu-button"
          type="button"
          aria-label="Toggle navigation"
          aria-controls="main-navigation"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((value) => !value)}
        >
          <MenuIcon />
        </button>
        <nav
          id="main-navigation"
          className={menuOpen ? 'topnav open' : 'topnav'}
          aria-label="Main navigation"
          onClick={() => setMenuOpen(false)}
        >
          <NavLink to="/" end>Home</NavLink>
          <NavLink to="/scholarships">Scholarships</NavLink>
          {user ? (
            <>
              <NavLink to={destinationForRealm(user.realm)}>
                {user.realm === 'STUDENT' ? 'AI workspace' : 'Workspace'}
              </NavLink>
              {user.realm === 'STUDENT' && <NavLink to="/student/applications">Applications</NavLink>}
              <button className="text-button" type="button" onClick={() => void handleLogout()}>Sign out</button>
            </>
          ) : (
            <>
              <NavLink to="/login/student">Student sign in</NavLink>
              <NavLink className="nav-cta" to="/providers">Providers</NavLink>
            </>
          )}
        </nav>
      </header>
      <div id="main-content" tabIndex={-1}>{children}</div>
      <footer className="footer">
        <Brand />
        <p>For scholarship queries, use the contact information shown on the scholarship page.</p>
        <span>© 2026 ScholarSaathi</span>
      </footer>
    </div>
  )
}
