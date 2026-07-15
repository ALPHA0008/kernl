"use client";

import { forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

/** Vercel in-app button: 6px radius (--geist-radius), not the marketing pill.
 *  Full hover/active/focus/disabled/loading states. */
const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-ink text-on-primary shadow-[0_1px_2px_rgba(0,0,0,0.12)] hover:bg-[#333] active:bg-black disabled:bg-mute disabled:shadow-none",
  secondary:
    "bg-canvas text-ink shadow-[var(--shadow-1)] hover:bg-canvas-soft active:bg-canvas-soft-2",
  ghost: "bg-transparent text-body hover:bg-canvas-soft hover:text-ink",
  danger: "bg-error text-on-primary shadow-[0_1px_2px_rgba(0,0,0,0.12)] hover:bg-error-deep active:bg-error-deep",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-9 px-4 text-[13px]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, disabled, className = "", children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-1.5 rounded-[6px] font-medium leading-none transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60 ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...rest}
    >
      {loading ? (
        <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-current border-t-transparent" />
      ) : null}
      {children}
    </button>
  );
});
