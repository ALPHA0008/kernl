"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";

interface LogEvent {
  timestamp: string;
  type: string;
  data: any;
}

const STAGE_LABELS: Record<string, string> = {
  pipeline_start: "🚀 Pipeline Started",
  LOADING_DOCS: "📂 Loading Documents",
  LOADING_DOCS_DONE: "✅ Sources Loaded",
  INGEST_NOTION: "📝 Ingesting SOPs",
  INGEST_SLACK: "💬 Ingesting Slack Messages",
  INGEST_TICKETS: "🎫 Ingesting Support Tickets",
  INGEST_JOIN: "🔗 Merging All Chunks",
  EXTRACT_DECISIONS: "⚖️ Extracting Rules & Policies",
  EXTRACT_DECISIONS_DONE: "✅ Rules Extracted",
  EXTRACT_WORKFLOWS: "🔁 Extracting Workflows",
  EXTRACT_WORKFLOWS_DONE: "✅ Workflows Extracted",
  EXTRACT_EXCEPTIONS: "⚠️ Extracting Exceptions & Edge Cases",
  EXTRACT_EXCEPTIONS_DONE: "✅ Exceptions Extracted",
  DETECT_CONTRADICTIONS: "🔄 Detecting Cross-Source Contradictions",
  DETECT_CONTRADICTIONS_DONE: "✅ Contradictions Analyzed",
  SYNTHESIZING_SKILLS: "⚡ Synthesizing Skills from All Extractions",
  SYNTHESIZING_DONE: "✅ Skills Synthesized",
  LINKING_EVIDENCE: "🔗 Linking Evidence to Skills",
  LINKING_DONE: "✅ Evidence Linked",
  SCORING_CONFIDENCE: "📊 Scoring Confidence",
  SCORING_DONE: "✅ Confidence Scored",
  WRITING_DB: "💾 Pre-embedding & Writing to Database",
  DONE: "✅ Pipeline Complete",
  pipeline_complete: "🎉 Compilation Finished",
  pipeline_error: "❌ Pipeline Error",
};

export default function CompileViewer({ params }: { params: Promise<{ jobId: string }> }) {
  const resolvedParams = use(params);
  const jobId = resolvedParams.jobId;
  const [logs, setLogs] = useState<LogEvent[]>([]);
  const [status, setStatus] = useState("Connecting...");
  const router = useRouter();

  useEffect(() => {
    if (!jobId) return;

    const eventSource = new EventSource(`http://localhost:8080/compile/${jobId}/stream`);

    eventSource.onmessage = (event) => {
      const parsed = JSON.parse(event.data);
      const eventType = parsed.event;
      const eventData = parsed.data;

      setLogs((prev) => [
        ...prev,
        { timestamp: new Date().toLocaleTimeString(), type: eventType, data: eventData },
      ]);

      // Update the status bar based on event type
      if (eventType === "stage") {
        const stageName = eventData.name || "";
        const label = STAGE_LABELS[stageName] || stageName;
        const detail = eventData.detail || "";
        setStatus(`${label}${detail ? ` — ${detail}` : ""}`);
      } else if (eventType === "pipeline_start") {
        setStatus(STAGE_LABELS.pipeline_start);
      } else if (eventType === "pipeline_complete") {
        setStatus(STAGE_LABELS.pipeline_complete);
        eventSource.close();
      } else if (eventType === "pipeline_error") {
        setStatus(`❌ Error: ${eventData.error || "Unknown"}`);
        eventSource.close();
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, [jobId]);

  return (
    <div className="min-h-screen p-8 flex flex-col">
      <div className="flex justify-between items-center mb-6 border-b border-gray-800 pb-4">
        <h1 className="text-2xl font-bold text-primary">Pipeline Stream</h1>
        <div className="flex items-center gap-4">
          <span
            className={`px-3 py-1 font-mono text-sm border ${
              status.includes("Finished") || status.includes("Complete")
                ? "border-green-500 text-green-500"
                : status.includes("Error")
                ? "border-red-500 text-red-500"
                : "border-primary text-primary animate-pulse"
            }`}
          >
            {status}
          </span>
          <button onClick={() => router.push("/")} className="text-text-secondary hover:text-foreground">
            Back
          </button>
        </div>
      </div>

      <div className="flex-1 bg-surface border border-gray-800 p-4 font-mono text-sm overflow-y-auto">
        {logs.map((log, i) => {
          const isStage = log.type === "stage";
          const stageName = isStage ? log.data?.name : log.type;
          const label = STAGE_LABELS[stageName] || stageName;
          const detail = isStage ? log.data?.detail || "" : JSON.stringify(log.data);
          const isError = stageName?.includes("error") || stageName?.includes("Error");

          return (
            <div key={i} className="mb-2">
              <span className="text-text-secondary">[{log.timestamp}]</span>{" "}
              <span className={isError ? "text-red-500" : "text-primary"}>{label}</span>{" "}
              <span className="text-foreground">{detail}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
