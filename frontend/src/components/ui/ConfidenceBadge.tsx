interface ConfidenceBadgeProps {
  value: number; // 0.0 - 1.0
  size?: "sm" | "md";
}

export default function ConfidenceBadge({ value, size = "sm" }: ConfidenceBadgeProps) {
  const pct = Math.round(value * 100);

  let colorVar: string;
  let bgVar: string;
  let borderVar: string;

  if (value >= 0.8) {
    colorVar = "var(--success)";
    bgVar = "var(--success-bg)";
    borderVar = "rgba(52, 211, 153, 0.25)";
  } else if (value >= 0.6) {
    colorVar = "var(--warning)";
    bgVar = "var(--warning-bg)";
    borderVar = "rgba(251, 191, 36, 0.25)";
  } else if (value >= 0.4) {
    colorVar = "var(--info)";
    bgVar = "var(--info-bg)";
    borderVar = "rgba(96, 165, 250, 0.25)";
  } else {
    colorVar = "var(--error)";
    bgVar = "var(--error-bg)";
    borderVar = "rgba(248, 113, 113, 0.25)";
  }

  const textSize = size === "sm" ? "text-[10px]" : "text-xs";
  const px = size === "sm" ? "px-2 py-0.5" : "px-2.5 py-1";

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono font-semibold ${textSize} ${px} rounded`}
      style={{
        color: colorVar,
        background: bgVar,
        border: `1px solid ${borderVar}`,
      }}
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ background: colorVar }}
      />
      {pct}%
    </span>
  );
}
