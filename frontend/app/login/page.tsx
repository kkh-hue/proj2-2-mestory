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
    <main className="mestory-login-screen">
      <style>{`\
        .mestory-login-screen { min-height:100vh; display:grid; place-items:center; overflow:hidden; background:#e9e9fb; }\
        .mestory-login-artboard { position:relative; width:min(100vw, 150vh, 1536px); aspect-ratio:3 / 2; flex:0 0 auto; }\
        .mestory-login-artboard > img { position:absolute; inset:0; width:100%; height:100%; display:block; object-fit:contain; }\
        .mestory-login-screen-mask { position:absolute; top:31%; left:56%; width:40%; height:50%; box-sizing:border-box; overflow:hidden; display:flex; justify-content:center; align-items:center; background:transparent; clip-path:polygon(3% 2%,98% 0%,100% 96%,0 100%); }\
        .mestory-login-panel { position:relative; inset:auto; width:100%; height:100%; box-sizing:border-box; overflow:hidden; display:flex; flex-direction:column; justify-content:center; align-items:center; gap:0; padding:8% 15%; color:#202957; transform:translateY(-7%) perspective(900px) rotateY(-20deg); transform-origin:center; }\
        .mestory-login-panel > div, .mestory-login-panel > form, .mestory-login-panel > p, .mestory-login-panel > button { position:relative; z-index:1; width:100%; max-width:330px; }\
        .mestory-login-panel h1 { color:#202957 !important; font-size:clamp(15px, 1.45vw, 23px) !important; text-shadow:0 1px 8px rgba(133,146,255,.25); }\
        .mestory-login-panel p { color:#5f6992 !important; }\
        .mestory-login-panel label { color:#39436e !important; }\
        .mestory-login-panel input { background:rgba(255,255,255,.7) !important; border-color:rgba(116,125,205,.42) !important; color:#202957 !important; padding:7px 10px !important; }\
        .mestory-login-panel input::placeholder { color:#8991b5; }\
        .mestory-login-panel button[type='submit'] { background:#7565d5 !important; box-shadow:0 4px 12px rgba(115,105,222,.28); padding:8px 14px !important; }\
        .mestory-login-panel > button[type='button'] { color:#6555c5 !important; margin-top:6px !important; }\
        @media (max-width: 760px) {\
          .mestory-login-screen { min-height:100svh; padding:24px 16px; overflow:auto; }\
          .mestory-login-artboard { width:100%; aspect-ratio:auto; }\
          .mestory-login-artboard > img { position:relative; inset:auto; width:100%; height:auto; object-fit:contain; opacity:.38; }\
          .mestory-login-screen-mask { top:0; left:0; width:100%; height:100%; clip-path:none; background:rgba(237,240,255,.96); }\
          .mestory-login-panel { position:absolute; inset:50% auto auto 50%; transform:translate(-50%, -50%); width:min(100%,390px); height:auto; max-height:none; padding:24px 22px; background:transparent; }\
        }\
      `}</style>
      <div className="mestory-login-artboard">
        <img src="/로그인 배경-화면흰색.png" alt="MESTORY 로그인 화면 배경" />
        <div className="mestory-login-screen-mask">
          <section className="mestory-login-panel">
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
        </div>
      </div>
    </main>
  );
}
