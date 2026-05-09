"use client";

import { useState, use } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import DashboardLayout from "@/components/DashboardLayout";
import GlassCard from "@/components/ui/GlassCard";
import ConfidenceBadge from "@/components/ui/ConfidenceBadge";

type AgentResponse = {
  recommended_action?: string;
  rule_applied?: string;
  evidence?: string[];
  skill_matched?: string;
  confidence?: number;
  retrieval_scores?: number[];
  reasoning?: string;
  error?: string;
};

const PRESETS = [
  { label: "Enterprise Refund", scenario: "Enterprise customer, 18 months tenure, wants a $1,200 refund for unused seats", context: '{"plan": "enterprise", "tenure_months": 18, "refund_amount": 1200}' },
  { label: "Priority Escalation", scenario: "Customer has been waiting 3 days for a response on a billing issue and is threatening to churn", context: '{"issue_type": "billing", "wait_days": 3, "sentiment": "frustrated"}' },
  { label: "New Hire Onboarding", scenario: "New support agent just started, needs to know the standard process for handling refund requests", context: '{"agent_level": "junior", "department": "support"}' },
];

export default function QueryDemo({ params }: { params: Promise<{ companyId: string }> }) {
  const resolvedParams = use(params);
  const companyId = resolvedParams.companyId;
  const [scenario, setScenario] = useState("");
  const [contextJson, setContextJson] = useState("");
  const [loading, setLoading] = useState(false);
  const [withBrain, setWithBrain] = useState<AgentResponse | null>(null);
  const [withoutBrain, setWithoutBrain] = useState<AgentResponse | null>(null);
  const router = useRouter();

  const applyPreset = (p: (typeof PRESETS)[0]) => { setScenario(p.scenario); setContextJson(p.context); setWithBrain(null); setWithoutBrain(null); };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scenario) return;
    setLoading(true); setWithBrain(null); setWithoutBrain(null);
    let ctx = {};
    try { if (contextJson.trim()) ctx = JSON.parse(contextJson); } catch { alert("Invalid JSON"); setLoading(false); return; }
    try {
      const [r1, r2] = await Promise.all([
        fetch(`${API_BASE}/agent/handle`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ company_id: companyId, scenario, context: ctx, with_brain: true }) }),
        fetch(`${API_BASE}/agent/handle`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ company_id: companyId, scenario, context: ctx, with_brain: false }) }),
      ]);
      setWithBrain(await r1.json()); setWithoutBrain(await r2.json());
    } catch { alert("Query failed — is the backend running?"); } finally { setLoading(false); }
  };

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-6xl mx-auto animate-fade-in">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>Brain Query Demo</h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>Compare AI responses with and without your compiled brain</p>
          </div>
          <button onClick={() => router.push(`/skills/${companyId}`)} className="btn-secondary">View Skills</button>
        </div>

        <div className="mb-6">
          <p className="input-label mb-2">Quick Presets</p>
          <div className="flex gap-2 flex-wrap">
            {PRESETS.map((p) => (<button key={p.label} onClick={() => applyPreset(p)} className="badge" style={{ background: "var(--primary-ghost)", color: "var(--primary)", border: "1px solid rgba(0,210,180,0.2)", cursor: "pointer" }}>{p.label}</button>))}
          </div>
        </div>

        <GlassCard className="mb-8">
          <form onSubmit={handleQuery} className="space-y-4">
            <div><label className="input-label">Scenario</label><textarea className="input-field" style={{ minHeight: "100px" }} placeholder="Describe the scenario..." value={scenario} onChange={(e) => setScenario(e.target.value)} /></div>
            <div><label className="input-label">Context (JSON)</label><textarea className="input-field input-field--mono" style={{ minHeight: "80px" }} placeholder='{"plan": "enterprise"}' value={contextJson} onChange={(e) => setContextJson(e.target.value)} /></div>
            <div className="flex justify-end"><button type="submit" disabled={loading || !scenario} className="btn-primary">{loading ? "Processing..." : "Compare Models"}</button></div>
          </form>
        </GlassCard>

        {(withBrain || withoutBrain) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 stagger-children">
            <GlassCard className="opacity-70">
              <div className="flex items-center gap-2 mb-5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--text-muted)" }} />
                <h2 className="text-lg font-bold" style={{ color: "var(--text-secondary)" }}>Without Brain</h2>
                <span className="badge badge--neutral ml-auto">Generic AI</span>
              </div>
              {withoutBrain ? (<div className="space-y-4">
                <div><p className="input-label">Response</p><div className="p-4 rounded text-sm" style={{ background: "var(--bg-input)", color: "var(--text-secondary)", border: "1px solid var(--border)" }}>{withoutBrain.recommended_action || "No action"}</div></div>
                <div><p className="input-label">Rule</p><p className="text-sm" style={{ color: "var(--text-muted)" }}>{withoutBrain.rule_applied || "General knowledge"}</p></div>
                {withoutBrain.reasoning && <div><p className="input-label">Reasoning</p><p className="text-sm" style={{ color: "var(--text-muted)" }}>{withoutBrain.reasoning}</p></div>}
              </div>) : <div className="animate-shimmer h-32 rounded" />}
            </GlassCard>

            <div className="glass-card p-5 relative" style={{ borderColor: "rgba(0,210,180,0.3)", boxShadow: "0 0 32px -8px rgba(0,210,180,0.08)" }}>
              <span className="absolute -top-3 right-4 text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full" style={{ background: "var(--primary)", color: "var(--text-inverse)" }}>Company Brain</span>
              <div className="flex items-center gap-2 mb-5"><span className="w-2.5 h-2.5 rounded-full animate-pulse" style={{ background: "var(--primary)" }} /><h2 className="text-lg font-bold" style={{ color: "var(--primary)" }}>With Brain</h2></div>
              {withBrain ? (<div className="space-y-4">
                {withBrain.error ? <p style={{ color: "var(--error)" }}>{withBrain.error}</p> : (<>
                  <div><p className="input-label">Recommended Action</p><div className="p-4 rounded text-base font-medium" style={{ background: "var(--primary-ghost)", color: "var(--text-primary)", border: "1px solid rgba(0,210,180,0.15)" }}>{withBrain.recommended_action}</div></div>
                  <div className="grid grid-cols-2 gap-4">
                    <div><p className="input-label">Skill Matched</p><p className="font-mono text-sm" style={{ color: "var(--text-primary)" }}>{withBrain.skill_matched || "N/A"}</p></div>
                    <div><p className="input-label">Confidence</p><div className="flex items-center gap-2 mt-1"><div className="progress-bar flex-1"><div className="progress-bar__fill" style={{ width: `${(withBrain.confidence || 0) * 100}%`, background: "var(--primary)" }} /></div><ConfidenceBadge value={withBrain.confidence || 0} /></div></div>
                  </div>
                  {withBrain.retrieval_scores && withBrain.retrieval_scores.length > 0 && <div><p className="input-label">Retrieval Scores</p><div className="flex gap-2 flex-wrap">{withBrain.retrieval_scores.map((s, i) => <span key={i} className="badge badge--neutral font-mono">#{i+1}: {(s*100).toFixed(1)}%</span>)}</div></div>}
                  <div><p className="input-label">Rule Applied</p><p className="text-sm font-medium pl-3 py-1" style={{ color: "var(--text-primary)", borderLeft: "2px solid var(--primary)" }}>{withBrain.rule_applied}</p></div>
                  {withBrain.reasoning && <div><p className="input-label">Reasoning</p><div className="text-sm p-3 rounded" style={{ color: "var(--text-secondary)", background: "var(--bg-input)", border: "1px solid var(--border)" }}>{withBrain.reasoning}</div></div>}
                  {withBrain.evidence && withBrain.evidence.length > 0 && <div><p className="input-label">Evidence Trail</p><div className="space-y-2">{withBrain.evidence.map((src, i) => <div key={i} className="text-sm p-3 rounded" style={{ color: "var(--text-secondary)", background: "var(--bg-input)", border: "1px solid var(--border)" }}>{src}</div>)}</div></div>}
                </>)}
              </div>) : <div className="animate-shimmer h-32 rounded" />}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
