import { Reveal } from '../components/Reveal.jsx';
import { IconArrowRight } from '../icons.jsx';
import { PROTOTYPE_URL } from '../constants.js';

export function FinalCTA() {
  return (
    <section id="try-it" className="relative overflow-hidden bg-ink px-6 py-24 sm:py-32">
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[440px] w-[760px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-50 blur-3xl"
        style={{
          background: 'radial-gradient(closest-side, rgba(13,148,136,0.22), transparent 75%)',
        }}
      />
      <div className="relative mx-auto flex max-w-2xl flex-col items-center text-center">
        <Reveal>
          <h2 className="font-serif text-3xl font-semibold leading-[1.2] text-paper sm:text-4xl">
            Built by someone who's filled out the incident form too.
          </h2>
        </Reveal>
        <Reveal delay={0.1}>
          <p className="mt-5 text-[15.5px] leading-relaxed text-white/60">
            RISKON is piloting with early facilities now. If you run safety at a plant with real operational
            risk, we'd rather show you than pitch you.
          </p>
        </Reveal>
        <Reveal delay={0.2}>
          <a
            href={PROTOTYPE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="group mt-8 inline-flex items-center gap-2 rounded-md bg-teal px-7 py-3.5 text-[14.5px] font-semibold text-ink transition-all duration-200 hover:-translate-y-0.5 hover:bg-teal-dark hover:text-paper"
          >
            RISKON V0
            <IconArrowRight width={16} height={16} className="transition-transform group-hover:translate-x-0.5" />
          </a>
        </Reveal>
      </div>
    </section>
  );
}
