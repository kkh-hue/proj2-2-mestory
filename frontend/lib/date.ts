// 화면 기본 날짜는 UTC가 아니라 KST(Asia/Seoul) 기준이어야 한다 —
// toISOString()은 UTC라 KST 자정~09시에 "어제"가 나온다. en-CA 로케일은 YYYY-MM-DD 형식이다.
export function todayKst(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
}

// 기준일이 오늘일 때만 주기적으로 다시 조회하게 하는 신호(tick). 지난 날짜는 시간이 흐르지 않으니
// 갱신하지 않고, 탭이 안 보일 때도 건너뛴다. 화면은 tick을 effect 의존성에 넣어 쓴다.
export const LIVE_REFRESH_MS = 60_000;
