import { IconMark } from '../icons.jsx';

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-ink px-6 py-8">
      <div className="mx-auto flex max-w-content flex-col items-center justify-between gap-4 sm:flex-row">
        <div className="flex items-center gap-2 text-white/70">
          <IconMark width={16} height={16} className="text-teal" />
          <span className="text-[13px]">RISKON — Industrial Risk Operating System</span>
        </div>
        <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-white/35">
          Prototype stage · Piloting now
        </span>
      </div>
    </footer>
  );
}
