"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, login, signup, type AuthUser } from "../../lib/authApi";
import { saveAccessToken } from "../../lib/authToken";
import { useAuth } from "../../components/AuthProvider";

const fieldStyle = { width: "100%", boxSizing: "border-box" as const, border: "1px solid #d9d6ee", borderRadius: 10, padding: "12px 13px", fontSize: 14 };

export default function LoginPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");
    setUser(null);
    try {
      const auth = mode === "login" ? await login(email, password) : await signup(email, password);
      saveAccessToken(auth.access_token);
      const currentUser = await getMe(auth.access_token);
      await refreshUser();
      setUser(currentUser);
      setMessage(mode === "login" ? "로그인되었습니다." : "회원가입 및 로그인이 완료되었습니다.");
      router.push("/");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "인증 요청에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: "70vh", display: "grid", placeItems: "center", padding: "32px 16px" }}>
      <section style={{ width: "100%", maxWidth: 420, background: "#fff", border: "1px solid #e6e2f4", borderRadius: 20, padding: 28, boxShadow: "0 12px 30px rgba(45,58,90,.08)" }}>
        <div style={{ marginBottom: 24 }}>
          <p style={{ margin: "0 0 8px", color: "#7565d5", fontSize: 12, fontWeight: 800, letterSpacing: ".08em" }}>MESTORY AUTH</p>
          <h1 style={{ margin: 0, color: "#20263a", fontSize: 26 }}> {mode === "login" ? "로그인" : "회원가입"}</h1>
          <p style={{ margin: "8px 0 0", color: "#707990", fontSize: 13 }}>설비 다운타임 분석 서비스를 이용하세요.</p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "grid", gap: 16 }}>
          <label style={{ display: "grid", gap: 7, color: "#4a5468", fontSize: 13, fontWeight: 700 }}>
            이메일
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" style={fieldStyle} />
          </label>
          <label style={{ display: "grid", gap: 7, color: "#4a5468", fontSize: 13, fontWeight: 700 }}>
            비밀번호
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} style={fieldStyle} />
          </label>
          <button type="submit" disabled={loading} style={{ border: 0, borderRadius: 10, padding: "12px 16px", background: "#7565d5", color: "#fff", fontWeight: 800, cursor: loading ? "wait" : "pointer" }}>
            {loading ? "처리 중..." : mode === "login" ? "로그인" : "회원가입"}
          </button>
        </form>

        {message && <p role="status" style={{ margin: "16px 0 0", color: "#2f9b68", fontSize: 13 }}>{message}{user ? ` ${user.email}` : ""}</p>}
        {error && <p role="alert" style={{ margin: "16px 0 0", color: "#c04b4b", fontSize: 13, whiteSpace: "pre-line" }}>{error}</p>}

        <button type="button" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); setMessage(""); }} style={{ width: "100%", marginTop: 18, border: 0, background: "transparent", color: "#7565d5", fontSize: 13, cursor: "pointer" }}>
          {mode === "login" ? "계정이 없으신가요? 회원가입" : "이미 계정이 있으신가요? 로그인"}
        </button>
      </section>
    </main>
  );
}
