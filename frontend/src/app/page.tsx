"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Dashboard() {
  const [companyId, setCompanyId] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleCompile = async () => {
    if (!companyId) return;
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8080/compile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company_id: companyId }),
      });
      const data = await res.json();
      if (data.job_id) {
        router.push(`/compile/${data.job_id}`);
      }
    } catch (err) {
      console.error(err);
      alert("Failed to start compilation");
    } finally {
      setLoading(false);
    }
  };

  const handleQuery = () => {
    if (companyId) {
      router.push(`/demo/${companyId}`);
    }
  };

  const handleViewSkills = () => {
    if (companyId) {
      router.push(`/skills/${companyId}`);
    }
  };

  return (
    <div className="min-h-screen p-8 flex flex-col items-center justify-center">
      <div className="max-w-md w-full bg-surface p-8 border border-gray-800 shadow-2xl">
        <h1 className="text-3xl font-bold text-primary mb-6">Kernl Compilation</h1>
        
        <div className="mb-6">
          <label className="block text-text-secondary text-sm font-bold mb-2">
            Company ID
          </label>
          <input
            type="text"
            className="w-full px-3 py-2 bg-background border border-gray-700 text-foreground focus:outline-none focus:border-primary"
            placeholder="e.g. comp_123"
            value={companyId}
            onChange={(e) => setCompanyId(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-3">
          <button
            onClick={handleCompile}
            disabled={loading || !companyId}
            className="w-full bg-primary text-background font-bold py-2 px-4 hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Starting..." : "Compile Brain"}
          </button>
          
          <button
            onClick={handleViewSkills}
            disabled={!companyId}
            className="w-full border border-primary text-primary font-bold py-2 px-4 hover:bg-primary/10 disabled:opacity-50"
          >
            View Skills File
          </button>
          
          <button
            onClick={handleQuery}
            disabled={!companyId}
            className="w-full border border-gray-600 text-foreground font-bold py-2 px-4 hover:bg-gray-800 disabled:opacity-50"
          >
            Query Agent Demo
          </button>
        </div>
      </div>
    </div>
  );
}
