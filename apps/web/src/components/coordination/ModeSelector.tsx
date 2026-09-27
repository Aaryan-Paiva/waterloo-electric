"use client";
export type CoordMode = "manual" | "agentic" | "historical";

export function ModeSelector({ mode, setMode }: { mode: CoordMode; setMode: (m: CoordMode) => void }) {
  const opt = (m: CoordMode, title: string, sub: string) => (
    <label className="flex-1 rounded-lg p-2 cursor-pointer text-xs" style={{ border: `1px solid ${mode === m ? "var(--accent)" : "var(--line)"}`, background: mode === m ? "var(--panel-2)" : "transparent" }}>
      <input type="radio" name="coord-mode" className="mr-1.5" checked={mode === m} onChange={() => setMode(m)} />
      <b>{title}</b>
      <div style={{ color: "var(--muted)" }}>{sub}</div>
    </label>
  );
  return (
    <fieldset className="panel p-3" aria-label="DER coordination mode">
      <legend className="sr-only">DER coordination mode</legend>
      <div className="text-xs font-semibold mb-2">DER Coordination</div>
      <div className="flex gap-2">
        {opt("manual", "Manual", "Participation sliders · deterministic · no LLM")}
        {opt("agentic", "Agentic", "Owner agents (LLM or stub) · one selected event")}
        {opt("historical", "Historical", "Every event 2021–25 · deterministic policy · 0 LLM calls")}
      </div>
    </fieldset>
  );
}
