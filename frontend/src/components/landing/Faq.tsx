/** Objection-handling FAQ as native <details> disclosure rows — crawlable text
 *  (no JS gate, good for AEO) and free accessible semantics. The four questions
 *  a careful buyer actually asks; kept identical to the FAQPage JSON-LD. */
export const FAQ_ITEMS = [
  {
    q: "Is Kernl another AI agent?",
    a: "No. Kernl is the neutral layer that decides and records. Your agents, human or AI, ask Kernl what policy allows, then act. Kernl never executes anything.",
  },
  {
    q: "Do we have to change our support workflow?",
    a: "No. Design partnerships run in shadow mode: read-only ingestion of decisions you already make. Your team changes nothing while the ledger builds.",
  },
  {
    q: "What does deterministic actually mean here?",
    a: "Same facts plus same policy version always produce the same decision. No model on the decision path. Ambiguous cases escalate to humans instead of guessing.",
  },
  {
    q: "Is our data safe with a young company?",
    a: "Shadow mode is read-only. A data processing agreement comes standard, deletion on request, and every bundle is cryptographically verifiable without trusting us.",
  },
];

export function Faq() {
  return (
    <div className="mt-10 divide-y divide-hairline border-y border-hairline">
      {FAQ_ITEMS.map((item) => (
        <details key={item.q} className="group py-1">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-[18px] font-medium text-ink transition-colors hover:text-body">
            {item.q}
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              className="shrink-0 text-mute transition-transform duration-200 group-open:rotate-45"
              aria-hidden
            >
              <path d="M8 3.5v9M3.5 8h9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
          </summary>
          <p className="max-w-[68ch] pb-5 text-[14px] leading-relaxed text-body">{item.a}</p>
        </details>
      ))}
    </div>
  );
}
