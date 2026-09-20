"use client";

import { useEffect, useState } from "react";

// 1초(기본)마다 새 Date를 내려주는 얇은 시계 훅. 데이터를 다시 불러오지 않고,
// "지금 몇 시" 표시나 "몇 분 후 종료" 같은 카운트다운 문구만 화면에서 갱신하는 데 쓴다.
// 실제 상태 전환(정지→정상)은 useLiveTick이 정확한 시각에 서버에 다시 물어봐서 반영한다 —
// 이 훅은 그 사이 화면에 보여줄 "지금까지 몇 초 남았는지"만 계산한다.
export function useNowTick(intervalMs = 1000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}
