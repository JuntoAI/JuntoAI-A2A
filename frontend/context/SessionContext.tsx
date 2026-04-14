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

// --- Types ---

export type Persona = "sales" | "founder" | null;

// --- Interfaces ---

export interface SessionState {
  email: string | null;
  tokenBalance: number;
  lastResetDate: string | null;
  tier: number;
  dailyLimit: number;
  isAuthenticated: boolean;
  isHydrated: boolean;
  persona: Persona;
}

export interface SessionContextValue extends SessionState {
  login: (email: string, tokenBalance: number, lastResetDate: string, tier?: number, dailyLimit?: number) => void;
  logout: () => void;
  updateTokenBalance: (newBalance: number) => void;
  updateTier: (tier: number, dailyLimit: number, tokenBalance: number) => void;
  setPersona: (persona: Persona) => void;
}

// --- Constants ---

const STORAGE_KEY_EMAIL = "junto_email";
const STORAGE_KEY_TOKEN_BALANCE = "junto_token_balance";
const STORAGE_KEY_LAST_RESET = "junto_last_reset";
const STORAGE_KEY_TIER = "junto_tier";
const STORAGE_KEY_DAILY_LIMIT = "junto_daily_limit";
const STORAGE_KEY_PERSONA = "junto_persona";
const SESSION_COOKIE_NAME = "junto_session";

const defaultState: SessionState = {
  email: null,
  tokenBalance: 0,
  lastResetDate: null,
  tier: 1,
  dailyLimit: 20,
  isAuthenticated: false,
  isHydrated: false,
  persona: null,
};

// --- Context ---

const SessionContext = createContext<SessionContextValue | null>(null);

// --- Provider ---

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>(defaultState);

  // Restore from sessionStorage on mount (or auto-auth in local mode)
  useEffect(() => {
    if (isLocalMode) {
      const storedPersona = sessionStorage.getItem(STORAGE_KEY_PERSONA) as Persona;
      setState({
        email: "local@dev",
        tokenBalance: Infinity,
        lastResetDate: null,
        tier: 3,
        dailyLimit: 100,
        isAuthenticated: true,
        isHydrated: true,
        persona: storedPersona ?? "sales",
      });
      return;
    }

    const email = sessionStorage.getItem(STORAGE_KEY_EMAIL);
    const balanceStr = sessionStorage.getItem(STORAGE_KEY_TOKEN_BALANCE);
    const lastReset = sessionStorage.getItem(STORAGE_KEY_LAST_RESET);
    const tierStr = sessionStorage.getItem(STORAGE_KEY_TIER);
    const dailyLimitStr = sessionStorage.getItem(STORAGE_KEY_DAILY_LIMIT);
    const storedPersona = sessionStorage.getItem(STORAGE_KEY_PERSONA) as Persona;

    if (email) {
      setState({
        email,
        tokenBalance: balanceStr !== null ? Number(balanceStr) : 0,
        lastResetDate: lastReset,
        tier: tierStr !== null ? Number(tierStr) : 1,
        dailyLimit: dailyLimitStr !== null ? Number(dailyLimitStr) : 20,
        isAuthenticated: true,
        isHydrated: true,
        persona: storedPersona,
      });
    } else {
      setState((prev) => ({ ...prev, isHydrated: true, persona: storedPersona }));
    }
  }, []);

  const login = useCallback(
    (email: string, tokenBalance: number, lastResetDate: string, tier: number = 1, dailyLimit: number = 20) => {
      // Persist to sessionStorage
      sessionStorage.setItem(STORAGE_KEY_EMAIL, email);
      sessionStorage.setItem(STORAGE_KEY_TOKEN_BALANCE, String(tokenBalance));
      sessionStorage.setItem(STORAGE_KEY_LAST_RESET, lastResetDate);
      sessionStorage.setItem(STORAGE_KEY_TIER, String(tier));
      sessionStorage.setItem(STORAGE_KEY_DAILY_LIMIT, String(dailyLimit));

      // Set cookie for middleware
      document.cookie = `${SESSION_COOKIE_NAME}=1; SameSite=Strict; path=/`;

      setState({
        email,
        tokenBalance,
        lastResetDate,
        tier,
        dailyLimit,
        isAuthenticated: true,
        isHydrated: true,
        persona: state.persona,
      });
    },
    [state.persona]
  );

  const logout = useCallback(() => {
    // Clear sessionStorage
    sessionStorage.removeItem(STORAGE_KEY_EMAIL);
    sessionStorage.removeItem(STORAGE_KEY_TOKEN_BALANCE);
    sessionStorage.removeItem(STORAGE_KEY_LAST_RESET);
    sessionStorage.removeItem(STORAGE_KEY_TIER);
    sessionStorage.removeItem(STORAGE_KEY_DAILY_LIMIT);
    sessionStorage.removeItem(STORAGE_KEY_PERSONA);

    // Remove cookie by setting max-age=0
    document.cookie = `${SESSION_COOKIE_NAME}=; SameSite=Strict; path=/; max-age=0`;

    // Keep isHydrated true so the protected layout redirect fires
    setState({ ...defaultState, isHydrated: true });
  }, []);

  const updateTokenBalance = useCallback((newBalance: number) => {
    sessionStorage.setItem(STORAGE_KEY_TOKEN_BALANCE, String(newBalance));
    setState((prev) => ({ ...prev, tokenBalance: newBalance }));
  }, []);

  const updateTier = useCallback((tier: number, dailyLimit: number, tokenBalance: number) => {
    sessionStorage.setItem(STORAGE_KEY_TIER, String(tier));
    sessionStorage.setItem(STORAGE_KEY_DAILY_LIMIT, String(dailyLimit));
    sessionStorage.setItem(STORAGE_KEY_TOKEN_BALANCE, String(tokenBalance));
    setState((prev) => ({ ...prev, tier, dailyLimit, tokenBalance }));
  }, []);

  const setPersona = useCallback((persona: Persona) => {
    if (persona) {
      sessionStorage.setItem(STORAGE_KEY_PERSONA, persona);
    } else {
      sessionStorage.removeItem(STORAGE_KEY_PERSONA);
    }
    setState((prev) => ({ ...prev, persona }));
  }, []);

  return (
    <SessionContext.Provider
      value={{ ...state, login, logout, updateTokenBalance, updateTier, setPersona }}
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
