"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";
import { isLocalMode } from "@/lib/runMode";

// --- Interfaces ---

export interface SessionState {
  email: string | null;
  tokenBalance: number;
  lastResetDate: string | null;
  isAuthenticated: boolean;
  isHydrated: boolean;
}

export interface SessionContextValue extends SessionState {
  login: (email: string, tokenBalance: number, lastResetDate: string) => void;
  logout: () => void;
  updateTokenBalance: (newBalance: number) => void;
}

// --- Constants ---

const STORAGE_KEY_EMAIL = "junto_email";
const STORAGE_KEY_TOKEN_BALANCE = "junto_token_balance";
const STORAGE_KEY_LAST_RESET = "junto_last_reset";
const SESSION_COOKIE_NAME = "junto_session";

const defaultState: SessionState = {
  email: null,
  tokenBalance: 0,
  lastResetDate: null,
  isAuthenticated: false,
  isHydrated: false,
};

// --- Context ---

const SessionContext = createContext<SessionContextValue | null>(null);

// --- Provider ---

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>(defaultState);

  // Restore from sessionStorage on mount (or auto-auth in local mode)
  useEffect(() => {
    if (isLocalMode) {
      setState({
        email: "local@dev",
        tokenBalance: Infinity,
        lastResetDate: null,
        isAuthenticated: true,
        isHydrated: true,
      });
      return;
    }

    const email = sessionStorage.getItem(STORAGE_KEY_EMAIL);
    const balanceStr = sessionStorage.getItem(STORAGE_KEY_TOKEN_BALANCE);
    const lastReset = sessionStorage.getItem(STORAGE_KEY_LAST_RESET);

    if (email) {
      setState({
        email,
        tokenBalance: balanceStr !== null ? Number(balanceStr) : 0,
        lastResetDate: lastReset,
        isAuthenticated: true,
        isHydrated: true,
      });
    } else {
      setState((prev) => ({ ...prev, isHydrated: true }));
    }
  }, []);

  const login = useCallback(
    (email: string, tokenBalance: number, lastResetDate: string) => {
      // Persist to sessionStorage
      sessionStorage.setItem(STORAGE_KEY_EMAIL, email);
      sessionStorage.setItem(STORAGE_KEY_TOKEN_BALANCE, String(tokenBalance));
      sessionStorage.setItem(STORAGE_KEY_LAST_RESET, lastResetDate);

      // Set cookie for middleware
      document.cookie = `${SESSION_COOKIE_NAME}=1; SameSite=Strict; path=/`;

      setState({
        email,
        tokenBalance,
        lastResetDate,
        isAuthenticated: true,
        isHydrated: true,
      });
    },
    []
  );

  const logout = useCallback(() => {
    // Clear sessionStorage
    sessionStorage.removeItem(STORAGE_KEY_EMAIL);
    sessionStorage.removeItem(STORAGE_KEY_TOKEN_BALANCE);
    sessionStorage.removeItem(STORAGE_KEY_LAST_RESET);

    // Remove cookie by setting max-age=0
    document.cookie = `${SESSION_COOKIE_NAME}=; SameSite=Strict; path=/; max-age=0`;

    // Keep isHydrated true so the protected layout redirect fires
    setState({ ...defaultState, isHydrated: true });
  }, []);

  const updateTokenBalance = useCallback((newBalance: number) => {
    sessionStorage.setItem(STORAGE_KEY_TOKEN_BALANCE, String(newBalance));
    setState((prev) => ({ ...prev, tokenBalance: newBalance }));
  }, []);

  return (
    <SessionContext.Provider
      value={{ ...state, login, logout, updateTokenBalance }}
    >
      {children}
    </SessionContext.Provider>
  );
}

// --- Hook ---

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return ctx;
}
