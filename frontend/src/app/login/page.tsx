"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative">
      {/* Background mesh */}
      <div className="mesh-gradient" />

      {/* Auth Card */}
      <div
        className="w-full max-w-sm animate-fade-up"
        style={{ animationDelay: "0.1s" }}
      >
        {/* Logo */}
        <div className="flex items-center justify-center mb-8">
          <div
            className="w-12 h-12 rounded-xl flex items-center justify-center animate-pulse-glow"
            style={{
              background: "var(--primary-ghost)",
              color: "var(--primary)",
            }}
          >
            <svg width="24" height="24" viewBox="0 0 18 18" fill="none">
              <path
                d="M3 2h3v14H3V2zm5 0h2l5 7-5 7H8l5-7-5-7z"
                fill="currentColor"
              />
            </svg>
          </div>
        </div>

        <div className="glass-card p-8">
          <h1
            className="text-xl font-bold mb-1 text-center"
            style={{ color: "var(--text-primary)" }}
          >
            Welcome back
          </h1>
          <p
            className="text-sm text-center mb-6"
            style={{ color: "var(--text-muted)" }}
          >
            Sign in to your Kernl workspace
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="input-label">Email</label>
              <input
                type="email"
                className="input-field"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="input-label">Password</label>
              <input
                type="password"
                className="input-field"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div
                className="text-sm px-3 py-2 rounded"
                style={{
                  color: "var(--error)",
                  background: "var(--error-bg)",
                  border: "1px solid rgba(248, 113, 113, 0.2)",
                }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full"
              style={{ padding: "12px 20px" }}
            >
              {loading ? (
                <span className="animate-spin-slow inline-block w-4 h-4 border-2 border-current border-t-transparent rounded-full" />
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          <p
            className="text-sm mt-6 text-center"
            style={{ color: "var(--text-muted)" }}
          >
            No account?{" "}
            <a
              href="/register"
              className="font-medium transition-colors"
              style={{ color: "var(--primary)" }}
            >
              Create one
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
