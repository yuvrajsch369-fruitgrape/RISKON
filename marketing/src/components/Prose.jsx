// The load-bearing container for this whole page — single column, ~740px,
// generous line-height. Almost every section on the vision page sits inside
// one of these instead of a grid, on purpose (this is an essay, not a deck).
export function Prose({ children, className = '' }) {
  return <div className={`mx-auto max-w-[740px] ${className}`}>{children}</div>;
}
