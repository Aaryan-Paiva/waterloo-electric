"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export const SPEEDS = { "1x": 1, "10x": 10, "100x": 100, "1000x": 1000 } as const;
export type SpeedKey = keyof typeof SPEEDS;

/** Advances a cursor through `length` hourly steps. 1x = 1 simulated hour per real second. */
export function usePlayback(length: number) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<SpeedKey>("10x");
  const frac = useRef(0);

  useEffect(() => {
    if (!playing || length <= 1) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000);
      last = now;
      frac.current += dt * SPEEDS[speed];
      const whole = Math.floor(frac.current);
      if (whole > 0) {
        frac.current -= whole;
        setIndex((i) => {
          const n = Math.min(length - 1, i + whole);
          if (n >= length - 1) setPlaying(false);
          return n;
        });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, length]);

  const seek = useCallback((i: number) => setIndex(Math.max(0, Math.min(length - 1, Math.round(i)))), [length]);
  return { index, seek, playing, setPlaying, speed, setSpeed };
}
