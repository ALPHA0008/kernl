"use client";

import { use, useEffect, useState } from "react";
import { ReplayReport } from "@/components/replay/ReplayReport";
import { BackLink } from "@/components/ui/BackLink";
import { Button } from "@/components/ui/Button";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { acknowledgeReplay, getReplay } from "@/lib/api";
import { useSession } from "@/lib/auth";
import type { ReplayRun } from "@/lib/types";

export default function ReplayDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { apiKey, principal } = useSession();
  const { toast } = useToast();

  const [run, setRun] = useState<ReplayRun | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [ackError, setAckError] = useState<unknown>(null);

  useEffect(() => {
    getReplay(apiKey, id).then(setRun).catch(setError);
  }, [apiKey, id]);

  async function acknowledge() {
    setBusy(true);
    setAckError(null);
    try {
      await acknowledgeReplay(apiKey, id);
      setRun(await getReplay(apiKey, id));
      toast("Blast radius acknowledged — publish gate unlocked.", "success");
    } catch (err) {
      setAckError(err);
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return (
      <>
        <BackLink href="/replays" label="Back to Replay" />
        <PageHeader title="Replay run" />
        <ErrorNotice error={error} />
      </>
    );
  }
  if (!run) {
    return (
      <>
        <BackLink href="/replays" label="Back to Replay" />
        <Skeleton className="mb-4 h-8 w-64" />
        <Skeleton className="h-40" />
      </>
    );
  }

  const canAck = principal.role === "owner";

  return (
    <>
      <BackLink href="/replays" label="Back to Replay" />
      <PageHeader
        eyebrow="Govern"
        title="Replay report"
        subtitle="Blast radius before publish. Acknowledging unlocks the gate for this exact candidate."
      >
        {run.acknowledged_by ? (
          <span className="rounded-full bg-approve-bg px-3 py-1.5 text-xs font-medium text-approve">acknowledged</span>
        ) : canAck ? (
          <Button loading={busy} onClick={() => void acknowledge()}>Acknowledge blast radius</Button>
        ) : (
          <span className="text-xs text-mute">owner required to acknowledge</span>
        )}
      </PageHeader>

      {ackError ? <div className="mb-4"><ErrorNotice error={ackError} /></div> : null}

      <ReplayReport run={run} />

      {!run.acknowledged_by ? (
        <p className="mt-4 text-xs text-mute">
          A human owns the blast radius. Until an owner acknowledges this report, the matching draft cannot be published.
        </p>
      ) : null}
    </>
  );
}
