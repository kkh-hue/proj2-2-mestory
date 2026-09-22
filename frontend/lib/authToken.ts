const AUTH_TOKEN_KEY = "mestory.access_token";

export function saveAccessToken(token: string): void {
  if (typeof window !== "undefined") window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function removeAccessToken(): void {
  if (typeof window !== "undefined") window.localStorage.removeItem(AUTH_TOKEN_KEY);
}
