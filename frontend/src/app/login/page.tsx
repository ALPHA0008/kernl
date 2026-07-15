"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { FieldLabel, Input } from "@/components/ui/Input";
import { Logo } from "@/components/ui/Logo";
import { API_URL, provisionTenant } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Organization ids must be lowercase alphanumerics + hyphens (backend pattern
 *  ^[a-z0-9][a-z0-9-]*$). Slugify as the user types so an invalid id — spaces,
 *  capitals, punctuation — simply cannot be entered. */
function slugify(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+/, "");
}

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "provision">("login");
  const [key, setKey] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const [adminKey, setAdminKey] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [issuedKey, setIssuedKey] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!key.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await login(key.trim());
      router.replace("/evaluate");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function provision(e: React.FormEvent) {
    e.preventDefault();
    if (!adminKey.trim() || !companyId.trim() || !companyName.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await provisionTenant(adminKey.trim(), companyId.trim(), companyName.trim());
      setIssuedKey(res.owner_api_key);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function enterWithIssuedKey() {
    if (!issuedKey) return;
    setBusy(true);
    try {
      await login(issuedKey);
      router.replace("/onboarding");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      {/* atmospheric mesh gradient — hero-scale only, per DESIGN.md */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[520px] w-[820px] -translate-x-1/2 opacity-[0.16] blur-3xl"
        style={{
          background:
            "conic-gradient(from 180deg at 50% 50%, #007cf0, #00dfd8, #7928ca, #ff0080, #ff4d4d, #f9cb28, #007cf0)",
        }}
      />

      <div className="relative w-full max-w-[400px] page-enter">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-ink text-on-primary shadow-[var(--shadow-3)]">
            <Logo size={24} />
          </div>
          <h1 className="t-display-md text-ink">kernl</h1>
          <p className="t-eyebrow mt-1">Decision Ledger Console</p>
        </div>

        <div className="rounded-lg bg-canvas shadow-[var(--shadow-4)]">
          <div className="flex border-b border-hairline px-2">
            {(["login", "provision"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                  setError(null);
                  setIssuedKey(null);
                }}
                className={`relative px-3 py-3 text-sm font-medium transition-colors ${
                  mode === m ? "text-ink" : "text-mute hover:text-body"
                }`}
              >
                {m === "login" ? "Sign in" : "New organization"}
                {mode === m ? (
                  <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-ink" />
                ) : null}
              </button>
            ))}
          </div>

          <div className="p-6">
            {mode === "login" ? (
              <form onSubmit={submit}>
                <FieldLabel htmlFor="api-key">API key</FieldLabel>
                <Input
                  id="api-key"
                  type="password"
                  autoComplete="off"
                  mono
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="tenant API key"
                />
                <Button type="submit" loading={busy} disabled={!key.trim()} className="mt-4 w-full">
                  Enter console
                </Button>
                {error ? (
                  <div className="mt-4">
                    <ErrorNotice error={error} />
                  </div>
                ) : null}
              </form>
            ) : issuedKey ? (
              <div>
                <p className="t-body-sm font-medium text-approve">Organization created.</p>
                <p className="mt-2 text-sm text-body">
                  This is your owner API key. It is shown once — store it now.
                </p>
                <code className="mt-3 block break-all rounded-md border border-hairline bg-canvas-soft px-3 py-2.5 font-mono text-xs text-ink">
                  {issuedKey}
                </code>
                <Button
                  onClick={() => void enterWithIssuedKey()}
                  loading={busy}
                  className="mt-4 w-full"
                >
                  Save it — enter onboarding
                </Button>
              </div>
            ) : (
              <form onSubmit={provision} className="space-y-4">
                <div>
                  <FieldLabel htmlFor="admin-key">Admin key</FieldLabel>
                  <Input
                    id="admin-key"
                    type="password"
                    autoComplete="off"
                    mono
                    value={adminKey}
                    onChange={(e) => setAdminKey(e.target.value)}
                    placeholder="provisioning admin key"
                  />
                </div>
                <div>
                  <FieldLabel htmlFor="company-id">Organization id</FieldLabel>
                  <Input
                    id="company-id"
                    mono
                    value={companyId}
                    onChange={(e) => setCompanyId(slugify(e.target.value))}
                    placeholder="acme-corp"
                  />
                  <p className="mt-1.5 text-xs text-mute">
                    Lowercase letters, numbers, hyphens. Spaces become hyphens.
                  </p>
                </div>
                <div>
                  <FieldLabel htmlFor="company-name">Organization name</FieldLabel>
                  <Input
                    id="company-name"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="Acme Corp"
                  />
                </div>
                <Button
                  type="submit"
                  loading={busy}
                  disabled={!adminKey.trim() || !companyId.trim() || !companyName.trim()}
                  className="w-full"
                >
                  Create organization
                </Button>
                {error ? <ErrorNotice error={error} /> : null}
              </form>
            )}
          </div>
        </div>

        <p className="mt-5 text-center font-mono text-xs text-mute">{API_URL}</p>
      </div>
    </div>
  );
}
