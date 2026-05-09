"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import DashboardLayout from "@/components/DashboardLayout";
import GlassCard from "@/components/ui/GlassCard";

type AnalysisResult = { suggested_industry: string; suggested_departments: string[]; suggested_size: string; rationale: string };

const STEP_LABELS = ["Company", "Upload", "Configure", "Compile"];

export default function OnboardingWizard() {
  const [step, setStep] = useState(1);
  const [companyName, setCompanyName] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [compiling, setCompiling] = useState(false);
  const [error, setError] = useState("");
  const [skippedUpload, setSkippedUpload] = useState(false);
  const [showSkipOptions, setShowSkipOptions] = useState(false);
  const [loadingSamples, setLoadingSamples] = useState(false);
  const [sourceCount, setSourceCount] = useState(0);
  const [manualIndustry, setManualIndustry] = useState("");
  const [manualSize, setManualSize] = useState("");
  const [manualDescription, setManualDescription] = useState("");
  const router = useRouter();

  const generateId = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  const handleBack = () => { setError(""); if (step > 1) { setStep(step - 1); if (step === 3) setShowSkipOptions(false); } else router.push("/"); };

  const handleNameSubmit = async () => {
    if (!companyName.trim()) return;
    const id = generateId(companyName);
    setCompanyId(id); setError("");
    try { await fetch(`${API_BASE}/companies/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: companyName }) }); } catch { /* ok */ }
    // Persist so dashboard auto-loads this company
    sessionStorage.setItem("kernl_company_id", id);
    setStep(2);
  };

  const handleUpload = async () => {
    if (!files || files.length === 0) return;
    setUploading(true); setError("");
    try {
      for (const file of Array.from(files)) { const form = new FormData(); form.append("company_id", companyId); form.append("file", file); const res = await fetch(`${API_BASE}/sources/upload`, { method: "POST", body: form }); if (!res.ok) throw new Error(`Failed: ${file.name}`); }
      setSourceCount(files.length); setSkippedUpload(false); setStep(3);
    } catch (err: unknown) { setError(err instanceof Error ? err.message : "Upload failed"); } finally { setUploading(false); }
  };

  const handleLoadSamples = async () => {
    setLoadingSamples(true); setError("");
    try { const res = await fetch(`${API_BASE}/companies/${companyId}/load-samples`, { method: "POST" }); if (!res.ok) throw new Error("Failed to load sample data"); const data = await res.json(); setSourceCount(data.count || 0); setSkippedUpload(false); setShowSkipOptions(false); setStep(3); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : "Failed to load samples"); } finally { setLoadingSamples(false); }
  };

  const handleSkipToManual = () => { setSkippedUpload(true); setShowSkipOptions(false); setSourceCount(0); setStep(3); };

  const handleAnalyze = async () => {
    setAnalyzing(true); setError("");
    try { const res = await fetch(`${API_BASE}/onboarding/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ company_id: companyId }) }); if (!res.ok) throw new Error("Analysis failed"); setAnalysis(await res.json()); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : "Analysis failed"); } finally { setAnalyzing(false); }
  };

  const handleSaveProfile = async () => {
    setError(""); const payload: Record<string, string> = {};
    if (analysis) { if (analysis.suggested_industry) payload.industry = analysis.suggested_industry; if (analysis.suggested_size) payload.company_size = analysis.suggested_size; if (analysis.rationale) payload.description = analysis.rationale; }
    else { if (manualIndustry) payload.industry = manualIndustry; if (manualSize) payload.company_size = manualSize; if (manualDescription) payload.description = manualDescription; }
    if (Object.keys(payload).length > 0) { try { await fetch(`${API_BASE}/companies/${companyId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); } catch (err) { console.warn("Failed to save:", err); } }
    setStep(4);
  };

  const handleCompile = async () => {
    setCompiling(true); setError("");
    try { const res = await fetch(`${API_BASE}/compile`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ company_id: companyId }) }); const data = await res.json(); if (data.job_id) router.push(`/compile/${data.job_id}`); }
    catch { setError("Failed to start compilation"); setCompiling(false); }
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-2xl mx-auto animate-fade-in">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button onClick={handleBack} className="btn-ghost" style={{ padding: "6px 12px" }}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 2L4 7l5 5" strokeLinecap="round" strokeLinejoin="round" /></svg>
            {step > 1 ? "Back" : "Home"}
          </button>
          <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>Onboarding</h1>
        </div>

        {/* Progress Steps */}
        <div className="flex mb-8 gap-1">
          {STEP_LABELS.map((label, i) => (
            <div key={label} className="flex-1">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{
                  background: step > i + 1 || step === i + 1 ? "var(--primary)" : "rgba(255,255,255,0.05)",
                  color: step > i + 1 || step === i + 1 ? "var(--text-inverse)" : "var(--text-muted)",
                }}>{step > i + 1 ? "✓" : i + 1}</span>
                <span className="text-xs font-medium" style={{ color: step === i + 1 ? "var(--primary)" : "var(--text-muted)" }}>{label}</span>
              </div>
              <div className="h-0.5 rounded-full" style={{ background: step > i + 1 ? "var(--primary)" : step === i + 1 ? "var(--primary-dim)" : "var(--border)" }} />
            </div>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center justify-between mb-6 p-3 rounded text-sm" style={{ background: "var(--error-bg)", color: "var(--error)", border: "1px solid rgba(248,113,113,0.2)" }}>
            <span>{error}</span>
            <button onClick={() => setError("")} style={{ color: "var(--error)" }}>✕</button>
          </div>
        )}

        {/* Step 1 */}
        {step === 1 && (
          <GlassCard elevated padding="lg">
            <h2 className="text-lg font-bold mb-4" style={{ color: "var(--text-primary)" }}>Name your company</h2>
            <input type="text" className="input-field mb-3" placeholder="e.g. Rivanly Inc." value={companyName} onChange={(e) => setCompanyName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && companyName && handleNameSubmit()} />
            {companyName && <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>ID: <span className="font-mono" style={{ color: "var(--primary)" }}>{generateId(companyName)}</span></p>}
            <button onClick={handleNameSubmit} disabled={!companyName.trim()} className="btn-primary">Next →</button>
          </GlassCard>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <GlassCard elevated padding="lg">
            <h2 className="text-lg font-bold mb-2" style={{ color: "var(--text-primary)" }}>Upload source documents</h2>
            <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>SOPs, Slack exports, Zendesk tickets — anything with operational knowledge.</p>
            <input type="file" multiple onChange={(e) => setFiles(e.target.files)} className="w-full text-sm mb-4 file:mr-4 file:py-2 file:px-4 file:border-0 file:rounded file:font-medium" style={{ color: "var(--text-secondary)" }} />
            <div className="flex gap-3 mb-4">
              <button onClick={handleUpload} disabled={!files || uploading} className="btn-primary">{uploading ? "Uploading..." : "Upload & Continue"}</button>
              <button onClick={() => setShowSkipOptions(true)} className="btn-secondary">Skip</button>
            </div>
            {showSkipOptions && (
              <div className="space-y-3 p-4 rounded" style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>No files? Choose how to proceed:</p>
                <button onClick={handleLoadSamples} disabled={loadingSamples} className="w-full text-left p-3 rounded transition-colors" style={{ background: "var(--primary-ghost)", border: "1px solid rgba(0,210,180,0.2)", color: "var(--primary)" }}>
                  <span className="font-semibold">{loadingSamples ? "Loading..." : "Load Sample Playbooks"}</span>
                  <span className="block text-xs mt-1" style={{ color: "var(--text-muted)" }}>Pre-configured demo data</span>
                </button>
                <button onClick={handleSkipToManual} className="w-full text-left p-3 rounded transition-colors" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                  <span className="font-semibold">Configure Manually</span>
                  <span className="block text-xs mt-1" style={{ color: "var(--text-muted)" }}>Set up by hand</span>
                </button>
                <button onClick={() => setShowSkipOptions(false)} className="text-sm" style={{ color: "var(--text-muted)" }}>Cancel</button>
              </div>
            )}
          </GlassCard>
        )}

        {/* Step 3 */}
        {step === 3 && (
          <div className="space-y-6">
            {!skippedUpload && (
              <GlassCard elevated padding="lg">
                <h2 className="text-lg font-bold mb-2" style={{ color: "var(--text-primary)" }}>AI Analysis</h2>
                <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>Analyze your {sourceCount} document{sourceCount !== 1 ? "s" : ""} to suggest profile settings.</p>
                {!analysis ? (
                  <div className="flex gap-3">
                    <button onClick={handleAnalyze} disabled={analyzing} className="btn-primary">{analyzing ? "Analyzing..." : "Analyze Documents"}</button>
                    <button onClick={handleSaveProfile} className="btn-secondary">Skip to Compile →</button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-3 gap-3">
                      {[{ label: "Industry", val: analysis.suggested_industry }, { label: "Size", val: analysis.suggested_size }, { label: "Depts", val: String(analysis.suggested_departments.length) }].map(({ label, val }) => (
                        <div key={label} className="p-3 rounded" style={{ background: "var(--bg-input)", border: "1px solid var(--border)" }}>
                          <p className="text-[10px] uppercase tracking-wider font-mono" style={{ color: "var(--text-muted)" }}>{label}</p>
                          <p className="font-bold" style={{ color: "var(--text-primary)" }}>{val}</p>
                        </div>
                      ))}
                    </div>
                    {analysis.suggested_departments.length > 0 && <div className="flex flex-wrap gap-2">{analysis.suggested_departments.map((d) => <span key={d} className="badge badge--primary">{d}</span>)}</div>}
                    {analysis.rationale && <p className="text-sm p-3 rounded" style={{ color: "var(--text-muted)", background: "var(--bg-input)", border: "1px solid var(--border)" }}>{analysis.rationale}</p>}
                    <button onClick={handleSaveProfile} className="btn-primary">Save & Continue</button>
                  </div>
                )}
              </GlassCard>
            )}
            {skippedUpload && (
              <GlassCard elevated padding="lg">
                <h2 className="text-lg font-bold mb-2" style={{ color: "var(--text-primary)" }}>Company Profile</h2>
                <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>Set up manually. You can update later.</p>
                <div className="space-y-4">
                  <div><label className="input-label">Industry</label><select value={manualIndustry} onChange={(e) => setManualIndustry(e.target.value)} className="input-field"><option value="">Select industry...</option>{["SaaS", "E-commerce", "FinTech", "HealthTech", "EdTech", "Consulting", "Manufacturing", "Other"].map(v => <option key={v} value={v}>{v}</option>)}</select></div>
                  <div><label className="input-label">Size</label><select value={manualSize} onChange={(e) => setManualSize(e.target.value)} className="input-field"><option value="">Select size...</option>{["1-10", "11-50", "51-200", "201+"].map(v => <option key={v} value={v}>{v} employees</option>)}</select></div>
                  <div><label className="input-label">Description</label><textarea value={manualDescription} onChange={(e) => setManualDescription(e.target.value)} placeholder="Brief description..." className="input-field" style={{ minHeight: "80px" }} /></div>
                </div>
                <div className="flex gap-3 mt-6">
                  <button onClick={handleSaveProfile} className="btn-primary">Save & Continue →</button>
                  <button onClick={() => setStep(4)} className="btn-secondary">Skip to Compile</button>
                </div>
              </GlassCard>
            )}
          </div>
        )}

        {/* Step 4 */}
        {step === 4 && (
          <GlassCard elevated padding="lg" className="text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center" style={{ background: "var(--primary-ghost)", color: "var(--primary)" }}>
              <svg width="28" height="28" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="10" cy="10" r="7" /><path d="M10 6v4l3 2" strokeLinecap="round" /></svg>
            </div>
            <h2 className="text-lg font-bold mb-2" style={{ color: "var(--text-primary)" }}>Ready to compile</h2>
            <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
              Company <span className="font-mono" style={{ color: "var(--primary)" }}>{companyId}</span>
              {sourceCount > 0 && <> has <span className="font-bold" style={{ color: "var(--primary)" }}>{sourceCount}</span> source document{sourceCount !== 1 ? "s" : ""}</>}
              . Compile your brain now.
            </p>
            <div className="flex gap-3 justify-center">
              <button onClick={handleCompile} disabled={compiling} className="btn-primary">{compiling ? "Starting..." : "Compile Brain"}</button>
              <button onClick={() => router.push(`/skills/${companyId}`)} className="btn-secondary">View Skills</button>
            </div>
          </GlassCard>
        )}
      </div>
    </DashboardLayout>
  );
}
