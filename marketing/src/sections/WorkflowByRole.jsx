import { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { SectionHeading } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { IconCheck } from '../icons.jsx';

const ROLES = [
  {
    id: 'employee',
    label: 'Employee',
    eyebrow: 'For the person on the floor',
    heading: 'Report what you see, in under two minutes.',
    body: "No safety-management jargon required. A short form — what happened, where, when, who was involved — and a confirmation that it's being looked at.",
    bullets: [
      'Files an incident or near-miss from the floor',
      'Sees their own report\'s status without chasing anyone',
      'Never has to know what "root cause analysis" means to use it',
    ],
  },
  {
    id: 'hse',
    label: 'HSE Manager',
    eyebrow: 'For the person who investigates',
    heading: 'Investigate with evidence, not a blank page.',
    body: 'Opens each incident to a full AI-drafted chain — classification, hazards, root-cause hypotheses, proposed actions — and edits, approves, or sends it back.',
    bullets: [
      'Reviews and approves every AI-generated field, with the reasoning shown',
      'Owns the risk register and tracks every corrective action to close',
      'Spends time on judgment calls, not re-typing what already happened',
    ],
  },
  {
    id: 'plant',
    label: 'Plant Manager',
    eyebrow: 'For the person who runs the site',
    heading: "See your facility's real risk picture.",
    body: "One dashboard for open incidents, overdue actions, and the facility's current risk profile — not a spreadsheet someone updates before the audit.",
    bullets: [
      'Sees every open incident and risk at this facility, live',
      "Drills into any incident's full investigation chain in one click",
      'Knows which corrective actions are overdue before an auditor does',
    ],
  },
  {
    id: 'exec',
    label: 'Executive',
    eyebrow: 'For the person who owns the portfolio',
    heading: 'Risk intelligence across every site, not a quarterly PDF.',
    body: 'Patterns that no single-site manager can see — the same equipment failing at two plants, a control quietly failing everywhere — surfaced across the whole portfolio.',
    bullets: [
      'Views risk exposure across every facility in one place',
      "Sees cross-site patterns individual plant teams structurally can't",
      'Gets current risk standing, not last quarter\'s summary',
    ],
  },
];

export function WorkflowByRole() {
  const [activeId, setActiveId] = useState(ROLES[0].id);
  const active = ROLES.find((r) => r.id === activeId);

  return (
    <section id="workflow" className="bg-sand px-6 py-24 sm:py-28">
      <div className="mx-auto max-w-content">
        <SectionHeading
          align="center"
          eyebrow="The Workflow, By Role"
          heading="Four people, one system"
          subtext="RISKON looks different depending on who's using it — because a forklift operator and a plant director need different things from the same incident."
        />

        <Reveal delay={0.1} className="mt-10 flex justify-center">
          <div className="inline-flex flex-wrap justify-center gap-2 rounded-full border border-ink/10 bg-white/50 p-1.5">
            {ROLES.map((role) => (
              <button
                key={role.id}
                type="button"
                onClick={() => setActiveId(role.id)}
                className={`rounded-full px-4 py-2 text-[13.5px] font-semibold transition-colors duration-200 ${
                  activeId === role.id ? 'bg-ink text-paper' : 'text-ink/55 hover:text-ink'
                }`}
              >
                {role.label}
              </button>
            ))}
          </div>
        </Reveal>

        <div className="relative mt-10 min-h-[280px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={active.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto grid max-w-3xl gap-8 rounded-xl border border-ink/10 bg-white p-8 sm:p-10 md:grid-cols-[1.1fr_0.9fr]"
            >
              <div>
                <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-teal">{active.eyebrow}</span>
                <h3 className="mt-3 font-serif text-2xl font-semibold leading-snug text-ink">{active.heading}</h3>
                <p className="mt-3 text-[14.5px] leading-relaxed text-ink/65">{active.body}</p>
              </div>
              <ul className="flex flex-col justify-center gap-3.5 border-t border-ink/10 pt-6 md:border-l md:border-t-0 md:pl-8 md:pt-0">
                {active.bullets.map((b) => (
                  <li key={b} className="flex items-start gap-2.5 text-[13.5px] leading-relaxed text-ink/70">
                    <IconCheck width={15} height={15} className="mt-0.5 shrink-0 text-teal" />
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
