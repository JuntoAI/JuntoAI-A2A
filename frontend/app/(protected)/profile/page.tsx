"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Loader2, CheckCircle2, Circle, ShieldCheck } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import {
  getProfile,
  updateProfile,
  requestEmailVerification,
  type ProfileResponse,
} from "@/lib/profile";
import {
  setPassword as apiSetPassword,
  changePassword as apiChangePassword,
  linkGoogle,
  unlinkGoogle,
} from "@/lib/auth";
import { COUNTRIES } from "@/lib/countries";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

// --- Google Identity Services type declarations ---
interface GoogleCredentialResponse {
  credential?: string;
}
interface GooglePromptNotification {
  isNotDisplayed(): boolean;
  isSkippedMoment(): boolean;
}
interface GoogleIdApi {
  initialize(config: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    cancel_on_tap_outside?: boolean;
  }): void;
  prompt(callback?: (notification: GooglePromptNotification) => void): void;
}

export default function ProfilePage() {
  const { isAuthenticated, isHydrated, email, updateTier } = useSession();
  const router = useRouter();

  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Form fields
  const [displayName, setDisplayName] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [country, setCountry] = useState("");

  // Email verification
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);

  // Password section
  const [passwordMode, setPasswordMode] = useState<"none" | "set" | "change">("none");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordMsg, setPasswordMsg] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  // Google OAuth
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [googleMsg, setGoogleMsg] = useState<string | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (isHydrated && !isAuthenticated) {
      router.replace("/");
    }
  }, [isHydrated, isAuthenticated, router]);

  // Fetch profile on mount
  const fetchProfile = useCallback(async () => {
    if (!email) return;
    setLoading(true);
    try {
      const p = await getProfile(email);
      setProfile(p);
      setDisplayName(p.display_name ?? "");
      setGithubUrl(p.github_url ?? "");
      setLinkedinUrl(p.linkedin_url ?? "");
      setCountry(p.country ?? "");
    } catch {
      setSaveError("Failed to load profile.");
    } finally {
      setLoading(false);
    }
  }, [email]);

  useEffect(() => {
    if (isHydrated && isAuthenticated && email) {
      fetchProfile();
    }
  }, [isHydrated, isAuthenticated, email, fetchProfile]);

  // --- Save profile ---
  async function handleSave() {
    if (!email) return;
    setSaving(true);
    setSaveMsg(null);
    setSaveError(null);
    try {
      const updated = await updateProfile(email, {
        display_name: displayName,
        github_url: githubUrl || null,
        linkedin_url: linkedinUrl || null,
        country: country || null,
      });
      setProfile(updated);
      updateTier(updated.tier, updated.daily_limit, updated.token_balance);
      setSaveMsg("Profile saved successfully.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  // --- Email verification ---
  async function handleVerifyEmail() {
    if (!email) return;
    setVerifyLoading(true);
    setVerifyMsg(null);
    try {
      await requestEmailVerification(email);
      setVerifyMsg("Verification email sent. Check your inbox.");
    } catch {
      setVerifyMsg("Failed to send verification email. Please try again.");
    } finally {
      setVerifyLoading(false);
    }
  }

  // --- Password handlers ---
  async function handleSetPassword() {
    if (!email) return;
    if (newPassword.length < 8 || newPassword.length > 128) {
      setPasswordError("Password must be between 8 and 128 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match.");
      return;
    }
    setPasswordLoading(true);
    setPasswordError(null);
    setPasswordMsg(null);
    try {
      await apiSetPassword(email, newPassword);
      setPasswordMsg("Password set successfully.");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMode("none");
      await fetchProfile();
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Failed to set password.");
    } finally {
      setPasswordLoading(false);
    }
  }

  async function handleChangePassword() {
    if (!email) return;
    if (newPassword.length < 8 || newPassword.length > 128) {
      setPasswordError("New password must be between 8 and 128 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match.");
      return;
    }
    setPasswordLoading(true);
    setPasswordError(null);
    setPasswordMsg(null);
    try {
      await apiChangePassword(email, currentPassword, newPassword);
      setPasswordMsg("Password changed successfully.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMode("none");
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Failed to change password.");
    } finally {
      setPasswordLoading(false);
    }
  }

  // --- Google OAuth handlers ---
  async function handleLinkGoogle() {
    if (!GOOGLE_CLIENT_ID || !email) return;
    setGoogleLoading(true);
    setGoogleError(null);
    setGoogleMsg(null);

    const google = (window as unknown as { google?: { accounts?: { id?: GoogleIdApi } } }).google;
    if (!google?.accounts?.id) {
      setGoogleError("Google sign-in is not available.");
      setGoogleLoading(false);
      return;
    }

    google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (response: GoogleCredentialResponse) => {
        if (!response.credential) {
          setGoogleLoading(false);
          return;
        }
        try {
          await linkGoogle(response.credential, email);
          setGoogleMsg("Google account linked successfully.");
          await fetchProfile();
        } catch (err) {
          setGoogleError(err instanceof Error ? err.message : "Failed to link Google account.");
        } finally {
          setGoogleLoading(false);
        }
      },
      cancel_on_tap_outside: true,
    });

    google.accounts.id.prompt((notification: GooglePromptNotification) => {
      if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
        setGoogleLoading(false);
      }
    });
  }

  async function handleUnlinkGoogle() {
    if (!email) return;
    setGoogleLoading(true);
    setGoogleError(null);
    setGoogleMsg(null);
    try {
      await unlinkGoogle(email);
      setGoogleMsg("Google account unlinked.");
      await fetchProfile();
    } catch (err) {
      setGoogleError(err instanceof Error ? err.message : "Failed to unlink Google account.");
    } finally {
      setGoogleLoading(false);
    }
  }

  // --- Progress indicator ---
  const steps = [
    { label: "Email verified", done: !!profile?.email_verified },
    { label: "Display name set", done: !!(profile?.display_name && profile.display_name.trim()) },
    { label: "Professional link added", done: !!(profile?.github_url || profile?.linkedin_url) },
  ];
  const completedSteps = steps.filter((s) => s.done).length;

  if (!isHydrated || !isAuthenticated) return null;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-brand-blue" />
      </div>
    );
  }

  const countryName = country
    ? COUNTRIES.find((c) => c.code === country)?.name ?? country
    : null;

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Your Profile</h1>

      {/* Progress indicator */}
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-sm font-medium text-gray-700 mb-3">
          Profile completion: {completedSteps} / {steps.length}
        </p>
        <div className="flex gap-4">
          {steps.map((step) => (
            <div key={step.label} className="flex items-center gap-1.5 text-sm">
              {step.done ? (
                <CheckCircle2 className="h-4 w-4 text-green-500" />
              ) : (
                <Circle className="h-4 w-4 text-gray-300" />
              )}
              <span className={step.done ? "text-gray-700" : "text-gray-400"}>
                {step.label}
              </span>
            </div>
          ))}
        </div>
        {profile?.tier && (
          <p className="mt-2 text-xs text-gray-500">
            Current tier: {profile.tier} — {profile.daily_limit} tokens/day
          </p>
        )}
      </div>

      {/* Email verification */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
        <h2 className="text-lg font-semibold text-gray-800">Email Verification</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">{email}</span>
          {profile?.email_verified ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
              <ShieldCheck className="h-3 w-3" /> Verified
            </span>
          ) : (
            <button
              onClick={handleVerifyEmail}
              disabled={verifyLoading}
              className="inline-flex items-center gap-1 rounded-md bg-brand-blue px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-60"
            >
              {verifyLoading && <Loader2 className="h-3 w-3 animate-spin" />}
              Verify Email
            </button>
          )}
        </div>
        {verifyMsg && <p className="text-xs text-gray-600">{verifyMsg}</p>}
      </div>

      {/* Profile form */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-4">
        <h2 className="text-lg font-semibold text-gray-800">Profile Details</h2>

        <div>
          <label htmlFor="displayName" className="block text-sm font-medium text-gray-700 mb-1">
            Display Name
          </label>
          <input
            id="displayName"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your display name"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-brand-charcoal placeholder-gray-400 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
          />
        </div>

        <div>
          <label htmlFor="githubUrl" className="block text-sm font-medium text-gray-700 mb-1">
            GitHub URL
          </label>
          <input
            id="githubUrl"
            type="url"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            placeholder="https://github.com/username"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-brand-charcoal placeholder-gray-400 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
          />
        </div>

        <div>
          <label htmlFor="linkedinUrl" className="block text-sm font-medium text-gray-700 mb-1">
            LinkedIn URL
          </label>
          <input
            id="linkedinUrl"
            type="url"
            value={linkedinUrl}
            onChange={(e) => setLinkedinUrl(e.target.value)}
            placeholder="https://linkedin.com/in/your-slug"
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-brand-charcoal placeholder-gray-400 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
          />
        </div>

        <div>
          <label htmlFor="country" className="block text-sm font-medium text-gray-700 mb-1">
            Country
          </label>
          <select
            id="country"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-brand-charcoal focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
          >
            <option value="">Select a country</option>
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
          {countryName && (
            <p className="mt-1 text-xs text-gray-500">Selected: {countryName}</p>
          )}
        </div>

        {saveError && <p className="text-sm text-red-600">{saveError}</p>}
        {saveMsg && <p className="text-sm text-green-600">{saveMsg}</p>}

        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-blue px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save Profile
        </button>
      </div>

      {/* Password section */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
        <h2 className="text-lg font-semibold text-gray-800">Password</h2>

        {!profile?.email_verified && (
          <p className="text-sm text-gray-500">Verify your email to set a password.</p>
        )}

        {profile?.email_verified && !profile.password_hash_set && passwordMode !== "set" && (
          <button
            onClick={() => { setPasswordMode("set"); setPasswordError(null); setPasswordMsg(null); }}
            className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
          >
            Set Password
          </button>
        )}

        {profile?.email_verified && profile.password_hash_set && passwordMode !== "change" && (
          <div className="space-y-2">
            <p className="text-sm text-gray-600">Password is set.</p>
            <button
              onClick={() => { setPasswordMode("change"); setPasswordError(null); setPasswordMsg(null); }}
              className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
            >
              Change Password
            </button>
          </div>
        )}

        {passwordMode === "set" && (
          <div className="space-y-3">
            <div>
              <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700 mb-1">
                New Password
              </label>
              <input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Min 8 characters"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm password"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>
            {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
            {passwordMsg && <p className="text-sm text-green-600">{passwordMsg}</p>}
            <div className="flex gap-2">
              <button
                onClick={handleSetPassword}
                disabled={passwordLoading}
                className="inline-flex items-center gap-1 rounded-md bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {passwordLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                Set Password
              </button>
              <button
                onClick={() => { setPasswordMode("none"); setNewPassword(""); setConfirmPassword(""); setPasswordError(null); }}
                className="rounded-md px-4 py-2 text-sm text-gray-500 hover:bg-gray-100"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {passwordMode === "change" && (
          <div className="space-y-3">
            <div>
              <label htmlFor="currentPassword" className="block text-sm font-medium text-gray-700 mb-1">
                Current Password
              </label>
              <input
                id="currentPassword"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>
            <div>
              <label htmlFor="newPasswordChange" className="block text-sm font-medium text-gray-700 mb-1">
                New Password
              </label>
              <input
                id="newPasswordChange"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Min 8 characters"
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>
            <div>
              <label htmlFor="confirmPasswordChange" className="block text-sm font-medium text-gray-700 mb-1">
                Confirm New Password
              </label>
              <input
                id="confirmPasswordChange"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
              />
            </div>
            {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
            {passwordMsg && <p className="text-sm text-green-600">{passwordMsg}</p>}
            <div className="flex gap-2">
              <button
                onClick={handleChangePassword}
                disabled={passwordLoading}
                className="inline-flex items-center gap-1 rounded-md bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60"
              >
                {passwordLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                Change Password
              </button>
              <button
                onClick={() => { setPasswordMode("none"); setCurrentPassword(""); setNewPassword(""); setConfirmPassword(""); setPasswordError(null); }}
                className="rounded-md px-4 py-2 text-sm text-gray-500 hover:bg-gray-100"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Google OAuth section */}
      <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
        <h2 className="text-lg font-semibold text-gray-800">Google Account</h2>

        {!profile?.email_verified && (
          <p className="text-sm text-gray-500">Verify your email to link a Google account.</p>
        )}

        {profile?.email_verified && !profile.google_oauth_id && (
          <button
            onClick={handleLinkGoogle}
            disabled={googleLoading || !GOOGLE_CLIENT_ID}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
          >
            {googleLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
              </svg>
            )}
            Link Google Account
          </button>
        )}

        {profile?.email_verified && profile.google_oauth_id && (
          <div className="space-y-2">
            <p className="text-sm text-gray-600">
              Google account linked <span className="font-medium">(ID: {profile.google_oauth_id.slice(0, 8)}…)</span>
            </p>
            <button
              onClick={handleUnlinkGoogle}
              disabled={googleLoading}
              className="inline-flex items-center gap-1 rounded-md bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-60"
            >
              {googleLoading && <Loader2 className="h-3 w-3 animate-spin" />}
              Unlink Google Account
            </button>
          </div>
        )}

        {googleError && <p className="text-sm text-red-600">{googleError}</p>}
        {googleMsg && <p className="text-sm text-green-600">{googleMsg}</p>}
      </div>
    </div>
  );
}
