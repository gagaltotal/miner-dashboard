import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError } from "../api/client";

type AuthState =
  | { status: "loading" }
  | { status: "needs_setup" }
  | { status: "logged_out" }
  | { status: "logged_in"; username: string };

interface AuthContextValue {
  state: AuthState;
  setup: (username: string, password: string) => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    (async () => {
      try {
        const { setup_complete } = await api.auth.status();
        if (!setup_complete) {
          setState({ status: "needs_setup" });
          return;
        }
        const me = await api.auth.me();
        setState({ status: "logged_in", username: me.username });
      } catch {
        setState({ status: "logged_out" });
      }
    })();
  }, []);

  const setup = async (username: string, password: string) => {
    const res = await api.auth.setup(username, password);
    setState({ status: "logged_in", username: res.username });
  };

  const login = async (username: string, password: string) => {
    const res = await api.auth.login(username, password);
    setState({ status: "logged_in", username: res.username });
  };

  const logout = async () => {
    try {
      await api.auth.logout();
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
    }
    setState({ status: "logged_out" });
  };

  return <AuthContext.Provider value={{ state, setup, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
