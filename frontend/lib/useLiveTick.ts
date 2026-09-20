"use client";

import { useEffect, useState } from "react";
import { LIVE_REFRESH_MS, todayKst } from "./date";

// 오늘 날짜일 때만 동작한다 — 지난 날짜는 시간이 안 흐르니 자동 갱신도 없다.
//
// 두 가지를 같이 쓴다:
// 1) 60초마다 한 번(heartbeat) — 새로 시작된 다운타임처럼 미리 알 수 없는 변화를 잡는다.
// 2) nextTransitions로 넘긴 시각들 — 화면에 이미 있는 "정지" 설비가 정확히 언제
//    끝나는지 안다면(backend가 active_until로 내려준다), 그 순간에 딱 맞춰 한 번 더
//    불러온다. heartbeat만 쓰면 최대 60초까지 늦게 반영되는데, 이걸 같이 쓰면 그
//    순간 바로("2대 → 1대") 반영된다.
export function useLiveTick(asOf: string, nextTransitions?: (string | null | undefined)[]): number {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (asOf !== todayKst()) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") setTick((value) => value + 1);
    }, LIVE_REFRESH_MS);
    return () => clearInterval(timer);
  }, [asOf]);

  // 배열은 렌더마다 새 참조가 생겨 effect가 매번 다시 도니, 문자열로 바꿔 비교한다.
  const transitionsKey = (nextTransitions ?? []).filter((value): value is string => !!value).join(",");

  useEffect(() => {
    if (asOf !== todayKst() || !transitionsKey) return;
    const now = Date.now();
    const timers = transitionsKey
      .split(",")
      .map((iso) => new Date(iso).getTime())
      // 이미 지난 시각(늦게 도착한 값 등)은 건너뛴다. 너무 먼 미래(1시간+)는 heartbeat가
      // 알아서 잡아 줄 테니 굳이 타이머를 오래 걸어두지 않는다.
      .filter((time) => time > now && time - now < 60 * 60 * 1000)
      .map((time) => setTimeout(() => setTick((value) => value + 1), time - now + 500));
    return () => timers.forEach(clearTimeout);
  }, [asOf, transitionsKey]);

  return tick;
}
