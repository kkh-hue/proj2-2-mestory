// 화면 기본 날짜는 UTC가 아니라 KST(Asia/Seoul) 기준이어야 한다 —
// toISOString()은 UTC라 KST 자정~09시에 "어제"가 나온다. en-CA 로케일은 YYYY-MM-DD 형식이다.
export function todayKst(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" }).format(new Date());
}
