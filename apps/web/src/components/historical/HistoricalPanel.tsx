"use client";
import { useMemo, useState } from "react";
import { ProvenanceBadge } from "@/components/world/ProvenanceBadges";
import { formatEst } from "@/lib/pressure";
import type { Agg, HistEvent, HistoricalResult } from "@/types/api";

const PRESETS = [40, 80, 120];
const DER = { battery: { label: "Batteries", color: "var(--accent)" }, ev_fleet: { label: "EV fleets", color: "var(--ok)" }, building: { label: "Buildings", color: "var(--hypo)" } } as const;
const STATUS: Record<string, { glyph: string; color: string }> = { resolved: { glyph: "●", color: "var(--ok)" }, partially_resolved: { glyph: "◐", color: "var(--warn)" }, unresolved: { glyph: "✖", color: "var(--bad)" } };
const f1 = (x: number) => x.toFixed(1);
const dt = (iso: string) => formatEst(iso, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).replace(" EST", "");

interface Props {
  results: Record<number, HistoricalResult>;
  selected: number | null;
  setSelected: (i: number) => void;
  busy: number | null;
  error: string | null;
  stale: boolean;
  hasProject: boolean;
  onRun: (incentive: number) => void;
  onClear: () => void;
  onJump: (ts: string) => void;
}

export function HistoricalPanel({ results, selected, setSelected, busy, error, stale, hasProject, onRun, onClear, onJump }: Props) {
  const [custom, setCustom] = useState("");
  const cv = Number(custom);
  const customOk = custom !== "" && Number.isFinite(cv) && cv > 0 && cv <= 1000;
  const r = selected != null ? results[selected] : undefined;
  const done = Object.values(results).sort((a, b) => a.incentivePricePerMwh - b.incentivePricePerMwh);
  return (
    <section className="panel p-4" aria-label="Historical DER coordination">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Historical coordination <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· every event, 2021–2025</span></h2>
        <div className="flex gap-1"><ProvenanceBadge type="modeled" /><ProvenanceBadge type="derived" /></div>
      </div>
      <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
        Coordinates every historical capacity-event window chronologically with the <b>deterministic modeled owner policy</b> (same Modeled owner preferences as Agentic Mode, <b>0 LLM calls</b>).
        Nearby events are simulated jointly; battery energy is carried between events, never reset. Each incentive is a user-selected scenario — not a recommendation and not a feasibility verdict.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5" role="group" aria-label="Incentive scenarios">
        {PRESETS.map((p) => <button key={p} className="btn" disabled={!hasProject || busy != null} aria-pressed={selected === p && !!results[p]} onClick={() => onRun(p)}>{busy === p ? "Running…" : results[p] && !stale ? `$${p} ✓` : `Run $${p}/MWh`}</button>)}
        <input aria-label="Custom incentive ($/MWh)" inputMode="numeric" placeholder="custom $" className="w-20 rounded-md px-2 py-1 text-xs" style={{ background: "var(--panel-2)", border: "1px solid var(--line)", color: "var(--text)" }}
          value={custom} onChange={(e) => setCustom(e.target.value.replace(/[^0-9.]/g, ""))} />
        <button className="btn" disabled={!customOk || !hasProject || busy != null} onClick={() => onRun(cv)}>Run custom</button>
      </div>
      {!hasProject && <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Add a project to create capacity events.</p>}
      {busy != null && <p className="text-xs mt-2" role="status" style={{ color: "var(--accent)" }}>Coordinating all event windows at ${busy}/MWh (about 10 s)…</p>}
      {error && <p className="text-xs mt-2" style={{ color: "var(--bad)" }}>{error}</p>}
      {stale && <div className="text-xs rounded p-2 mt-2" style={{ border: "1px solid var(--warn)", color: "var(--warn)" }}>▲ The scenario changed since these runs: run again.</div>}
      {!stale && done.length > 0 && (
        <>
          <Compare done={done} selected={selected} setSelected={setSelected} />
          {r && <Detail r={r} onJump={onJump} />}
          <button className="btn mt-3" onClick={onClear}>Clear results</button>
        </>
      )}
    </section>
  );
}

