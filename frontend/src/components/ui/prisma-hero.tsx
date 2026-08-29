import { motion, useInView, useReducedMotion } from 'framer-motion'
import { ArrowRight, Building2, GraduationCap, HeartHandshake, Landmark, Search, ShieldCheck, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { SiteNavigation } from '@/components/SiteNavigation'

interface WordsPullUpProps {
  text: string
  className?: string
  showAsterisk?: boolean
  style?: CSSProperties
}

export function WordsPullUp({ text, className = '', showAsterisk = false, style }: WordsPullUpProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const isInView = useInView(ref, { once: true })
  const reduceMotion = useReducedMotion()
  const words = text.split(' ')

  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className}`} style={style}>
      {words.map((word, index) => {
        const isLast = index === words.length - 1
        return (
          <motion.span
            key={`${word}-${index}`}
            initial={reduceMotion ? false : { y: 34, opacity: 0 }}
            animate={isInView ? { y: 0, opacity: 1 } : {}}
            transition={{ duration: 0.7, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="relative inline-block"
            style={{ marginRight: isLast ? 0 : '0.25em' }}
          >
            {word}
            {showAsterisk && isLast && <span className="hero-twinkle absolute -right-[0.32em] top-[0.05em] text-[0.24em] text-[#dfff82]">✦</span>}
          </motion.span>
        )
      })}
    </span>
  )
}

interface Segment {
  text: string
  className?: string
}

interface WordsPullUpMultiStyleProps {
  segments: Segment[]
  className?: string
  style?: CSSProperties
}

export function WordsPullUpMultiStyle({ segments, className = '', style }: WordsPullUpMultiStyleProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const isInView = useInView(ref, { once: true })
  const reduceMotion = useReducedMotion()
  const words = segments.flatMap((segment) => segment.text.split(' ').filter(Boolean).map((word) => ({ word, className: segment.className })))

  return (
    <span ref={ref} className={`inline-flex flex-wrap ${className}`} style={style}>
      {words.map((item, index) => (
        <motion.span
          key={`${item.word}-${index}`}
          initial={reduceMotion ? false : { y: 34, opacity: 0 }}
          animate={isInView ? { y: 0, opacity: 1 } : {}}
          transition={{ duration: 0.7, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
          className={`mr-[0.2em] inline-block ${item.className ?? ''}`}
        >
          {item.word}
        </motion.span>
      ))}
    </span>
  )
}

const heroSlides = ['/hero-campus.jpg', '/hero-graduate.jpg', '/hero-library.jpg', '/hero-study.jpg']

const providerTicker = [
  { label: 'Central Government', icon: Landmark },
  { label: 'State Government', icon: GraduationCap },
  { label: 'Private Companies', icon: Building2 },
  { label: 'NGOs', icon: HeartHandshake },
] as const

export function PrismaHero() {
  const navigate = useNavigate()
  const reduceMotion = useReducedMotion()
  const [query, setQuery] = useState('')
  const [slide, setSlide] = useState(0)

  useEffect(() => {
    if (reduceMotion) return
    const timer = window.setInterval(() => setSlide((current) => (current + 1) % heroSlides.length), 6000)
    return () => window.clearInterval(timer)
  }, [reduceMotion])

  function searchScholarships(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const params = new URLSearchParams()
    if (query.trim()) params.set('q', query.trim())
    navigate(`/scholarships${params.size ? `?${params.toString()}` : ''}`)
  }

  return (
    <section className="relative min-h-[100svh] w-full bg-[#050807] p-2 sm:p-3" aria-labelledby="home-hero-title">
      <div className="hero-frame relative min-h-[760px] w-full overflow-hidden rounded-[1.5rem] sm:rounded-[2rem] lg:min-h-[calc(100svh-1.5rem)]">
        {heroSlides.map((source, index) => (
          <img
            key={source}
            src={source}
            alt=""
            aria-hidden="true"
            className={`hero-slide absolute inset-0 h-full w-full object-cover object-center ${index === slide ? 'hero-slide-active' : ''}`}
            {...(index === 0 ? { fetchPriority: 'high' as const } : { loading: 'lazy' as const })}
          />
        ))}

        <div className="hero-aurora pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(94deg,rgba(4,9,7,0.92)_0%,rgba(4,9,7,0.62)_46%,rgba(4,9,7,0.3)_100%)]" aria-hidden="true" />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(3,6,5,0.72)_0%,transparent_34%,rgba(3,6,5,0.9)_100%)]" aria-hidden="true" />
        <div className="modern-noise pointer-events-none absolute inset-0 opacity-20 mix-blend-overlay" aria-hidden="true" />
        <div className="hero-orb hero-orb-one pointer-events-none absolute" aria-hidden="true" />
        <div className="hero-orb hero-orb-two pointer-events-none absolute" aria-hidden="true" />
        <div className="hero-scanline pointer-events-none absolute inset-x-0 top-0" aria-hidden="true" />

        <SiteNavigation variant="hero" />

        <div className="relative z-10 flex min-h-[760px] flex-col justify-end px-5 pb-6 pt-32 sm:px-8 sm:pb-8 lg:min-h-[calc(100svh-1.5rem)] lg:px-12 xl:px-16">
          <motion.div
            initial={reduceMotion ? false : { y: 18, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-[#dfff82]/35 bg-[#050807]/70 px-3.5 py-2 text-[0.65rem] font-bold tracking-[0.14em] text-[#f4f7f1] uppercase backdrop-blur-md"
          >
            <Sparkles aria-hidden="true" className="hero-twinkle h-3.5 w-3.5 text-[#dfff82]" /> Evidence-led scholarship discovery
          </motion.div>

          <div className="grid items-end gap-8 lg:grid-cols-12 lg:gap-10">
            <div className="lg:col-span-7">
              <h1 id="home-hero-title" className="m-0 text-[19vw] font-medium leading-[0.78] tracking-[-0.075em] text-[#f4f5ea] sm:text-[15.5vw] lg:text-[10vw] xl:text-[9.4vw]">
                <WordsPullUp text="Scholar" />
                <span className="hero-gradient-text block"><WordsPullUp text="Saathi" showAsterisk /></span>
              </h1>

              <motion.div
                initial={reduceMotion ? false : { opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.9, delay: 0.9 }}
                className="mt-6 hidden overflow-hidden lg:block"
                aria-hidden="true"
              >
                <div className="hero-marquee flex w-max items-center gap-3">
                  {[...providerTicker, ...providerTicker].map(({ label, icon: Icon }, index) => (
                    <span className="inline-flex shrink-0 items-center gap-2 rounded-full border border-white/20 bg-white/[0.07] px-3.5 py-2 text-[0.68rem] font-semibold text-[#eef2ea] backdrop-blur-md" key={`${label}-${index}`}>
                      <Icon className="h-3.5 w-3.5 text-[#dfff82]" /> {label}
                    </span>
                  ))}
                </div>
              </motion.div>
            </div>

            <div className="flex flex-col gap-5 pb-1 lg:col-span-5 lg:pb-4 xl:pl-8">
              <motion.p initial={reduceMotion ? false : { y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, delay: 0.45, ease: [0.16, 1, 0.3, 1] }} className="m-0 max-w-xl text-sm leading-relaxed text-[#e4e9e2] sm:text-base lg:text-[1.05rem]">
                Find scholarships that fit your studies, location, and goals—then ask the AI assistant questions grounded in provider-confirmed information.
              </motion.p>

              <motion.form initial={reduceMotion ? false : { y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, delay: 0.6, ease: [0.16, 1, 0.3, 1] }} className="flex w-full max-w-xl items-center gap-2 rounded-full border border-white/30 bg-white/95 p-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.45)] backdrop-blur-xl" onSubmit={searchScholarships}>
                <Search aria-hidden="true" className="ml-3 h-5 w-5 shrink-0 text-[#4f6a60]" />
                <label className="sr-only" htmlFor="hero-scholarship-search">Search scholarships</label>
                <input id="hero-scholarship-search" className="min-w-0 flex-1 border-0 bg-transparent px-2 py-3 text-sm text-[#101c16] shadow-none outline-none placeholder:text-[#68766f] focus:shadow-none" maxLength={120} placeholder="Course, state, scholarship or provider" value={query} onChange={(event) => setQuery(event.target.value)} />
                <button className="grid h-11 w-11 shrink-0 place-items-center rounded-full border-0 bg-[#12483a] text-white transition hover:scale-105 hover:bg-[#0c3327]" type="submit" aria-label="Search scholarships"><ArrowRight aria-hidden="true" className="h-4 w-4" /></button>
              </motion.form>

              <motion.div initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.8 }} className="flex flex-wrap items-center gap-3 text-xs font-semibold text-[#dfe6df]">
                <span className="inline-flex items-center gap-1.5"><ShieldCheck aria-hidden="true" className="h-4 w-4 text-[#dfff82]" /> Provider-confirmed evidence</span>
                <span aria-hidden="true" className="h-1 w-1 rounded-full bg-white/40" />
                <Link className="inline-flex items-center gap-1 text-[#ffffff] underline decoration-[#dfff82]/60 underline-offset-4 hover:decoration-[#dfff82]" to="/login/student?mode=register">Create a free student account <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" /></Link>
              </motion.div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
