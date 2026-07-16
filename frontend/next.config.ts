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
};

export default nextConfig;
