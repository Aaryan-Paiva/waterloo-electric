"use client";

import { useState } from "react";

const INK = "#1D2320", LINE = "#D9D1BE", AMB = "#F2A72E", TEAL = "#1F9E89", CORAL = "#E5533D", BLUE = "#3F86D8";
const FD = "var(--font-display), 'Bricolage Grotesque', system-ui, sans-serif";

const TERMS: [string, string, string, string][] = [
  ["Physical capability", "installed capacity", "A 5 MW / 15 MWh battery. What it could deliver with no other constraint.", BLUE],
  ["Participation", "× enrolment", "Only 40% of owners are enrolled in the program. The other 60% never see a request.", TEAL],
  ["Incentive", "× price response", "At $40/MWh an owner declines; at $120/MWh the same owner offers the same MW.", AMB],
  ["Customer constraints", "× real limits", "A battery won't drop below 20% reserve. An EV must be full by 7 am. A building has a comfort budget.", CORAL],
  ["Timing", "× the actual hour", "A depot that's flexible all night has nothing to give at the 6 pm peak, when the request happens.", "#8C7AE0"],
];

export function FlexEquation() {
  const [hover, setHover] = useState<number | null>(null);
  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5 sm:gap-2.5 text-sm sm:text-base" style={{ fontFamily: FD, fontWeight: 700 }}>
        {TERMS.map(([short, , , c], i) => (
          <span key={short} className="contents">
            <span
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((h) => (h === i ? null : h))}
              onFocus={() => setHover(i)}
              onBlur={() => setHover((h) => (h === i ? null : h))}
              tabIndex={0}
              role="button"
              style={{
                padding: "8px 14px",
                borderRadius: 10,
                cursor: "pointer",
                background: hover === i ? c : "rgba(29,35,32,.04)",
                color: hover === i ? "#fff" : INK,
                border: `1px solid ${hover === i ? c : LINE}`,
                transition: "background .15s, color .15s",
              }}
            >
              {short}
            </span>
            {i < TERMS.length - 1 && <span style={{ color: "#8A8F82" }}>×</span>}
          </span>
        ))}
        <span style={{ color: "#8A8F82" }}>=</span>
        <span style={{ padding: "8px 14px", borderRadius: 10, background: INK, color: "#FBF7EE" }}>usable flexibility</span>
      </div>
      <div className="mt-5 rounded-xl p-4 sm:p-5" style={{ border: `1px solid ${LINE}`, minHeight: 78, background: "rgba(29,35,32,.02)" }}>
        {hover === null ? (
          <div className="text-sm" style={{ color: "#8A8F82" }}>Hover or tap a term above for a concrete example.</div>
        ) : (
          <div>
            <div style={{ fontFamily: FD, fontWeight: 700, color: TERMS[hover][3] }} className="text-sm">{TERMS[hover][0]} <span style={{ color: "#8A8F82", fontWeight: 500 }}>({TERMS[hover][1]})</span></div>
            <div className="mt-1 text-sm sm:text-base" style={{ color: "#4A4F45", lineHeight: 1.5 }}>{TERMS[hover][2]}</div>
          </div>
        )}
      </div>
    </div>
  );
}
