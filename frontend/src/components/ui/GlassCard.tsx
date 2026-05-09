import { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  elevated?: boolean;
  padding?: "none" | "sm" | "md" | "lg";
  onClick?: () => void;
  style?: React.CSSProperties;
}

const paddingMap = {
  none: "",
  sm: "p-4",
  md: "p-5",
  lg: "p-6",
};

export default function GlassCard({
  children,
  className = "",
  interactive = false,
  elevated = false,
  padding = "md",
  onClick,
  style,
}: GlassCardProps) {
  const baseClass = elevated ? "glass-card--elevated" : "glass-card";
  const interactiveClass = interactive ? "glass-card--interactive" : "";
  const padClass = paddingMap[padding];

  return (
    <div
      className={`${baseClass} ${interactiveClass} ${padClass} ${className}`}
      style={style}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}
