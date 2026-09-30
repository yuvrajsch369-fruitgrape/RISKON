import { Eyebrow } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

const ROLES = [
  {
    label: 'Employee',
    heading: 'The report becomes a two-way signal, not a one-way form',
    body: "Today, filing a report is the whole interaction. In the future workflow, an employee who reports a near-miss can see, later, what it led to — the corrective action it triggered, whether the same thing happened at another site too — instead of a report disappearing into a system they never hear from again. That loop is what turns reporting from a compliance obligation into something workers actually trust is worth doing.",
  },
  {
    label: 'HSE Manager',
    heading: 'Reviewing shifts from single incidents to a prioritized risk queue',
    body: "Today, an HSE manager reviews one AI-drafted investigation at a time, as incidents come in. Once cross-facility pattern detection and the early-warning layer are real, that queue reorders itself — a hazard showing up for the third time in six weeks, or a control the data suggests is quietly failing, surfaces before the next incident makes it undeniable. The manager still approves everything; what changes is what gets put in front of them first.",
  },
  {
    label: 'Plant Manager',
    heading: "The facility's own numbers, next to everyone else's",
    body: "A plant manager's dashboard today shows this facility's incidents and risks. The future version adds the comparison that's currently invisible: how this facility's risk trajectory compares to the company's other sites, and whether a maintenance delay here is following the same pattern that preceded an incident somewhere else in the company.",
  },
  {
    label: 'Executive',
    heading: 'Portfolio risk that updates itself, not a slide someone built',
    body: "Today, an executive gets current cross-facility standing instead of a quarterly rollup — that part is already real in the prototype. The future version is what that standing is built from: the same reasoning engine feeding risk data directly into whatever system leadership already runs the business on, instead of RISKON being one more dashboard someone has to remember to open.",
  },
];

export function FutureWorkflow() {
  return (
    <section id="future-workflow" className="bg-paper px-6 py-20 sm:py-24">
      <Prose>
        <Reveal y={12}>
          <Eyebrow>The Future Workflow, By Role</Eyebrow>
        </Reveal>
        <Reveal y={12} delay={0.06} className="mt-5">
          <p className="text-[16px] leading-[1.75] text-ink/75">
            The current prototype already gives each role a working version of this loop. Here's what
            changes once cross-facility pattern detection and the early-warning layer above are actually
            built — not a different workflow, the same one with more built underneath it.
          </p>
        </Reveal>
      </Prose>

      <Prose className="mt-12 flex flex-col gap-10">
        {ROLES.map((role, i) => (
          <Reveal key={role.label} y={12} delay={Math.min(i * 0.04, 0.16)}>
            <div className={`pt-8 ${i !== 0 ? 'border-t border-ink/10' : ''}`}>
              <span className="font-mono text-[11px] uppercase tracking-[0.12em] text-teal">{role.label}</span>
              <h3 className="mt-2.5 font-serif text-[19px] font-semibold leading-snug text-ink sm:text-[21px]">
                {role.heading}
              </h3>
              <p className="mt-3 text-[15px] leading-[1.75] text-ink/70">{role.body}</p>
            </div>
          </Reveal>
        ))}
      </Prose>
    </section>
  );
}
