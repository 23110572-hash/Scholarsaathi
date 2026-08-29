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
        <div className="absolute bottom-0 left-0 right-0 px-4 pb-6 sm:px-6 md:px-10 lg:pb-12">
          <div className="grid grid-cols-12 items-start gap-4 h-full pt-[15vh] sm:pt-[20vh] md:pt-[25vh]">
            
            <div className="col-span-12 lg:col-span-6">
              <h1
                className="font-semibold leading-[0.85] tracking-[-0.05em] text-[11vw] sm:text-[9vw] md:text-[7.5vw] lg:text-[6.5vw] xl:text-[6vw] text-white drop-shadow-2xl"
              >
                ScholarSaathi<span className="text-[0.4em] align-top relative top-[-0.2em]">*</span>
              </h1>
            </div>

            <div className="col-span-12 flex flex-col gap-5 lg:col-span-6 lg:pt-0 self-start mt-[-3rem] sm:mt-[-5rem] md:mt-[-7rem] lg:mt-[-12rem] xl:mt-[-14rem] relative z-10">
              
              <p
                className="text-sm text-[#F6F8FB]/95 sm:text-base md:text-lg lg:text-xl font-light drop-shadow-lg max-w-3xl"
                style={{ lineHeight: 1.5 }}
              >
                Students are searching for scholarships. Find the perfect scholarship for your studies in the cloud. Let ScholarSaathi guide you through the opportunities and help you secure your future.
              </p>

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


