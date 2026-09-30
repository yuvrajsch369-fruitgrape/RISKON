import { Link } from 'react-router-dom';
import { IconMark } from '../icons.jsx';
import { PROTOTYPE_URL } from '../constants.js';

const LANDING_LINKS = [
  { href: '#the-loop', label: 'The Loop' },
  { href: '#why-different', label: 'Why Different' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#how-it-works', label: 'How It Works' },
];

const VISION_LINKS = [
  { href: '#the-bet', label: 'The Bet' },
  { href: '#what-it-can-become', label: 'What It Can Become' },
  { href: '#the-cority-scenario', label: 'The Cority Scenario' },
  { href: '#roadmap', label: 'Roadmap' },
  { href: '#future-workflow', label: 'Future Workflow' },
];

// One shared nav, two link sets — `page` decides which anchors show and
// which page the secondary button points at, so the landing page and the
// vision page can send someone to each other without duplicating the bar.
export function Nav({ page = 'landing' }) {
  const isVision = page === 'vision';
  const links = isVision ? VISION_LINKS : LANDING_LINKS;

  return (
    <nav className="sticky top-0 z-50 border-b border-white/10 bg-ink/95 backdrop-blur">
      <div className="mx-auto flex max-w-content items-center justify-between px-6 py-3.5">
        <Link to="/" className="flex items-center gap-2.5 text-paper">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-teal/15 text-teal">
            <IconMark width={17} height={17} strokeWidth={1.7} />
          </span>
          <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.16em]">RISKON</span>
        </Link>

        <div className="hidden items-center gap-7 md:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-[13.5px] text-white/65 transition-colors hover:text-white"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2.5">
          {isVision ? (
            <Link
              to="/"
              className="hidden rounded-md border border-white/20 px-3.5 py-2 text-[12.5px] font-semibold text-white/80 transition-colors duration-200 hover:border-white/40 hover:text-white sm:inline-flex"
            >
              Back to Overview
            </Link>
          ) : (
            <Link
              to="/future-vision"
              className="hidden rounded-md border border-white/20 px-3.5 py-2 text-[12.5px] font-semibold text-white/80 transition-colors duration-200 hover:border-white/40 hover:text-white sm:inline-flex"
            >
              Future Vision
            </Link>
          )}
          <a
            href={PROTOTYPE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-md bg-teal px-4 py-2 text-[13px] font-semibold text-ink transition-transform duration-200 hover:-translate-y-0.5 hover:bg-teal-dark hover:text-paper"
          >
            RISKON V0
          </a>
        </div>
      </div>
    </nav>
  );
}
