"use client";

/** Last-resort boundary: only fires if the root layout itself throws (the
 *  console-scoped error.tsx handles everything inside the app shell). Must
 *  define its own html/body since it replaces the root layout when active. */
export default function GlobalError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif" }}>
        <div
          style={{
            display: "flex",
            minHeight: "100vh",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "1rem",
            textAlign: "center",
            padding: "2rem",
          }}
        >
          <h2 style={{ fontSize: "1.125rem", fontWeight: 600 }}>
            Kernl hit an unexpected error.
          </h2>
          <p style={{ maxWidth: "32rem", fontSize: "0.875rem", color: "#666" }}>
            {error.message}
          </p>
          <button
            onClick={() => unstable_retry()}
            style={{
              height: "2.25rem",
              padding: "0 1rem",
              borderRadius: "6px",
              border: "1px solid #ddd",
              background: "#fff",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
