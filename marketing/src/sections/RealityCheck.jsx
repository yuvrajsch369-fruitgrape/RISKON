import { SectionHeading } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { IconCheck } from '../icons.jsx';

// The "13-stage pipeline running live end to end" framing sometimes floating
// around for this product is not quite what's true today, and this section's
// whole job is to draw an honest line — so it gets stated precisely here
// rather than repeating the rounder version: what's actually wired is a real
// Claude call reasoning over a real incident's real facility/equipment/
// hazard/control history, with a fuller staged trace built and demonstrated
// on real data, not yet the same thing running live end to end on every case.
const TODAY = [
  'A real, wired Claude integration that investigates a submitted incident against its actual facility, equipment, hazard, and control history — every output labeled fact, hypothesis, or recommendation, with a confidence score attached',
  'Every workflow screen built and working: incident reporting, the AI investigation review, corrective action tracking, the risk register, management intelligence dashboards',
  'A validated relational database proving the data model — incidents, hazards, controls, and actions actually connect the way the workflow claims',
  "Deployed and piloting — tested on synthetic incident data, not yet on a real facility's live feed",
];

const FUTURE = [
  "Live incident intake running on a real facility's actual reports, not historical or synthetic data",
  "Cross-facility pattern detection working across a company's real, multiple sites — the part that needs real incident volume to prove out",
  "Enterprise-grade security and data-handling built for a plant's actual incident and injury records, not prototype-appropriate auth",
  'Integrations into the systems already running a plant — maintenance platforms, ERPs — instead of a standalone tool',
];

function List({ items, tone }) {
  const dot = tone === 'amber' ? 'text-amber' : 'text-teal';
  return (
    <ul className="flex flex-col gap-4">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-3">
          <IconCheck width={15} height={15} className={`mt-0.5 shrink-0 ${dot}`} />
          <span className="text-[14px] leading-relaxed">{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function RealityCheck() {
  return (
    <section className="bg-paper px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-content">
        <SectionHeading
          eyebrow="Where This Actually Stands"
          heading="What's real today, and what this becomes"
          subtext="A pilot conversation should start from an honest line between the two — not a demo that quietly implies more than what's actually running."
        />

        <div className="mt-12 grid gap-5 md:grid-cols-2">
          <Reveal>
            <div className="h-full rounded-xl border border-ink/10 bg-white p-8">
              <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-teal">Prototype Today</span>
              <div className="mt-5 text-ink/75">
                <List items={TODAY} tone="teal" />
              </div>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <div className="h-full rounded-xl bg-ink-raised p-8">
              <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-amber">
                The Product This Becomes
              </span>
              <div className="mt-5 text-white/65">
                <List items={FUTURE} tone="amber" />
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
