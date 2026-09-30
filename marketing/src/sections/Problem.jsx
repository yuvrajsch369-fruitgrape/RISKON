import { SectionHeading } from '../components/SectionHeading.jsx';
import { Stagger, StaggerItem } from '../components/Reveal.jsx';

const PAIN_POINTS = [
  "Incidents get logged, but root-cause analysis depends on who's on shift and how much time they have that day.",
  "Near-misses go uninvestigated — there's no injury forcing the paperwork, so the warning gets lost.",
  'The risk register goes stale between audits, so it reflects last quarter\'s plant, not this week\'s.',
  'The same equipment failure, the same control quietly not working, repeats across facilities that never compare notes.',
];

export function Problem() {
  return (
    <section className="bg-paper px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-content">
        <SectionHeading
          eyebrow="The Problem"
          heading="Safety data has a blind spot problem"
          subtext="Most industrial operations don't lack safety data. They lack a system that connects it."
        />

        <Stagger className="mt-12 grid gap-4 sm:grid-cols-2">
          {PAIN_POINTS.map((text, i) => (
            <StaggerItem key={i}>
              <div className="h-full rounded-lg border border-ink/10 bg-white/40 p-6 transition-shadow duration-200 hover:shadow-[0_4px_24px_-8px_rgba(11,15,20,0.12)]">
                <p className="text-[15px] leading-relaxed text-ink/75">{text}</p>
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </section>
  );
}
