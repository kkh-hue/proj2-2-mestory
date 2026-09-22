"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getMe, type AuthUser } from "../lib/authApi";
import { getAccessToken, removeAccessToken } from "../lib/authToken";
import AppShell from "./AppShell";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  refreshUser: () => Promise<AuthUser | null>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setUser(null);
      return null;
    }
    try {
      const currentUser = await getMe(token);
      setUser(currentUser);
      return currentUser;
    } catch {
      removeAccessToken();
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    refreshUser().finally(() => setLoading(false));
  }, [refreshUser]);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    isAuthenticated: user !== null,
    refreshUser,
    logout: () => {
      removeAccessToken();
      setUser(null);
    },
  }), [loading, refreshUser, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function AuthLayout({ children }: { children: ReactNode }) {
  const { isAuthenticated, loading } = useAuth();
  return (
    <AuthGate>
      {loading || !isAuthenticated ? children : <AppShell>{children}</AppShell>}
    </AuthGate>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { loading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!loading && !isAuthenticated && pathname !== "/login") router.replace("/login");
    if (!loading && isAuthenticated && pathname === "/login") router.replace("/");
  }, [isAuthenticated, loading, pathname, router]);

  if (loading) return <div style={{ minHeight: "100vh", background: "#fafbff" }} aria-busy="true" />;
  if (!isAuthenticated && pathname !== "/login") return null;
  return <>{children}</>;
}
