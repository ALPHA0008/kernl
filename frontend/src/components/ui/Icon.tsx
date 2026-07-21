/** Line-icon system — geometric, 1.5 stroke, currentColor, 16px default.
 *  Matches the Vercel/Geist icon language: simple, consistent, monochrome. */

type IconName =
  | "evaluate"
  | "ledger"
  | "escalations"
  | "policies"
  | "replay"
  | "onboarding"
  | "sources"
  | "settings"
  | "search"
  | "chevron-down"
  | "chevron-right"
  | "arrow-left"
  | "arrow-right"
  | "check"
  | "plus"
  | "external"
  | "copy"
  | "hash"
  | "logout"
  | "shield"
  | "clock"
  | "filter";

const PATHS: Record<IconName, React.ReactNode> = {
  // play / decision
  evaluate: <path d="M4.5 3.5v9l7-4.5-7-4.5z" />,
  // stacked layers
  ledger: (
    <>
      <path d="M8 2l6 3-6 3-6-3 6-3z" />
      <path d="M2 8l6 3 6-3M2 11l6 3 6-3" />
    </>
  ),
  // alert triangle
  escalations: (
    <>
      <path d="M8 2.5l5.5 10h-11l5.5-10z" />
      <path d="M8 6.5v3M8 11.2v.2" />
    </>
  ),
  // document with check
  policies: (
    <>
      <path d="M4 2h5l3 3v9H4V2z" />
      <path d="M9 2v3h3" />
      <path d="M6 9.5l1.3 1.3L10 8" />
    </>
  ),
  // circular replay
  replay: (
    <>
      <path d="M13 8a5 5 0 1 1-1.5-3.5" />
      <path d="M13 3v2.5h-2.5" />
    </>
  ),
  // upload / build
  onboarding: (
    <>
      <path d="M8 10.5V3.5M5 6l3-3 3 3" />
      <path d="M3 11v1.5h10V11" />
    </>
  ),
  // stacked documents
  sources: (
    <>
      <path d="M4.5 2.5h5l3 3v8h-8v-11z" />
      <path d="M2.5 5v8.5h6.5" />
    </>
  ),
  // gear
  settings: (
    <>
      <circle cx="8" cy="8" r="2" />
      <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4" />
    </>
  ),
  search: (
    <>
      <circle cx="7" cy="7" r="4.2" />
      <path d="M10 10l3 3" />
    </>
  ),
  "chevron-down": <path d="M4 6l4 4 4-4" />,
  "chevron-right": <path d="M6 4l4 4-4 4" />,
  "arrow-left": <path d="M9.5 4L5.5 8l4 4M5.5 8H12" />,
  "arrow-right": <path d="M6.5 4l4 4-4 4M10.5 8H4" />,
  check: <path d="M3.5 8.5l3 3 6-6" />,
  plus: <path d="M8 3.5v9M3.5 8h9" />,
  external: (
    <>
      <path d="M6 3h7v7" />
      <path d="M13 3L7 9" />
      <path d="M11 9v4H3V5h4" />
    </>
  ),
  copy: (
    <>
      <rect x="5" y="5" width="8" height="8" rx="1.5" />
      <path d="M3 11V4a1.5 1.5 0 0 1 1.5-1.5H11" />
    </>
  ),
  hash: <path d="M6 2.5L4.5 13.5M11.5 2.5L10 13.5M2.5 6h11M2 10h11" />,
  logout: (
    <>
      <path d="M6 3H3.5v10H6" />
      <path d="M9 5l3 3-3 3M12 8H5.5" />
    </>
  ),
  shield: <path d="M8 2l5 2v4c0 3-2.2 5.2-5 6-2.8-.8-5-3-5-6V4l5-2z" />,
  clock: (
    <>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 5v3l2 1.5" />
    </>
  ),
  filter: <path d="M2.5 3.5h11l-4.2 5v4l-2.6 1.3v-5.3L2.5 3.5z" />,
};

export function Icon({
  name,
  size = 16,
  className = "",
  strokeWidth = 1.4,
}: {
  name: IconName;
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  const filled = name === "evaluate" || name === "shield" || name === "filter";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill={filled ? "currentColor" : "none"}
      stroke={filled ? "none" : "currentColor"}
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden
    >
      {PATHS[name]}
    </svg>
  );
}

export type { IconName };
