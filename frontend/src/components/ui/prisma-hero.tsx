import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { SiteNavigation } from '@/components/SiteNavigation'

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
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-black/20 via-black/10 to-black/80" />

        {/* Consistent Navbar overlaying the Hero */}
        <SiteNavigation variant="hero" />

        {/* Hero content */}
        <div className="absolute bottom-0 left-0 right-0 px-4 pb-8 sm:px-8 md:px-12 lg:pb-16 flex justify-center">
          <div className="w-full max-w-[90rem] flex flex-col items-start justify-end gap-6">
            
            <p className="text-sm text-[#F6F8FB]/95 sm:text-base md:text-lg lg:text-xl font-light drop-shadow-lg max-w-2xl" style={{ lineHeight: 1.5 }}>
              Students are searching for scholarships. Find the perfect scholarship for your studies in the cloud. Let ScholarSaathi guide you through the opportunities and help you secure your future.
            </p>

            <h1 className="font-semibold leading-[0.85] tracking-[-0.05em] text-[12vw] sm:text-[10vw] md:text-[9vw] lg:text-[8vw] xl:text-[7vw] text-white drop-shadow-2xl">
              ScholarSaathi<span className="text-[0.4em] align-top relative top-[-0.2em]">*</span>
            </h1>

            <Link to="/scholarships" className="mt-2 group inline-flex items-center gap-2 rounded-full bg-[#FFFFFF] py-1.5 pl-6 pr-1.5 text-sm font-semibold text-black transition-all hover:gap-4 hover:bg-gray-100 sm:text-base shadow-xl hover:shadow-2xl">
              Find Scholarships
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-black transition-transform group-hover:scale-110 sm:h-12 sm:w-12">
                <ArrowRight className="h-4 w-4 sm:h-5 sm:w-5 text-[#FFFFFF]" />
              </span>
            </Link>

          </div>
        </div>
      </div>
    </section>
  );
};


