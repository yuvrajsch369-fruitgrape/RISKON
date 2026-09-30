import { Eyebrow } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

export function PeopleImpact() {
  return (
    <section className="bg-paper px-6 py-20 sm:py-24">
      <Prose>
        <Reveal y={12}>
          <Eyebrow>How This Actually Changes Things for People</Eyebrow>
        </Reveal>
        <Reveal y={12} delay={0.08} className="mt-6 flex flex-col gap-5">
          <p className="text-[16px] leading-[1.75] text-ink/75">
            The reason any of this matters isn't the business model — it's who's actually exposed right
            now. Government data obtained through Right to Information requests shows roughly three workers
            dying every day in India's registered factories, and DGFASLI's own 2023 figures count 1,090
            fatal and 2,949 non-fatal injuries — in registered factories alone, which cover a fraction of a
            workforce that's roughly 90% informal.
          </p>
          <p className="text-[16px] leading-[1.75] text-ink/75">
            The people most exposed to that risk are rarely the ones a quarterly compliance report was
            built to protect: a contractor on their second visit to a site, a shift worker filling in on a
            line they don't normally run, a near-miss nobody had time to investigate before the next shift
            started. A system that makes real investigation and pattern detection available to a
            mid-market plant — not just the multinationals that can afford a full EHS department — does
            more for that exposure than another audit checklist ever will.
          </p>
        </Reveal>
      </Prose>
    </section>
  );
}
