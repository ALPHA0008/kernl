"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";

type Skill = {
  id?: string;
  category?: string;
  rule?: string;
  rationale?: string;
  evidence?: string[];
  confidence?: number;
};

type SkillsData = {
  skills: Skill[];
  version?: string;
  compiled_at?: string;
  brain_id?: string;
};

export default function SkillsViewer({ params }: { params: Promise<{ companyId: string }> }) {
  const resolvedParams = use(params);
  const companyId = resolvedParams.companyId;
  const [data, setData] = useState<SkillsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");
  const [sortBy, setSortBy] = useState<"category" | "confidence">("category");
  const router = useRouter();

  useEffect(() => {
    fetch(`http://localhost:8080/skills/${companyId}`)
      .then((res) => res.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, [companyId]);

  const skills = data?.skills || [];
  const categories = [...new Set(skills.map((s) => s.category || "Unknown"))];

  const filtered = skills
    .filter((s) => {
      if (!filter) return true;
      return (s.category || "").toLowerCase().includes(filter.toLowerCase());
    })
    .sort((a, b) => {
      if (sortBy === "confidence") return (b.confidence || 0) - (a.confidence || 0);
      return (a.category || "").localeCompare(b.category || "");
    });

  const confidenceColor = (c: number) => {
    if (c >= 0.8) return "text-green-400 border-green-400/30";
    if (c >= 0.6) return "text-yellow-400 border-yellow-400/30";
    if (c >= 0.4) return "text-orange-400 border-orange-400/30";
    return "text-red-400 border-red-400/30";
  };

  return (
    <div className="min-h-screen p-8 flex flex-col">
      <div className="flex justify-between items-center mb-6 border-b border-gray-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-primary">Skills File Viewer</h1>
          {data?.version && (
            <p className="text-text-secondary text-sm mt-1">
              Version: <span className="font-mono text-primary">{data.version}</span>
              {data.compiled_at && (
                <> · Compiled: {new Date(data.compiled_at).toLocaleString()}</>
              )}
              {" · "}{skills.length} skills
            </p>
          )}
        </div>
        <button onClick={() => router.push("/")} className="text-text-secondary hover:text-foreground">
          Back
        </button>
      </div>

      {/* Filter + Sort Controls */}
      <div className="flex gap-4 mb-4">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-surface border border-gray-700 text-foreground px-3 py-2 text-sm"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as "category" | "confidence")}
          className="bg-surface border border-gray-700 text-foreground px-3 py-2 text-sm"
        >
          <option value="category">Sort by Category</option>
          <option value="confidence">Sort by Confidence</option>
        </select>
      </div>

      {/* Skills Grid */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="text-text-secondary">Loading skills...</div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-text-secondary text-lg">No skills compiled yet.</p>
            <p className="text-text-secondary text-sm mt-2">
              Go to Dashboard → Compile Brain to generate skills from your source documents.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filtered.map((skill, i) => (
              <div
                key={skill.id || i}
                className="bg-surface border border-gray-800 p-5 hover:border-primary/30 transition-colors"
              >
                <div className="flex justify-between items-start mb-3">
                  <span className="text-xs font-mono bg-primary/10 text-primary px-2 py-1 rounded">
                    {skill.category || "Unknown"}
                  </span>
                  <span
                    className={`text-xs font-mono px-2 py-1 border rounded ${confidenceColor(
                      skill.confidence || 0
                    )}`}
                  >
                    {((skill.confidence || 0) * 100).toFixed(0)}%
                  </span>
                </div>

                <p className="text-white font-medium mb-2">{skill.rule}</p>

                {skill.rationale && (
                  <p className="text-text-secondary text-sm mb-3 italic">{skill.rationale}</p>
                )}

                {skill.evidence && skill.evidence.length > 0 && (
                  <div className="border-t border-gray-800 pt-3 mt-3">
                    <h4 className="text-xs text-text-secondary uppercase tracking-wider mb-2">
                      Evidence ({skill.evidence.length})
                    </h4>
                    {skill.evidence.map((e, j) => (
                      <p key={j} className="text-xs text-gray-400 mb-1 pl-2 border-l border-gray-700">
                        {e}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
