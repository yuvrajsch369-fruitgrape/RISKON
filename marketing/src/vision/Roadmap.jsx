import { SectionHeading } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

const ROWS = [
  {
    label: 'Now',
    body: "The closed-loop reasoning engine — incident to classification to root cause to risk register, human-approved at every step, piloting on one facility's historical data.",
  },
  {
    label: 'Next',
    body: 'Live incident intake at a real facility, plus a worker-facing reporting experience simple enough that near-misses actually get filed, not just injuries.',
  },
  {
    label: 'After that',
    body: "Cross-facility pattern detection across a company's own multiple sites — the hardest and most valuable piece, because it needs real incident volume across real facilities to mean anything.",
  },
  {
    label: 'Later',
    body: 'The engine-as-infrastructure model — licensing the reasoning core to maintenance platforms, ERPs, and eventually larger EHS suites, rather than only selling a standalone product.',
  },
];

export function Roadmap() {
  return (
    <section id="roadmap" className="bg-ink px-6 py-20 sm:py-24">
      <Prose>
        <SectionHeading dark eyebrow="Where This Can Be Built, In Order" heading="A roadmap, stated plainly" />
      </Prose>

      <Prose className="mt-12 flex flex-col">
        {ROWS.map((row, i) => (
          <Reveal key={row.label} y={12} delay={Math.min(i * 0.05, 0.2)}>
            <div
              className={`grid grid-cols-[90px_1fr] gap-6 py-6 sm:grid-cols-[120px_1fr] ${
                i !== 0 ? 'border-t border-white/10' : ''
              }`}
            >
              <span className="font-mono text-[11.5px] uppercase tracking-[0.1em] text-amber">{row.label}</span>
              <p className="text-[15px] leading-[1.75] text-white/65">{row.body}</p>
            </div>
          </Reveal>
        ))}
      </Prose>
    </section>
  );
}
