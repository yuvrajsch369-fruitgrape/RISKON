import { Eyebrow } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

export function CorityScenario() {
  return (
    <section id="the-cority-scenario" className="bg-sand px-6 py-20 sm:py-24">
      <Prose>
        <Reveal y={12}>
          <Eyebrow>The Cority Scenario</Eyebrow>
        </Reveal>
        <Reveal y={12} delay={0.08} className="mt-6 flex flex-col gap-5">
          <p className="text-[16px] leading-[1.75] text-ink/75">
            Here's the honest test of whether any of this holds up, because a vision page that skips the
            competition isn't a serious one.
          </p>
          <p className="text-[16px] leading-[1.75] text-ink/75">
            Cority isn't standing still. Its Cortex AI platform, launched in 2025, ships more than a dozen
            embedded EHS AI agents and was ranked the strongest AI platform in Verdantix's 2026
            process-safety benchmark, with human-in-the-loop guardrails built in. So this isn't a story
            about an empty market, and pretending otherwise would be dishonest.
          </p>
          <p className="text-[16px] leading-[1.75] text-ink/75">
            But CorityOne, like Intelex and Enablon, is built, priced, and sold the way enterprise software
            for large multinational operations gets built, priced, and sold — long implementation cycles,
            enterprise procurement, a customer profile that looks like a Fortune 500 EHS department, not a
            single mid-market plant trying something for the first time. That's the actual opening: not
            that the incumbents have nothing, but that what they've built isn't reachable, quickly, by the
            segment of the market RISKON is starting in.
          </p>
          <p className="text-[16px] leading-[1.75] text-ink/75">
            None of this starts with a pitch deck. It starts with proof — a real pilot, a pattern RISKON
            caught that a plant's existing process missed, numbers good enough to be worth showing off.
          </p>
        </Reveal>
      </Prose>
    </section>
  );
}
