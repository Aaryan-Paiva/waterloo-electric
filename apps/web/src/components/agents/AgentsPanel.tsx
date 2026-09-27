"use client";
import { useState } from "react";
import { Line, LineChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { ProvenanceBadge } from "@/components/world/ProvenanceBadges";
import { formatEst } from "@/lib/pressure";
import type { AgentDetail, AgentSummary, AgentType, PopulationPotential, PopulationSummary } from "@/types/api";

export const TYPE_LABEL: Record<AgentType, string> = { battery: "Batteries", ev_fleet: "EV fleets", building: "Flexible buildings", solar: "Solar clusters" };
const RATE: Partial<Record<AgentType, "batteryParticipation" | "evParticipation" | "buildingParticipation">> = { battery: "batteryParticipation", ev_fleet: "evParticipation", building: "buildingParticipation" };
const CAP_TEXT: Record<AgentType, (c: Record<string, number>) => string> = {
  battery: (c) => `${c.powerMw?.toFixed(1)} MW / ${c.energyMwh?.toFixed(1)} MWh`,
  ev_fleet: (c) => `${Math.round(c.vehicles)} vehicles · ${c.maxChargingMw?.toFixed(1)} MW`,
  building: (c) => `${c.peakLoadMw?.toFixed(1)} MW peak load`,
  solar: (c) => `${c.installedMw?.toFixed(1)} MWp`,
};
const SERIES_KEY: Record<AgentType, { key: string; label: string }> = {
  battery: { key: "soc", label: "State of charge" }, ev_fleet: { key: "chargingMw", label: "Charging MW" },
  building: { key: "hvacLoadMw", label: "HVAC load MW" }, solar: { key: "generationMw", label: "Generation MW" },
};
const TYPES: AgentType[] = ["battery", "ev_fleet", "building", "solar"];

interface Props {
  population: PopulationSummary | null;
  potential: PopulationPotential | null;
  agents: AgentSummary[];
  detail: AgentDetail | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  windowHours: number;
  setWindowHours: (h: number) => void;
  onRate: (k: "batteryParticipation" | "evParticipation" | "buildingParticipation", v: number) => void;
  timestamp: string;
}

export function AgentsPanel({ population, potential, agents, detail, selectedId, onSelect, windowHours, setWindowHours, onRate, timestamp }: Props) {
  const [local, setLocal] = useState<Record<string, number>>({});
  if (!population) return <section className="panel p-4"><h2 className="text-sm font-semibold">DER agents</h2><p className="text-xs mt-2" style={{ color: "var(--muted)" }}>Generating the seeded population…</p></section>;
  const names = new Map(agents.map((a) => [a.id, a]));
  const rows = (potential?.agents ?? []).filter((r) => r.type !== "solar").sort((a, b) => b.potentialIfEnrolledMw - a.potentialIfEnrolledMw).slice(0, 8);
  const maxType = Math.max(0.01, ...TYPES.map((t) => potential?.byType[t].potentialIfAllEnrolledMw ?? 0));
  const deficit = potential?.deficitMw ?? 0;
  return (
    <section className="panel p-4" aria-label="DER agents">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">DER agents <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· {population.totalAgents} · seed {population.seed}</span></h2>
        <ProvenanceBadge type="modeled" />
      </div>
      <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>Synthetic flexibility around a baseline that already contains historical consumption and solar. Potential only: nothing is dispatched.</p>

      <div className="mt-3 flex flex-col gap-2">
        {TYPES.map((t) => {
          const s = population.byType[t];
          const k = RATE[t];
          const val = local[t] ?? population.participationRates[t] ?? 0;
          return (
            <div key={t} className="rounded-lg p-2" style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }}>
              <div className="flex items-baseline justify-between text-sm"><span>{TYPE_LABEL[t]} · {s.count}</span>
                <span className="text-xs" style={{ color: "var(--muted)" }}>{k ? `${s.participating}/${s.count} participating` : "not a flexibility participant"}</span></div>
              <div className="text-[11px]" style={{ color: "var(--muted)" }}>{CAP_TEXT[t](s.capacity)}</div>
              {k && (
                <label className="flex items-center gap-2 text-xs mt-1" style={{ color: "var(--muted)" }}>
                  Participation <b style={{ color: "var(--text)" }} className="w-9">{Math.round(val * 100)}%</b>
                  <input type="range" min={0} max={100} step={5} value={Math.round(val * 100)} className="flex-1" aria-label={`${TYPE_LABEL[t]} participation`}
                    onChange={(e) => { const v = Number(e.target.value) / 100; setLocal((p) => ({ ...p, [t]: v })); onRate(k, v); }} />
                </label>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold">Potential flexibility · {formatEst(timestamp, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })}</h3>
          <div className="flex gap-1" role="group" aria-label="Window length">
            {[1, 2, 4].map((h) => <button key={h} className="btn !py-0.5 !px-2 text-xs" aria-pressed={windowHours === h} onClick={() => setWindowHours(h)}>{h} h</button>)}
          </div>
        </div>
        {potential && (
          <>
            {TYPES.map((t) => {
              const p = potential.byType[t];
              return (
                <div key={t} className="flex items-center gap-2 text-xs my-1">
                  <span className="w-28 truncate" title={TYPE_LABEL[t]}>{TYPE_LABEL[t]}</span>
                  <div className="flex-1 h-2 rounded relative" style={{ background: "var(--panel-2)" }} aria-hidden>
                    <div className="absolute h-2 rounded" style={{ width: `${(p.potentialIfAllEnrolledMw / maxType) * 100}%`, background: "var(--accent)", opacity: 0.3 }} />
                    <div className="absolute h-2 rounded" style={{ width: `${(p.potentialMw / maxType) * 100}%`, background: "var(--accent)" }} />
                  </div>
                  <span className="tabular-nums w-28 text-right">{t === "solar" ? "0 · in baseline" : `${p.potentialMw.toFixed(1)} / ${p.potentialIfAllEnrolledMw.toFixed(1)} MW`}</span>
                </div>
              );
            })}
            <div className="text-[11px]" style={{ color: "var(--muted)" }}>Solid = participating now · faded = if every eligible agent enrolled · {windowHours} h sustained</div>
            <div className="rounded-lg p-2 mt-2 text-sm" style={{ border: `1px solid ${deficit > 0 ? "var(--bad)" : "var(--line)"}`, background: "var(--panel-2)" }}>
              <b>{potential.totalPotentialMw.toFixed(1)} MW</b> potential now
              {deficit > 0 ? <> vs deficit <b style={{ color: "var(--bad)" }}>{deficit.toFixed(1)} MW</b> · could cover <b>{potential.coversDeficitPct?.toFixed(0)}%</b> <span className="text-xs" style={{ color: "var(--muted)" }}>(not dispatched)</span></>
                : <span className="text-xs" style={{ color: "var(--muted)" }}> · no capacity deficit at this hour</span>}
              <div className="text-xs" style={{ color: "var(--muted)" }}>If all eligible agents enrolled: {potential.totalIfAllEnrolledMw.toFixed(1)} MW</div>
            </div>
          </>
        )}
      </div>

      {rows.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold mb-1">Most flexible agents now · click to inspect</h3>
          <table className="w-full text-xs">
            <tbody>
              {rows.map((r) => (
                <tr key={r.agentId} className="cursor-pointer hover:bg-[var(--panel-2)]" tabIndex={0} onClick={() => onSelect(r.agentId === selectedId ? null : r.agentId)}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(r.agentId === selectedId ? null : r.agentId); }} aria-selected={r.agentId === selectedId}>
                  <td className="py-1 pr-2">{names.get(r.agentId)?.name ?? r.agentId}</td>
                  <td style={{ color: r.participating ? "var(--ok)" : "var(--muted)" }}>{r.participating ? "● enrolled" : "○ not enrolled"}</td>
                  <td className="text-right tabular-nums">{(r.participating ? r.potentialMw : r.potentialIfEnrolledMw).toFixed(2)} MW{r.participating ? "" : "*"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-[11px]" style={{ color: "var(--muted)" }}>* would offer if enrolled</div>
        </div>
      )}
      {detail && <Inspector d={detail} onClose={() => onSelect(null)} />}
    </section>
  );
}

function Inspector({ d, onClose }: { d: AgentDetail; onClose: () => void }) {
  const s = SERIES_KEY[d.type];
  const series = d.daySeries.map((p, h) => ({ h, v: Number(p.values[s.key] ?? 0) }));
  const hour = new Date(d.state.timestamp).getUTCHours() - 5;
  return (
    <div className="mt-4 rounded-lg p-3" style={{ background: "var(--panel-2)", border: "1px solid var(--line)" }} role="region" aria-label={`Agent ${d.name}`}>
      <div className="flex items-center justify-between gap-2"><b className="text-sm">{d.name}</b><div className="flex items-center gap-2"><ProvenanceBadge type="modeled" /><button className="btn !py-0.5 !px-2 text-xs" onClick={onClose}>Close</button></div></div>
      <div className="text-xs mt-1" style={{ color: d.state.available ? "var(--ok)" : "var(--warn)" }}>
        {d.participating ? "● Enrolled" : "○ Not enrolled"} · {d.state.available ? "available" : `unavailable: ${d.state.unavailableReason}`} · potential {(d.participating ? d.potential.potentialMw : 0).toFixed(2)} MW ({d.potential.limitingFactor.replace(/_/g, " ")})
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs mt-2">
        {Object.entries(d.state.values).filter(([, v]) => v !== null && typeof v !== "object").slice(0, 8).map(([k, v]) => (
          <div key={k}><dt style={{ color: "var(--muted)" }}>{k}</dt><dd className="tabular-nums">{typeof v === "number" ? v : String(v)}</dd></div>
        ))}
      </dl>
      <div className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>{s.label} through the day (at-rest behavior, already in the baseline)</div>
      <div style={{ height: 70 }} role="img" aria-label={`${s.label} across the selected day`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={series} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
            <XAxis dataKey="h" tick={{ fill: "var(--muted)", fontSize: 9 }} interval={5} />
            <YAxis tick={{ fill: "var(--muted)", fontSize: 9 }} width={34} />
            <Line dataKey="v" stroke="var(--accent)" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            <ReferenceLine x={hour} stroke="var(--text)" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
