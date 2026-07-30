import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/components/ui/Toast";
import { SITE_URL } from "@/lib/site";

const DESCRIPTION =
  "Kernl turns operating policy into deterministic, versioned code. Every decision a human or AI agent makes: authorized, signed, replay-tested, on the record.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Kernl · The decision ledger for enterprise AI",
    template: "%s · Kernl",
  },
  description: DESCRIPTION,
  applicationName: "Kernl",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: "Kernl",
    title: "Every decision, on the record.",
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: "Every decision, on the record.",
    description: DESCRIPTION,
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
