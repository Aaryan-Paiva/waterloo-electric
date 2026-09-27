import { describe, expect, it } from "vitest";
import type { EventWindow } from "@/types/api";
import { durationLabel, nextWindow, runs, topWindows } from "./events";

const w = (id: string, peak: string, deficit: number, hours = 2): EventWindow => ({
  id, start: peak, end: peak, hours, peakDeficitMw: deficit, peakTimestamp: peak, meanDeficitMw: deficit, energyOverMwh: deficit * hours, days: 1,
});
const ws = [w("a", "2025-06-01T10:00:00-05:00", 2), w("b", "2025-06-24T16:00:00-05:00", 8), w("c", "2025-08-11T15:00:00-05:00", 5.9)];

describe("event navigation", () => {
  it("finds the next and previous window around a timestamp", () => {
    expect(nextWindow(ws, "2025-06-10T00:00:00-05:00", 1)?.id).toBe("b");
    expect(nextWindow(ws, "2025-06-10T00:00:00-05:00", -1)?.id).toBe("a");
    expect(nextWindow(ws, "2025-09-01T00:00:00-05:00", 1)).toBeNull();
    expect(nextWindow(ws, "2025-01-01T00:00:00-05:00", -1)).toBeNull();
  });
  it("ranks windows by worst deficit", () => {
    expect(topWindows(ws, 2).map((x) => x.id)).toEqual(["b", "c"]);
  });
});

describe("helpers", () => {
  it("groups contiguous constrained hours", () => {
    expect(runs([false, true, true, false, true, false, true])).toEqual([[1, 2], [4, 4], [6, 6]]);
    expect(runs([false, false])).toEqual([]);
  });
  it("labels durations", () => {
    expect(durationLabel(1)).toBe("1 h");
    expect(durationLabel(14)).toBe("14 h");
  });
});
