import { SectionHeading } from '../components/SectionHeading.jsx';
import { Reveal, Stagger, StaggerItem } from '../components/Reveal.jsx';

const STEPS = [
  {
    n: 'Step 1',
    title: 'Pilot on history',
    body: "Run RISKON against a facility's past incidents — no live deployment risk.",
  },
  {
    n: 'Step 2',
    title: 'One facility, live',
    body: 'The safety team runs real incident intake through the full loop.',
  },
  {
    n: 'Step 3',
    title: 'Site-wide rollout',
    body: 'Every department, every shift, reporting into one register.',
  },
  {
    n: 'Step 4',
    title: 'Multi-site intelligence',
    body: 'Patterns across facilities become visible to leadership for the first time.',
  },
];

export function Adoption() {
  return (
    <section id="how-it-works" className="bg-paper px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-content">
        <SectionHeading
          eyebrow="How RISKON Enters an Industry"
          heading="Trust is earned one facility at a time"
          subtext="Safety software doesn't get adopted by pitch deck. It gets adopted by proving itself on one plant's real history before it's trusted with a live incident feed."
        />

        <Stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <StaggerItem key={s.n}>
              <div className="h-full rounded-lg border border-ink/10 bg-white/40 p-6">
                <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-teal">{s.n}</span>
                <h3 className="mt-3 font-serif text-[18px] font-semibold text-ink">{s.title}</h3>
                <p className="mt-2 text-[14px] leading-relaxed text-ink/60">{s.body}</p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>

        <Reveal delay={0.1} className="mt-6">
          <div className="rounded-xl bg-ink px-8 py-10 sm:px-12 sm:py-12">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-teal">How Companies Use It</span>
            <h3 className="mt-3 max-w-xl font-serif text-2xl font-semibold leading-snug text-paper">
              It replaces the incident binder, not the safety team.
            </h3>
            <p className="mt-4 max-w-2xl text-[14.5px] leading-relaxed text-white/60">
              Frontline workers report through it. HSE managers investigate through it. Plant managers run their
              morning safety review off it. Executives get their risk picture from it instead of a quarterly
              rollup someone assembled by hand.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
