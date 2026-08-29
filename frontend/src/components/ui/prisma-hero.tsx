import { motion, useInView, useReducedMotion } from 'framer-motion'
import { ArrowRight, Building2, GraduationCap, HeartHandshake, Landmark, Search } from 'lucide-react'
import { useRef, useState } from 'react'
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
            {showAsterisk && isLast && <span className="hero-twinkle absolute -right-[0.3em] top-[0.06em] text-[0.22em] text-[#ff9933]">✦</span>}
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

  function searchScholarships(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const params = new URLSearchParams()
    if (query.trim()) params.set('q', query.trim())
    navigate(`/scholarships${params.size ? `?${params.toString()}` : ''}`)
  }

  return (
    <section className="hero-frame relative w-full overflow-hidden" aria-labelledby="home-hero-title">
      <div className="hero-tricolor-beams pointer-events-none absolute inset-0" aria-hidden="true" />
      <div className="hero-grid-lines pointer-events-none absolute inset-0" aria-hidden="true" />
      <img className="hero-emblem pointer-events-none absolute" src="/logo.png" alt="" aria-hidden="true" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(96deg,rgba(6,17,36,0.94)_0%,rgba(6,17,36,0.72)_48%,rgba(6,17,36,0.42)_100%)]" aria-hidden="true" />
      <div className="modern-noise pointer-events-none absolute inset-0 opacity-15 mix-blend-overlay" aria-hidden="true" />
      <div className="hero-tricolor-rule pointer-events-none absolute inset-x-0 bottom-0" aria-hidden="true" />

      <SiteNavigation variant="hero" />

      <div className="relative z-10 flex min-h-[38rem] flex-col justify-center px-5 pb-14 pt-28 sm:px-8 sm:pb-16 sm:pt-32 lg:min-h-[42rem] lg:px-12 lg:pb-20 xl:px-16">
        <div className="grid items-center gap-10 lg:grid-cols-12 lg:gap-12">
          <div className="lg:col-span-7">
            <h1 id="home-hero-title" className="m-0 text-[17vw] font-medium leading-[0.82] tracking-[-0.07em] text-[#f6f8fb] sm:text-[13vw] lg:text-[7.6vw] xl:text-[7.1vw]">
              <WordsPullUp text="Scholar" />
              <span className="hero-gradient-text block"><WordsPullUp text="Saathi" showAsterisk /></span>
            </h1>

            <motion.div
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.9, delay: 0.8 }}
              className="mt-7 hidden overflow-hidden lg:block"
              aria-hidden="true"
            >
              <div className="hero-marquee flex w-max items-center gap-3">
                {[...providerTicker, ...providerTicker].map(({ label, icon: Icon }, index) => (
                  <span className="inline-flex shrink-0 items-center gap-2 rounded-full border border-white/20 bg-white/[0.06] px-3.5 py-2 text-[0.68rem] font-semibold text-[#eef1f6] backdrop-blur-md" key={`${label}-${index}`}>
                    <Icon className="h-3.5 w-3.5 text-[#ff9933]" /> {label}
                  </span>
                ))}
              </div>
            </motion.div>
          </div>

          <div className="flex flex-col gap-5 lg:col-span-5 xl:pl-8">
            <motion.p initial={reduceMotion ? false : { y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, delay: 0.4, ease: [0.16, 1, 0.3, 1] }} className="m-0 max-w-xl text-sm leading-relaxed text-[#dde3ec] sm:text-base lg:text-[1.05rem]">
              Find scholarships that fit your studies, location, and goals—then ask the AI assistant questions grounded in provider-confirmed information.
            </motion.p>

            <motion.form initial={reduceMotion ? false : { y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, delay: 0.55, ease: [0.16, 1, 0.3, 1] }} className="flex w-full max-w-xl items-center gap-2 rounded-full border border-white/25 bg-white/96 p-1.5 shadow-[0_18px_44px_rgba(3,10,24,0.5)]" onSubmit={searchScholarships}>
              <Search aria-hidden="true" className="ml-3 h-5 w-5 shrink-0 text-[#5b6980]" />
              <label className="sr-only" htmlFor="hero-scholarship-search">Search scholarships</label>
              <input id="hero-scholarship-search" className="min-w-0 flex-1 border-0 bg-transparent px-2 py-3 text-sm text-[#101827] shadow-none outline-none placeholder:text-[#6b7789] focus:shadow-none" maxLength={120} placeholder="Course, state, scholarship or provider" value={query} onChange={(event) => setQuery(event.target.value)} />
              <button className="grid h-11 w-11 shrink-0 place-items-center rounded-full border-0 bg-[#10265c] text-white transition hover:scale-105 hover:bg-[#0a1b45]" type="submit" aria-label="Search scholarships"><ArrowRight aria-hidden="true" className="h-4 w-4" /></button>
            </motion.form>

            <motion.div initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.7 }}>
              <Link className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#ffffff] underline decoration-[#ff9933]/70 underline-offset-4 hover:decoration-[#ff9933]" to="/login/student?mode=register">Create a student account <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" /></Link>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  )
}
