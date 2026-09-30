import { SectionHeading } from '../components/SectionHeading.jsx';
import { Reveal } from '../components/Reveal.jsx';
import { Prose } from '../components/Prose.jsx';

const ITEMS = [
  {
    n: '1',
    heading: "Something that catches the pattern while it's still forming",
    body: 'Most EHS platforms show a facility its own incidents — full stop. The same forklift near-miss happening at two plants three states apart looks like two unrelated rows in two separate reports, because nothing connects them. RISKON\'s underlying schema was built from day one to treat "the same hazard, twice, in two places" as the thing worth surfacing — not an afterthought bolted onto a dashboard later. Of everything on this page, this is the one already partly proven in the prototype.',
  },
  {
    n: '2',
    heading: "An AI that shows its work, not just its answer",
    body: "Incumbent EHS platforms are shipping AI features fast right now — real ones, not vaporware. What most of them don't expose is the reasoning underneath the answer. RISKON attaches a source (extracted from the report vs. inferred), a confidence level, and a plain-language reasoning trail to every AI-generated field, by schema design, not as a debug log nobody reads. A safety officer reviewing a root-cause hypothesis can see exactly why the model thinks what it thinks, and reject it cleanly when it's wrong.",
  },
  {
    n: '3',
    heading: 'A control caught quietly failing on the second incident, not the fifth',
    body: 'Control effectiveness usually gets reassessed on a schedule — annually, or after an audit finding. RISKON can track every time a control gets invoked across an incident, a near-miss, or an inspection, and flag when the same control keeps showing up next to a repeat problem, long before the formal reassessment that would have caught it anyway.',
  },
  {
    n: '4',
    heading: 'Something a single mid-market plant can actually pilot',
    body: 'Enterprise EHS platforms are sold the way enterprise software gets sold — an RFP, a multi-month evaluation, an implementation team. That\'s the right process for a multinational rolling out across forty sites. It\'s a wall for a 300-person manufacturer whose safety officer wants to try something next month, not next year. RISKON\'s honest opening isn\'t "better than the incumbents." It\'s "usable by the plant their sales process was never built to reach quickly."',
  },
  {
    n: '5',
    heading: 'A reporting experience simple enough that near-misses actually get filed',
    body: "Most near-misses go unreported for a boring reason: filing one takes almost as much effort as filing an injury, with none of the urgency forcing it. A two-minute form a shift worker can complete without learning a system is the unglamorous feature that gives every downstream part of RISKON — the pattern detection, the risk register — data to actually work with.",
  },
  {
    n: '6',
    heading: 'The engine other industrial software runs on, not just another suite',
    body: "The bigger version of this, long term, probably isn't a bigger EHS suite. It's a reasoning engine other systems plug into — a maintenance platform that wants incident context next to a work order, an ERP that wants risk exposure next to a production line. That's a stranger, larger business than another subscription tier, and it's the version of RISKON hardest for an incumbent to bolt on after the fact, because it means being infrastructure, not a screen someone logs into.",
  },
];

export function SixThings() {
  return (
    <section id="what-it-can-become" className="bg-sand px-6 py-20 sm:py-24">
      <Prose>
        <SectionHeading
          eyebrow="What RISKON Can Become"
          heading="Six things most safety software isn't built for"
        />
      </Prose>

      <Prose className="mt-14 flex flex-col gap-14">
        {ITEMS.map((item, i) => (
          <Reveal key={item.n} y={14} delay={Math.min(i * 0.04, 0.16)}>
            <div className="flex gap-5 sm:gap-7">
              <span className="select-none font-serif text-[42px] font-medium leading-none text-teal/30 sm:text-[52px]">
                {item.n}
              </span>
              <div className="pt-1">
                <h3 className="font-serif text-[20px] font-semibold leading-snug text-ink sm:text-[22px]">
                  {item.heading}
                </h3>
                <p className="mt-3 text-[15px] leading-[1.75] text-ink/70">{item.body}</p>
              </div>
            </div>
          </Reveal>
        ))}
      </Prose>
    </section>
  );
}
