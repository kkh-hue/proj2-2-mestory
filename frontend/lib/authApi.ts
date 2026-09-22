import type { AuthSession, AuthenticatedUser, LoginCredentials } from "../types/authHistory";

function baseUrl() {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (value) return value.replace(/\/+$/, "");
  if (process.env.NODE_ENV === "production") throw new Error("NEXT_PUBLIC_API_BASE_URL이 설정되지 않았습니다.");
  return "http://localhost:8000";
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${baseUrl()}${path}`, { ...init, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } });
  if (!response.ok) throw new Error(`인증 요청 실패 (HTTP ${response.status})`);
  return (await response.json()) as T;
}

export const signup = (credentials: LoginCredentials) => request<AuthSession>("/auth/signup", { method: "POST", body: JSON.stringify(credentials) });
export const login = (credentials: LoginCredentials) => request<AuthSession>("/auth/login", { method: "POST", body: JSON.stringify(credentials) });
export const getCurrentUser = (token: string) => request<AuthenticatedUser>("/auth/me", {}, token);
