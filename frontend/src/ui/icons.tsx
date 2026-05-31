// Minimal stroke icons (inherit currentColor). 24px grid.
type P = { size?: number; fill?: boolean };
const s = (n = 24) => ({ width: n, height: n, viewBox: "0 0 24 24", fill: "none" });
const stroke = { stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export const IconLibrary = ({ size }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <rect x="3.5" y="3.5" width="7" height="7" rx="2" />
    <rect x="13.5" y="3.5" width="7" height="7" rx="2" />
    <rect x="3.5" y="13.5" width="7" height="7" rx="2" />
    <rect x="13.5" y="13.5" width="7" height="7" rx="2" />
  </g></svg>
);

export const IconSections = ({ size }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <path d="M12 3.2 21 7.5 12 11.8 3 7.5z" />
    <path d="M3.5 12 12 16l8.5-4M3.5 16.4 12 20.4l8.5-4" />
  </g></svg>
);

export const IconWave = ({ size }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <path d="M4 12v0M8 8v8M12 5v14M16 8v8M20 12v0" />
  </g></svg>
);

export const IconProfile = ({ size }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <circle cx="12" cy="8" r="3.4" />
    <path d="M5 20c1.2-3.6 4-5 7-5s5.8 1.4 7 5" />
  </g></svg>
);

export const IconPlay = ({ size = 24 }: P) => (
  <svg {...s(size)}><path d="M8 5.5v13l11-6.5z" fill="currentColor" /></svg>
);
export const IconPause = ({ size = 24 }: P) => (
  <svg {...s(size)}><g fill="currentColor"><rect x="6.5" y="5.5" width="3.4" height="13" rx="1.1" /><rect x="14.1" y="5.5" width="3.4" height="13" rx="1.1" /></g></svg>
);
export const IconPrev = ({ size = 24 }: P) => (
  <svg {...s(size)}><g fill="currentColor"><rect x="5" y="6" width="2.4" height="12" rx="1.1" /><path d="M19 6.2v11.6L10 12z" /></g></svg>
);
export const IconNext = ({ size = 24 }: P) => (
  <svg {...s(size)}><g fill="currentColor"><rect x="16.6" y="6" width="2.4" height="12" rx="1.1" /><path d="M5 6.2v11.6L14 12z" /></g></svg>
);
export const IconShuffle = ({ size = 24 }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <path d="M3 6h3.5c1.5 0 2.5.8 3.3 2M21 6h-3.5c-2.5 0-3.5 2.2-5.5 6s-3 6-5.5 6H3" />
    <path d="M3 18h3.5c1.5 0 2.5-.8 3.3-2" />
    <path d="M18.5 3.5 21 6l-2.5 2.5M18.5 15.5 21 18l-2.5 2.5" />
  </g></svg>
);
export const IconLoop = ({ size = 24 }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <path d="M4 9a4 4 0 0 1 4-4h9l-2.2-2.2M20 15a4 4 0 0 1-4 4H7l2.2 2.2" />
  </g></svg>
);
export const IconSpeed = ({ size = 24 }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <path d="M5 18a8 8 0 1 1 14 0" />
    <path d="M12 13l3.5-3" />
  </g></svg>
);
export const IconHeart = ({ size = 24, fill }: P) => (
  <svg {...s(size)}>
    <path d="M12 20s-7-4.4-9-9c-1.3-3 .4-6 3.3-6 2 0 3 1.2 3.7 2.3C14.7 4.2 15.7 5 17.7 5 20.6 5 22.3 8 21 11c-2 4.6-9 9-9 9z"
      fill={fill ? "currentColor" : "none"} {...stroke} />
  </svg>
);
export const IconChevron = ({ size = 20 }: P) => (
  <svg {...s(size)}><path d="M9 5l7 7-7 7" {...stroke} /></svg>
);
export const IconBack = ({ size = 20 }: P) => (
  <svg {...s(size)}><path d="M15 5l-7 7 7 7" {...stroke} /></svg>
);
export const IconGear = ({ size = 20 }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" />
  </g></svg>
);
export const IconImport = ({ size = 20 }: P) => (
  <svg {...s(size)}><g {...stroke}><path d="M12 3v11M8 10l4 4 4-4M5 20h14" /></g></svg>
);
export const IconInfo = ({ size = 20 }: P) => (
  <svg {...s(size)}><g {...stroke}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.6v.2" /></g></svg>
);
export const IconCheck = ({ size = 16 }: P) => (
  <svg {...s(size)}><path d="M5 12l4 4 10-10" {...stroke} /></svg>
);
export const IconArrowUp = ({ size = 24 }: P) => (
  <svg {...s(size)}><path d="M12 19V5M6 11l6-6 6 6" {...stroke} /></svg>
);
export const IconRefresh = ({ size = 20 }: P) => (
  <svg {...s(size)}><g {...stroke}>
    <path d="M21 12a9 9 0 1 1-2.64-6.36" />
    <path d="M21 4v4.5h-4.5" />
  </g></svg>
);
