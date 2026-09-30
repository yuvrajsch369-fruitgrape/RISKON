import { Eyebrow } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

export function WhereThisStands() {
  return (
    <section className="bg-paper px-6 py-20 sm:py-28">
      <Prose>
        <Reveal y={12}>
          <Eyebrow>Where This Actually Stands Right Now</Eyebrow>
        </Reveal>
        <Reveal y={12} delay={0.08} className="mt-6">
          {/* Kept precise rather than repeating the rounder "thirteen stages
              running end to end" framing verbatim: what's actually wired is
              a real Claude call reasoning over a real incident's real
              facility/equipment/hazard/control history; the fuller
              thirteen-stage trace is built and demonstrated on real data,
              not yet what generates live for every case. Same standard this
              section is asking to be held to. */}
          <p className="text-[16px] leading-[1.75] text-ink/75">
            What's built so far is the full closed-loop pipeline running on synthetic data: a real, wired
            Claude integration that investigates a submitted incident against its actual facility,
            equipment, hazard, and control history; the fuller thirteen-stage reasoning trace — information
            extraction through risk-register impact — built and demonstrated end to end on real incident
            data; a validated relational database; a working frontend; deployed and piloting. Everything
            above is the case for why it's worth finishing, and why the constraint at its center — a human
            approves every decision the system doesn't get to make itself — is worth keeping even when it
            would be faster not to.
          </p>
        </Reveal>
        <Reveal y={12} delay={0.16} className="mt-10">
          <p className="font-serif text-[18px] italic leading-relaxed text-ink/55">
            This page is written assuming someone will hold RISKON to the same standard. That's on purpose.
          </p>
        </Reveal>
      </Prose>
    </section>
  );
}
