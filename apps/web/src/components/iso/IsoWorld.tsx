"use client";
import { useEffect, useMemo, useRef } from "react";
import { H, W, buildScene, drawFrame, type Look, type PlacedLoad, type SimState } from "./scene";

interface Props { season: Look["season"]; night: number; phase: SimState["phase"]; active: SimState["active"]; loads: { id: string; kind: PlacedLoad["kind"]; lot: number }[]; dragging: boolean; hoverLot: number | null }

/** The isometric town. Canvas 2D at 1440x900 logical pixels (CSS-scaled by the stage). Effects are bound to props only. */
export function IsoWorld({ season, night, phase, active, loads, dragging, hoverLot }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const scene = useMemo(() => buildScene(season), [season]);
  const live = useRef({ season, night, phase, active, loads, dragging, hoverLot });
  useEffect(() => { live.current = { season, night, phase, active, loads, dragging, hoverLot }; }, [season, night, phase, active, loads, dragging, hoverLot]);
  const rise = useRef<Map<string, number>>(new Map());
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const c = cv.getContext("2d"); if (!c) return;
    let raf = 0, t = 0;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const loop = () => {
      const l = live.current;
      const placed: PlacedLoad[] = l.loads.map((ld) => {
        const cur = rise.current.get(ld.id) ?? (reduced ? 1 : 0);
        const nx = Math.min(1, cur + 0.035); rise.current.set(ld.id, nx);
        return { ...ld, rise: nx };
      });
      for (const k of [...rise.current.keys()]) if (!l.loads.some((ld) => ld.id === k)) rise.current.delete(k);
      t += reduced ? 0 : 1;
      drawFrame(c, scene, { phase: l.phase, active: l.active, loads: placed, t, dragging: l.dragging, hoverLot: l.hoverLot }, { season: l.season, night: l.night });
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [scene]);
  return <canvas ref={ref} width={W} height={H} style={{ position: "absolute", left: 0, top: 0, width: W, height: H, display: "block" }} role="img" aria-label="Isometric town map of the Waterloo demo zone with homes, offices, a depot, batteries and a substation" />;
}
