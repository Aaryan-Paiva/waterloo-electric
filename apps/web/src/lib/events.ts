import type { EventWindow } from "@/types/api";

/** Timestamps from the API share one fixed offset, so ISO strings compare chronologically. */
export function nextWindow(windows: EventWindow[], ts: string, dir: 1 | -1): EventWindow | null {
  const sorted = [...windows].sort((a, b) => (a.peakTimestamp < b.peakTimestamp ? -1 : 1));
  if (dir === 1) return sorted.find((w) => w.peakTimestamp > ts) ?? null;
  for (let i = sorted.length - 1; i >= 0; i--) if (sorted[i].peakTimestamp < ts) return sorted[i];
  return null;
}

export const topWindows = (windows: EventWindow[], n: number) =>
  [...windows].sort((a, b) => b.peakDeficitMw - a.peakDeficitMw || (a.start < b.start ? -1 : 1)).slice(0, n);

export const durationLabel = (hours: number) => (hours === 1 ? "1 h" : `${hours} h`);

/** Contiguous runs of `true` in a boolean array -> [startIndex, endIndex] pairs (inclusive). */
export function runs(flags: boolean[]): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  let s = -1;
  flags.forEach((f, i) => {
    if (f && s < 0) s = i;
    if (!f && s >= 0) { out.push([s, i - 1]); s = -1; }
  });
  if (s >= 0) out.push([s, flags.length - 1]);
  return out;
}
