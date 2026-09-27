import { describe, expect, it } from "vitest";
import { dayProfile, formatEst, pressureState } from "./pressure";

describe("pressureState", () => {
  it("classifies against modeled capacity", () => {
    expect(pressureState(50, 90)).toBe("normal");
    expect(pressureState(76.5, 90)).toBe("approaching"); // exactly 85%
    expect(pressureState(90, 90)).toBe("approaching");
    expect(pressureState(90.1, 90)).toBe("constrained");
    expect(pressureState(10, 0)).toBe("constrained");
  });
});

describe("dayProfile", () => {
  it("returns the 24 values of the containing day", () => {
    const v = Array.from({ length: 72 }, (_, i) => i);
    expect(dayProfile(v, 30)).toEqual(v.slice(24, 48));
    expect(dayProfile(v, 0)).toHaveLength(24);
  });
});

describe("formatEst", () => {
  it("shows fixed EST regardless of browser timezone", () => {
    expect(formatEst("2025-07-01T00:00:00-05:00", { hour: "2-digit", minute: "2-digit", hour12: false })).toBe("00:00 EST");
  });
});
