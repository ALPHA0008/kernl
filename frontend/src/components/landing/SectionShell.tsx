"use client";

import { useReveal } from "./useReveal";

/** Narrative-section wrapper. Owns the vertical rhythm and draws its own segment
 *  of the ledger spine plus a node at its top — the segments abut into one
 *  continuous hairline (guaranteed aligned because line + node share this box),
 *  and each node "posts" to ink as its section enters view: the record accruing
 *  as you read. lg+ only; on mobile the content is its own spine.
 *
 *  SPINE_X aligns to ~2.5rem left of the content text column (which starts at
 *  box-left + 5rem via the page's lg:pl-20).
 *
 *  `reveal` opts the section's own content into the shared fade-rise; artifact-
 *  led sections pass reveal={false} so they don't get a second entrance (craft
 *  floor: not one identical entrance on every section). */
const SPINE_X = "left-[calc(max(0px,(100vw-1200px)/2)+2.5rem)]";

export function SectionShell({
  id,
  children,
  reveal = true,
  className = "",
}: {
  id?: string;
  children: React.ReactNode;
  reveal?: boolean;
  className?: string;
}) {
  const { ref, inView } = useReveal<HTMLElement>();
  return (
    <section
      ref={ref}
      id={id}
      className={`relative scroll-mt-20 py-20 sm:py-24 lg:py-28 ${inView ? "in-view" : ""} ${className}`}
    >
      {/* spine segment for this section */}
      <span aria-hidden className={`absolute inset-y-0 ${SPINE_X} hidden w-px bg-hairline lg:block`} />
      {/* node: posts to ink when the section arrives */}
      <span
        aria-hidden
        className={`absolute top-24 ${SPINE_X} hidden h-2.5 w-2.5 -translate-x-[5px] rounded-full border transition-colors duration-300 lg:block ${
          inView ? "border-ink bg-ink" : "border-hairline-strong bg-canvas"
        }`}
      />
      <div className={reveal ? "reveal" : ""}>{children}</div>
    </section>
  );
}
