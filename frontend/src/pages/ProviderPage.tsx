import { Link } from 'react-router-dom'
import { ArrowIcon } from '../components/Icons'

export function ProviderPage() {
  return (
    <main className="modern-workspace-page modern-provider-page" style={{ minHeight: 'calc(100vh - 80px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="modern-container" style={{ padding: '0 2rem' }}>
        <section className="glass-card" style={{ padding: 'clamp(2rem, 5vw, 5rem)', textAlign: 'center', background: 'rgba(255, 255, 255, 0.95)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255, 255, 255, 0.4)', borderRadius: '1.5rem', boxShadow: '0 20px 40px -10px rgba(0, 0, 0, 0.2)' }}>
          <p className="eyebrow" style={{ justifyContent: 'center' }}>Provider access</p>
          <h2 style={{ fontSize: 'clamp(2rem, 5vw, 3rem)', margin: '1rem auto 2rem', color: '#0f172a', maxWidth: '800px' }}>Maintain scholarships through one organization-owned workspace.</h2>
          <p style={{ color: '#64748b', fontSize: '1.2rem', marginBottom: '3rem' }}>Authorized organization members can manage publication and application workflows.</p>
          <Link className="modern-button-primary" to="/login/organization" style={{ fontSize: '1.1rem', padding: '1.25rem 3rem' }}>
            Open provider sign in <ArrowIcon />
          </Link>
        </section>
      </div>
    </main>
  )
}
