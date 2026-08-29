import { motion, useInView } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useRef } from "react";
import { Link } from "react-router-dom";
import { SiteNavigation } from '@/components/SiteNavigation'

/* ---------------- WordsPullUp ---------------- */
interface WordsPullUpProps {
  text: string;
  className?: string;
  showAsterisk?: boolean;
  style?: React.CSSProperties;
}

export const WordsPullUp = ({ text, className = "", showAsterisk = false, style }: WordsPullUpProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true });
  const words = text.split(" ");

  return (
    <div ref={ref} className={`inline-flex flex-wrap ${className}`} style={style}>
      {words.map((word, i) => {
        const isLast = i === words.length - 1;
        return (
          <motion.span
            key={i}
            initial={{ y: 20, opacity: 0 }}
            animate={isInView ? { y: 0, opacity: 1 } : {}}
            transition={{ duration: 0.6, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
            className="inline-block relative"
            style={{ marginRight: isLast ? 0 : "0.25em" }}
          >
            {word}
            {showAsterisk && isLast && (
              <span className="absolute top-[0.65em] -right-[0.3em] text-[0.31em]">*</span>
            )}
          </motion.span>
        );
      })}
    </div>
  );
};

/* ---------------- Hero ---------------- */
export const PrismaHero = () => {
  return (
    <section className="h-[100dvh] w-full bg-black">
      <div className="relative h-full w-full overflow-hidden">
        
        {/* Background video */}
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 h-full w-full object-cover"
          src="/background-video.mp4"
        />

        {/* Noise overlay */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.4] mix-blend-overlay bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" />

        {/* Gradient overlay */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/60 via-transparent to-black/80" />

        {/* Consistent Navbar overlaying the Hero */}
        <SiteNavigation variant="hero" />

        {/* Hero content */}
        <div className="absolute bottom-0 left-0 right-0 px-4 pb-6 sm:px-6 md:px-10 lg:pb-12">
          <div className="grid grid-cols-12 items-end gap-4">
            
            <div className="col-span-12 lg:col-span-8 pt-20">
              <h1
                className="font-medium leading-[0.85] tracking-[-0.07em] text-[15vw] sm:text-[14vw] md:text-[12vw] lg:text-[11vw] xl:text-[10vw]"
                style={{ color: "#FFFFFF" }}
              >
                <WordsPullUp text="ScholarSaathi" showAsterisk />
              </h1>
            </div>

            <div className="col-span-12 flex flex-col gap-5 pb-2 lg:col-span-4">
              
              <motion.p
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="text-sm text-[#F6F8FB]/90 sm:text-base md:text-lg font-light drop-shadow-md"
                style={{ lineHeight: 1.4 }}
              >
                Students are searching for scholarships. Find the perfect scholarship for your studies in the cloud. Let ScholarSaathi guide you through the opportunities and help you secure your future.
              </motion.p>

              <Link to="/scholarships" className="group inline-flex items-center gap-2 self-start rounded-full bg-[#FFFFFF] py-1 pl-5 pr-1 text-sm font-medium text-black transition-all hover:gap-3 hover:bg-gray-100 sm:text-base shadow-lg hover:shadow-xl">
                Find Scholarships
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-black transition-transform group-hover:scale-110 sm:h-10 sm:w-10">
                  <ArrowRight className="h-4 w-4 text-[#FFFFFF]" />
                </span>
              </Link>

            </div>
          </div>
        </div>
      </div>
    </section>
  );
};


