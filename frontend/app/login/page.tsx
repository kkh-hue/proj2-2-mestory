"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe, login, signup, type AuthUser } from "../../lib/authApi";
import { saveAccessToken } from "../../lib/authToken";
import { useAuth } from "../../components/AuthProvider";

const fieldStyle = { width: "100%", boxSizing: "border-box" as const, border: "1px solid #d9d6ee", borderRadius: 10, padding: "12px 13px", fontSize: 14 };

function toKoreanAuthError(cause: unknown, mode: "login" | "signup") {
  const raw = cause instanceof Error ? cause.message : String(cause ?? "");
  const message = raw.toLowerCase();
  if (mode === "signup" && (message.includes("409") || message.includes("conflict") || message.includes("already exists"))) return "이미 가입된 이메일입니다.";
  if (message.includes("not found")) return "요청한 정보를 찾을 수 없습니다.";
  if (message.includes("failed to fetch") || message.includes("network") || message.includes("연결")) return "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.";
  if (mode === "login" || message.includes("invalid") || message.includes("unauthorized") || message.includes("401")) return "이메일 또는 비밀번호가 올바르지 않습니다.";
  return "오류가 발생했습니다. 다시 시도해주세요.";
}

export default function LoginPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordVisible, setPasswordVisible] = useState(false);
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
      setError(toKoreanAuthError(cause, mode));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mestory-login-screen">
      <style>{`\
        .mestory-login-screen { position:relative; width:100vw; height:100vh; height:100dvh; overflow:hidden; background:#e9e9fb; }\
        .mestory-login-artboard { position:absolute; top:50%; left:50%; width:max(100vw, 150vh); aspect-ratio:3 / 2; transform:translate(-50%, -50%); }\
        .mestory-login-artboard > img { position:absolute; inset:0; width:100%; height:100%; display:block; object-fit:contain; }\
        .mestory-login-screen-mask { position:absolute; top:31%; left:56%; width:40%; height:50%; box-sizing:border-box; overflow:hidden; display:flex; justify-content:center; align-items:center; background:transparent; clip-path:polygon(3% 2%,98% 0%,100% 96%,0 100%); }\
        .mestory-login-panel { position:relative; inset:auto; width:100%; height:100%; box-sizing:border-box; overflow:hidden; display:flex; flex-direction:column; justify-content:center; align-items:center; gap:0; padding:8% 15%; color:#202957; transform:translateY(-7%) perspective(900px) rotateY(-20deg); transform-origin:center; }\
        .mestory-login-panel > div, .mestory-login-panel > form, .mestory-login-panel > p, .mestory-login-panel > button { position:relative; z-index:1; width:100%; max-width:330px; }\
        .mestory-login-panel h1 { color:#202957 !important; font-size:clamp(15px, 1.45vw, 23px) !important; text-shadow:0 1px 8px rgba(133,146,255,.25); }\
        .mestory-login-panel p { color:#5f6992 !important; }\
        .mestory-login-panel label { color:#39436e !important; }\
        .mestory-login-panel input { background:rgba(255,255,255,.7) !important; border-color:rgba(116,125,205,.42) !important; color:#202957 !important; padding:7px 10px !important; }\
        .mestory-login-panel input::placeholder { color:#8991b5; }\
        .mestory-password-field { position:relative; }\
        .mestory-password-field input { padding-right:38px !important; }\
        .mestory-password-toggle { position:absolute; right:8px; bottom:8px; width:28px; height:28px; display:grid; place-items:center; border:0; border-radius:8px; color:#8b82c9; background:transparent; cursor:pointer; }\
        .mestory-password-toggle:hover { background:#f0edff; color:#7565d5; }\
        .mestory-password-toggle svg { width:17px; height:17px; }\
        .mestory-login-error { margin:0; color:#e74c3c; font-size:13px; font-weight:700; line-height:1.5; text-align:center; }\
        .mestory-login-panel button[type='submit'] { background:#7565d5 !important; box-shadow:0 4px 12px rgba(115,105,222,.28); padding:8px 14px !important; }\
        .mestory-login-panel > button[type='button'] { color:#6555c5 !important; margin-top:6px !important; }\
        @media (max-width: 760px) {\
          .mestory-login-screen { min-height:100svh; height:auto; padding:24px 16px; overflow:auto; }\
          .mestory-login-artboard { position:relative; top:auto; left:auto; width:100%; min-height:100svh; aspect-ratio:auto; transform:none; }\
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
          <p style={{ margin: "0 0 8px", color: "#7565d5", fontSize: 12, fontWeight: 800, letterSpacing: ".08em" }}>MESTORY</p>
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
            <span className="mestory-password-field">
              <input type={passwordVisible ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} autoComplete={mode === "login" ? "current-password" : "new-password"} style={fieldStyle} />
              <button type="button" className="mestory-password-toggle" onClick={() => setPasswordVisible((visible) => !visible)} aria-label={passwordVisible ? "비밀번호 숨기기" : "비밀번호 표시"}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                  {passwordVisible ? <><path d="M3 3l18 18" /><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" /><path d="M9.9 4.3A10.8 10.8 0 0 1 12 4c5.2 0 8.6 4 9.8 6a18 18 0 0 1-3.1 3.8M6.1 6.1C3.8 7.5 2.5 9.4 2.2 10c1.2 2 4.6 6 9.8 6 1 0 2-.2 2.8-.5" /></> : <><path d="M2.2 12s3.4-6 9.8-6 9.8 6 9.8 6-3.4 6-9.8 6-9.8-6-9.8-6Z" /><circle cx="12" cy="12" r="2.5" /></>}
                </svg>
              </button>
            </span>
          </label>
          {error && <p className="mestory-login-error" role="alert">{error}</p>}
          <button type="submit" disabled={loading} style={{ border: 0, borderRadius: 10, padding: "12px 16px", background: "#7565d5", color: "#fff", fontWeight: 800, cursor: loading ? "wait" : "pointer" }}>
            {loading ? "처리 중..." : mode === "login" ? "로그인" : "회원가입"}
          </button>
        </form>

        {message && <p role="status" style={{ margin: "16px 0 0", color: "#2f9b68", fontSize: 13 }}>{message}{user ? ` ${user.email}` : ""}</p>}

        <button type="button" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); setMessage(""); }} style={{ width: "100%", marginTop: 18, border: 0, background: "transparent", color: "#7565d5", fontSize: 13, cursor: "pointer" }}>
          {mode === "login" ? "계정이 없으신가요? 회원가입" : "이미 계정이 있으신가요? 로그인"}
        </button>
          </section>
        </div>
      </div>
    </main>
  );
}
