"use client";

import { useState, use } from "react";
import { useRouter } from "next/navigation";

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

export default function QueryDemo({ params }: { params: Promise<{ companyId: string }> }) {
  const resolvedParams = use(params);
  const companyId = resolvedParams.companyId;
  const [scenario, setScenario] = useState("");
  const [contextJson, setContextJson] = useState("{}");
  const [loading, setLoading] = useState(false);

  const [withBrainResponse, setWithBrainResponse] = useState<AgentResponse | null>(null);
  const [withoutBrainResponse, setWithoutBrainResponse] = useState<AgentResponse | null>(null);

  const router = useRouter();

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scenario) return;
    setLoading(true);
    setWithBrainResponse(null);
    setWithoutBrainResponse(null);

    let parsedContext = {};
    try {
      if (contextJson.trim()) {
        parsedContext = JSON.parse(contextJson);
      }
    } catch {
      alert("Invalid JSON in context field");
      setLoading(false);
      return;
    }

    try {
      const [resWithBrain, resWithoutBrain] = await Promise.all([
        fetch("http://localhost:8080/agent/handle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ company_id: companyId, scenario, context: parsedContext, with_brain: true }),
        }),
        fetch("http://localhost:8080/agent/handle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ company_id: companyId, scenario, context: parsedContext, with_brain: false }),
        }),
      ]);

      setWithBrainResponse(await resWithBrain.json());
      setWithoutBrainResponse(await resWithoutBrain.json());
    } catch (err) {
      console.error(err);
      alert("Query failed — is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const confidenceColor = (c: number) => {
    if (c >= 0.75) return "bg-green-500";
    if (c >= 0.5) return "bg-yellow-500";
    if (c >= 0.25) return "bg-orange-500";
    return "bg-red-500";
  };

  return (
    <div className="min-h-screen p-8 flex flex-col items-center">
      <div className="w-full max-w-5xl">
        <div className="flex justify-between items-center mb-6 border-b border-gray-800 pb-4">
          <h1 className="text-2xl font-bold text-primary">Brain Query Demo</h1>
          <button onClick={() => router.push("/")} className="text-text-secondary hover:text-foreground">
            Back to Dashboard
          </button>
        </div>

        <form onSubmit={handleQuery} className="mb-8 bg-surface p-6 border border-gray-800">
          <div className="flex flex-col gap-4">
            <div>
              <label className="block text-text-secondary text-sm font-bold mb-2">Scenario</label>
              <textarea
                className="w-full px-4 py-3 bg-background border border-gray-700 text-foreground focus:outline-none focus:border-primary min-h-[100px]"
                placeholder="Enterprise customer, 18 months tenure, wants $1,200 refund"
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-text-secondary text-sm font-bold mb-2">Context (JSON)</label>
              <textarea
                className="w-full px-4 py-3 bg-background border border-gray-700 text-foreground focus:outline-none focus:border-primary font-mono text-sm min-h-[80px]"
                placeholder='{"plan": "enterprise", "tenure_months": 18, "refund_amount": 1200}'
                value={contextJson}
                onChange={(e) => setContextJson(e.target.value)}
              />
            </div>
            <button
              type="submit"
              disabled={loading || !scenario}
              className="bg-primary text-background font-bold py-3 px-6 hover:opacity-90 disabled:opacity-50 self-end"
            >
              {loading ? "Thinking..." : "Compare Models"}
            </button>
          </div>
        </form>

        {(withBrainResponse || withoutBrainResponse) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* WITHOUT BRAIN */}
            <div className="bg-surface border border-gray-800 p-6 opacity-75">
              <h2 className="text-xl font-bold text-gray-400 mb-4 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-gray-500"></span>
                Without Brain (Generic AI)
              </h2>

              {withoutBrainResponse ? (
                <div className="space-y-4 text-gray-300">
                  <div>
                    <h3 className="text-gray-500 text-sm font-bold uppercase tracking-wider mb-1">Response</h3>
                    <p className="text-lg bg-background p-4 border border-gray-800 rounded">
                      {withoutBrainResponse.recommended_action || "No action"}
                    </p>
                  </div>
                  <div>
                    <h3 className="text-gray-500 text-sm font-bold uppercase tracking-wider mb-1">Rule Applied</h3>
                    <p className="italic">{withoutBrainResponse.rule_applied || "General knowledge"}</p>
                  </div>
                  {withoutBrainResponse.reasoning && (
                    <div>
                      <h3 className="text-gray-500 text-sm font-bold uppercase tracking-wider mb-1">Reasoning</h3>
                      <p className="text-sm">{withoutBrainResponse.reasoning}</p>
                    </div>
                  )}
                </div>
              ) : (
                <p>Loading...</p>
              )}
            </div>

            {/* WITH BRAIN */}
            <div className="bg-surface border-2 border-primary p-6 relative shadow-[0_0_15px_rgba(45,212,191,0.1)]">
              <div className="absolute -top-3 -right-3 bg-primary text-background text-xs font-bold px-3 py-1 uppercase tracking-wider rounded-full">
                Company Brain
              </div>
              <h2 className="text-xl font-bold text-primary mb-4 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                With Brain (Compiled Agent)
              </h2>

              {withBrainResponse ? (
                <div className="space-y-4">
                  {withBrainResponse.error ? (
                    <p className="text-red-400">{withBrainResponse.error}</p>
                  ) : (
                    <>
                      <div>
                        <h3 className="text-primary/70 text-sm font-bold uppercase tracking-wider mb-1">
                          Recommended Action
                        </h3>
                        <p className="text-xl font-semibold text-white bg-primary/10 p-4 border border-primary/30 rounded">
                          {withBrainResponse.recommended_action}
                        </p>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <h3 className="text-primary/70 text-sm font-bold uppercase tracking-wider mb-1">
                            Skill Matched
                          </h3>
                          <p className="font-mono text-sm bg-background p-2 rounded">
                            {withBrainResponse.skill_matched || "N/A"}
                          </p>
                        </div>
                        <div>
                          <h3 className="text-primary/70 text-sm font-bold uppercase tracking-wider mb-1">
                            Confidence
                          </h3>
                          <div className="flex items-center gap-2 mt-2">
                            <div className="flex-1 bg-background h-2 rounded-full overflow-hidden">
                              <div
                                className={`h-full ${confidenceColor(withBrainResponse.confidence || 0)}`}
                                style={{ width: `${(withBrainResponse.confidence || 0) * 100}%` }}
                              ></div>
                            </div>
                            <span className="text-xs font-mono">
                              {((withBrainResponse.confidence || 0) * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Retrieval Scores */}
                      {withBrainResponse.retrieval_scores && withBrainResponse.retrieval_scores.length > 0 && (
                        <div>
                          <h3 className="text-primary/70 text-sm font-bold uppercase tracking-wider mb-1">
                            Retrieval Scores (Top {withBrainResponse.retrieval_scores.length} Skills)
                          </h3>
                          <div className="flex gap-2 flex-wrap">
                            {withBrainResponse.retrieval_scores.map((score, i) => (
                              <span
                                key={i}
                                className="bg-background border border-gray-700 px-2 py-1 rounded text-xs font-mono"
                              >
                                #{i + 1}: {(score * 100).toFixed(1)}%
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <div>
                        <h3 className="text-primary/70 text-sm font-bold uppercase tracking-wider mb-1">
                          Rule Applied
                        </h3>
                        <p className="text-white border-l-2 border-primary pl-3 py-1 font-medium">
                          {withBrainResponse.rule_applied}
                        </p>
                      </div>

                      {/* Reasoning */}
                      {withBrainResponse.reasoning && (
                        <div>
                          <h3 className="text-primary/70 text-sm font-bold uppercase tracking-wider mb-1">
                            LLM Reasoning
                          </h3>
                          <p className="text-sm text-gray-300 bg-background p-3 rounded border border-gray-800">
                            {withBrainResponse.reasoning}
                          </p>
                        </div>
                      )}

                      {withBrainResponse.evidence && withBrainResponse.evidence.length > 0 && (
                        <div>
                          <h3 className="text-primary/70 text-sm font-bold uppercase tracking-wider mb-2">
                            Evidence Trail
                          </h3>
                          <ul className="space-y-2">
                            {withBrainResponse.evidence.map((src, i) => (
                              <li key={i} className="text-gray-300 text-sm bg-background p-3 rounded border border-gray-800">
                                {src}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ) : (
                <p>Loading...</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
