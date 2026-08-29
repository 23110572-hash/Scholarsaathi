import { LayoutDashboard, LogOut, Menu, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { destinationForRealm, useAuth } from '@/context/AuthContext'

const primaryItems = [
  { label: 'Home', to: '/' },
  { label: 'Scholarships', to: '/scholarships' },
  { label: 'Student Login', to: '/login/student' },
  { label: 'Providers', to: '/providers' },
] as const

interface SiteBrandProps {
  inverse?: boolean
  compact?: boolean
}

export function SiteBrand({ inverse = false, compact = false }: SiteBrandProps) {
  return (
    <Link className="inline-flex items-center gap-3" to="/" aria-label="ScholarSaathi home">
      <img
        src="/logo.png"
        alt=""
        width={64}
        height={64}
        className="h-14 w-14 shrink-0 object-contain drop-shadow-[0_4px_10px_rgba(0,0,0,0.28)]"
      />
      {!compact && (
        <span className="grid leading-none">
          <strong className={`text-[0.98rem] font-semibold tracking-[-0.035em] ${inverse ? 'text-[#ffffff]' : 'text-[#152019]'}`}>ScholarSaathi</strong>
          <small className={`mt-1 text-[0.58rem] font-semibold tracking-[0.14em] uppercase ${inverse ? 'text-[#d9e2dc]' : 'text-[#68736d]'}`}>Scholarship companion</small>
        </span>
      )}
    </Link>
  )
}

interface SiteNavigationProps {
  variant?: 'hero' | 'shell'
}

export function SiteNavigation({ variant = 'shell' }: SiteNavigationProps) {
  const { user, loading, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [logoutError, setLogoutError] = useState('')
  const isHero = variant === 'hero'
  const menuId = `site-navigation-${variant}`

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!menuOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [menuOpen])

  async function handleLogout() {
    setLogoutError('')
    try {
      await logout()
      navigate('/')
    } catch (caught) {
      setLogoutError(caught instanceof Error ? caught.message : 'Could not sign out')
    }
  }

  const primaryLinkClass = ({ isActive }: { isActive: boolean }) => [
    'relative rounded-full px-4 py-2.5 text-[0.82rem] font-bold transition-colors lg:px-5',
    isHero ? 'text-[#f6f8fb] hover:bg-white/12 hover:text-[#ffffff]' : 'text-[#33405a] hover:bg-[#eaeef7] hover:text-[#101827]',
    isActive ? (isHero ? 'bg-[#ff9933] text-[#0b1c3f] shadow-[0_4px_14px_rgba(0,0,0,0.3)]' : 'bg-[#10265c] text-[#ffffff]') : '',
  ].join(' ')

  const accountLinkClass = isHero
    ? 'inline-flex min-h-10 items-center gap-2 rounded-full border border-white/35 bg-[#061124]/85 px-4 text-xs font-bold text-[#ffffff] backdrop-blur-md transition hover:bg-[#132c5c]'
    : 'inline-flex min-h-10 items-center gap-2 rounded-full border border-[#ccd5e6] bg-white px-4 text-xs font-semibold text-[#16305e] transition hover:bg-[#eaeef7]'

  return (
    <header className={isHero ? 'absolute inset-x-0 top-0 z-30 px-4 py-4 sm:px-7 sm:py-5' : 'sticky top-0 z-40 border-b border-[#dbe2ee] bg-[#f9fafd]/95 px-4 py-3 shadow-[0_8px_30px_rgba(16,38,92,0.06)] backdrop-blur-xl sm:px-7'}>
      <div className="mx-auto flex w-full max-w-[90rem] items-center justify-between gap-4">
        <SiteBrand inverse={isHero} />

        <nav className={`hidden items-center rounded-full p-1.5 md:flex ${isHero ? 'border border-white/35 bg-[#061124]/90 shadow-[0_8px_28px_rgba(0,0,0,0.5)] backdrop-blur-2xl' : 'border border-[#d2dbec] bg-white shadow-[0_6px_20px_rgba(16,38,92,0.08)]'}`} aria-label="Primary navigation">
          {primaryItems.map((item) => <NavLink key={item.to} className={primaryLinkClass} to={item.to} end={item.to === '/'}>{item.label}</NavLink>)}
        </nav>

        <div className="hidden min-w-[9rem] items-center justify-end gap-2 md:flex" aria-label="Account controls">
          {!loading && user && (
            <>
              <Link className={accountLinkClass} to={destinationForRealm(user.realm)}><LayoutDashboard aria-hidden="true" className="h-4 w-4" />Workspace</Link>
              <button className={`grid h-10 w-10 place-items-center rounded-full border transition ${isHero ? 'border-white/20 bg-black/25 text-white hover:bg-white/15' : 'border-[#ced8d0] bg-white text-[#183d32] hover:bg-[#edf2ed]'}`} type="button" onClick={() => void handleLogout()} aria-label="Sign out"><LogOut aria-hidden="true" className="h-4 w-4" /></button>
            </>
          )}
        </div>

        <button className={`grid h-11 w-11 place-items-center rounded-full border md:hidden ${isHero ? 'border-white/30 bg-[#061124]/70 text-white backdrop-blur-md' : 'border-[#ccd5e6] bg-white text-[#16305e]'}`} type="button" aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-controls={menuId} aria-expanded={menuOpen} onClick={() => setMenuOpen((value) => !value)}>
          {menuOpen ? <X aria-hidden="true" className="h-5 w-5" /> : <Menu aria-hidden="true" className="h-5 w-5" />}
        </button>
      </div>

      {menuOpen && (
        <div id={menuId} className={`absolute left-4 right-4 top-full mt-2 mx-auto max-w-md rounded-3xl border p-3 shadow-2xl md:hidden ${isHero ? 'border-white/15 bg-[#08152e]/96 text-white backdrop-blur-2xl' : 'border-[#d5dcea] bg-white text-[#101827]'}`}>
          <nav className="grid gap-1" aria-label="Primary navigation">
            {primaryItems.map((item) => <NavLink key={item.to} className={({ isActive }) => `rounded-2xl px-4 py-3 text-sm font-semibold ${isActive ? (isHero ? 'bg-[#ff9933] text-[#0b1c3f]' : 'bg-[#10265c] text-white') : ''}`} to={item.to} end={item.to === '/'}>{item.label}</NavLink>)}
          </nav>
          {!loading && user && (
            <div className={`mt-2 grid gap-2 border-t pt-3 ${isHero ? 'border-white/15' : 'border-[#dce2dc]'}`} aria-label="Account controls">
              <Link className="inline-flex min-h-11 items-center gap-2 rounded-2xl px-4 text-sm font-semibold" to={destinationForRealm(user.realm)}><LayoutDashboard aria-hidden="true" className="h-4 w-4" />My workspace</Link>
              <button className="inline-flex min-h-11 items-center gap-2 rounded-2xl px-4 text-left text-sm font-semibold" type="button" onClick={() => void handleLogout()}><LogOut aria-hidden="true" className="h-4 w-4" />Sign out</button>
            </div>
          )}
        </div>
      )}
      {logoutError && <p className="absolute right-6 top-full mt-2 rounded-xl bg-[#9b2f2f] px-3 py-2 text-xs text-white" role="alert">{logoutError}</p>}
    </header>
  )
}
