"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import DashboardLayout from "@/components/DashboardLayout";
import StatCard from "@/components/ui/StatCard";
import GlassCard from "@/components/ui/GlassCard";

type CompanyInfo = {
  id: string;
  name?: string;
  industry?: string;
  company_size?: string;
  skill_count?: number;
  source_count?: number;
  last_compile?: { completed_at: string; result_version: string } | null;
};

export default function Dashboard() {
  const [companyId, setCompanyId] = useState("");
  const [loading, setLoading] = useState(false);
  const [company, setCompany] = useState<CompanyInfo | null>(null);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState("");
  const [autoLoaded, setAutoLoaded] = useState(false);
  const router = useRouter();
  const { user } = useAuth();

  const fetchCompany = useCallback(async (id: string) => {
    if (!id) return;
    setFetching(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/companies/${id}`);
      if (!res.ok) throw new Error("Not found");
      const data = await res.json();
      setCompany(data);
      // Persist the company ID so it auto-loads next time
      sessionStorage.setItem("kernl_company_id", id);
    } catch {
      setCompany(null);
      setError("Company not found. Create it first via Onboarding.");
    } finally {
      setFetching(false);
    }
  }, []);

  // Auto-load saved company when user is signed in
  useEffect(() => {
    if (autoLoaded) return;
    const savedCompanyId = sessionStorage.getItem("kernl_company_id");
    if (savedCompanyId) {
      setCompanyId(savedCompanyId);
      fetchCompany(savedCompanyId);
      setAutoLoaded(true);
    }
  }, [autoLoaded, fetchCompany]);

  const handleCompile = async () => {
    if (!companyId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/compile`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_id: companyId }),
      });
      const data = await res.json();
      if (data.job_id) router.push(`/compile/${data.job_id}`);
    } catch {
      alert("Failed to start compilation");
    } finally {
      setLoading(false);
    }
  };

  // Determine if we should show the lookup section
  // Hide it when we have a loaded company (auto or manual)
  const showLookup = !company;

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-6xl mx-auto animate-fade-in">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
          <div>
            <h1
              className="text-2xl font-bold tracking-tight"
              style={{ color: "var(--text-primary)" }}
            >
              {company ? company.name || companyId : "Command Center"}
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              {company
                ? "Operational brain dashboard"
                : "Compile operational knowledge into an executable AI brain"}
            </p>
          </div>
          <div className="flex gap-3">
            {company && (
              <button
                onClick={() => {
                  setCompany(null);
                  setCompanyId("");
                  setError("");
                  sessionStorage.removeItem("kernl_company_id");
                }}
                className="btn-ghost"
                style={{ fontSize: "13px", padding: "8px 14px" }}
              >
                Switch Company
              </button>
            )}
            <button
              onClick={() => router.push("/onboarding")}
              className="btn-secondary"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M7 1v12M1 7h12" strokeLinecap="round" />
              </svg>
              New Company
            </button>
          </div>
        </div>

        {/* Company Lookup — only visible when no company is loaded */}
        {showLookup && (
          <GlassCard className="mb-8">
            <label className="input-label">Company ID</label>
            <div className="flex gap-3">
              <input
                type="text"
                className="input-field input-field--mono flex-1"
                placeholder="e.g. rivanly-inc"
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
                onKeyDown={(e) =>
                  e.key === "Enter" && companyId && fetchCompany(companyId)
                }
              />
              <button
                onClick={() => fetchCompany(companyId)}
                disabled={!companyId || fetching}
                className="btn-primary"
              >
                {fetching ? (
                  <span className="animate-spin-slow inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full" />
                ) : (
                  "Load"
                )}
              </button>
            </div>

            {error && (
              <p className="text-xs mt-2" style={{ color: "var(--error)" }}>
                {error}
              </p>
            )}

            {!company && !error && (
              <p className="text-xs mt-3" style={{ color: "var(--text-muted)" }}>
                Try:{" "}
                <button
                  onClick={() => {
                    setCompanyId("rivanly-inc");
                    fetchCompany("rivanly-inc");
                  }}
                  className="font-mono transition-colors"
                  style={{ color: "var(--primary)" }}
                >
                  rivanly-inc
                </button>{" "}
                (pre-loaded demo company)
              </p>
            )}
          </GlassCard>
        )}

        {/* Company Dashboard */}
        {company && (
          <div className="stagger-children">
            {/* Stat Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <StatCard
                label="Skills"
                value={company.skill_count ?? 0}
                accent="primary"
                icon={
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M2 4h12M2 8h8M2 12h10" strokeLinecap="round" />
                  </svg>
                }
              />
              <StatCard
                label="Sources"
                value={company.source_count ?? 0}
                accent="info"
                icon={
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="3" y="2" width="10" height="12" rx="1.5" />
                    <path d="M6 5h4M6 8h4M6 11h2" strokeLinecap="round" />
                  </svg>
                }
              />
              <StatCard
                label="Company Size"
                value={company.company_size || "—"}
                accent="warning"
                icon={
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <circle cx="8" cy="5" r="3" />
                    <path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6" strokeLinecap="round" />
                  </svg>
                }
              />
              <StatCard
                label="Industry"
                value={company.industry || "—"}
                accent="success"
                icon={
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <rect x="2" y="6" width="4" height="8" rx="0.5" />
                    <rect x="6" y="3" width="4" height="11" rx="0.5" />
                    <rect x="10" y="1" width="4" height="13" rx="0.5" />
                  </svg>
                }
              />
            </div>

            {/* Quick Actions */}
            <GlassCard className="mb-6" elevated>
              <p
                className="text-[10px] font-semibold uppercase tracking-[0.08em] font-mono mb-4"
                style={{ color: "var(--text-muted)" }}
              >
                Quick Actions
              </p>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <button onClick={handleCompile} disabled={loading} className="btn-primary w-full">
                  {loading ? "Starting..." : "Compile Brain"}
                </button>
                <button
                  onClick={() => router.push(`/skills/${companyId}`)}
                  className="btn-secondary w-full"
                >
                  View Skills
                </button>
                <button
                  onClick={() => router.push(`/demo/${companyId}`)}
                  className="btn-secondary w-full"
                >
                  Query Agent
                </button>
                <button
                  onClick={() => {
                    const a = document.createElement("a");
                    a.href = `${API_BASE}/skills/${companyId}/download`;
                    a.click();
                  }}
                  className="btn-ghost w-full"
                >
                  Download JSON
                </button>
              </div>
            </GlassCard>

            {/* Last Compilation */}
            {company.last_compile && (
              <GlassCard>
                <div className="flex items-center gap-3">
                  <span
                    className="w-8 h-8 rounded-lg flex items-center justify-center"
                    style={{
                      background: "var(--success-bg)",
                      color: "var(--success)",
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M3 8l4 4 6-8" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                  <div>
                    <p
                      className="text-[10px] font-semibold uppercase tracking-[0.08em] font-mono"
                      style={{ color: "var(--text-muted)" }}
                    >
                      Last Compilation
                    </p>
                    <p className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                      {new Date(company.last_compile.completed_at).toLocaleString()}
                      {company.last_compile.result_version && (
                        <span
                          className="ml-2 font-mono text-xs"
                          style={{ color: "var(--text-muted)" }}
                        >
                          {company.last_compile.result_version}
                        </span>
                      )}
                    </p>
                  </div>
                </div>
              </GlassCard>
            )}
          </div>
        )}

        {/* Empty State — only when no company ID has been entered and nothing loaded */}
        {!company && !error && !companyId && (
          <div className="empty-state animate-fade-up">
            <div className="empty-state__icon">
              <svg width="28" height="28" viewBox="0 0 28 28" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="14" cy="14" r="10" />
                <path d="M14 9v5l3 3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h2 className="text-xl font-bold mb-2" style={{ color: "var(--text-primary)" }}>
              Your company&apos;s operational brain
            </h2>
            <p
              className="text-sm mb-8 max-w-md mx-auto leading-relaxed"
              style={{ color: "var(--text-secondary)" }}
            >
              Upload SOPs, Slack exports, and support tickets. Kernl compiles them into structured,
              queryable skills that make your AI agent actually understand your business.
            </p>
            <button
              onClick={() => router.push("/onboarding")}
              className="btn-primary"
            >
              Get Started
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M1 7h12M8 2l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
