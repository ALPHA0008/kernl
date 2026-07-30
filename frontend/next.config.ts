import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Hide the Next.js dev-tools overlay button (the floating "N" indicator
  // that appeared bottom-left over the sidebar footer in development).
  devIndicators: false,

  // Turbopack infers the project root by walking up for a lockfile, but on
  // this Windows/Git-Bash setup it was misresolving to the repo root
  // (E:\Kernl) instead of this directory -- causing `next dev` to fail
  // resolving 'tailwindcss', retry, and spawn hundreds of orphaned worker
  // processes until the machine ran out of memory. Pinning the root
  // explicitly (the documented fix for ambiguous root inference) removes
  // the ambiguity entirely.
  turbopack: {
    root: path.join(__dirname),
  },

  // Security headers. Vercel already sets HSTS, so it is not repeated here.
  //
  // The CSP deliberately omits `default-src`, `script-src` and `connect-src`:
  // the console talks to the Kernl API cross-origin and Next.js injects inline
  // hydration scripts, so a restrictive policy on those directives would need a
  // nonce pipeline and real cross-browser testing before it could ship safely.
  // The three directives set below are the ones that harden the app without any
  // risk of breaking it -- unset directives simply stay unrestricted.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
          {
            key: "Content-Security-Policy",
            value: "base-uri 'self'; object-src 'none'; frame-ancestors 'none'",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
