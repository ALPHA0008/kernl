import { forwardRef } from "react";

/** Vercel form-input: 40px tall, 6px radius, hairline border, focus ring.
 *  Width defaults to full but any w-* in className overrides it (Tailwind
 *  emits w-* after this base, so a passed w-auto wins). */
const base =
  "rounded-[6px] border border-hairline bg-canvas px-3 text-sm text-ink placeholder:text-mute transition-colors focus:border-hairline-strong focus:ring-2 focus:ring-ink/5 disabled:opacity-50";

// default to full width unless the caller sets an explicit width class
const widthDefault = (cn: string) => (/\bw-/.test(cn) ? "" : "w-full");

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { mono?: boolean }>(
  function Input({ className = "", mono, ...rest }, ref) {
    return (
      <input
        ref={ref}
        className={`${base} ${widthDefault(className)} h-10 ${mono ? "font-mono" : ""} ${className}`}
        {...rest}
      />
    );
  },
);

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & { mono?: boolean }
>(function Textarea({ className = "", mono, ...rest }, ref) {
  return (
    <textarea
      ref={ref}
      className={`${base} ${widthDefault(className)} py-2 leading-relaxed ${mono ? "font-mono text-[13px]" : ""} ${className}`}
      {...rest}
    />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement> & { mono?: boolean }
>(function Select({ className = "", mono, children, ...rest }, ref) {
  return (
    <select
      ref={ref}
      className={`${base} ${widthDefault(className)} h-9 cursor-pointer ${mono ? "font-mono text-[13px]" : ""} ${className}`}
      {...rest}
    >
      {children}
    </select>
  );
});

export function FieldLabel({
  children,
  htmlFor,
  required,
}: {
  children: React.ReactNode;
  htmlFor?: string;
  required?: boolean;
}) {
  return (
    <label htmlFor={htmlFor} className="t-eyebrow mb-1.5 block">
      {children}
      {required ? <span className="ml-0.5 text-error">*</span> : null}
    </label>
  );
}
