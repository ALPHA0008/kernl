"use client";

import { useState } from "react";
import { shortHash } from "@/lib/format";

/** Content-address chip: truncated hash, click to copy the full value. */
export function HashChip({ hash, chars = 12 }: { hash: string | null; chars?: number }) {
  const [copied, setCopied] = useState(false);
  if (!hash) return <span className="text-mute">—</span>;
  return (
    <button
      type="button"
      title={hash}
      onClick={() => {
        navigator.clipboard.writeText(hash).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
      className="inline-flex items-center gap-1 rounded-[6px] border border-hairline bg-canvas-soft px-1.5 py-0.5 font-mono text-xs text-body transition-colors hover:border-hairline-strong hover:text-ink"
    >
      {copied ? (
        <span className="text-approve">copied</span>
      ) : (
        shortHash(hash, chars)
      )}
    </button>
  );
}
