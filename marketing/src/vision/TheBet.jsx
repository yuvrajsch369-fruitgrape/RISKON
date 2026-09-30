import { Eyebrow } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

export function TheBet() {
  return (
    <section id="the-bet" className="bg-paper px-6 py-20 sm:py-24">
      <Prose>
        <Reveal y={12}>
          <Eyebrow>The Bet</Eyebrow>
        </Reveal>
        <Reveal y={12} delay={0.08} className="mt-5">
          <p className="text-[17px] leading-[1.75] text-ink/80">
            Every incident-management system that exists right now — the binder, the spreadsheet, the
            enterprise EHS suite — records what a human already worked out. RISKON's bet is that the
            version of this worth building sits earlier: at the moment an incident is reported, doing the
            first pass of classification, hazard identification, and root-cause reasoning before a person
            has to start from a blank page — and never once making the actual safety call itself.
            Everything below follows from that one idea.
          </p>
        </Reveal>
      </Prose>
    </section>
  );
}
