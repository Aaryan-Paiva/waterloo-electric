import { describe, expect, it } from "vitest";
import { changeNote, derivePhase, gaugeLoad, hourLabel, nightOf } from "./sandboxLogic";
import type { SandboxRun } from "./sandbox";

const run = (o: Partial<SandboxRun> = {}) => ({ hasOverload: true, loadBeforeMw: 98, loadAfterMw: 90, remainingMw: 0, absorbedMw: 8, overloadMw: 8, ...o }) as SandboxRun;

describe("time of day", () => {
  it("is dark at night, light at midday, ramping at dusk", () => {
    expect(nightOf(2)).toBe(1); expect(nightOf(13)).toBe(0); expect(nightOf(19)).toBeGreaterThan(0); expect(nightOf(19)).toBeLessThan(1);
    expect(hourLabel(0)).toBe("12 am"); expect(hourLabel(14)).toBe("2 pm");
  });
});
describe("phase", () => {
  it("calm with nothing placed, stress once placed, balancing after the optimizer starts, balanced when nothing remains", () => {
    expect(derivePhase({ run: null, placed: false, finished: false, cleared: false, capacity: 90 })).toBe("calm");
    expect(derivePhase({ run: null, placed: true, finished: false, cleared: false, capacity: 90 })).toBe("stress");
    expect(derivePhase({ run: run(), placed: true, finished: false, cleared: true, capacity: 90 })).toBe("balancing");
    expect(derivePhase({ run: run(), placed: true, finished: true, cleared: true, capacity: 90 })).toBe("balanced");
  });
  it("stays in stress when overload remains, and when there was no run overload but the load is over capacity", () => {
    expect(derivePhase({ run: run({ remainingMw: 2.6 }), placed: true, finished: true, cleared: true, capacity: 90 })).toBe("stress");
    expect(derivePhase({ run: run({ hasOverload: false, loadBeforeMw: 84 }), placed: true, finished: true, cleared: false, capacity: 90 })).toBe("balanced");
  });
});
describe("gauge", () => {
  it("shows base, then base + data centre, then the recorded values", () => {
    expect(gaugeLoad({ run: null, placed: false, finished: false, base: 78, dcMw: 20 })).toBe(78);
    expect(gaugeLoad({ run: null, placed: true, finished: false, base: 78, dcMw: 20 })).toBe(98);
    expect(gaugeLoad({ run: run(), placed: true, finished: false, base: 78, dcMw: 20 })).toBe(98);
    expect(gaugeLoad({ run: run(), placed: true, finished: false, lastDispatchLoad: 94.5, base: 78, dcMw: 20 })).toBe(94.5);
    expect(gaugeLoad({ run: run(), placed: true, finished: true, base: 78, dcMw: 20 })).toBe(90);
  });
});
describe("what changed", () => {
  it("describes the difference honestly and stays quiet without a previous run", () => {
    expect(changeNote(null, run())).toBeNull();
    expect(changeNote({ absorbed: 3.1, remaining: 4.9 }, run({ absorbedMw: 6.4 }))).toContain("3.3 MW more");
    expect(changeNote({ absorbed: 8, remaining: 0 }, run({ absorbedMw: 5 }))).toContain("less");
    expect(changeNote({ absorbed: 8, remaining: 0 }, run())).toBe("No change from the previous run.");
    expect(changeNote({ absorbed: 1, remaining: 0 }, run({ hasOverload: false }))).toBeNull();
  });
});
