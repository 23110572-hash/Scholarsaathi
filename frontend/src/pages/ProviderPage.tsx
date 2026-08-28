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
    <main className="providers-page">
      <section className="providers-hero">
        <div className="section-pad providers-hero-inner">
          <div>
            <div className="eyebrow"><span /> Organization-owner publishing infrastructure</div>
            <h1>Publish directly.<br /><em>Guide every student clearly.</em></h1>
            <p>
              A common workspace for authenticated organization owners to create drafts, confirm
              provider-supplied evidence, publish or pause directly, and manage only their records.
            </p>
            <div className="hero-actions">
              <Link className="button provider-primary-button" to="/login/organization">
                Sign in to provider workspace <ArrowIcon />
              </Link>
              <a className="button provider-outline-button" href="#provider-model">See how it works</a>
            </div>
            <div className="provider-access-note"><ShieldIcon /> Access is restricted to authorized organization members.</div>
          </div>
          <div className="provider-console-preview" aria-label="Organization-owned scholarship publishing workspace preview">
            <div className="console-topbar"><span /><span /><span /><strong>Owner publishing workspace</strong></div>
            <div className="console-body">
              <aside><i /><i /><i /><i /></aside>
              <div>
                <p>Scholarship registry</p>
                <h2>2026–27 opportunities</h2>
                <div className="console-metrics"><span><strong>2</strong> Published</span><span><strong>1</strong> Owner draft</span></div>
                <article><BuildingIcon /><div><strong>Technical Learner Support</strong><small>Published directly · Source confirmed</small></div><b>Live</b></article>
                <article><BuildingIcon /><div><strong>New scholarship version</strong><small>Draft · Ready for owner publication</small></div><b>Draft</b></article>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="provider-types-section section-pad" id="provider-model">
        <div className="provider-section-title">
          <p className="section-kicker">One ownership model, four provider types</p>
          <h2>Built for the full scholarship ecosystem.</h2>
          <p>Each organization owns and manages only its isolated records, source evidence, publication state, and student decisions.</p>
        </div>
        <div className="provider-types-grid">
          {providerTypes.map(([name, description], index) => (
            <article key={name}>
              <span>0{index + 1}</span>
              <BuildingIcon />
              <h3>{name}</h3>
              <p>{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="provider-value-section">
        <div className="section-pad provider-value-grid">
          <div>
            <p className="section-kicker">Why a shared platform</p>
            <h2>Keep ownership. Remove duplication.</h2>
            <p>
              ScholarSaathi does not scrape or reinterpret an uncontrolled web page. Organization
              teams publish structured facts and confirm their supplied source material for discovery.
            </p>
          </div>
          <div className="provider-value-list">
            <article><SearchIcon /><div><strong>One provider-owned record</strong><p>Students find the current version your organization chose to publish.</p></div></article>
            <article><SparkIcon /><div><strong>Provider-confirmed AI evidence</strong><p>AI answers are restricted to passages your organization supplied and confirmed.</p></div></article>
            <article><ShieldIcon /><div><strong>Strict organization isolation</strong><p>Authenticated members access only their organization’s records, publication controls, and applications.</p></div></article>
          </div>
        </div>
      </section>

      <section className="provider-workflow section-pad">
        <div className="provider-section-title centered-provider-title">
          <p className="section-kicker">Owner publishing workflow</p>
          <h2>A direct path from organization draft to public record.</h2>
        </div>
        <div className="provider-workflow-grid">
          {providerSteps.map(([title, copy], index) => (
            <article key={title}>
              <span>{index + 1}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="provider-ownership section-pad">
        <div className="provider-ownership-mark"><ShieldIcon /></div>
        <div>
          <p className="section-kicker">Ownership by design</p>
          <h2>Every scholarship record and publication decision stays with its organization.</h2>
          <p>
            The platform standardizes publication, discovery, and application infrastructure.
            It does not review or approve provider publication, and it does not replace provider
            eligibility checks, selection committees, or final student decisions.
          </p>
        </div>
        <ul>
          <li>Authenticated organization membership with strict record isolation</li>
          <li>Owners, editors, and publishers directly publish and pause only their records</li>
          <li>Provider teams retain student application review and final decisions</li>
        </ul>
      </section>

      <section className="provider-final-cta">
        <div className="section-pad">
          <p className="section-kicker">Provider access</p>
          <h2>Maintain scholarships through one organization-owned workspace.</h2>
          <p>Authorized organization members can manage publication and application workflows.</p>
          <Link className="button provider-primary-button" to="/login/organization">Open provider sign in <ArrowIcon /></Link>
        </div>
      </section>
    </main>
  )
}
