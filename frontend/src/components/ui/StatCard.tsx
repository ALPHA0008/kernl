interface StatCardProps {
  label: string;
  value: string | number;
  icon?: React.ReactNode;
  accent?: "primary" | "success" | "warning" | "info";
  subtitle?: string;
}

const accentMap = {
  primary: { bg: "var(--primary-ghost)", color: "var(--primary)" },
  success: { bg: "var(--success-bg)", color: "var(--success)" },
  warning: { bg: "var(--warning-bg)", color: "var(--warning)" },
  info: { bg: "var(--info-bg)", color: "var(--info)" },
};

export default function StatCard({
  label,
  value,
  icon,
  accent = "primary",
  subtitle,
}: StatCardProps) {
  const colors = accentMap[accent];

  return (
    <div className="glass-card p-5 animate-fade-in">
      <div className="flex items-start justify-between mb-3">
        <span
          className="text-[10px] font-semibold uppercase tracking-[0.08em] font-mono"
          style={{ color: "var(--text-muted)" }}
        >
          {label}
        </span>
        {icon && (
          <span
            className="w-8 h-8 rounded-lg flex items-center justify-center text-sm"
            style={{ background: colors.bg, color: colors.color }}
          >
            {icon}
          </span>
        )}
      </div>
      <p
        className="text-2xl font-bold tracking-tight"
        style={{ color: colors.color }}
      >
        {value}
      </p>
      {subtitle && (
        <p
          className="text-xs mt-1"
          style={{ color: "var(--text-muted)" }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}
