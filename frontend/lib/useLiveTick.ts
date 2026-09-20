"use client";

import { useEffect, useState } from "react";
import { LIVE_REFRESH_MS, todayKst } from "./date";

export function useLiveTick(asOf: string): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (asOf !== todayKst()) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") setTick((value) => value + 1);
    }, LIVE_REFRESH_MS);
    return () => clearInterval(timer);
  }, [asOf]);
  return tick;
}
