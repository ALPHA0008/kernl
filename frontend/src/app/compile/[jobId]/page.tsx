"use client";

import { useEffect, useState, use, useRef } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import DashboardLayout from "@/components/DashboardLayout";
import GlassCard from "@/components/ui/GlassCard";

interface LogEvent { timestamp: string; type: string; data: Record<string, unknown>; }

const STAGES: Record<string, { label: string; icon: string }> = {
  pipeline_start: { label: "Pipeline Started", icon: "▶" },
  LOADING_DOCS: { label: "Loading Documents", icon: "◈" },
  LOADING_DOCS_DONE: { label: "Sources Loaded", icon: "✓" },
  CHUNKING: { label: "Chunking Documents", icon: "◈" },
  CHUNKING_DONE: { label: "Documents Chunked", icon: "✓" },
  EXTRACT_DECISIONS: { label: "Extracting Rules", icon: "◈" },
  EXTRACT_DECISIONS_DONE: { label: "Rules Extracted", icon: "✓" },
  EXTRACT_WORKFLOWS: { label: "Extracting Workflows", icon: "◈" },
  EXTRACT_WORKFLOWS_DONE: { label: "Workflows Extracted", icon: "✓" },
  EXTRACT_EXCEPTIONS: { label: "Extracting Exceptions", icon: "◈" },
  EXTRACT_EXCEPTIONS_DONE: { label: "Exceptions Extracted", icon: "✓" },
  DETECT_CONTRADICTIONS: { label: "Detecting Contradictions", icon: "◈" },
  DETECT_CONTRADICTIONS_DONE: { label: "Contradictions Analyzed", icon: "✓" },
  SYNTHESIZING_SKILLS: { label: "Synthesizing Skills", icon: "◈" },
  SYNTHESIZING_DONE: { label: "Skills Synthesized", icon: "✓" },
  LINKING_EVIDENCE: { label: "Linking Evidence", icon: "◈" },
  LINKING_DONE: { label: "Evidence Linked", icon: "✓" },
  SCORING_CONFIDENCE: { label: "Scoring Confidence", icon: "◈" },
  SCORING_DONE: { label: "Confidence Scored", icon: "✓" },
  WRITING_DB: { label: "Writing to Database", icon: "◈" },
  DONE: { label: "Pipeline Complete", icon: "✓" },
  pipeline_complete: { label: "Compilation Finished", icon: "✓" },
  pipeline_error: { label: "Pipeline Error", icon: "✕" },
};

