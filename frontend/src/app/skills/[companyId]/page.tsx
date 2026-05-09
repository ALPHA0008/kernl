"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";
import DashboardLayout from "@/components/DashboardLayout";
import GlassCard from "@/components/ui/GlassCard";
import ConfidenceBadge from "@/components/ui/ConfidenceBadge";

type Skill = {
  id?: string;
  category?: string;
  rule?: string;
  rationale?: string;
  evidence?: string[];
  confidence?: number;
  source_files?: string[];
  embedding_vector?: number[];
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
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const router = useRouter();

  useEffect(() => {
    fetch(`${API_BASE}/skills/${companyId}`)
      .then((res) => res.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [companyId]);

  const skills = data?.skills || [];
  const categories = [...new Set(skills.map((s) => s.category || "Unknown"))];

  const filtered = skills
    .filter((s) => {
      if (!filter) return true;
      return (s.category || "") === filter;
    })
    .sort((a, b) => {
      if (sortBy === "confidence") return (b.confidence || 0) - (a.confidence || 0);
      return (a.category || "").localeCompare(b.category || "");
    });

  return (
    <DashboardLayout>
      <div className="p-6 lg:p-8 max-w-7xl mx-auto animate-fade-in">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Skills Explorer
            </h1>
            {data?.version && (
              <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
                <span className="font-mono" style={{ color: "var(--primary)" }}>
                  {data.version}
                </span>
                {data.compiled_at && (
                  <> · {new Date(data.compiled_at).toLocaleDateString()}</>
                )}
                {" · "}
                <span style={{ color: "var(--text-secondary)" }}>{skills.length} skills</span>
              </p>
            )}
          </div>
          <button
            onClick={() => router.push(`/demo/${companyId}`)}
            className="btn-primary"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="7" cy="7" r="5.5" />
              <path d="M7 4v3l2 1.5" strokeLinecap="round" />
            </svg>
            Query Agent
          </button>
        </div>

        {/* Filter Chips */}
        <div className="flex gap-2 flex-wrap mb-6">
          <button
            onClick={() => setFilter("")}
            className="badge transition-all"
            style={{
              background: !filter ? "var(--primary-ghost)" : "transparent",
              color: !filter ? "var(--primary)" : "var(--text-muted)",
              border: `1px solid ${!filter ? "rgba(0,210,180,0.2)" : "var(--border)"}`,
              cursor: "pointer",
            }}
          >
            All ({skills.length})
          </button>
          {categories.map((cat) => {
            const count = skills.filter((s) => (s.category || "Unknown") === cat).length;
            const active = filter === cat;
            return (
              <button
                key={cat}
                onClick={() => setFilter(active ? "" : cat)}
                className="badge transition-all"
                style={{
                  background: active ? "var(--primary-ghost)" : "transparent",
                  color: active ? "var(--primary)" : "var(--text-muted)",
                  border: `1px solid ${active ? "rgba(0,210,180,0.2)" : "var(--border)"}`,
                  cursor: "pointer",
                }}
              >
                {cat} ({count})
              </button>
            );
          })}

          {/* Sort toggle */}
          <div className="ml-auto">
            <button
              onClick={() => setSortBy(sortBy === "category" ? "confidence" : "category")}
              className="badge transition-all"
              style={{
                background: "transparent",
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
                cursor: "pointer",
              }}
            >
              Sort: {sortBy === "category" ? "Category" : "Confidence"}
            </button>
          </div>
        </div>

        {/* Skills Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="glass-card p-5 animate-shimmer" style={{ height: "180px" }} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state animate-fade-up">
            <div className="empty-state__icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="4" y="4" width="16" height="16" rx="2" />
                <path d="M9 9h6M9 12h4" strokeLinecap="round" />
              </svg>
            </div>
            <h2 className="text-lg font-bold mb-2" style={{ color: "var(--text-primary)" }}>
              No skills compiled yet
            </h2>
            <p className="text-sm mb-6" style={{ color: "var(--text-secondary)" }}>
              Compile your company brain to generate skills from source documents.
            </p>
            <button onClick={() => router.push("/onboarding")} className="btn-primary">
              Start Onboarding
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
            {filtered.map((skill, i) => (
              <GlassCard
                key={skill.id || i}
                interactive
                onClick={() => setSelectedSkill(skill)}
              >
                <div className="flex justify-between items-start mb-3">
                  <span className="badge badge--primary">{skill.category || "Unknown"}</span>
                  <ConfidenceBadge value={skill.confidence || 0} />
                </div>

                <p className="text-sm font-medium mb-2" style={{ color: "var(--text-primary)" }}>
                  {skill.rule}
                </p>

                {skill.rationale && (
                  <p
                    className="text-xs leading-relaxed line-clamp-2 mb-3"
                    style={{ color: "var(--text-muted)" }}
                  >
                    {skill.rationale}
                  </p>
                )}

                {skill.evidence && skill.evidence.length > 0 && (
                  <div
                    className="pt-3 mt-auto"
                    style={{ borderTop: "1px solid var(--border)" }}
                  >
                    <p className="text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                      {skill.evidence.length} evidence source{skill.evidence.length !== 1 ? "s" : ""}
                    </p>
                  </div>
                )}
              </GlassCard>
            ))}
          </div>
        )}
      </div>

      {/* Detail Slide-in Panel */}
      {selectedSkill && (
        <div
          className="fixed inset-0 z-50 flex"
          onClick={() => setSelectedSkill(null)}
        >
          {/* Backdrop */}
          <div
            className="flex-1"
            style={{ background: "rgba(0, 0, 0, 0.5)" }}
          />

          {/* Panel */}
          <div
            className="w-full max-w-lg overflow-y-auto animate-slide-right"
            style={{
              background: "var(--bg-surface)",
              borderLeft: "1px solid var(--border)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Panel Header */}
            <div
              className="sticky top-0 z-10 flex items-center justify-between px-6 py-4"
              style={{
                background: "var(--bg-surface)",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <h2 className="text-lg font-bold" style={{ color: "var(--primary)" }}>
                Skill Detail
              </h2>
              <button
                onClick={() => setSelectedSkill(null)}
                className="w-8 h-8 flex items-center justify-center rounded-lg transition-colors"
                style={{ color: "var(--text-muted)" }}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
                </svg>
              </button>
            </div>

            {/* Panel Body */}
            <div className="p-6 space-y-6">
              <div className="flex justify-between items-start">
                <span className="badge badge--primary">{selectedSkill.category || "Unknown"}</span>
                <ConfidenceBadge value={selectedSkill.confidence || 0} size="md" />
              </div>

              <div>
                <p className="input-label">Rule</p>
                <p className="text-base font-medium" style={{ color: "var(--text-primary)" }}>
                  {selectedSkill.rule}
                </p>
              </div>

              {selectedSkill.rationale && (
                <div>
                  <p className="input-label">Rationale</p>
                  <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    {selectedSkill.rationale}
                  </p>
                </div>
              )}

              {selectedSkill.evidence && selectedSkill.evidence.length > 0 && (
                <div>
                  <p className="input-label">
                    Evidence ({selectedSkill.evidence.length})
                  </p>
                  <div className="space-y-2">
                    {selectedSkill.evidence.map((e, j) => (
                      <div
                        key={j}
                        className="text-sm p-3 rounded"
                        style={{
                          color: "var(--text-secondary)",
                          background: "var(--bg-input)",
                          border: "1px solid var(--border)",
                        }}
                      >
                        {e}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {selectedSkill.source_files && selectedSkill.source_files.length > 0 && (
                <div>
                  <p className="input-label">Source Files</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedSkill.source_files.map((sf, j) => (
                      <span key={j} className="badge badge--neutral font-mono">
                        {sf}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ borderTop: "1px solid var(--border)", paddingTop: "24px" }}>
                <button
                  onClick={() => setSelectedSkill(null)}
                  className="btn-secondary w-full"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
