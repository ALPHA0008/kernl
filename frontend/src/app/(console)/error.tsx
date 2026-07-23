"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/Button";

/** Catches uncaught render exceptions anywhere under the console shell so a
 *  bug in one screen never takes down the whole app to a blank Next.js crash
 *  page. Fetch failures are already handled per-screen via ErrorNotice; this
 *  is the backstop for everything else (a bad render, a thrown assertion).
 *
 *  Recovery is two-pronged on purpose: "Try again" re-renders the same screen
 *  (fixes a transient error), but if the error is deterministic (a data shape
 *  the screen can't handle), retry would loop — so we always offer a way OUT
 *  to the Ledger. The raw message is demoted to a monospace detail line, not
 *  the headline, so an operator isn't handed a developer stack string as the
 *  primary content. */
export default function ConsoleError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 px-6 text-center">
      <div>
        <h2 className="t-display-sm mb-1.5 text-ink">This screen hit an error</h2>
        <p className="max-w-md text-sm text-body">
          The rest of the console is unaffected. Try again, or head back to the Ledger.
        </p>
      </div>
      {error.message ? (
        <p className="max-w-md break-words rounded-md bg-canvas-soft px-3.5 py-2 font-mono text-xs text-mute">
          {error.message}
        </p>
      ) : null}
      <div className="flex items-center gap-2.5">
        <Button onClick={() => unstable_retry()}>Try again</Button>
        <Link href="/ledger">
          <Button variant="secondary">Back to Ledger</Button>
        </Link>
      </div>
    </div>
  );
}
