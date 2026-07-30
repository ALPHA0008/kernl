/** The canonical public origin of the marketing site.
 *
 *  This is the SINGLE source of truth. It used to be declared independently in
 *  layout.tsx, sitemap.ts, page.tsx and robots -- which is exactly how they
 *  drifted apart: production shipped canonical/OG/JSON-LD/sitemap all pointing
 *  at a domain that no longer resolves, because the fix landed in some of those
 *  files and not others. Import from here; never re-declare it.
 *
 *  Set NEXT_PUBLIC_SITE_URL in the hosting environment to override (e.g. for a
 *  staging origin). The fallback is the real production origin, so a missing
 *  env var degrades to "correct" rather than "silently wrong".
 */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://kernlbase.com";
