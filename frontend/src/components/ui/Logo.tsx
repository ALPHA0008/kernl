import React from "react";

interface LogoProps extends React.SVGProps<SVGSVGElement> {
  size?: number;
}

/**
 * Kernl's locked, category-defining M-1 Golden Split Monolith.
 * Two flat monolithic columns separated by an open line of judgment.
 */
export function Logo({ size = 24, className, ...props }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      {...props}
    >
      {/* Left Column (Authority/Constitution) */}
      <rect x="28" y="12" width="26" height="76" fill="currentColor" />
      {/* Right Column (Warrant/Execution) */}
      <rect x="61" y="12" width="11" height="76" fill="currentColor" />
    </svg>
  );
}