function Compare({ done, selected, setSelected }: { done: HistoricalResult[]; selected: number | null; setSelected: (i: number) => void }) {
  const b = done[0].totals;
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-xs tabular-nums" aria-label="Incentive scenario comparison">
        <thead><tr style={{ color: "var(--muted)" }}><th className="text-left font-normal">Scenario</th><th className="text-right font-normal">Hours</th><th className="text-right font-normal">Energy above cap.</th><th className="text-right font-normal">Worst</th><th className="text-right font-normal">R/P/U</th></tr></thead>
        <tbody>
          <tr style={{ color: "var(--muted)" }}><td>Before coordination</td><td className="text-right">{b.violationHoursBefore}</td><td className="text-right">{f1(b.energyAboveCapacityBeforeMwh)} MWh</td><td className="text-right">{f1(b.worstDeficitBeforeMw)} MW</td><td className="text-right">{b.events} events</td></tr>
          {done.map((r) => (
            <tr key={r.id} onClick={() => setSelected(r.incentivePricePerMwh)} className="cursor-pointer" style={{ background: selected === r.incentivePricePerMwh ? "var(--panel-2)" : "transparent" }}>
              <td className="py-0.5"><b>${r.incentivePricePerMwh}/MWh</b></td><td className="text-right">{r.totals.violationHoursAfter}</td><td className="text-right">{f1(r.totals.energyAboveCapacityAfterMwh)} MWh</td>
              <td className="text-right">{f1(r.totals.worstDeficitAfterMw)} MW</td><td className="text-right">{r.totals.resolved}/{r.totals.partiallyResolved}/{r.totals.unresolved}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="text-[10px] mt-1" style={{ color: "var(--muted)" }}>After coordination, per scenario · R/P/U = resolved / partially resolved / unresolved events · click a row to inspect it</div>
    </div>
  );
}

function AggTable({ title, rows }: { title: string; rows: [string, Agg][] }) {
  return (
    <div className="mt-3 overflow-x-auto">
      <h4 className="text-xs font-semibold mb-1">{title}</h4>
      <table className="w-full text-xs tabular-nums">
        <thead><tr style={{ color: "var(--muted)" }}><th className="text-left font-normal"> </th><th className="text-right font-normal">Events</th><th className="text-right font-normal">Hours</th><th className="text-right font-normal">Energy (MWh)</th><th className="text-right font-normal">Worst (MW)</th><th className="text-right font-normal">R/P/U</th></tr></thead>
        <tbody>{rows.map(([k, a]) => (
          <tr key={k}><td className="py-0.5 capitalize">{k}</td><td className="text-right">{a.events}</td><td className="text-right">{a.violationHoursBefore}→{a.violationHoursAfter}</td>
            <td className="text-right">{f1(a.energyAboveCapacityBeforeMwh)}→{f1(a.energyAboveCapacityAfterMwh)}</td><td className="text-right">{f1(a.worstDeficitBeforeMw)}→{f1(a.worstDeficitAfterMw)}</td><td className="text-right">{a.resolved}/{a.partiallyResolved}/{a.unresolved}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function Detail({ r, onJump }: { r: HistoricalResult; onJump: (ts: string) => void }) {
  const t = r.totals;
  const [filter, setFilter] = useState<"all" | "unresolved" | "partially_resolved" | "resolved">("all");
  const events = useMemo(() => r.events.filter((e) => filter === "all" || e.status === filter), [r.events, filter]);
  const worst = useMemo(() => [...events].sort((a, b) => b.energyAboveCapacityAfterMwh - a.energyAboveCapacityAfterMwh), [events]);
  const maxShare = Math.max(...r.byDerType.map((d) => d.dispatchedMwh), 1e-9);
  return (
    <div className="mt-4">
      <div className="rounded-lg p-3" style={{ border: "1px solid var(--line)", background: "var(--panel-2)" }}>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="chip" style={{ borderColor: "var(--modeled)" }}>Deterministic modeled owner policy · {r.llmCalls} LLM calls</span>
          <span style={{ color: "var(--muted)" }}>${r.incentivePricePerMwh}/MWh ceiling · {r.hoursTested.toLocaleString()} hours tested · {t.events} event windows in {r.clusters.length} joint simulations</span>
        </div>
        <table className="w-full text-sm mt-2 tabular-nums">
          <thead><tr style={{ color: "var(--muted)" }}><th className="text-left font-normal text-xs">Whole history</th><th className="text-right font-normal text-xs">Before</th><th className="text-right font-normal text-xs">After</th></tr></thead>
          <tbody>
            <tr><td>Constrained hours</td><td className="text-right">{t.violationHoursBefore}</td><td className="text-right">{t.violationHoursAfter}</td></tr>
            <tr><td>Energy above capacity</td><td className="text-right">{f1(t.energyAboveCapacityBeforeMwh)} MWh</td><td className="text-right">{f1(t.energyAboveCapacityAfterMwh)} MWh</td></tr>
            <tr><td>Worst deficit</td><td className="text-right">{f1(t.worstDeficitBeforeMw)} MW</td><td className="text-right">{f1(t.worstDeficitAfterMw)} MW</td></tr>
            <tr><td>Events (resolved / partial / unresolved)</td><td className="text-right">{t.events}</td><td className="text-right">{t.resolved} / {t.partiallyResolved} / {t.unresolved}</td></tr>
          </tbody>
        </table>
        <div className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>
          Requested {f1(t.requestedMwh)} · offered {f1(t.offeredMwh)} · validated {f1(t.validatedMwh)} · dispatched {f1(t.dispatchedMwh)} MWh · modeled clearing cost ${t.clearingCost.toFixed(0)} · hash {r.resultHash}
        </div>
      </div>

      <h4 className="text-xs font-semibold mt-3 mb-1">DER contribution (delivered MWh)</h4>
      {r.byDerType.map((d) => (
        <div key={d.type} className="my-1">
          <div className="flex justify-between text-xs"><span>{DER[d.type].label}</span><span className="tabular-nums" style={{ color: "var(--muted)" }}>{f1(d.dispatchedMwh)} MWh · {(d.share * 100).toFixed(0)}% · {d.eventsServed} events</span></div>
          <div style={{ background: "var(--panel-2)", height: 8, borderRadius: 4 }}><div style={{ width: `${(d.dispatchedMwh / maxShare) * 100}%`, background: DER[d.type].color, height: 8, borderRadius: 4 }} /></div>
        </div>
      ))}

      <AggTable title="By year" rows={Object.entries(r.byYear)} />
      <AggTable title="By season" rows={Object.entries(r.bySeason).filter(([, a]) => a.events > 0)} />
      <AggTable title="By event severity (worst pre-dispatch deficit: minor <1, moderate <3, major <6, severe ≥6 MW)" rows={Object.entries(r.bySeverity)} />

      <div className="flex items-center justify-between mt-4">
        <h4 className="text-xs font-semibold">Events (sorted by remaining energy above capacity)</h4>
        <select aria-label="Filter events by status" className="rounded-md px-2 py-1 text-xs" style={{ background: "var(--panel-2)", border: "1px solid var(--line)", color: "var(--text)" }} value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
          <option value="all">all ({r.events.length})</option><option value="unresolved">unresolved</option><option value="partially_resolved">partially resolved</option><option value="resolved">resolved</option>
        </select>
      </div>
      <ul className="mt-1 max-h-72 overflow-y-auto grid gap-1" aria-label="Historical events">
        {worst.slice(0, 40).map((e: HistEvent) => (
          <li key={e.windowId}>
            <button className="w-full text-left rounded-md px-2 py-1 text-xs flex items-center gap-2" style={{ border: "1px solid var(--line)", background: "var(--panel-2)" }} onClick={() => onJump(e.start)} title="Jump to this event in the timeline">
              <span style={{ color: STATUS[e.status].color }} aria-label={e.status.replace("_", " ")}>{STATUS[e.status].glyph}</span>
              <span className="tabular-nums shrink-0">{dt(e.start)}</span>
              <span className="tabular-nums shrink-0" style={{ color: "var(--muted)" }}>{e.hours} h · {e.severity}</span>
              <span className="tabular-nums ml-auto">{f1(e.energyAboveCapacityBeforeMwh)}→{f1(e.energyAboveCapacityAfterMwh)} MWh · {f1(e.worstDeficitBeforeMw)}→{f1(e.worstDeficitAfterMw)} MW</span>
            </button>
          </li>
        ))}
      </ul>
      {worst.length > 40 && <div className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>Showing 40 of {worst.length}.</div>}

      <details className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
        <summary className="cursor-pointer">Verification · {r.checksPassed ? "all checks passed" : "CHECK FAILED"} · state continuity</summary>
        <ul className="mt-1">{r.checks.map((c) => <li key={c.name}>{c.passed ? "✓" : "✗"} {c.name.replace(/_/g, " ")}{c.detail ? ` (${c.detail})` : ""}</li>)}</ul>
        <p className="mt-1">Carried battery energy between joint simulations: max {Math.max(0, ...r.clusters.map((c) => c.carryInBatteryMwh)).toFixed(2)} MWh at a cluster start; windows ≤ {r.mergeGapHours} h apart are simulated together; recovery tail {r.tailHours} h.</p>
      </details>
      <p className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>{r.note}</p>
    </div>
  );
}
