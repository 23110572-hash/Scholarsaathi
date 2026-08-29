import { ArrowRight, Bot, Building2, Check, HeartHandshake, Landmark, MapPinned, Search, ShieldCheck, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PrismaHero } from '@/components/ui/prisma-hero'

const providerGroups = [
  { label: 'Central Government', value: 'CENTRAL_GOVERNMENT', description: 'National programmes and public scholarship schemes.', icon: Landmark },
  { label: 'State Government', value: 'STATE_GOVERNMENT', description: 'Scholarships offered for specific States and Union Territories.', icon: MapPinned },
  { label: 'Private Companies', value: 'PRIVATE_COMPANY', description: 'Education support backed by responsible businesses.', icon: Building2 },
  { label: 'NGOs', value: 'NGO', description: 'Opportunity programmes from verified social organisations.', icon: HeartHandshake },
] as const

const steps = [
  { number: '01', title: 'Search clearly', copy: 'Start with your course, location, scholarship name, or provider.', icon: Search },
  { number: '02', title: 'Check the fit', copy: 'Compare study level, course, location, benefits, and deadlines.', icon: Check },
  { number: '03', title: 'Ask ScholarSaathi', copy: 'Use the AI assistant to clarify eligibility and requirements.', icon: Bot },
  { number: '04', title: 'Apply confidently', copy: 'Review the requested information and continue with the provider.', icon: ArrowRight },
] as const

