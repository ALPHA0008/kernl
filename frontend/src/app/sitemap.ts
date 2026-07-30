import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/** /login is deliberately absent: it is a bare credential form with no unique
 *  content, and its canonical already points at "/". Listing it here would ask
 *  Google to index a URL that simultaneously declares itself non-canonical.
 *  It stays crawlable in robots.txt so the canonical signal is actually seen --
 *  Disallow-ing it instead would hide that signal and is the worse pattern. */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: `${SITE_URL}/`,
      lastModified: new Date(),
      changeFrequency: "weekly",
      priority: 1,
    },
  ];
}
