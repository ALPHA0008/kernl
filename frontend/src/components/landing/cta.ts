/** Conversation-first CTAs (per the GTM playbooks: optimize for design-partner
 *  conversations, never a waitlist). mailto with prefilled subjects that double
 *  as channel tags.
 *
 *  This address must stay a real, monitored inbox: it is the only conversion
 *  path on the site, so a dead mailbox here means every inbound lead is lost
 *  silently. It previously pointed at hello@kernl.dev, a domain with no mailbox
 *  behind it. Now routed via Cloudflare Email Routing on kernlbase.com. */
export const CONTACT_EMAIL = "support@kernlbase.com";

export const CTA_PARTNER = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(
  "Design partner program",
)}&body=${encodeURIComponent(
  "Hi Kernl team,\n\nWe're deploying / evaluating AI support agents and want to talk about the design partner program.\n\nCompany:\nRole:\nHelp desk (Zendesk / Intercom / other):\nAgent vendor (Decagon / Fin / Sierra / other / none yet):\n",
)}`;

export const CTA_DEMO = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("Request a demo")}`;
