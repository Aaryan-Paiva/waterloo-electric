"use client";
import { durationLabel, topWindows } from "@/lib/events";
import { formatEst } from "@/lib/pressure";
import type { CapacityAnalysis } from "@/types/api";

const d = (iso?: string | null) => (iso ? formatEst(iso, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }) : "—");

const day = (iso: string) => formatEst(iso, { year: "numeric", month: "short", day: "numeric" }).replace(" EST", "");

export function AnalysisPanel({ a, hasProject, onJump }: { a: CapacityAnalysis; hasProject: boolean; onJump: (ts: string, windowId?: string) => void }) {
  const constrained = a.feasibility === "constraints_detected";
  const color = constrained ? "var(--bad)" : "var(--ok)";
  const title = !hasProject ? "Baseline within capacity" : constrained ? "Constraint events detected" : "Feasible as-is";
  const glyph = constrained ? "✖" : "●";
  const years = Object.entries(a.byYear);
  const maxYear = Math.max(1, ...years.map(([, v]) => v.constrainedHours));
  return (
    <section className="panel p-4" aria-label="Capacity analysis">
      <div className="rounded-lg p-3" style={{ border: `1px solid ${color}`, background: "var(--panel-2)" }}>
        <div className="font-semibold" style={{ color }}>{glyph} {title}</div>
        <div className="text-xs mt-1" style={{ color: "var(--muted)" }}>
          {constrained
            ? "Before any flexibility. DER agents and the optimizer are not applied yet (later phases), so this is not a feasibility verdict with flexibility."
            : "No tested hour exceeds modeled capacity without any flexibility."}
        </div>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-3 text-sm mt-4">
        <M k="Hours tested" v={a.hoursTested.toLocaleString()} />
        <M k="Constrained hours" v={`${a.constrainedHours.toLocaleString()}`} sub={`${a.percentWithinCapacity.toFixed(2)}% of hours within capacity`} />
        <M k="Affected days" v={String(a.affectedDays)} />
        <M k="Event windows" v={String(a.windowCount)} />
        <M k="Worst deficit" v={`${a.worstDeficitMw.toFixed(1)} MW`} sub={d(a.worstDeficitTimestamp)} />
        <M k="Projected peak" v={`${a.projectedPeakMw.toFixed(1)} MW`} sub={`baseline ${a.baselinePeakMw.toFixed(1)} · capacity ${a.capacityMw}`} />
      </dl>
      <p className="text-xs mt-3" style={{ color: "var(--muted)" }}>Historical period {day(a.historicalStart)} – {day(a.historicalEnd)} · a stress test of historical conditions, not a forecast.</p>

      {years.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold mb-1">Constrained hours by year</h3>
          {years.map(([y, v]) => (
            <div key={y} className="flex items-center gap-2 text-xs my-1">
              <span className="w-10 tabular-nums" style={{ color: "var(--muted)" }}>{y}</span>
              <div className="flex-1 h-2 rounded" style={{ background: "var(--panel-2)" }}><div className="h-2 rounded" style={{ width: `${(v.constrainedHours / maxYear) * 100}%`, background: "var(--bad)" }} /></div>
              <span className="tabular-nums w-24 text-right">{v.constrainedHours} h · {v.affectedDays} d</span>
            </div>
          ))}
        </div>
      )}

      {a.windows.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold mb-1">Worst event windows <span style={{ color: "var(--muted)" }}>(top {Math.min(8, a.windows.length)} of {a.windowCount}) · click to replay</span></h3>
          <table className="w-full text-xs">
            <thead><tr style={{ color: "var(--muted)" }}><th className="text-left font-normal">Starts (EST)</th><th className="text-right font-normal">Duration</th><th className="text-right font-normal">Peak deficit</th></tr></thead>
            <tbody>
              {topWindows(a.windows, 8).map((w) => (
                <tr key={w.id} className="cursor-pointer hover:bg-[var(--panel-2)]" onClick={() => onJump(w.peakTimestamp, w.id)} tabIndex={0}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onJump(w.peakTimestamp, w.id); }}>
                  <td className="py-1">{d(w.start)}</td>
                  <td className="text-right tabular-nums">{durationLabel(w.hours)}</td>
                  <td className="text-right tabular-nums" style={{ color: "var(--bad)" }}>{w.peakDeficitMw.toFixed(1)} MW</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function M({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return <div><dt className="text-xs" style={{ color: "var(--muted)" }}>{k}</dt><dd className="tabular-nums text-base">{v}</dd>{sub && <div className="text-[11px]" style={{ color: "var(--muted)" }}>{sub}</div>}</div>;
}
