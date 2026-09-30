import { SectionHeading } from '../components/SectionHeading.jsx';
import { Reveal, Stagger, StaggerItem } from '../components/Reveal.jsx';

const STEPS = [
  { n: '01', label: 'Incident Report' },
  { n: '02', label: 'AI Classification' },
  { n: '03', label: 'Preliminary Investigation' },
  { n: '04', label: 'Root-Cause Analysis' },
  { n: '05', label: 'Corrective / Preventive Actions' },
  { n: '06', label: 'Human Approval', gate: true },
  { n: '07', label: 'Risk Register Update' },
  { n: '08', label: 'Management Intelligence' },
];

export function Loop() {
  return (
    <section id="the-loop" className="bg-ink px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-content">
        <SectionHeading
          dark
          eyebrow="The Change RISKON Brings"
          heading="One connected loop, not eight disconnected tools"
          subtext="Every incident moves through the same closed chain — traceable at every stage, and never final until a human says so."
        />

        <Stagger className="mt-12 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {STEPS.map((s) => (
            <StaggerItem key={s.n}>
              <div
                className={`h-full rounded-lg border p-5 transition-transform duration-200 hover:-translate-y-1 ${
                  s.gate ? 'border-teal/50 bg-teal/10' : 'border-white/10 bg-white/[0.03]'
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-[13px] text-teal">{s.n}</span>
                  {s.gate && (
                    <span className="rounded-full border border-teal/40 px-2 py-0.5 font-mono text-[9.5px] uppercase tracking-[0.1em] text-teal">
                      Required Gate
                    </span>
                  )}
                </div>
                <p className="mt-2.5 text-[13.5px] font-semibold leading-snug text-paper">{s.label}</p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>

        <Reveal delay={0.1} className="mt-8">
          <p className="text-center text-[13.5px] leading-relaxed text-white/50">
            Nothing in this chain — no severity rating, no corrective action, no risk register entry — becomes
            real until a plant's own safety team approves it.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
