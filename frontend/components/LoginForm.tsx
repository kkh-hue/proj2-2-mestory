"use client";

import { useState } from "react";
import type { LoginCredentials, LoginHandler } from "../types/authHistory";

type Props = { onLogin?: LoginHandler; onSignup?: LoginHandler };

/** 실제 handler를 props로 받을 때만 인증 요청을 수행한다. */
export default function LoginForm({ onLogin, onSignup }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function run(handler?: LoginHandler) {
    if (!handler || submitting) return;
    setError(""); setSubmitting(true);
    try { await handler({ email, password }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "로그인에 실패했습니다."); }
    finally { setSubmitting(false); }
  }

  return <section aria-labelledby="login-title">
    <h2 id="login-title">로그인</h2>
    <form onSubmit={(event) => { event.preventDefault(); void run(onLogin); }}>
      <label>이메일<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></label>
      <label>비밀번호<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required minLength={12} /></label>
      <button type="submit" disabled={!onLogin || submitting}>{submitting ? "로그인 중" : "로그인"}</button>
      {onSignup && <button type="button" disabled={submitting} onClick={() => void run(onSignup)}>회원가입</button>}
    </form>
    {!onLogin && <p>인증 서비스가 아직 연결되지 않았습니다.</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
