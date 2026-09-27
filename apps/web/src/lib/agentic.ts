import type { AgenticRun, OwnerAgent, TraceEvent } from "@/types/api";

export type Live = { label: string; tone: "muted" | "ok" | "warn" | "bad" | "accent"; detail?: string };

const num = (v: unknown) => (typeof v === "number" ? v : 0);

/** What each owner looks like after the first `n` trace events. Purely derived from the recorded backend trace (nothing invented client-side). */
export function ownerLiveStatus(trace: TraceEvent[], n: number): Record<string, Live> {
  const out: Record<string, Live> = {};
  for (const e of trace.slice(0, n)) {
    const id = e.ownerId;
    if (!id) continue;
    const p = e.payload;
    switch (e.type) {
      case "owner.evaluating": out[id] = { label: "Evaluating…", tone: "muted" }; break;
      case "owner.offer_submitted": out[id] = { label: e.payload.revision === 1 ? "Revised offer submitted" : "Offer submitted", tone: "accent", detail: `${num(p.peakMw) ? num(p.peakMw).toFixed(2) + " MW peak · " : ""}$${num(p.pricePerMwh).toFixed(0)}/MWh` }; break;
      case "owner.declined": out[id] = { label: "Declined", tone: "muted", detail: String(p.reasonCode ?? "").replace(/_/g, " ") }; break;
      case "validation.failed": out[id] = { label: "Physical validation failed", tone: "warn", detail: String(p.violation ?? "").replace(/_/g, " ") }; break;
      case "owner.revising": out[id] = { label: "Revising…", tone: "warn", detail: String(p.violation ?? "").replace(/_/g, " ") }; break;
      case "validation.passed": out[id] = { label: "Physically valid", tone: "accent" }; break;
      case "offer.accepted": out[id] = { label: "Accepted", tone: "ok", detail: `${num(p.peakMw).toFixed(2)} MW · ${num(p.mwh).toFixed(1)} MWh` }; break;
      case "offer.priced_out": out[id] = { label: "Counteroffer (above ceiling)", tone: "warn", detail: `asks $${num(p.pricePerMwh).toFixed(0)} vs $${num(p.incentive).toFixed(0)}` }; break;
      case "offer.rejected": out[id] = { label: "Rejected", tone: "bad", detail: String(p.violation ?? "").replace(/_/g, " ") }; break;
      case "agent.dispatched": out[id] = { label: "Dispatched", tone: "ok", detail: `${num(p.mwh).toFixed(1)} MWh · $${num(p.cost).toFixed(0)}` }; break;
      case "provider.fallback": out[id] = { label: "Stub fallback", tone: "warn", detail: "provider failed" }; break;
    }
  }
  return out;
}

/** One human-readable line per trace event for the live feed. */
export function traceLine(e: TraceEvent, owners: OwnerAgent[]): string {
  const name = owners.find((o) => o.id === e.ownerId)?.name ?? "CapacityOS";
  const p = e.payload;
  switch (e.type) {
    case "request.created": return `CapacityOS requested ${num(p.peakRequestedMw).toFixed(1)} MW peak (${num(p.requestedMwh).toFixed(1)} MWh) at $${num(p.incentivePricePerMwh).toFixed(0)}/MWh`;
    case "owner.evaluating": return `${name} evaluating…`;
    case "owner.offer_submitted": return `${name} offered ${num(p.peakMw) ? num(p.peakMw).toFixed(2) + " MW" : "a revised profile"} @ $${num(p.pricePerMwh).toFixed(0)}/MWh`;
    case "owner.declined": return `${name} declined — ${String(p.reasonCode ?? "").replace(/_/g, " ")}`;
    case "validation.passed": return `Physical validation passed — ${name}`;
    case "validation.failed": return `Physical validation FAILED — ${name}: ${String(p.violation ?? "").replace(/_/g, " ")}`;
    case "owner.revising": return `${name} revising once…`;
    case "offer.accepted": return `Offer accepted — ${name} (${num(p.mwh).toFixed(1)} MWh)`;
    case "offer.priced_out": return `${name} priced out ($${num(p.pricePerMwh).toFixed(0)} > $${num(p.incentive).toFixed(0)})`;
    case "offer.rejected": return `Offer rejected — ${name}: ${String(p.violation ?? "").replace(/_/g, " ")}`;
    case "provider.fallback": return `Provider fallback: ${String(p.reason ?? "")}`;
    case "optimizer.started": return `OR-Tools clearing ${num(p.assets)} validated assets…`;
    case "optimizer.completed": return `Optimizer ${String(p.status)} — worst remaining deficit ${num(p.remainingWorstDeficitMw).toFixed(1)} MW`;
    case "agent.dispatched": return `${name} dispatched ${num(p.mwh).toFixed(1)} MWh`;
    case "market.cleared": return `Market cleared — peak dispatch ${num(p.dispatchedPeakMw).toFixed(1)} MW, modeled cost $${num(p.clearingCost).toFixed(0)}`;
    default: return e.type;
  }
}

export const runSummary = (r: AgenticRun) => `${r.market.ownersAccepted}/${r.market.ownersTotal} owners cleared · ${r.market.dispatchedMwh.toFixed(1)} MWh dispatched`;
