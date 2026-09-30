import { Eyebrow } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

export function HumanApproval() {
  return (
    <section className="bg-ink-raised px-6 py-20 sm:py-24">
      <Prose>
        <Reveal y={12}>
          <Eyebrow dark tone="teal">
            Why Human Approval Has to Stay Non-Negotiable
          </Eyebrow>
        </Reveal>
        <Reveal y={12} delay={0.08} className="mt-6 flex flex-col gap-5">
          <p className="text-[16px] leading-[1.75] text-white/70">
            None of the six things above work if a plant can't trust what the AI hands them, and trust in a
            safety-critical system isn't earned by a benchmark score. It's earned by a system that's
            structurally incapable of quietly upgrading its own suggestion into a decision. That's why the
            approval gate sits in RISKON's data model, not its settings menu — a severity rating, a
            corrective action, a risk register entry, none of it becomes real without a person signing off.
          </p>
          <p className="text-[16px] leading-[1.75] text-white/70">
            It also means the harder question in industrial AI — who's liable when a model gets it wrong —
            never has a wrong answer to give, because the model never had the authority to be wrong in the
            way that matters. As AI liability regulation in workplace safety software starts getting real
            attention — plausible, not yet certain — being the platform built around that constraint from
            the start stops being a value statement and starts being the reason a customer's legal team
            says yes.
          </p>
        </Reveal>
      </Prose>
    </section>
  );
}
