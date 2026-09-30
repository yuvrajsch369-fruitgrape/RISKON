import { IconMark } from '../icons.jsx';
import { PROTOTYPE_URL } from '../constants.js';

const LINKS = [
  { href: '#the-loop', label: 'The Loop' },
  { href: '#why-different', label: 'Why Different' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#how-it-works', label: 'How It Works' },
];

export function Nav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-white/10 bg-ink/95 backdrop-blur">
      <div className="mx-auto flex max-w-content items-center justify-between px-6 py-3.5">
        <a href="#top" className="flex items-center gap-2.5 text-paper">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-teal/15 text-teal">
            <IconMark width={17} height={17} strokeWidth={1.7} />
          </span>
          <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.16em]">RISKON</span>
        </a>

        <div className="hidden items-center gap-7 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-[13.5px] text-white/65 transition-colors hover:text-white"
            >
              {l.label}
            </a>
          ))}
        </div>

        <a
          href={PROTOTYPE_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md bg-teal px-4 py-2 text-[13px] font-semibold text-ink transition-transform duration-200 hover:-translate-y-0.5 hover:bg-teal-dark hover:text-paper"
        >
          RISKON V0
        </a>
      </div>
    </nav>
  );
}
