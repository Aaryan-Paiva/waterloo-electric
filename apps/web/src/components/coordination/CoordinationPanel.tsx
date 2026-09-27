"use client";
import { Area, Bar, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ProvenanceBadge } from "@/components/world/ProvenanceBadges";
import { formatEst } from "@/lib/pressure";
import type { CoordinationResult, CoordStatus, EventWindow } from "@/types/api";

const STATUS: Record<CoordStatus, { label: string; glyph: string; color: string }> = {
  resolved: { label: "Resolved", glyph: "●", color: "var(--ok)" },
  partially_resolved: { label: "Partially resolved", glyph: "◐", color: "var(--warn)" },
  unresolved: { label: "Unresolved", glyph: "✖", color: "var(--bad)" },
};
export const MODE_STYLE: Record<string, { letter: string; color: string }> = {
  discharging: { letter: "D", color: "var(--accent)" }, charging: { letter: "C", color: "#7aa2d6" },
  deferring: { letter: "F", color: "var(--ok)" }, recovering: { letter: "R", color: "var(--warn)" },
  shedding: { letter: "S", color: "var(--hypo)" }, rebound: { letter: "B", color: "var(--muted)" }, idle: { letter: "·", color: "transparent" },
};
const tip = { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--text)", fontSize: 12 };
const hh = (iso: string) => formatEst(iso, { month: "short", day: "numeric", hour: "2-digit", hour12: false }).replace(" EST", "");
const dt = (iso: string) => formatEst(iso, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

interface Props {
  result: CoordinationResult | null;
  stale: boolean;
  busy: boolean;
  error: string | null;
  activeWindow: EventWindow | null;
  hasProject: boolean;
  cursorTs: string;
  onCoordinate: () => void;
  onClear: () => void;
}

export function CoordinationPanel({ result, stale, busy, error, activeWindow, hasProject, cursorTs, onCoordinate, onClear }: Props) {
  return (
    <section className="panel p-4" aria-label="DER coordination">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Coordinate DERs <span className="text-xs font-normal" style={{ color: "var(--muted)" }}>· single event</span></h2>
        <div className="flex gap-1"><ProvenanceBadge type="derived" /><ProvenanceBadge type="modeled" /></div>
      </div>
      <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>OR-Tools dispatches only enrolled, available batteries, EV fleets and buildings across one event window (plus a recovery tail). Solar stays informational.</p>
      <button className="btn mt-3 w-full" style={{ borderColor: "var(--accent)" }} disabled={!activeWindow || busy || !hasProject} onClick={onCoordinate}>
        {busy ? "Optimizing…" : activeWindow ? `⚡ Coordinate DERs · ${dt(activeWindow.start)} → ${activeWindow.hours} h event` : hasProject ? "Move the cursor into a capacity event, or pick one from the list" : "Add a project to create capacity events"}
      </button>
      {error && <p className="text-xs mt-2" style={{ color: "var(--bad)" }}>{error}</p>}
      {result && <Result r={result} stale={stale} cursorTs={cursorTs} onClear={onClear} />}
    </section>
  );
}

export function Result({ r, stale, cursorTs, onClear }: { r: CoordinationResult; stale: boolean; cursorTs: string; onClear: () => void }) {
  const st = STATUS[r.status];
  const rows = r.hourly.map((h) => ({ label: hh(h.timestamp), pre: h.preDispatchNetMw, opt: h.optimizedNetMw, bat: h.batteryReductionMw, ev: h.evReductionMw, bld: h.buildingReductionMw }));
  const top = Math.ceil(Math.max(r.capacityMw * 1.05, ...rows.map((x) => x.pre * 1.02)) / 5) * 5;
  const low = Math.floor(Math.min(...rows.map((x) => Math.min(x.opt, x.pre))) / 10) * 10;
  const dispatching = r.agents.filter((a) => a.included && a.energyMwh > 0.001).sort((a, b) => b.energyMwh - a.energyMwh);
  const w = r.window;
  return (
    <div className="mt-3">
      {stale && <div className="text-xs rounded p-2 mb-2" style={{ border: "1px solid var(--warn)", color: "var(--warn)" }}>▲ Scenario or participation changed since this run: coordinate again.</div>}
      <div className="rounded-lg p-3" style={{ border: `1px solid ${st.color}`, background: "var(--panel-2)", opacity: stale ? 0.6 : 1 }}>
        <div className="font-semibold" style={{ color: st.color }}>{st.glyph} Event {st.label.toLowerCase()}</div>
        <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>{r.statusReason}</div>
      </div>
      <table className="w-full text-xs mt-3">
        <thead><tr style={{ color: "var(--muted)" }}><th className="text-left font-normal">In the event window</th><th className="text-right font-normal">Before</th><th className="text-right font-normal">After</th></tr></thead>
        <tbody className="tabular-nums">
          <tr><td className="py-0.5">Violation hours</td><td className="text-right">{w.violationHoursBefore}</td><td className="text-right">{w.violationHoursAfter}</td></tr>
          <tr><td className="py-0.5">Energy above capacity</td><td className="text-right">{w.energyAboveCapacityBeforeMwh.toFixed(1)} MWh</td><td className="text-right">{w.energyAboveCapacityAfterMwh.toFixed(1)} MWh</td></tr>
          <tr><td className="py-0.5">Worst deficit</td><td className="text-right">{w.worstDeficitBeforeMw.toFixed(1)} MW</td><td className="text-right">{w.worstDeficitAfterMw.toFixed(1)} MW</td></tr>
          <tr><td className="py-0.5">Recovery tail ({r.tailHours} h) violations</td><td className="text-right">{r.tail.violationHoursBefore}</td><td className="text-right">{r.tail.violationHoursAfter}</td></tr>
        </tbody>
      </table>
      <div className="text-xs mt-2" style={{ color: "var(--muted)" }}>
        Peak dispatch {r.peakDispatchMw.toFixed(1)} MW · energy: batteries {(r.dispatchedEnergyMwh.battery ?? 0).toFixed(1)}, EV {(r.dispatchedEnergyMwh.ev_fleet ?? 0).toFixed(1)}, buildings {(r.dispatchedEnergyMwh.building ?? 0).toFixed(1)} MWh · {r.includedAgents}/{r.participatingAgents} {r.mode === "agentic" ? "assets with validated offers" : "enrolled agents"} dispatched
      </div>

      <h3 className="text-xs font-semibold mt-4 mb-1">Before vs after (event + recovery tail)</h3>
      <div style={{ height: 190 }} role="img" aria-label="Net load before and after coordination compared with capacity">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
            <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 9 }} interval={Math.max(1, Math.floor(rows.length / 6))} />
            <YAxis domain={[low, top]} tick={{ fill: "var(--muted)", fontSize: 9 }} unit=" MW" width={50} />
            <Tooltip contentStyle={tip} formatter={(v, n) => [`${Number(v).toFixed(2)} MW`, n === "pre" ? "Before (pre-dispatch)" : "After (optimized)"]} />
            <Area type="monotone" dataKey="pre" stroke="var(--hypo)" fill="var(--hypo)" fillOpacity={0.12} isAnimationActive={false} dot={false} />
            <Line type="monotone" dataKey="opt" stroke="var(--ok)" strokeWidth={2.2} isAnimationActive={false} dot={false} />
            <ReferenceLine y={r.capacityMw} stroke="var(--bad)" strokeDasharray="5 4" label={{ value: `capacity ${r.capacityMw} MW`, fill: "var(--bad)", fontSize: 10, position: "insideTopRight" }} />
            <ReferenceLine x={hh(cursorTs)} stroke="var(--text)" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[11px]" style={{ color: "var(--muted)" }}>Pink = before dispatch · green = after · gap above the dashed line = remaining deficit</div>

      <h3 className="text-xs font-semibold mt-3 mb-1">Dispatch by type (MW; negative = recharge, recovery or rebound)</h3>
      <div style={{ height: 120 }} role="img" aria-label="Hourly dispatch by resource type">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 4, right: 8, left: -12, bottom: 0 }} stackOffset="sign">
            <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 9 }} interval={Math.max(1, Math.floor(rows.length / 6))} />
            <YAxis tick={{ fill: "var(--muted)", fontSize: 9 }} width={50} />
            <Tooltip contentStyle={tip} formatter={(v, n) => [`${Number(v).toFixed(2)} MW`, String(n)]} />
            <Bar dataKey="bat" name="Batteries" stackId="s" fill="var(--accent)" isAnimationActive={false} />
            <Bar dataKey="ev" name="EV fleets" stackId="s" fill="var(--ok)" isAnimationActive={false} />
            <Bar dataKey="bld" name="Buildings" stackId="s" fill="var(--hypo)" isAnimationActive={false} />
            <ReferenceLine y={0} stroke="var(--line)" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {dispatching.length > 0 && (
        <div className="mt-3">
          <h3 className="text-xs font-semibold mb-1">Agent dispatch ({dispatching.length} dispatched)</h3>
          <div className="text-[10px] mb-1" style={{ color: "var(--muted)" }}>D discharge · C charge · F defer · R recover · S shed · B rebound</div>
          {dispatching.slice(0, 10).map((a) => (
            <div key={a.agentId} className="my-1">
              <div className="flex justify-between text-xs"><span className="truncate">{a.name}</span><span className="tabular-nums" style={{ color: "var(--muted)" }}>peak {a.peakMw.toFixed(2)} MW · {a.energyMwh.toFixed(2)} MWh</span></div>
              <div className="flex" role="img" aria-label={`${a.name} hourly dispatch modes`}>
                {a.mode.map((m, i) => { const s = MODE_STYLE[m] ?? MODE_STYLE.idle; return <span key={i} title={`${hh(r.hourly[i].timestamp)} ${m} ${a.dispatchMw[i].toFixed(2)} MW`} className="text-[8px] text-center flex-1" style={{ background: s.color, color: "#06121f", height: 12, lineHeight: "12px", borderRight: "1px solid var(--panel-2)" }}>{s.letter}</span>; })}
              </div>
            </div>
          ))}
        </div>
      )}
      <details className="mt-3 text-xs" style={{ color: "var(--muted)" }}>
        <summary className="cursor-pointer">Verification · {r.checksPassed ? "all physical constraints passed" : "CONSTRAINT VIOLATION"} · reconciled {r.reconciled ? "✓" : "✗"}</summary>
        <ul className="mt-1">{r.checks.map((c) => <li key={c.name}>{c.passed ? "✓" : "✗"} {c.name.replace(/_/g, " ")} (max {c.maxViolation.toExponential(1)})</li>)}</ul>
        <p className="mt-1">Solver {String(r.solver.name)} · {String(r.solver.status)} · deterministic. Result is Derived from Modeled resources.</p>
      </details>
      <p className="text-[11px] mt-2" style={{ color: "var(--muted)" }}>{r.note}</p>
      <button className="btn mt-2 text-xs" onClick={onClear}>Clear result</button>
    </div>
  );
}
