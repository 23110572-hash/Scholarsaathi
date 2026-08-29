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
      {!isHome && (
        <footer className="border-t-4 border-[#ff9933] bg-[#f7f9fd] px-5 py-10 text-[#101827] sm:px-8">
          <div className="mx-auto grid max-w-[86rem] items-center gap-7 md:grid-cols-[1fr_1.2fr_auto]">
            <SiteBrand />
            <p className="m-0 max-w-xl text-xs leading-relaxed text-[#5d6a80]">AI guidance is not an official eligibility decision. Verify requirements and deadlines with the scholarship provider before applying.</p>
            <div className="grid gap-2 text-xs md:text-right">
              <span className="text-[#5d6a80]">© 2026 ScholarSaathi</span>
              <Link className="text-[#16305e]" to="/providers">Provider information</Link>
            </div>
          </div>
        </footer>
      )}
    </div>
  )
}
