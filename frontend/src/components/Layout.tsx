import type { PropsWithChildren } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { SiteBrand, SiteNavigation } from './SiteNavigation'

export function Layout({ children }: PropsWithChildren) {
  const location = useLocation()
  const isHome = location.pathname === '/'

  return (
    <div className="site-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      {!isHome && <SiteNavigation variant="shell" />}
      <div id="main-content" tabIndex={-1}>{children}</div>
      <footer className={`border-t px-5 py-10 sm:px-8 ${isHome ? 'border-white/10 bg-[#0d1713] text-white' : 'border-[#d8e0d9] bg-[#f7f9f4] text-[#142019]'}`}>
        <div className="mx-auto grid max-w-[86rem] items-center gap-7 md:grid-cols-[1fr_1.2fr_auto]">
          <SiteBrand inverse={isHome} />
          <p className={`m-0 max-w-xl text-xs leading-relaxed ${isHome ? 'text-white/52' : 'text-[#68756f]'}`}>AI guidance is not an official eligibility decision. Verify requirements and deadlines with the scholarship provider before applying.</p>
          <div className="grid gap-2 text-xs md:text-right">
            <span className={isHome ? 'text-white/45' : 'text-[#68756f]'}>© 2026 ScholarSaathi</span>
            <Link className={isHome ? 'text-white/75 hover:text-white' : 'text-[#245b49]'} to="/providers">Provider information</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