export function LandingPage() {
  return (
    <main className="overflow-hidden bg-[#f3f5ee] text-[#132019]">
      <PrismaHero />

      <section className="border-b border-[#dce3db] bg-white" aria-label="ScholarSaathi principles">
        <div className="mx-auto grid max-w-[90rem] divide-y divide-[#dce3db] px-5 md:grid-cols-3 md:divide-x md:divide-y-0 md:px-8">
          <article className="flex items-start gap-4 py-7 md:px-7">
            <ShieldCheck aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0 text-[#1f604a]" />
            <div><h2 className="m-0 text-sm font-semibold">Evidence before answers</h2><p className="mb-0 mt-1 text-xs leading-relaxed text-[#68756f]">AI guidance is constrained to information confirmed by scholarship providers.</p></div>
          </article>
          <article className="flex items-start gap-4 py-7 md:px-7">
            <Sparkles aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0 text-[#1f604a]" />
            <div><h2 className="m-0 text-sm font-semibold">Eligibility made conversational</h2><p className="mb-0 mt-1 text-xs leading-relaxed text-[#68756f]">Describe your studies naturally and see where more information is needed.</p></div>
          </article>
          <article className="flex items-start gap-4 py-7 md:px-7">
            <HeartHandshake aria-hidden="true" className="mt-0.5 h-6 w-6 shrink-0 text-[#1f604a]" />
            <div><h2 className="m-0 text-sm font-semibold">You stay in control</h2><p className="mb-0 mt-1 text-xs leading-relaxed text-[#68756f]">Provider sources and next steps remain visible before you apply.</p></div>
          </article>
        </div>
      </section>

      <section className="px-5 py-20 sm:px-8 lg:py-28" aria-labelledby="provider-heading">
        <div className="mx-auto max-w-[86rem]">
          <div className="mb-10 flex flex-col justify-between gap-5 md:flex-row md:items-end">
            <div>
              <p className="mb-3 text-xs font-bold tracking-[0.16em] text-[#41705f] uppercase">Explore the ecosystem</p>
              <h2 id="provider-heading" className="m-0 max-w-3xl text-4xl font-semibold leading-[1.02] tracking-[-0.05em] sm:text-5xl lg:text-6xl">Opportunity comes from many places.</h2>
            </div>
            <Link className="inline-flex items-center gap-2 text-sm font-semibold text-[#1a5542]" to="/scholarships">Browse every scholarship <ArrowRight aria-hidden="true" className="h-4 w-4" /></Link>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {providerGroups.map(({ label, value, description, icon: Icon }, index) => (
              <Link className="group flex min-h-64 flex-col justify-between rounded-[1.75rem] border border-[#d9e0d9] bg-white p-6 shadow-[0_12px_40px_rgba(30,55,43,0.05)] transition duration-300 hover:-translate-y-1 hover:border-[#aac2b6] hover:shadow-[0_22px_55px_rgba(30,55,43,0.10)]" key={value} to={`/scholarships?organization_type=${value}`}>
                <div className="flex items-start justify-between"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-[#e9f0e7] text-[#1b5944]"><Icon aria-hidden="true" className="h-5 w-5" /></span><span className="text-xs font-semibold text-[#89938e]">0{index + 1}</span></div>
                <div><h3 className="mb-2 text-xl font-semibold tracking-[-0.03em]">{label}</h3><p className="m-0 text-sm leading-relaxed text-[#68756f]">{description}</p><span className="mt-5 inline-flex items-center gap-2 text-xs font-bold text-[#1b5944]">View scholarships <ArrowRight aria-hidden="true" className="h-4 w-4 transition-transform group-hover:translate-x-1" /></span></div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-[#11241d] px-5 py-20 text-white sm:px-8 lg:py-28" aria-labelledby="journey-heading">
        <div className="mx-auto max-w-[86rem]">
          <div className="grid gap-10 lg:grid-cols-[0.7fr_1.3fr] lg:gap-20">
            <div className="lg:sticky lg:top-28 lg:self-start">
              <p className="mb-3 text-xs font-bold tracking-[0.16em] text-[#dfff82] uppercase">A simpler journey</p>
              <h2 id="journey-heading" className="m-0 text-4xl font-semibold leading-[1.03] tracking-[-0.05em] sm:text-5xl">From uncertainty to a clear next step.</h2>
              <p className="mb-0 mt-5 max-w-lg text-sm leading-relaxed text-white/60">ScholarSaathi combines a public scholarship catalog, provider evidence, and a conversational assistant without pretending AI makes the final decision.</p>
            </div>
            <ol className="m-0 grid list-none gap-3 p-0">
              {steps.map(({ number, title, copy, icon: Icon }) => (
                <li className="grid min-h-36 items-center gap-5 rounded-3xl border border-white/10 bg-white/[0.055] p-5 sm:grid-cols-[3rem_1fr_auto] sm:p-7" key={number}>
                  <span className="text-xs font-bold text-[#dfff82]">{number}</span>
                  <div><h3 className="mb-2 text-xl font-semibold tracking-[-0.03em]">{title}</h3><p className="m-0 text-sm leading-relaxed text-white/58">{copy}</p></div>
                  <span className="grid h-11 w-11 place-items-center rounded-full bg-[#dfff82] text-[#11241d]"><Icon aria-hidden="true" className="h-4 w-4" /></span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="px-5 py-20 sm:px-8 lg:py-28">
        <div className="mx-auto grid max-w-[86rem] overflow-hidden rounded-[2rem] bg-[#dfff82] lg:grid-cols-[1.15fr_0.85fr]">
          <div className="p-7 sm:p-10 lg:p-14">
            <span className="inline-flex items-center gap-2 rounded-full bg-[#173e32]/10 px-3 py-2 text-xs font-bold text-[#173e32]"><Bot aria-hidden="true" className="h-4 w-4" /> ScholarSaathi AI</span>
            <h2 className="mb-5 mt-8 max-w-3xl text-4xl font-semibold leading-[1.02] tracking-[-0.055em] text-[#102019] sm:text-5xl lg:text-6xl">Ask the question you were afraid was “too specific.”</h2>
            <p className="mb-8 max-w-2xl text-sm leading-relaxed text-[#34473f] sm:text-base">Open the scholarship catalog and tap the floating AI assistant. Share only non-sensitive study details, compare possible matches, and follow citations back to provider information.</p>
            <Link className="group inline-flex min-h-12 items-center gap-3 rounded-full bg-[#102019] py-1 pl-5 pr-1 text-sm font-semibold text-white" to="/scholarships">Ask about scholarships <span className="grid h-10 w-10 place-items-center rounded-full bg-white text-[#102019] transition-transform group-hover:scale-105"><ArrowRight aria-hidden="true" className="h-4 w-4" /></span></Link>
          </div>
          <div className="relative min-h-80 overflow-hidden bg-[#193f33] p-7 sm:p-10 lg:min-h-full">
            <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full border border-white/10" />
            <div className="absolute -bottom-24 -left-10 h-72 w-72 rounded-full border border-[#dfff82]/20" />
            <div className="relative flex h-full flex-col justify-end">
              <div className="max-w-sm rounded-3xl bg-white p-5 shadow-2xl"><p className="mb-3 text-[0.65rem] font-bold tracking-[0.12em] text-[#567067] uppercase">Example question</p><p className="m-0 text-base font-semibold leading-snug text-[#122019]">“I study BTech in Odisha. Which scholarships might fit me?”</p></div>
              <div className="ml-auto mt-3 max-w-[85%] rounded-3xl rounded-br-md bg-[#dfff82] p-5 text-[#122019]"><p className="m-0 text-sm leading-relaxed">I’ll compare your details with provider-confirmed criteria and tell you what information is still missing.</p></div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-[#dce3db] bg-white px-5 py-16 sm:px-8">
        <div className="mx-auto grid max-w-[86rem] gap-4 md:grid-cols-2">
          <article className="rounded-3xl border border-[#dce3db] bg-[#f5f7f2] p-7 sm:p-9"><p className="mb-3 text-xs font-bold tracking-[0.14em] text-[#41705f] uppercase">For students</p><h2 className="mb-3 text-3xl font-semibold tracking-[-0.04em]">Keep your scholarship journey together.</h2><p className="mb-6 text-sm leading-relaxed text-[#68756f]">Create a free account to save scholarships and manage application drafts.</p><Link className="inline-flex items-center gap-2 text-sm font-bold text-[#194f3e]" to="/login/student?mode=register">Create student account <ArrowRight aria-hidden="true" className="h-4 w-4" /></Link></article>
          <article className="rounded-3xl bg-[#17201c] p-7 text-white sm:p-9"><p className="mb-3 text-xs font-bold tracking-[0.14em] text-[#dfff82] uppercase">For providers</p><h2 className="mb-3 text-3xl font-semibold tracking-[-0.04em]">Publish information students can trust.</h2><p className="mb-6 text-sm leading-relaxed text-white/60">Manage scholarship records and keep provider evidence current.</p><Link className="inline-flex items-center gap-2 text-sm font-bold text-white" to="/providers">Explore provider tools <ArrowRight aria-hidden="true" className="h-4 w-4" /></Link></article>
        </div>
      </section>
    </main>
  )
}
