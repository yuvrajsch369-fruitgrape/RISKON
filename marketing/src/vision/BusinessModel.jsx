import { Eyebrow } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

export function BusinessModel() {
  return (
    <section className="bg-paper px-6 py-20 sm:py-24">
      <Prose>
        <Reveal y={12}>
          <Eyebrow>How This Actually Makes Money</Eyebrow>
        </Reveal>
        <Reveal y={12} delay={0.08} className="mt-5">
          <p className="text-[16px] leading-[1.75] text-ink/75">
            The per-facility subscription is the visible part — a pilot on historical data, then a paid
            tier once a plant runs live incidents through it. That's not where the largest number
            eventually sits, though. The larger number is the reasoning engine itself, licensed to systems
            that already sit inside a plant: a maintenance platform, an ERP, eventually a larger EHS suite
            that would rather license explainable incident reasoning than rebuild it from scratch with the
            same guardrail discipline. Three different buyers — the plant safety team, the software vendor,
            the enterprise integrator — one engine underneath all of them.
          </p>
        </Reveal>
      </Prose>
    </section>
  );
}