export default function CompileViewer({ params }: { params: Promise<{ jobId: string }> }) {
  const resolvedParams = use(params);
  const jobId = resolvedParams.jobId;
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [status, setStatus] = useState("Connecting...");
  const [companyId, setCompanyId] = useState<string | null>(null);
  const [pipelineDone, setPipelineDone] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!jobId) return;
    const es = new EventSource(`${API_BASE}/compile/${jobId}/stream`);
    es.onmessage = (event) => {
      const parsed = JSON.parse(event.data);
      const et = parsed.event;
      const ed = parsed.data;
      setLogs((prev) => [...prev, { timestamp: new Date().toLocaleTimeString(), type: et, data: ed }]);
      if (et === "pipeline_start" && ed?.company_id) setCompanyId(ed.company_id as string);
      if (et === "stage") {
        const n = (ed.name as string) || "";
        const s = STAGES[n];
        const d = (ed.detail as string) || "";
        setCurrentStage(n);
        setStatus(`${s?.label || n}${d ? ` — ${d}` : ""}`);
      } else if (et === "pipeline_start") { setStatus("Pipeline Started"); }
      else if (et === "pipeline_complete") { setStatus("Compilation Finished"); setPipelineDone(true); es.close(); }
      else if (et === "pipeline_error") { setStatus(`Error: ${(ed.error as string) || "Unknown"}`); setPipelineError((ed.error as string) || "Unknown error"); es.close(); }
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [jobId]);

  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [logs]);

  const stageKeys = ["LOADING_DOCS", "CHUNKING", "EXTRACT_DECISIONS", "EXTRACT_WORKFLOWS", "EXTRACT_EXCEPTIONS", "DETECT_CONTRADICTIONS", "SYNTHESIZING_SKILLS", "LINKING_EVIDENCE", "SCORING_CONFIDENCE", "WRITING_DB"];
  const completedStages = new Set(logs.filter(l => l.type === "stage").map(l => l.data?.name as string));
  const currentIdx = currentStage ? stageKeys.findIndex(k => k === currentStage || k + "_DONE" === currentStage) : -1;
  const progress = pipelineDone ? 100 : pipelineError ? 0 : Math.max(0, Math.round(((currentIdx + 1) / stageKeys.length) * 100));

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-6xl mx-auto animate-fade-in">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>Compile Pipeline</h1>
            <p className="text-sm mt-1 font-mono" style={{ color: "var(--text-muted)" }}>Job: {jobId}</p>
          </div>
          <span className={`badge ${pipelineDone ? "badge--success" : pipelineError ? "badge--error" : "badge--primary"}`}>
            {pipelineDone ? "✓ Complete" : pipelineError ? "✕ Failed" : "● Running"}
          </span>
        </div>

        {/* Progress Bar */}
        <div className="mb-6">
          <div className="flex justify-between items-center mb-2">
            <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>{status}</span>
            <span className="text-xs font-mono font-bold" style={{ color: "var(--primary)" }}>{progress}%</span>
          </div>
          <div className="progress-bar"><div className="progress-bar__fill" style={{ width: `${progress}%`, background: pipelineError ? "var(--error)" : "var(--primary)" }} /></div>
        </div>

        {/* Success Card */}
        {pipelineDone && (
          <GlassCard className="mb-6" style={{ borderColor: "rgba(52,211,153,0.3)" } as React.CSSProperties}>
            <div className="flex items-center gap-3 mb-4">
              <span className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: "var(--success-bg)", color: "var(--success)" }}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 10l4 4 8-8" strokeLinecap="round" strokeLinejoin="round" /></svg>
              </span>
              <div>
                <h2 className="text-lg font-bold" style={{ color: "var(--success)" }}>Brain Compiled Successfully!</h2>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>Your operational brain is ready.{companyId && <> Company: <span className="font-mono" style={{ color: "var(--primary)" }}>{companyId}</span></>}</p>
              </div>
            </div>
            <div className="flex gap-3 flex-wrap">
              {companyId && (<><button onClick={() => router.push(`/demo/${companyId}`)} className="btn-primary">Query Demo</button><button onClick={() => router.push(`/skills/${companyId}`)} className="btn-secondary">View Skills</button></>)}
              <button onClick={() => router.push("/")} className="btn-ghost">Dashboard</button>
            </div>
          </GlassCard>
        )}

        {/* Error Card */}
        {pipelineError && (
          <GlassCard className="mb-6" style={{ borderColor: "rgba(248,113,113,0.3)" } as React.CSSProperties}>
            <div className="flex items-center gap-3 mb-4">
              <span className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: "var(--error-bg)", color: "var(--error)" }}>
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" /></svg>
              </span>
              <div>
                <h2 className="text-lg font-bold" style={{ color: "var(--error)" }}>Compilation Failed</h2>
                <p className="text-sm" style={{ color: "var(--text-muted)" }}>{pipelineError}</p>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => window.location.reload()} className="btn-secondary">Retry</button>
              <button onClick={() => router.push("/")} className="btn-ghost">Dashboard</button>
            </div>
          </GlassCard>
        )}

        {/* Pipeline Stages + Terminal */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Pipeline Stages */}
          <div className="lg:col-span-2">
            <GlassCard elevated padding="lg">
              <p className="input-label mb-4">Pipeline Stages</p>
              <div className="space-y-0">
                {stageKeys.map((key, i) => {
                  const s = STAGES[key];
                  const done = completedStages.has(key) || completedStages.has(key + "_DONE");
                  const active = currentStage === key;
                  const isPast = currentIdx > i || pipelineDone;
                  return (
                    <div key={key}>
                      <div className="flex items-center gap-3 py-2.5">
                        <span className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0" style={{
                          background: done || isPast ? "var(--primary)" : active ? "var(--primary-ghost)" : "rgba(255,255,255,0.04)",
                          color: done || isPast ? "var(--text-inverse)" : active ? "var(--primary)" : "var(--text-muted)",
                          border: active ? "1px solid var(--primary)" : "1px solid transparent",
                        }}>
                          {done || isPast ? "✓" : i + 1}
                        </span>
                        <span className="text-sm" style={{ color: done || isPast ? "var(--text-primary)" : active ? "var(--primary)" : "var(--text-muted)" }}>
                          {s?.label || key}
                        </span>
                        {active && !done && !isPast && <span className="w-1.5 h-1.5 rounded-full animate-pulse ml-auto" style={{ background: "var(--primary)" }} />}
                      </div>
                      {i < stageKeys.length - 1 && <div className="ml-3.5 w-px h-3" style={{ background: isPast ? "var(--primary-dim)" : "var(--border)" }} />}
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          </div>

          {/* Terminal Log */}
          <div className="lg:col-span-3">
            <div className="terminal h-[500px]" ref={logRef}>
              <div className="flex items-center gap-2 mb-3 pb-3" style={{ borderBottom: "1px solid var(--border)" }}>
                <span className="w-2 h-2 rounded-full" style={{ background: pipelineDone ? "var(--success)" : pipelineError ? "var(--error)" : "var(--primary)" }} />
                <span className="text-xs font-bold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>Live Log</span>
              </div>
              {logs.map((log, i) => {
                const isStage = log.type === "stage";
                const sn = isStage ? (log.data?.name as string) : log.type;
                const s = STAGES[sn];
                const label = s?.label || sn;
                const detail = isStage ? (log.data?.detail as string) || "" : JSON.stringify(log.data);
                const isErr = sn?.includes("error");
                return (
                  <div key={i} className="terminal-line mb-1">
                    <span className="terminal-time">{log.timestamp}</span>
                    <span className={isErr ? "terminal-error" : "terminal-event"}>{label}</span>
                    {detail && <span className="terminal-detail">{detail}</span>}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
