"use client";

import { useState, useCallback, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import { joinWaitlist } from "@/lib/waitlist";
import { needsReset, resetTokens } from "@/lib/tokens";
import { getProfile } from "@/lib/profile";
import { checkEmail, loginWithPassword, loginWithGoogle } from "@/lib/auth";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

export default function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [hasPassword, setHasPassword] = useState(false);
  const [emailChecked, setEmailChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const { login } = useSession();
  const router = useRouter();

  // --- Check email for password requirement ---
  const handleCheckEmail = useCallback(async (emailValue: string): Promise<boolean> => {
    const trimmed = emailValue.trim();
    if (!trimmed || !EMAIL_REGEX.test(trimmed)) return false;

    try {
      const result = await checkEmail(trimmed);
      setHasPassword(result.has_password);
      setEmailChecked(true);
      return result.has_password;
    } catch {
      // If check-email fails (e.g. network), default to no password flow
      setHasPassword(false);
      setEmailChecked(true);
      return false;
    }
  }, []);

  const handleEmailBlur = () => {
    if (!emailChecked) {
      handleCheckEmail(email);
    }
  };

  // --- Shared: complete login with profile tier info ---
  async function completeLoginWithProfile(
    userEmail: string,
    tokenBalance: number,
    lastResetDate: string,
  ) {
    let tier = 1;
    let dailyLimit = 20;

    try {
      const profile = await getProfile(userEmail);
      tier = profile.tier;
      dailyLimit = profile.daily_limit;
    } catch {
      // No profile yet — default Tier 1
    }

    // Check if tokens need a daily reset
    if (needsReset(lastResetDate)) {
      await resetTokens(userEmail, dailyLimit);
      tokenBalance = dailyLimit;
      lastResetDate = new Date().toISOString().slice(0, 10);
    }

    login(userEmail, tokenBalance, lastResetDate, tier, dailyLimit);
    router.push("/arena");
  }

  // --- Email (+ optional password) submit ---
  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = email.trim();
    if (!trimmed || !EMAIL_REGEX.test(trimmed)) {
      setError("Please enter a valid email address.");
      return;
    }

    setIsLoading(true);

    try {
      // Determine if password is needed
      let needsPassword = hasPassword;
      if (!emailChecked) {
        needsPassword = await handleCheckEmail(trimmed);
      }

      // Password login flow
      if (needsPassword) {
        if (!password) {
          setError("Please enter your password.");
          setIsLoading(false);
          return;
        }

        try {
          const result = await loginWithPassword(trimmed, password);
          const lastReset = new Date().toISOString().slice(0, 10);
          login(result.email, result.token_balance, lastReset, result.tier, result.daily_limit);
          router.push("/arena");
          return;
        } catch (err) {
          if (err instanceof Error && err.message === "Invalid password") {
            setError("Invalid password. Please try again.");
          } else {
            setError("Login failed. Please try again.");
          }
          setIsLoading(false);
          return;
        }
      }

      // Email-only login flow (no password set)
      const doc = await joinWaitlist(trimmed);
      await completeLoginWithProfile(doc.email, doc.token_balance, doc.last_reset_date);
    } catch (err) {
      console.error("[WaitlistForm] submission failed:", err);
      setError("Something went wrong. Please try again.");
      setIsLoading(false);
    }
  }

  // --- Google sign-in ---
  function handleGoogleSignIn() {
    if (!GOOGLE_CLIENT_ID) {
      setError("Google sign-in is not configured.");
      return;
    }

    setIsGoogleLoading(true);
    setError(null);

    // Use Google Identity Services (GIS) one-tap / popup flow
    const google = (window as unknown as { google?: { accounts?: { id?: GoogleIdApi } } }).google;
    if (!google?.accounts?.id) {
      setError("Google sign-in is not available. Please try email login.");
      setIsGoogleLoading(false);
      return;
    }

    google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response: GoogleCredentialResponse) => {
        if (!response.credential) {
          // User cancelled or no credential — graceful handling
          setIsGoogleLoading(false);
          return;
        }

        try {
          const result = await loginWithGoogle(response.credential);
          const lastReset = new Date().toISOString().slice(0, 10);
          login(result.email, result.token_balance, lastReset, result.tier, result.daily_limit);
          router.push("/arena");
        } catch (err) {
          if (err instanceof Error && err.message.includes("No linked account")) {
            setError("No linked account found for this Google account. Please sign in with email first and link your Google account from the profile page.");
          } else {
            setError("Google sign-in failed. Please try again.");
          }
          setIsGoogleLoading(false);
        }
      },
      cancel_on_tap_outside: true,
    });

    google.accounts.id.prompt((notification: GooglePromptNotification) => {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        // Fallback: try the button-based flow or just stop loading
        setIsGoogleLoading(false);
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 w-full max-w-md">
      <div className="flex flex-col gap-1">
        <input
          type="email"
          value={email}
          onChange={(e) => {
            setEmail(e.target.value);
            setEmailChecked(false);
            setHasPassword(false);
            setPassword("");
          }}
          onBlur={handleEmailBlur}
          placeholder="you@example.com"
          aria-label="Email address"
          aria-describedby={error ? "waitlist-error" : undefined}
          className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm text-brand-charcoal placeholder-gray-400 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
        />

        {hasPassword && (
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            aria-label="Password"
            className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm text-brand-charcoal placeholder-gray-400 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
          />
        )}

        {error && (
          <p id="waitlist-error" role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
      </div>

      <button
        type="submit"
        disabled={isLoading || isGoogleLoading}
        className="flex items-center justify-center gap-2 rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
        {isLoading
          ? "Starting..."
          : hasPassword
            ? "Sign In"
            : "Start the AI 2 AI Negotiation"}
      </button>

      {GOOGLE_CLIENT_ID && (
        <>
          <div className="flex items-center gap-2">
            <div className="flex-1 border-t border-gray-200" />
            <span className="text-xs text-gray-400">or</span>
            <div className="flex-1 border-t border-gray-200" />
          </div>

          <button
            type="button"
            onClick={handleGoogleSignIn}
            disabled={isLoading || isGoogleLoading}
            className="flex items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-6 py-3 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isGoogleLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                  fill="#4285F4"
                />
                <path
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  fill="#34A853"
                />
                <path
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  fill="#FBBC05"
                />
                <path
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  fill="#EA4335"
                />
              </svg>
            )}
            Sign in with Google
          </button>
        </>
      )}

      <p className="text-center text-xs text-brand-charcoal/50">
        By running this demo you&apos;re signing up for the{" "}
        <a
          href="https://juntoai.org"
          target="_blank"
          rel="noopener noreferrer"
          className="underline text-brand-blue hover:text-blue-700"
        >
          JuntoAI
        </a>{" "}
        waitlist and supporting our vision of building the next-generation business network which is AI enabled and outcome oriented.
      </p>
    </form>
  );
}

// --- Google Identity Services type declarations ---
interface GoogleCredentialResponse {
  credential?: string;
  select_by?: string;
}

interface GooglePromptNotification {
  isNotDisplayed(): boolean;
  isSkippedMoment(): boolean;
  isDismissedMoment(): boolean;
}

interface GoogleIdApi {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    cancel_on_tap_outside?: boolean;
  }): void;
  prompt(callback?: (notification: GooglePromptNotification) => void): void;
}
