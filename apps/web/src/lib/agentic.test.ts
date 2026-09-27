import { describe, expect, it } from "vitest";
import { ownerLiveStatus, traceLine } from "./agentic";
import type { TraceEvent } from "@/types/api";

const t = (seq: number, type: string, ownerId: string | null, payload: Record<string, unknown> = {}): TraceEvent => ({ seq, type, ownerId, payload });
const trace = [
  t(0, "request.created", null, { peakRequestedMw: 8, requestedMwh: 75.7, incentivePricePerMwh: 80 }),
  t(1, "owner.evaluating", "o1"), t(2, "owner.offer_submitted", "o1", { peakMw: 1.2, pricePerMwh: 70 }),
  t(3, "validation.failed", "o1", { violation: "insufficient_usable_energy" }), t(4, "owner.revising", "o1"), t(5, "offer.accepted", "o1", { peakMw: 0.8, mwh: 3.2 }),
  t(6, "owner.declined", "o2", { reasonCode: "incentive_below_minimum" }),
];

describe("ownerLiveStatus", () => {
  it("reveals only events up to n", () => {
    expect(ownerLiveStatus(trace, 2).o1.label).toBe("Evaluating…");
    expect(ownerLiveStatus(trace, 4).o1.label).toBe("Physical validation failed");
    expect(ownerLiveStatus(trace, 4).o1.detail).toBe("insufficient usable energy");
    expect(ownerLiveStatus(trace, 5).o1.label).toBe("Revising…");
  });
  it("shows final outcomes", () => {
    const s = ownerLiveStatus(trace, trace.length);
    expect(s.o1.label).toBe("Accepted");
    expect(s.o2).toMatchObject({ label: "Declined", detail: "incentive below minimum" });
  });
});

describe("traceLine", () => {
  it("describes the request", () => expect(traceLine(trace[0], [])).toContain("8.0 MW"));
});
