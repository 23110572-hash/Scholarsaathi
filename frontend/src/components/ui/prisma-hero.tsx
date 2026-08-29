import { motion, useInView, useReducedMotion } from 'framer-motion'
import { ArrowRight, Search, ShieldCheck, Sparkles } from 'lucide-react'
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
            initial={reduceMotion ? false : { y: 30, opacity: 0 }}
            animate={isInView ? { y: 0, opacity: 1 } : {}}
            transition={{ duration: 0.65, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="relative inline-block"
            style={{ marginRight: isLast ? 0 : '0.25em' }}
          >
            {word}
            {showAsterisk && isLast && <span className="absolute -right-[0.3em] top-[0.07em] text-[0.24em] text-[#dfff82]">✦</span>}
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
          initial={reduceMotion ? false : { y: 30, opacity: 0 }}
          animate={isInView ? { y: 0, opacity: 1 } : {}}
          transition={{ duration: 0.65, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
          className={`mr-[0.2em] inline-block ${item.className ?? ''}`}
        >
          {item.word}
        </motion.span>
      ))}
    </span>
  )
}

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
    <section className="relative min-h-[100svh] w-full bg-[#080c0a] p-2 sm:p-3" aria-labelledby="home-hero-title">
      <div className="relative min-h-[780px] w-full overflow-hidden rounded-[1.5rem] bg-[#122019] sm:rounded-[2rem] lg:min-h-[calc(100svh-1.5rem)]">
        <motion.img
          initial={reduceMotion ? false : { scale: 1.08, opacity: 0.8 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 1.8, ease: [0.16, 1, 0.3, 1] }}
          className="absolute inset-0 h-full w-full object-cover object-center"
          src="https://images.unsplash.com/photo-1523050854058-8df90110c9f1?auto=format&fit=crop&w=2400&q=88"
          alt=""
          aria-hidden="true"
          fetchPriority="high"
        />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(6,13,9,0.86)_0%,rgba(6,13,9,0.44)_52%,rgba(6,13,9,0.22)_100%)]" />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(4,8,6,0.5)_0%,transparent_30%,rgba(4,8,6,0.86)_100%)]" />
        <div className="modern-noise pointer-events-none absolute inset-0 opacity-25 mix-blend-overlay" />

        <SiteNavigation variant="hero" />

        <div className="relative z-10 flex min-h-[780px] flex-col justify-end px-5 pb-7 pt-32 sm:px-8 sm:pb-10 lg:min-h-[calc(100svh-1.5rem)] lg:px-12 xl:px-16">
          <motion.div
            initial={reduceMotion ? false : { y: 18, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="mb-5 inline-flex w-fit items-center gap-2 rounded-full border border-white/20 bg-black/25 px-3 py-2 text-[0.65rem] font-semibold tracking-[0.12em] text-white/80 uppercase backdrop-blur-md"
          >
            <Sparkles aria-hidden="true" className="h-3.5 w-3.5 text-[#dfff82]" /> Evidence-led scholarship discovery
          </motion.div>

          <div className="grid items-end gap-7 lg:grid-cols-12 lg:gap-10">
            <div className="lg:col-span-7">
              <h1 id="home-hero-title" className="m-0 text-[20vw] font-medium leading-[0.78] tracking-[-0.075em] text-[#f1f2e8] sm:text-[16vw] lg:text-[10.5vw] xl:text-[9.7vw]">
                <WordsPullUp text="Scholar" />
                <span className="block text-[#dfff82]"><WordsPullUp text="Saathi" showAsterisk /></span>
              </h1>
            </div>

            <div className="flex flex-col gap-5 pb-1 lg:col-span-5 lg:pb-3 xl:pl-8">
              <motion.p initial={reduceMotion ? false : { y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, delay: 0.45, ease: [0.16, 1, 0.3, 1] }} className="m-0 max-w-xl text-sm leading-relaxed text-white/78 sm:text-base lg:text-[1.05rem]">
                Find scholarships that fit your studies, location, and goals—then ask the AI assistant questions grounded in provider-confirmed information.
              </motion.p>

              <motion.form initial={reduceMotion ? false : { y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.8, delay: 0.6, ease: [0.16, 1, 0.3, 1] }} className="flex w-full max-w-xl items-center gap-2 rounded-full border border-white/25 bg-white/94 p-1.5 shadow-2xl backdrop-blur-xl" onSubmit={searchScholarships}>
                <Search aria-hidden="true" className="ml-3 h-5 w-5 shrink-0 text-[#557067]" />
                <label className="sr-only" htmlFor="hero-scholarship-search">Search scholarships</label>
                <input id="hero-scholarship-search" className="min-w-0 flex-1 border-0 bg-transparent px-2 py-3 text-sm text-[#132019] shadow-none outline-none placeholder:text-[#6d7b75] focus:shadow-none" maxLength={120} placeholder="Course, state, scholarship or provider" value={query} onChange={(event) => setQuery(event.target.value)} />
                <button className="grid h-11 w-11 shrink-0 place-items-center rounded-full border-0 bg-[#153f33] text-white transition hover:scale-105 hover:bg-[#0e3026]" type="submit" aria-label="Search scholarships"><ArrowRight aria-hidden="true" className="h-4 w-4" /></button>
              </motion.form>

              <motion.div initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.8 }} className="flex flex-wrap items-center gap-3 text-xs font-medium text-white/65">
                <span className="inline-flex items-center gap-1.5"><ShieldCheck aria-hidden="true" className="h-4 w-4 text-[#dfff82]" /> Provider-confirmed evidence</span>
                <span aria-hidden="true" className="h-1 w-1 rounded-full bg-white/35" />
                <Link className="inline-flex items-center gap-1 text-white underline decoration-white/35 underline-offset-4 hover:decoration-white" to="/login/student?mode=register">Create a free student account <ArrowRight aria-hidden="true" className="h-3.5 w-3.5" /></Link>
              </motion.div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
