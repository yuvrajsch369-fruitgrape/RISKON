import { motion } from 'motion/react';
import { Eyebrow } from '../components/SectionHeading.jsx';
import { IconArrowRight } from '../icons.jsx';
import { PROTOTYPE_URL } from '../constants.js';

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden bg-ink pb-24 pt-28 sm:pb-32 sm:pt-36">
      <div
        className="pointer-events-none absolute left-1/2 top-[-10%] h-[520px] w-[900px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{
          background:
            'radial-gradient(closest-side, rgba(13,148,136,0.28), rgba(13,148,136,0.06) 60%, transparent 80%)',
        }}
      />

      <div className="relative mx-auto flex max-w-content flex-col items-center px-6 text-center">
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        >
          <Eyebrow dark tone="teal">
            AI-Native Industrial Risk Operating System
          </Eyebrow>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mt-6 max-w-3xl font-serif text-4xl font-semibold leading-[1.12] text-paper sm:text-5xl md:text-6xl"
        >
          Every incident becomes intelligence.
          <br className="hidden sm:block" /> Every risk becomes visible.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="mt-6 max-w-xl text-[16.5px] leading-relaxed text-white/65"
        >
          RISKON turns incident reports into investigated, root-caused, human-approved risk intelligence — across
          every facility you run, in one connected system instead of a dozen disconnected ones.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="mt-10 flex flex-col items-center gap-3 sm:flex-row"
        >
          <a
            href={PROTOTYPE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-2 rounded-md bg-teal px-6 py-3 text-[14px] font-semibold text-ink transition-all duration-200 hover:-translate-y-0.5 hover:bg-teal-dark hover:text-paper"
          >
            RISKON V0
            <IconArrowRight width={16} height={16} className="transition-transform group-hover:translate-x-0.5" />
          </a>
          <a
            href="#the-loop"
            className="inline-flex items-center gap-2 rounded-md border border-white/20 px-6 py-3 text-[14px] font-semibold text-white/85 transition-all duration-200 hover:-translate-y-0.5 hover:border-white/40 hover:text-white"
          >
            See the Workflow
          </a>
        </motion.div>
      </div>
    </section>
  );
}
