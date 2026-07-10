"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { clearToken, getToken, setToken as persistToken } from "@/lib/api";

interface AuthContextValue {
  token: string | null;
  isReady: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    setTokenState(getToken());
    setIsReady(true);
  }, []);

  const login = (newToken: string) => {
    persistToken(newToken);
    setTokenState(newToken);
  };

  const logout = () => {
    clearToken();
    setTokenState(null);
  };

  return (
    <AuthContext.Provider value={{ token, isReady, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
