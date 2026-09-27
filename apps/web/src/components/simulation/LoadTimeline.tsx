"use client";
import { Area, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { runs } from "@/lib/events";
import { formatEst } from "@/lib/pressure";

export interface Row { label: string; baseline: number; net: number; opt?: number }
export interface DayRow { ts: string; label: string; baseline: number; net: number; over: number }

const tip = { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--text)", fontSize: 12 };
const nameOf: Record<string, string> = { baseline: "Baseline", net: "Baseline + project", peak: "Daily peak" };

/** Hourly detail (±3.5 days): baseline area, baseline + project line, red shading where net load exceeds capacity. */
export function DetailTimeline({ rows, capacityMw, cursorLabel, hasProject }: { rows: Row[]; capacityMw: number; cursorLabel: string; hasProject: boolean }) {
  const hasOpt = rows.some((r) => r.opt !== undefined);
  const over = runs(rows.map((r) => (r.opt ?? r.net) > capacityMw));
  const top = Math.ceil(Math.max(capacityMw * 1.1, ...rows.map((r) => r.net * 1.03)) / 10) * 10;
  return (
    <div className="panel p-3">
      <div className="text-xs mb-1" style={{ color: "var(--muted)" }}>Hourly load vs modeled capacity · baseline is derived{hasProject ? " · red shading = load above capacity (after coordination when shown)" : ""}</div>
      <div style={{ height: 220 }} role="img" aria-label="Hourly baseline and project load compared with modeled capacity around the current time">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
            <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 10 }} interval={11} />
            <YAxis domain={[0, top]} tick={{ fill: "var(--muted)", fontSize: 10 }} unit=" MW" width={54} />
            <Tooltip contentStyle={tip} formatter={(v, n) => [`${Number(v).toFixed(1)} MW`, n === "opt" ? "After DER coordination" : (nameOf[String(n)] ?? String(n))]} />
            {over.map(([a, b], i) => <ReferenceArea key={i} x1={rows[a].label} x2={rows[b].label} fill="var(--bad)" fillOpacity={0.22} strokeOpacity={0} />)}
            <Area type="monotone" dataKey="baseline" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.18} isAnimationActive={false} dot={false} />
            {hasProject && <Line type="monotone" dataKey="net" stroke="var(--hypo)" strokeWidth={2} isAnimationActive={false} dot={false} />}
            {hasOpt && <Line type="monotone" dataKey="opt" stroke="var(--ok)" strokeWidth={2.2} isAnimationActive={false} dot={false} connectNulls={false} />}
            <ReferenceLine y={capacityMw} stroke="var(--bad)" strokeDasharray="5 4" label={{ value: `Modeled capacity ${capacityMw} MW`, fill: "var(--bad)", fontSize: 11, position: "insideTopRight" }} />
            <ReferenceLine x={cursorLabel} stroke="var(--text)" strokeWidth={1.5} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Whole-history overview (daily peaks). Red dots = days with at least one constrained hour. Click to jump. */
export function OverviewTimeline({ rows, capacityMw, onPick, cursorLabel, hasProject }: { rows: DayRow[]; capacityMw: number; onPick: (ts: string) => void; cursorLabel: string; hasProject: boolean }) {
  const top = Math.ceil(Math.max(capacityMw * 1.1, ...rows.map((r) => r.net * 1.03)) / 10) * 10;
  return (
    <div className="panel p-3">
      <div className="text-xs mb-1" style={{ color: "var(--muted)" }}>Daily peak across the historical period · click to jump{hasProject ? " · red dots = days over capacity" : ""}</div>
      <div style={{ height: 160 }} role="img" aria-label="Daily peak load across the historical period compared with modeled capacity">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}
            onClick={(s: unknown) => { const st = s as { activeIndex?: number | string } | null; if (st?.activeIndex != null) { const r = rows[Number(st.activeIndex)]; if (r) onPick(r.ts); } }}>
            <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 10 }} interval={Math.max(1, Math.floor(rows.length / 8))} />
            <YAxis domain={[0, top]} tick={{ fill: "var(--muted)", fontSize: 10 }} unit=" MW" width={54} />
            <Tooltip contentStyle={tip} formatter={(v, n) => [`${Number(v).toFixed(1)} MW`, n === "baseline" ? "Baseline daily peak" : "Net daily peak"]} />
            <Area type="monotone" dataKey="baseline" stroke="var(--derived)" fill="var(--derived)" fillOpacity={0.2} isAnimationActive={false} dot={false} />
            {hasProject && (
              <Line type="monotone" dataKey="net" stroke="var(--hypo)" strokeWidth={1} isAnimationActive={false}
                dot={(p: { cx?: number; cy?: number; payload?: DayRow; index?: number }) => p.payload && p.payload.over > 0 && p.cx != null && p.cy != null
                  ? <circle key={p.index} cx={p.cx} cy={p.cy} r={2.4} fill="var(--bad)" /> : <g key={p.index} />} />
            )}
            <ReferenceLine y={capacityMw} stroke="var(--bad)" strokeDasharray="5 4" />
            <ReferenceLine x={cursorLabel} stroke="var(--text)" strokeWidth={1.5} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export const dayLabel = (iso: string) => formatEst(iso, { year: "2-digit", month: "short", day: "numeric" }).replace(" EST", "");
export const hourLabel = (iso: string) => formatEst(iso, { month: "short", day: "numeric", hour: "2-digit", hour12: false }).replace(" EST", "");
