import { Link } from 'react-router-dom'
import { ArrowIcon, BuildingIcon, SearchIcon, ShieldIcon, SparkIcon } from '../components/Icons'

const providerTypes = [
  ['Central Government', 'National schemes, ministries, and common scholarship programmes'],
  ['State Government', 'State and Union Territory departments and scholarship boards'],
  ['Private Companies', 'CSR foundations, employers, and industry-funded opportunities'],
  ['NGOs', 'Mission-led grants, fellowships, mentoring, and student support'],
]

const providerSteps = [
  ['Create an owner draft', 'Maintain scholarship terms as a versioned record owned by your organization instead of scattered notices.'],
  ['Supply and confirm evidence', 'Attach the exact provider-supplied source passages your organization confirms for student and AI use.'],
  ['Publish directly', 'Owners, editors, and publishers publish the draft themselves. ScholarSaathi has no publication approval step.'],
  ['Manage your records', 'Publish, pause, and maintain only your organization’s records; review student applications in a separate workflow.'],
]

export function ProviderPage() {
  return (
    <main className="modern-workspace-page modern-provider-page">
      <div className="modern-container" style={{ padding: '0 2rem' }}>
        <section className="modern-results-heading" style={{ marginTop: '2rem', textAlign: 'center' }}>
          <div className="eyebrow" style={{ justifyContent: 'center', marginBottom: '1rem' }}><span /> Organization-owner publishing infrastructure</div>
          <h1 style={{ fontSize: 'clamp(2.5rem, 5vw, 4rem)', marginBottom: '1rem', color: '#0f172a' }}>Publish directly.<br /><em style={{ color: 'var(--green)', fontStyle: 'normal' }}>Guide every student clearly.</em></h1>
          <p style={{ maxWidth: '700px', margin: '0 auto 2rem', color: '#64748b', fontSize: '1.2rem', lineHeight: '1.6' }}>
            A common workspace for authenticated organization owners to create drafts, confirm
            provider-supplied evidence, publish or pause directly, and manage only their records.
          </p>
          <div className="hero-actions" style={{ justifyContent: 'center', marginBottom: '2rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <Link className="modern-button-primary" to="/login/organization">
              Sign in to provider workspace <ArrowIcon />
            </Link>
            <a className="modern-button-secondary" href="#provider-model">See how it works</a>
          </div>
          <div className="provider-access-note" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', background: 'rgba(255,255,255,0.7)', borderRadius: '2rem', fontSize: '0.875rem', color: '#64748b', backdropFilter: 'blur(10px)' }}><ShieldIcon /> Access is restricted to authorized organization members.</div>
        </section>

        <section className="glass-card" style={{ padding: 'clamp(1rem, 5vw, 3rem)', margin: '4rem 0', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div className="console-topbar" style={{ display: 'flex', gap: '0.5rem', width: '100%', paddingBottom: '1rem', borderBottom: '1px solid rgba(0,0,0,0.1)', marginBottom: '2rem', alignItems: 'center' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#ef4444' }}/>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#eab308' }}/>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#22c55e' }}/>
            <strong style={{ marginLeft: '1rem', color: '#0f172a' }}>Owner publishing workspace</strong>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem', width: '100%' }}>
            <article className="glass-card modern-hover-lift" style={{ padding: '1.5rem', border: '1px solid rgba(0,0,0,0.05)', background: 'white' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                <div style={{ padding: '1rem', background: 'rgba(34,197,94,0.1)', borderRadius: '1rem', color: '#16a34a', display: 'flex' }}><BuildingIcon /></div>
                <div>
                  <h3 style={{ fontSize: '1.1rem', margin: '0', color: '#0f172a' }}>Technical Learner Support</h3>
                  <small style={{ color: '#64748b' }}>Published directly · Source confirmed</small>
                </div>
                <span style={{ marginLeft: 'auto', padding: '0.25rem 0.75rem', background: '#dcfce7', color: '#166534', borderRadius: '1rem', fontSize: '0.75rem', fontWeight: 'bold' }}>Live</span>
              </div>
            </article>
            <article className="glass-card modern-hover-lift" style={{ padding: '1.5rem', border: '1px solid rgba(0,0,0,0.05)', background: 'white' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
                <div style={{ padding: '1rem', background: 'rgba(234,179,8,0.1)', borderRadius: '1rem', color: '#ca8a04', display: 'flex' }}><BuildingIcon /></div>
                <div>
                  <h3 style={{ fontSize: '1.1rem', margin: '0', color: '#0f172a' }}>New scholarship version</h3>
                  <small style={{ color: '#64748b' }}>Draft · Ready for owner publication</small>
                </div>
                <span style={{ marginLeft: 'auto', padding: '0.25rem 0.75rem', background: '#fef3c7', color: '#92400e', borderRadius: '1rem', fontSize: '0.75rem', fontWeight: 'bold' }}>Draft</span>
              </div>
            </article>
          </div>
        </section>

        <section id="provider-model" style={{ margin: '6rem 0' }}>
          <div style={{ textAlign: 'center', marginBottom: '3rem' }}>
            <p className="eyebrow" style={{ justifyContent: 'center' }}>One ownership model, four provider types</p>
            <h2 style={{ fontSize: 'clamp(2rem, 4vw, 2.5rem)', margin: '1rem 0', color: '#0f172a' }}>Built for the full scholarship ecosystem.</h2>
            <p style={{ color: '#64748b', fontSize: '1.1rem' }}>Each organization owns and manages only its isolated records, source evidence, publication state, and student decisions.</p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '2rem' }}>
            {providerTypes.map(([name, description], index) => (
              <article key={name} className="glass-card modern-hover-lift" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem', position: 'relative', overflow: 'hidden' }}>
                <span style={{ fontSize: '6rem', fontWeight: '900', color: 'rgba(34,197,94,0.05)', lineHeight: '1', position: 'absolute', top: '-10px', right: '-10px', pointerEvents: 'none' }}>0{index + 1}</span>
                <div style={{ width: '48px', height: '48px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--green)', color: 'white', borderRadius: '50%' }}><BuildingIcon /></div>
                <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#0f172a' }}>{name}</h3>
                <p style={{ color: '#64748b', margin: 0, lineHeight: '1.6' }}>{description}</p>
              </article>
            ))}
          </div>
        </section>

        <section style={{ margin: '6rem 0' }} className="glass-card modern-hover-lift">
          <div className="provider-responsive-grid" style={{ display: 'grid', gap: '4rem', padding: 'clamp(2rem, 5vw, 4rem)', alignItems: 'center' }}>
            <div>
              <p className="eyebrow">Why a shared platform</p>
              <h2 style={{ fontSize: 'clamp(2rem, 4vw, 2.5rem)', margin: '1rem 0', color: '#0f172a' }}>Keep ownership.<br/>Remove duplication.</h2>
              <p style={{ color: '#64748b', fontSize: '1.1rem', lineHeight: '1.6', maxWidth: '500px' }}>
                ScholarSaathi does not scrape or reinterpret an uncontrolled web page. Organization
                teams publish structured facts and confirm their supplied source material for discovery.
              </p>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
              <article style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start' }}>
                <div style={{ padding: '1rem', background: 'rgba(34,197,94,0.1)', color: 'var(--green)', borderRadius: '1rem', flexShrink: 0, display: 'flex' }}><SearchIcon /></div>
                <div><strong style={{ display: 'block', fontSize: '1.2rem', marginBottom: '0.5rem', color: '#0f172a' }}>One provider-owned record</strong><p style={{ color: '#64748b', margin: 0, lineHeight: '1.5' }}>Students find the current version your organization chose to publish.</p></div>
              </article>
              <article style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start' }}>
                <div style={{ padding: '1rem', background: 'rgba(34,197,94,0.1)', color: 'var(--green)', borderRadius: '1rem', flexShrink: 0, display: 'flex' }}><SparkIcon /></div>
                <div><strong style={{ display: 'block', fontSize: '1.2rem', marginBottom: '0.5rem', color: '#0f172a' }}>Provider-confirmed AI evidence</strong><p style={{ color: '#64748b', margin: 0, lineHeight: '1.5' }}>AI answers are restricted to passages your organization supplied and confirmed.</p></div>
              </article>
              <article style={{ display: 'flex', gap: '1.5rem', alignItems: 'flex-start' }}>
                <div style={{ padding: '1rem', background: 'rgba(34,197,94,0.1)', color: 'var(--green)', borderRadius: '1rem', flexShrink: 0, display: 'flex' }}><ShieldIcon /></div>
                <div><strong style={{ display: 'block', fontSize: '1.2rem', marginBottom: '0.5rem', color: '#0f172a' }}>Strict organization isolation</strong><p style={{ color: '#64748b', margin: 0, lineHeight: '1.5' }}>Authenticated members access only their organization’s records, publication controls, and applications.</p></div>
              </article>
            </div>
          </div>
        </section>

        <section style={{ margin: '6rem 0' }}>
          <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
            <p className="eyebrow" style={{ justifyContent: 'center' }}>Owner publishing workflow</p>
            <h2 style={{ fontSize: 'clamp(2rem, 4vw, 2.5rem)', margin: '1rem 0', color: '#0f172a' }}>A direct path from organization draft to public record.</h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '2rem' }}>
            {providerSteps.map(([title, copy], index) => (
              <article key={title} className="glass-card modern-hover-lift" style={{ padding: '2.5rem 1.5rem', textAlign: 'center' }}>
                <div style={{ width: '48px', height: '48px', margin: '0 auto 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--green)', color: 'white', borderRadius: '50%', fontSize: '1.2rem', fontWeight: 'bold' }}>{index + 1}</div>
                <h3 style={{ margin: '0 0 1rem', color: '#0f172a', fontSize: '1.15rem' }}>{title}</h3>
                <p style={{ color: '#64748b', margin: 0, fontSize: '0.95rem', lineHeight: '1.6' }}>{copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="glass-card" style={{ margin: '6rem 0', padding: 'clamp(2rem, 5vw, 5rem)', textAlign: 'center', background: 'linear-gradient(135deg, rgba(255,255,255,0.9), rgba(240,253,244,0.9))' }}>
          <div style={{ width: '64px', height: '64px', margin: '0 auto 2rem', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--green)', color: 'white', borderRadius: '1rem' }}><ShieldIcon /></div>
          <p className="eyebrow" style={{ justifyContent: 'center' }}>Ownership by design</p>
          <h2 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.5rem)', margin: '1rem auto 2rem', color: '#0f172a', maxWidth: '800px' }}>Every scholarship record and publication decision stays with its organization.</h2>
          <p style={{ color: '#64748b', fontSize: '1.15rem', maxWidth: '800px', margin: '0 auto 3rem', lineHeight: '1.7' }}>
            The platform standardizes publication, discovery, and application infrastructure.
            It does not review or approve provider publication, and it does not replace provider
            eligibility checks, selection committees, or final student decisions.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', justifyContent: 'center' }}>
            <span style={{ padding: '0.75rem 1.5rem', background: 'white', borderRadius: '2rem', border: '1px solid rgba(0,0,0,0.05)', fontSize: '0.95rem', fontWeight: '600', color: '#334155' }}>🔒 Authenticated membership</span>
            <span style={{ padding: '0.75rem 1.5rem', background: 'white', borderRadius: '2rem', border: '1px solid rgba(0,0,0,0.05)', fontSize: '0.95rem', fontWeight: '600', color: '#334155' }}>📝 Direct publication controls</span>
            <span style={{ padding: '0.75rem 1.5rem', background: 'white', borderRadius: '2rem', border: '1px solid rgba(0,0,0,0.05)', fontSize: '0.95rem', fontWeight: '600', color: '#334155' }}>🎓 Provider retains final decisions</span>
          </div>
        </section>

        <section style={{ margin: '6rem 0 8rem', textAlign: 'center' }}>
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
