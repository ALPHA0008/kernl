const LABELS: Record<string, string> = {
  missing_facts: "missing facts",
  conflict: "conflict",
  no_matching_policy: "no matching policy",
  policy_directed: "policy-directed",
  authority_required: "authority required",
};

export function ReasonChip({ reason }: { reason: string }) {
  return (
    <span className="inline-block rounded-full bg-escalate-bg px-2 py-0.5 text-xs font-medium text-escalate">
      {LABELS[reason] ?? reason}
    </span>
  );
}
