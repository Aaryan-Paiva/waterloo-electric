import type { Phase } from "@/components/iso/scene";
import type { SandboxRun } from "@/lib/sandbox";

/** 0 = day, 1 = full night, ramping through dusk and dawn. */
export const nightOf = (h: number) => (h >= 21 || h < 5 ? 1 : h >= 18 ? (h - 17) / 4 : h < 7 ? (7 - h) / 2.5 : 0);
export const hourLabel = (h: number) => `${h % 12 || 12} ${h < 12 ? "am" : "pm"}`;

/** What the town should look like right now. Everything comes from the recorded run; nothing is invented client-side. */
export function derivePhase(o: { run: SandboxRun | null; placed: boolean; finished: boolean; cleared: boolean; capacity: number }): Phase {
  const { run, placed, finished, cleared, capacity } = o;
  if (!run) return placed ? "stress" : "calm";
  if (finished) return run.remainingMw > 0.05 || (!run.hasOverload && run.loadBeforeMw > capacity) ? "stress" : "balanced";
  return cleared ? "balancing" : "stress";
}

/** The load the gauge shows while the script plays: before, then falling as each dispatch step is revealed, then the final value. */
export function gaugeLoad(o: { run: SandboxRun | null; placed: boolean; finished: boolean; lastDispatchLoad?: number | null; base: number; dcMw: number }): number {
  const { run, placed, finished, lastDispatchLoad, base, dcMw } = o;
  if (run) return finished ? run.loadAfterMw : lastDispatchLoad ?? run.loadBeforeMw;
  return placed ? base + dcMw : base;
}

/** Plain-language delta shown after the user edits something and re-runs. */
export function changeNote(prev: { absorbed: number; remaining: number } | null, run: SandboxRun): string | null {
  if (!prev || !run.hasOverload) return null;
  const d = run.absorbedMw - prev.absorbed;
  if (Math.abs(d) < 0.05) return "No change from the previous run.";
  return `Absorbs ${Math.abs(d).toFixed(1)} MW ${d > 0 ? "more" : "less"} than the previous run (${prev.absorbed.toFixed(1)} MW).`;
}
