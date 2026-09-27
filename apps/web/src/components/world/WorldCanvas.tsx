"use client";
import { PRESSURE_COLOR, PRESSURE_GLYPH, PRESSURE_LABEL, pressureState } from "@/lib/pressure";

interface Props {
  name: string;
  capacityMw: number;
  netMw: number;
  baselineMw: number;
  projectMw: number;
  baselineDay: number[]; // 24 hourly baseline values of the day being replayed
  projectDay: number[]; // 24 hourly project increments
  hour: number;
  projectLabel?: string | null;
  agentLayer?: AgentLayerItem[];
  optimizedNetMw?: number | null;
  dispatchDay?: number[];
}

export interface AgentLayerItem { type: string; label: string; count: number; participating: number | null; potentialMw: number; note?: string; dispatchMw?: number; dispatching?: number }

const W = 760, H = 470, CX = W / 2, CY = 212, R_IN = 70, R_BAR0 = 90, R_SPAN = 78, CLAMP = 1.25;

/** The living world: the zone, its capacity node, the day's 24 hourly loads as stacked polar bars
 *  (baseline + project, red where net load exceeds capacity), and the hypothetical project node.
 *  Everything drawn maps to model data. DER clusters arrive in later phases. */
export function WorldCanvas({ name, capacityMw, netMw, baselineMw, projectMw, baselineDay, projectDay, hour, projectLabel, agentLayer, optimizedNetMw, dispatchDay }: Props) {
  const shown = optimizedNetMw ?? netMw;
  const state = pressureState(shown, capacityMw);
  const color = PRESSURE_COLOR[state];
  const ratio = Math.min(CLAMP, shown / capacityMw);
  const circ = 2 * Math.PI * (R_IN - 6);
  const capR = R_BAR0 + R_SPAN;
  const angle = (h: number) => ((h + 0.5) / 24) * 2 * Math.PI - Math.PI / 2;
  const rad = (mw: number) => R_BAR0 + R_SPAN * Math.min(CLAMP, mw / capacityMw);
  const pt = (r: number, a: number) => [CX + r * Math.cos(a), CY + r * Math.sin(a)] as const;
  const seg = (h: number, r0: number, r1: number, stroke: string, w: number, op: number) => {
    const a = angle(h), [x1, y1] = pt(r0, a), [x2, y2] = pt(r1, a);
    return <line key={`${h}-${stroke}-${r0}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke={stroke} strokeWidth={w} strokeLinecap="butt" opacity={op} />;
  };
  return (
    <figure className="panel p-2" aria-label={`${name} capacity world`}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-describedby="world-desc">
        <desc id="world-desc">{`${optimizedNetMw != null ? `Optimized net load ${optimizedNetMw.toFixed(1)} (was ${netMw.toFixed(1)})` : `Net load ${netMw.toFixed(1)}`} megawatts (baseline ${baselineMw.toFixed(1)} plus project ${projectMw.toFixed(1)}) against modeled capacity ${capacityMw} megawatts. State: ${PRESSURE_LABEL[state]}.`}</desc>
        <path d="M70 250 C40 150 120 60 250 52 C360 44 470 24 570 70 C690 120 740 220 690 320 C640 410 470 425 350 410 C210 395 100 370 70 250 Z"
          fill="var(--panel-2)" stroke="var(--line)" strokeWidth="1.5" strokeDasharray="6 6" />
        <text x="92" y="86" fill="var(--muted)" fontSize="13">{name} · synthetic zone boundary</text>
        <circle cx={CX} cy={CY} r={capR} fill="none" stroke="var(--bad)" strokeWidth="1.2" strokeDasharray="5 4" opacity=".8" />
        <text x={CX + capR * 0.7} y={CY - capR * 0.72 - 6} fill="var(--bad)" fontSize="11">capacity {capacityMw} MW</text>
        {baselineDay.map((b, h) => {
          const p = projectDay[h] ?? 0, active = h === hour, op = active ? 1 : 0.55, w = active ? 10 : 6;
          const rb = rad(b), rn = rad(b + p);
          return (
            <g key={h}>
              {seg(h, R_BAR0, rb, "var(--accent)", w, op)}
              {p > 0 && seg(h, rb, rn, "var(--hypo)", w, op)}
              {(dispatchDay?.[h] ?? 0) > 0.005 && seg(h, rad(b + p - (dispatchDay?.[h] ?? 0)), rn, "var(--ok)", w + 3, 1)}
              {b + p - (dispatchDay?.[h] ?? 0) > capacityMw && seg(h, Math.max(rad(capacityMw), R_BAR0), rad(b + p - (dispatchDay?.[h] ?? 0)), "var(--bad)", w + 2, 1)}
            </g>
          );
        })}
        {[0, 6, 12, 18].map((h) => { const [x, y] = pt(capR + 30, (h / 24) * 2 * Math.PI - Math.PI / 2); return <text key={h} x={x} y={y + 4} fill="var(--muted)" fontSize="11" textAnchor="middle">{String(h).padStart(2, "0")}h</text>; })}
        <circle cx={CX} cy={CY} r={R_IN} fill="var(--panel)" stroke="var(--line)" strokeWidth="2" />
        <circle cx={CX} cy={CY} r={R_IN - 6} fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${circ * 0.94 * Math.min(1, ratio)} ${circ}`} transform={`rotate(-90 ${CX} ${CY})`} style={{ transition: "stroke-dasharray .25s" }} />
        <text x={CX} y={CY - 8} textAnchor="middle" fill="var(--text)" fontSize="26" fontWeight="700">{shown.toFixed(1)}</text>
        <text x={CX} y={CY + 10} textAnchor="middle" fill="var(--muted)" fontSize="12">{optimizedNetMw != null ? `optimized · was ${netMw.toFixed(1)}` : `MW of ${capacityMw} MW`}</text>
        <text x={CX} y={CY + 30} textAnchor="middle" fill={color} fontSize="12" fontWeight="600">{PRESSURE_GLYPH[state]} {PRESSURE_LABEL[state]}</text>
        {/* modeled DER agent layer: real counts and potential, not decorative */}
        {(agentLayer ?? []).map((a, i) => {
          const y = 118 + i * 58, dispatched = (a.dispatchMw ?? 0) > 0.005, live = dispatched || (netMw > capacityMw && a.potentialMw > 0);
          return (
            <g key={a.type} aria-label={`${a.label}: ${a.count} agents`}>
              <line x1={148} y1={y + 24} x2={CX - R_IN} y2={CY} stroke="var(--accent)" strokeWidth={live ? 1.6 : 0.8} strokeDasharray="3 4" opacity={live ? 0.9 : 0.25} />
              <rect x={22} y={y} width={126} height={50} rx={9} fill="var(--panel)" stroke={dispatched ? "var(--ok)" : live ? "var(--accent)" : "var(--line)"} strokeWidth={live ? 2 : 1} />
              <text x={32} y={y + 16} fill="var(--text)" fontSize="12" fontWeight="600">{a.label}</text>
              <text x={32} y={y + 30} fill="var(--muted)" fontSize="10.5">{a.participating === null ? `${a.count} clusters` : `${a.participating}/${a.count} participating`}</text>
              <text x={32} y={y + 43} fill={dispatched ? "var(--ok)" : live ? "var(--accent)" : "var(--muted)"} fontSize="10.5" fontWeight={live ? 600 : 400}>{dispatched ? `▼ ${a.dispatchMw!.toFixed(1)} MW dispatched${a.dispatching === undefined ? "" : ` · ${a.dispatching} agent${a.dispatching === 1 ? "" : "s"}`}` : (a.note ?? `${a.potentialMw.toFixed(1)} MW potential`)}</text>
              <text x={140} y={y + 14} textAnchor="end" fill="var(--modeled)" fontSize="9">◇ Modeled</text>
            </g>
          );
        })}
        {/* hypothetical project node */}
        <line x1={CX + R_IN} y1={CY + 30} x2={572} y2={368} stroke="var(--hypo)" strokeWidth="1.5" strokeDasharray="4 4" opacity={projectLabel ? 1 : 0.35} />
        <rect x={572} y={344} width={150} height={56} rx={10} fill="var(--panel)" stroke="var(--hypo)" strokeWidth="1.5" strokeDasharray={projectLabel ? "0" : "5 4"} opacity={projectLabel ? 1 : 0.6} />
        <text x={647} y={366} textAnchor="middle" fill="var(--hypo)" fontSize="12" fontWeight="600">{projectLabel ?? "No project yet"}</text>
        <text x={647} y={384} textAnchor="middle" fill="var(--muted)" fontSize="11">{projectLabel ? `✦ Hypothetical · ${projectMw.toFixed(0)} MW now` : "add one in the scenario panel"}</text>
        <text x={CX} y={H - 10} textAnchor="middle" fill="var(--muted)" fontSize="11">
          Bars = today&apos;s 24 hourly loads: baseline (blue) + project (pink), red where net load exceeds capacity · green = dispatched by the optimizer; otherwise agents show potential only
        </text>
      </svg>
    </figure>
  );
}
