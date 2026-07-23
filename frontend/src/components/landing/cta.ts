/** Conversation-first CTAs (per the GTM playbooks: optimize for design-partner
 *  conversations, never a waitlist). mailto with prefilled subjects that double
 *  as channel tags. NOTE for handoff: point CONTACT_EMAIL at a real monitored
 *  inbox before launch. */
export const CONTACT_EMAIL = "hello@kernl.dev";

export const CTA_PARTNER = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
  "Design partner program",
)}&body=${encodeURIComponent(
  "Hi Kernl team,\n\nWe're deploying / evaluating AI support agents and want to talk about the design partner program.\n\nCompany:\nRole:\nHelp desk (Zendesk / Intercom / other):\nAgent vendor (Decagon / Fin / Sierra / other / none yet):\n",
)}`;

export const CTA_DEMO = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("Request a demo")}`;
