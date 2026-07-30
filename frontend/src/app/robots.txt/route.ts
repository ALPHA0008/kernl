import { SITE_URL } from "@/lib/site";

/** Served at /robots.txt.
 *
 *  This is a Route Handler rather than the `robots.ts` metadata convention for
 *  two reasons: MetadataRoute.Robots has no way to express the `Content-Signal`
 *  directive, and a hand-written static robots.txt would re-introduce the exact
 *  failure this fixes -- a hardcoded origin drifting out of sync with the one
 *  canonical/sitemap/JSON-LD use. Deriving it from SITE_URL makes drift
 *  impossible by construction.
 */

/** The authenticated console. Product UI with no SEO value; keeping it out of
 *  the index also avoids thin-content dilution of the marketing page. */
const CONSOLE_ROUTES = [
  "/evaluate",
  "/ledger",
  "/escalations",
  "/policies",
  "/replays",
  "/sources",
  "/settings",
  "/onboarding",
  "/decisions",
] as const;

/** Content Signals (contentsignals.org): search indexing and real-time AI
 *  answering are welcome; harvesting the corpus for model training is not.
 *  `/login` is intentionally NOT disallowed -- it must stay crawlable for its
 *  canonical-to-"/" signal to be read. */
const BODY = [
  "User-Agent: *",
  "Content-Signal: ai-train=no, search=yes, ai-input=yes",
  "Allow: /",
  ...CONSOLE_ROUTES.map((route) => `Disallow: ${route}`),
  "",
  `Sitemap: ${SITE_URL}/sitemap.xml`,
  "",
].join("\n");

export const dynamic = "force-static";

export function GET(): Response {
  return new Response(BODY, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
