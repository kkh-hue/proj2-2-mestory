// 전체 페이지 레이아웃 (F-07). 담당: 강경희
// 지금은 배포 파이프라인 확인용 최소 플레이스홀더 — 실제 레이아웃/스타일은 강경희 님이 교체
import type { ReactNode } from "react";
import "./globals.css";

export const metadata = { title: "MESTORY" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
