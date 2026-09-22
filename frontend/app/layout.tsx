// 전체 페이지 레이아웃 (F-07). 담당: 강경희
// 사이드바(대시보드/다운타임 분석/리포트/설비 관리/알림) + 각 페이지 콘텐츠 구조
import type { ReactNode } from "react";
import AppShell from "../components/AppShell";
import { AuthGate, AuthProvider, useAuth } from "../components/AuthProvider";
import "./globals.css";

export const metadata = { title: "MESTORY" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <AuthProvider>
          <AuthLayout>{children}</AuthLayout>
        </AuthProvider>
      </body>
    </html>
  );
}

function AuthLayout({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  return (
    <AuthGate>
      {loading || !isAuthenticated ? children : <AppShell>{children}</AppShell>}
    </AuthGate>
  );
}
