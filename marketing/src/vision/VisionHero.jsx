import { motion } from 'motion/react';
import { Eyebrow } from '../components/SectionHeading.jsx';
import { Prose } from '../components/Prose.jsx';

const EASE = [0.22, 1, 0.36, 1];

export function VisionHero() {
  return (
    <section className="relative overflow-hidden bg-ink pb-20 pt-28 sm:pb-24 sm:pt-36">
      <div
        className="pointer-events-none absolute left-1/2 top-[-6%] h-[480px] w-[820px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
        style={{
          background:
            'radial-gradient(closest-side, rgba(217,130,43,0.22), rgba(217,130,43,0.05) 60%, transparent 80%)',
        }}
      />
      <div className="relative px-6">
        <Prose className="flex flex-col items-center text-center">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            <Eyebrow dark tone="amber">
              The Road Ahead
            </Eyebrow>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.08, ease: EASE }}
            className="mt-6 font-serif text-[28px] font-semibold leading-[1.28] text-paper sm:text-[34px] md:text-[38px]"
          >
            Every safety platform tells you what already happened. RISKON exists to become the one that
            helps a plant see the pattern before the same accident happens a second time.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.18, ease: EASE }}
            className="mt-7 max-w-[600px] text-[15.5px] leading-relaxed text-white/60"
          >
            This started as a solo prototype build. What follows isn't the pilot — it's what RISKON can
            become from here. What's real today and what's still ahead are marked honestly throughout,
            because a vision page that can't tell the two apart isn't worth much.
          </motion.p>
        </Prose>
      </div>
    </section>
  );
}
