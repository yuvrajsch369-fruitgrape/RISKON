import { SectionHeading } from '../components/SectionHeading.jsx';
import { Stagger, StaggerItem } from '../components/Reveal.jsx';
import { IconLoop, IconEye, IconGate, IconConnect } from '../icons.jsx';

const ITEMS = [
  {
    icon: IconLoop,
    heading: 'One closed loop by design',
    body: 'Incident, investigation, root cause, action, and the risk register all live in one connected system — not five tools exporting CSVs to each other.',
  },
  {
    icon: IconEye,
    heading: "Every AI output shows its work",
    body: 'Classification, hazards, root cause — each carries its source (extracted from the report vs. inferred), a confidence level, and the reasoning behind it. Not a black box.',
  },
  {
    icon: IconGate,
    heading: 'Human approval is architecture, not a setting',
    body: "The approval gate is built into the data model itself — nothing becomes authoritative without it. It can't be quietly switched off under deadline pressure.",
  },
  {
    icon: IconConnect,
    heading: 'Cross-facility pattern detection from day one',
    body: "A forklift near-miss at one plant and a similar one at another look disconnected in most systems. RISKON is built to surface that they're the same problem.",
  },
];

export function Differentiators() {
  return (
    <section id="why-different" className="bg-paper px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-content">
        <SectionHeading
          eyebrow="What's Actually Different"
          heading="Not a module bolted onto a module"
          subtext="Most EHS platforms grew by acquisition — a reporting tool here, a risk register there. RISKON was designed as one chain from the first line of the schema."
        />

        <Stagger className="mt-12 grid gap-4 sm:grid-cols-2">
          {ITEMS.map((item) => (
            <StaggerItem key={item.heading}>
              <div className="h-full rounded-lg border border-ink/10 bg-white p-7 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_8px_30px_-12px_rgba(11,15,20,0.15)]">
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-teal-soft text-teal">
                  <item.icon width={19} height={19} />
                </span>
                <h3 className="mt-4 font-serif text-[19px] font-semibold text-ink">{item.heading}</h3>
                <p className="mt-2.5 text-[14.5px] leading-relaxed text-ink/65">{item.body}</p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
