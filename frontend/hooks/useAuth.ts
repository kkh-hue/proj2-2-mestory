"use client";

import { useCallback, useEffect, useState } from "react";
import { getCurrentUser, login as loginRequest, signup as signupRequest } from "../lib/authApi";
import type { AuthenticatedUser, LoginCredentials } from "../types/authHistory";

const TOKEN_KEY = "mestory.access_token";

export function useAuth() {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const acceptSession = useCallback((session: { access_token: string; user: AuthenticatedUser }) => {
    sessionStorage.setItem(TOKEN_KEY, session.access_token); setToken(session.access_token); setUser(session.user);
  }, []);
  const authenticate = useCallback(async (credentials: LoginCredentials, action: typeof loginRequest) => {
    setError(null); const session = await action(credentials); acceptSession(session); return session.user;
  }, [acceptSession]);
  const login = useCallback((credentials: LoginCredentials) => authenticate(credentials, loginRequest), [authenticate]);
  const signup = useCallback((credentials: LoginCredentials) => authenticate(credentials, signupRequest), [authenticate]);
  const logout = useCallback(() => { sessionStorage.removeItem(TOKEN_KEY); setToken(null); setUser(null); setError(null); }, []);

  useEffect(() => { const saved = sessionStorage.getItem(TOKEN_KEY); if (!saved) { setIsLoading(false); return; } getCurrentUser(saved).then((current) => { setToken(saved); setUser(current); }).catch(() => sessionStorage.removeItem(TOKEN_KEY)).finally(() => setIsLoading(false)); }, []);
  return { user, token, isAuthenticated: user !== null, isLoading, error, login, signup, logout, setError };
}
