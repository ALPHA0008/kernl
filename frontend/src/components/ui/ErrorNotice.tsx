import { ApiError } from "@/lib/api";

/** Renders the backend's real failure. 409s are gate refusals (system policy,
 *  not errors); 503 means storage is down — never faked. */
export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  const isApi = error instanceof ApiError;
  const status = isApi ? (error as ApiError).status : null;
  const text = isApi
    ? (error as ApiError).detail
    : error instanceof Error
      ? error.message
      : String(error);
  const isGate = status === 409;
  const tone = isGate
    ? "bg-warning-soft text-warning-deep"
    : "bg-error-soft text-error-deep";
  return (
    <div
      className={`flex items-start gap-2 rounded-md px-3.5 py-2.5 text-sm ${tone}`}
      role="alert"
    >
      {status ? (
        <span className="mt-px shrink-0 font-mono text-[11px] opacity-70">{status}</span>
      ) : null}
      <span>{text}</span>
    </div>
  );
}
