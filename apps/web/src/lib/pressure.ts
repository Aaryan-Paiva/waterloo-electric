// Capacity-pressure semantics (CLAUDE.md §25.4). Phase 1 has no flexibility, so only the first three apply.
export type PressureState = "normal" | "approaching" | "constrained";

export const APPROACHING_RATIO = 0.85;

export function pressureState(loadMw: number, capacityMw: number): PressureState {
  if (capacityMw <= 0) return "constrained";
  const r = loadMw / capacityMw;
  if (r > 1) return "constrained";
  return r >= APPROACHING_RATIO ? "approaching" : "normal";
}

export const PRESSURE_LABEL: Record<PressureState, string> = {
  normal: "Normal",
  approaching: "Approaching limit",
  constrained: "Constrained",
};
export const PRESSURE_GLYPH: Record<PressureState, string> = { normal: "●", approaching: "▲", constrained: "✖" };
export const PRESSURE_COLOR: Record<PressureState, string> = {
  normal: "var(--ok)",
  approaching: "var(--warn)",
  constrained: "var(--bad)",
};

/** IESO reports in fixed EST; timestamps arrive with a -05:00 offset. Display them as EST, never as browser-local time. */
export function formatEst(iso: string, opts: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short" }): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Etc/GMT+5", ...opts }).format(new Date(iso)) + " EST";
}

/** The 24 hourly values of the day that contains `index` (indexes into an hourly series that starts at midnight). */
export function dayProfile(values: number[], index: number): number[] {
  const start = Math.floor(index / 24) * 24;
  return values.slice(start, start + 24);
}
