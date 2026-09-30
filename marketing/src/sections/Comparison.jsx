import { SectionHeading } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { IconArrowRight } from '../icons.jsx';

const ROWS = [
  {
    old: 'Records what a human already worked out',
    riskon: 'Drafts the investigation for a human to review',
  },
  {
    old: 'Separate modules for incidents, risk, and actions',
    riskon: 'One chain, one schema, from report to risk register',
  },
  {
    old: 'AI features that give an answer with no shown reasoning',
    riskon: 'Every AI field shows its source, confidence, and reasoning',
  },
  {
    old: 'Each facility sees only its own data',
    riskon: 'Built to detect patterns across facilities from the start',
  },
];

export function Comparison() {
  return (
    <section className="bg-sand px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-content">
        <SectionHeading eyebrow="Why RISKON, Not Traditional EHS Software" heading="Same category, different foundation" />

        <Reveal delay={0.1} className="mt-12 overflow-hidden rounded-xl border border-ink/10 bg-white">
          <div className="grid grid-cols-2 border-b border-ink/10 bg-ink/[0.03]">
            <div className="px-5 py-4 sm:px-8">
              <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink/45">
                Traditional EHS / GRC software
              </span>
            </div>
            <div className="px-5 py-4 sm:px-8">
              <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-teal">RISKON</span>
            </div>
          </div>
          {ROWS.map((row, i) => (
            <div
              key={i}
              className={`grid grid-cols-2 ${i !== ROWS.length - 1 ? 'border-b border-ink/10' : ''}`}
            >
              <div className="flex items-center px-5 py-5 sm:px-8">
                <p className="text-[14px] leading-relaxed text-ink/50">{row.old}</p>
              </div>
              <div className="flex items-center gap-2.5 bg-teal-soft/40 px-5 py-5 sm:px-8">
                <IconArrowRight width={14} height={14} className="hidden shrink-0 text-teal sm:block" />
                <p className="text-[14px] font-medium leading-relaxed text-ink">{row.riskon}</p>
              </div>
            </div>
          ))}
        </Reveal>
      </div>
    </section>
  );
}
