"use client";
import { useState } from "react";
import { ProvenanceBadge } from "@/components/world/ProvenanceBadges";
import type { Project, Scenario } from "@/types/api";

interface Props {
  scenario: Scenario;
  busy: boolean;
  onAdd: (mw: number) => void;
  onSetMw: (pid: string, mw: number) => void;
  onRemove: (pid: string) => void;
  onReset: () => void;
  onGolden: () => void;
}

export function ProjectPanel({ scenario, busy, onAdd, onSetMw, onRemove, onReset, onGolden }: Props) {
  const dc = scenario.projects[0];
  return (
    <section className="panel p-4" aria-label="Scenario and project">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">Scenario</h2>
          <div className="text-xs" style={{ color: "var(--muted)" }}>{scenario.name} · {scenario.id}</div>
        </div>
        <span className="text-[11px]" style={{ color: "var(--muted)" }} aria-live="polite">{busy ? "Recomputing 5 years…" : ""}</span>
      </div>
      <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Projects overlay the historical baseline. The baseline world is never modified.</p>

      {!dc ? (
        <div className="mt-3">
          <div className="text-sm mb-2">Add a data centre <span className="text-xs" style={{ color: "var(--muted)" }}>(constant 24/7 load)</span></div>
          <div className="flex flex-wrap gap-2">
            {[10, 20, 30].map((m) => <button key={m} className="btn" disabled={busy} onClick={() => onAdd(m)}>+ {m} MW</button>)}
          </div>
        </div>
      ) : (
        <DcCard key={dc.id} project={dc} busy={busy} onSetMw={onSetMw} onRemove={onRemove} />
      )}
      <div className="flex gap-2 mt-3">
        <button className="btn" onClick={onGolden} disabled={busy}>★ Golden demo (20 MW)</button>
        <button className="btn" onClick={onReset} disabled={busy}>Reset scenario</button>
      </div>
    </section>
  );
}

function DcCard({ project: dc, busy, onSetMw, onRemove }: { project: Project; busy: boolean; onSetMw: (pid: string, mw: number) => void; onRemove: (pid: string) => void }) {
  const [mw, setMw] = useState(dc.nominalLoadMw);
  return (
    <div className="mt-3 rounded-lg p-3" style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-medium">{dc.name}</div>
        <ProvenanceBadge type="hypothetical" />
      </div>
      <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>Constant 24/7 · no flexible compute yet</div>
      <label className="block mt-3 text-xs" style={{ color: "var(--muted)" }} htmlFor="dc-mw">Size: <b style={{ color: "var(--text)" }}>{mw} MW</b></label>
      <input id="dc-mw" type="range" min={1} max={60} step={1} value={mw} className="w-full"
        onChange={(e) => { const v = Number(e.target.value); setMw(v); onSetMw(dc.id, v); }} />
      <div className="flex gap-2 mt-2">
        {[10, 20, 30].map((m) => <button key={m} className="btn" aria-pressed={mw === m} disabled={busy} onClick={() => { setMw(m); onSetMw(dc.id, m); }}>{m} MW</button>)}
        <button className="btn ml-auto" disabled={busy} onClick={() => onRemove(dc.id)}>Remove</button>
      </div>
    </div>
  );
}
