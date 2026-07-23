import type { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://kernl.dev";

/** Marketing pages are indexable; the authenticated console is not (product UI,
 *  no SEO value, avoids thin-content dilution). */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/evaluate",
        "/ledger",
        "/escalations",
        "/policies",
        "/replays",
        "/sources",
        "/settings",
        "/onboarding",
        "/decisions",
      ],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
