"use client";

import AnalysisHistory from "./AnalysisHistory";
import LoginForm from "./LoginForm";
import { useAuth } from "../hooks/useAuth";
import { useAnalysisHistory } from "../hooks/useAnalysisHistory";

/** 기존 페이지에 아직 연결하지 않는 신규 auth/history 조합 패널이다. */
export default function AuthHistoryPanel() {
  const auth = useAuth();
  const history = useAnalysisHistory(auth.token, auth.user?.user_id ?? null);
  if (!auth.isAuthenticated) return <LoginForm onLogin={auth.login} onSignup={auth.signup} />;
  return <section>
    <p>{auth.user?.display_name ?? auth.user?.user_id}님</p>
    <button type="button" onClick={auth.logout}>로그아웃</button>
    <button type="button" onClick={() => void history.load()} disabled={history.isLoading}>분석 기록 불러오기</button>
    {history.error && <p role="alert">{history.error}</p>}
    <AnalysisHistory entries={history.entries} onSelect={(report) => history.setSelectedReport(report)} />
  </section>;
}
