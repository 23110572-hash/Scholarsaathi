import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { SiteNavigation } from '@/components/SiteNavigation'

/* ---------------- Hero ---------------- */
export const PrismaHero = () => {
  // Width is pinned to the viewport rather than the content box. The content box narrows
  // while a scrollbar is present, which rescaled the object-cover video and looked like
  // the background sliding sideways on arrival.
  return (
    <section className="h-[100dvh] w-screen overflow-hidden bg-black">
      <div className="relative h-full w-full overflow-hidden">

        {/* Background video. Width and height are declared so the frame is laid out
            before metadata arrives, which stops a visible jump on the first paint. */}
        <video
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          disablePictureInPicture
          width={1920}
          height={1080}
          tabIndex={-1}
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 h-full w-full select-none object-cover object-center"
          src="/background-video.mp4"
        />

        {/* Noise overlay, generated locally so no external asset can load late */}
        <div className="modern-noise pointer-events-none absolute inset-0 opacity-[0.35] mix-blend-overlay" />

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
                ScholarSaathi
              </h1>
            </div>

            <div className="col-span-12 flex flex-col gap-5 lg:col-span-6 lg:pt-0 self-start mt-[-3rem] sm:mt-[-5rem] md:mt-[-7rem] lg:mt-[-12rem] xl:mt-[-14rem] relative z-10">

              <p
                className="text-sm text-white sm:text-base md:text-lg lg:text-xl font-medium max-w-3xl"
                style={{ lineHeight: 1.5, textShadow: '0 2px 10px rgba(0,0,0,0.7), 0 1px 3px rgba(0,0,0,0.8)' }}
              >
                Your Scholarship Search Starts Here Find scholarships you’re eligible for and take the next step toward your education.
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


