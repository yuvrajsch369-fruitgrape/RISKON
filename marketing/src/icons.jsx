// Hand-drawn, minimal stroke icons — deliberately not a generic icon-pack
// look, and matching the same thin-stroke, no-fill convention the actual
// RISKON product UI already uses (see frontend/app.template.html's ICONS
// object), so the marketing page and the product feel like one thing.
const base = {
  width: 24,
  height: 24,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export function IconMark(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 2.5L20 6v6c0 5.2-3.4 8.7-8 9.5-4.6-.8-8-4.3-8-9.5V6l8-3.5Z" />
      <path d="M8.3 12.2l2.4 2.4L16 9.3" />
    </svg>
  );
}

export function IconReport(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3L21 20H3L12 3Z" />
      <path d="M12 9.5v4" />
      <circle cx="12" cy="16.3" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconInvestigate(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M15.2 15.2L21 21" />
    </svg>
  );
}

export function IconTarget(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconCheck(props) {
  return (
    <svg {...base} {...props}>
      <path d="M4.5 12.3l4.3 4.3L19.5 6.2" />
    </svg>
  );
}

export function IconAction(props) {
  return (
    <svg {...base} {...props}>
      <rect x="4" y="4" width="16" height="16" rx="2.5" />
      <path d="M8.5 12.3l2.4 2.4L16 9.4" />
    </svg>
  );
}

export function IconGate(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 2.8L19.5 6v6c0 4.7-3.1 7.9-7.5 8.7-4.4-.8-7.5-4-7.5-8.7V6L12 2.8Z" />
      <path d="M12 8.2v4.4" />
      <circle cx="12" cy="15.4" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function IconRegister(props) {
  return (
    <svg {...base} {...props}>
      <rect x="5" y="3.5" width="14" height="17" rx="1.5" />
      <path d="M8.5 8h7M8.5 12h7M8.5 16h4.5" />
    </svg>
  );
}

export function IconChart(props) {
  return (
    <svg {...base} {...props}>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <path d="M7.5 16.5l3.4-4.6 3 2.4L18.5 9" />
    </svg>
  );
}

export function IconConnect(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="6" cy="6.5" r="2.2" />
      <circle cx="18" cy="6.5" r="2.2" />
      <circle cx="12" cy="18" r="2.2" />
      <path d="M8 7.6L10.3 16M16 7.6L13.7 16M8.2 6.5h7.6" />
    </svg>
  );
}

export function IconFacility(props) {
  return (
    <svg {...base} {...props}>
      <path d="M4 20V9.5L9 6v3l5-3.5v5" />
      <path d="M4 20h16" />
      <path d="M14 20v-6h6v6" />
      <path d="M8 13.5h.01M8 17h.01" />
    </svg>
  );
}

export function IconLayers(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3.5l8 4.3-8 4.3-8-4.3 8-4.3Z" />
      <path d="M4 12.3l8 4.3 8-4.3M4 16.1l8 4.3 8-4.3" />
    </svg>
  );
}

export function IconEye(props) {
  return (
    <svg {...base} {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.6" />
    </svg>
  );
}

export function IconArrowRight(props) {
  return (
    <svg {...base} {...props}>
      <path d="M4 12h16" />
      <path d="M13.5 5.5L20 12l-6.5 6.5" />
    </svg>
  );
}

export function IconLoop(props) {
  return (
    <svg {...base} {...props}>
      <path d="M4 12a8 8 0 0 1 14-5.2" />
      <path d="M20 12a8 8 0 0 1-14 5.2" />
      <path d="M17.5 4.5v3.3h-3.3M6.5 19.5v-3.3h3.3" />
    </svg>
  );
}
