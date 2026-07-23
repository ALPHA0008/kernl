import { ImageResponse } from "next/og";

export const alt = "Kernl · Every decision, on the record.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** Ink-on-paper OG card: wordmark, the headline, one ledger row. Matches the
 *  landing hero. Edge-generated at build; no asset pipeline. */
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#ffffff",
          padding: "72px 80px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: "#171717",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: 20,
              fontWeight: 700,
            }}
          >
            K
          </div>
          <div style={{ fontSize: 26, fontWeight: 600, color: "#171717", letterSpacing: -0.5 }}>
            Kernl
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 20,
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              fontSize: 76,
              fontWeight: 600,
              color: "#171717",
              letterSpacing: -3,
              lineHeight: 1.02,
            }}
          >
            <span>Every decision,</span>
            <span>on the record.</span>
          </div>
          <div style={{ fontSize: 24, color: "#4d4d4d", maxWidth: 760, lineHeight: 1.4 }}>
            The decision ledger for enterprise AI.
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            fontSize: 20,
            color: "#4d4d4d",
            fontFamily: "monospace",
            borderTop: "1px solid #ebebeb",
            paddingTop: 24,
          }}
        >
          <span>#4821</span>
          <span style={{ color: "#171717" }}>refund.annual_full_14d</span>
          <span
            style={{
              color: "#0a7c4a",
              background: "#e9f7ef",
              padding: "3px 12px",
              borderRadius: 100,
              fontSize: 17,
            }}
          >
            approve
          </span>
          <span>a3f2…9c</span>
          <span>sealed</span>
        </div>
      </div>
    ),
    { ...size },
  );
}
