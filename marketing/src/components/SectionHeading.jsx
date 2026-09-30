import { Reveal } from './Reveal.jsx';

export function Eyebrow({ children, tone = 'teal', dark = false }) {
  const toneClasses =
    tone === 'amber'
      ? 'text-amber border-amber/40'
      : dark
      ? 'text-teal/90 border-teal/30'
      : 'text-teal border-teal/30';
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 font-mono text-[11px] uppercase tracking-[0.14em] ${toneClasses}`}
    >
      {children}
    </span>
  );
}

export function SectionHeading({ eyebrow, heading, subtext, dark = false, align = 'left', tone = 'teal' }) {
  const alignClass = align === 'center' ? 'text-center items-center mx-auto' : 'text-left items-start';
  return (
    <div className={`flex max-w-2xl flex-col gap-4 ${alignClass}`}>
      <Reveal>
        <Eyebrow dark={dark} tone={tone}>
          {eyebrow}
        </Eyebrow>
      </Reveal>
      <Reveal delay={0.08}>
        <h2
          className={`font-serif text-3xl font-semibold leading-[1.15] sm:text-4xl ${
            dark ? 'text-paper' : 'text-ink'
          }`}
        >
          {heading}
        </h2>
      </Reveal>
      {subtext && (
        <Reveal delay={0.14}>
          <p className={`text-[15.5px] leading-relaxed ${dark ? 'text-white/60' : 'text-ink/60'}`}>{subtext}</p>
        </Reveal>
      )}
    </div>
  );
}
