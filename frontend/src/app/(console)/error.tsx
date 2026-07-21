"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/Button";

/** Catches uncaught render exceptions anywhere under the console shell so a
 *  bug in one screen never takes down the whole app to a blank Next.js crash
 *  page. Fetch failures are already handled per-screen via ErrorNotice; this
 *  is the backstop for everything else (a bad render, a thrown assertion). */
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
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div className="flex items-start gap-2 rounded-md bg-error-soft px-3.5 py-2.5 text-sm text-error-deep">
        <span>Something went wrong rendering this screen.</span>
      </div>
      <p className="max-w-md text-sm text-body">{error.message}</p>
      <Button variant="secondary" onClick={() => unstable_retry()}>
        Try again
      </Button>
    </div>
  );
}
