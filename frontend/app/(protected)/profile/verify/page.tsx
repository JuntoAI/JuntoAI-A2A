"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, XCircle, Loader2, AlertTriangle } from "lucide-react";
import { requestEmailVerification } from "@/lib/profile";
import { useSession } from "@/context/SessionContext";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

type VerifyState = "loading" | "success" | "expired" | "invalid";

function VerifyContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const { email } = useSession();

  const [state, setState] = useState<VerifyState>("loading");
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setState("invalid");
      return;
    }

    let cancelled = false;

    async function verify() {
      try {
        const res = await fetch(`${API_URL}/api/v1/profile/verify/${encodeURIComponent(token!)}`);
        if (cancelled) return;

        if (res.ok) {
          setState("success");
        } else if (res.status === 410) {
          setState("expired");
        } else {
          setState("invalid");
        }
      } catch {
        if (!cancelled) setState("invalid");
      }
    }

    verify();
    return () => { cancelled = true; };
  }, [token]);

  async function handleResend() {
    if (!email) return;
    setResending(true);
    setResendMsg(null);
    try {
      await requestEmailVerification(email);
      setResendMsg("Verification email sent. Check your inbox.");
    } catch {
      setResendMsg("Failed to resend. Please try again.");
    } finally {
      setResending(false);
    }
  }

  if (state === "loading") {
    return (
      <div className="flex flex-col items-center gap-4 py-20">
        <Loader2 className="h-8 w-8 animate-spin text-brand-blue" />
        <p className="text-gray-600">Verifying your email…</p>
      </div>
    );
  }

  if (state === "success") {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <CheckCircle2 className="h-12 w-12 text-green-500" />
        <h1 className="text-xl font-bold text-gray-900">Email Verified</h1>
        <p className="text-gray-600">
          Your email has been verified. You&apos;ve been upgraded to Tier 2 (50 tokens/day).
        </p>
        <Link
          href="/profile"
          className="rounded-lg bg-brand-blue px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Go to Profile
        </Link>
      </div>
    );
  }

  if (state === "expired") {
    return (
      <div className="flex flex-col items-center gap-4 py-20 text-center">
        <AlertTriangle className="h-12 w-12 text-yellow-500" />
        <h1 className="text-xl font-bold text-gray-900">Link Expired</h1>
        <p className="text-gray-600">
          This verification link has expired. Request a new one below.
        </p>
        {email && (
          <button
            onClick={handleResend}
            disabled={resending}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-blue px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {resending && <Loader2 className="h-4 w-4 animate-spin" />}
            Resend Verification Email
          </button>
        )}
        {resendMsg && <p className="text-sm text-gray-600">{resendMsg}</p>}
        <Link href="/profile" className="text-sm text-brand-blue hover:underline">
          Back to Profile
        </Link>
      </div>
    );
  }

  // invalid
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <XCircle className="h-12 w-12 text-red-500" />
      <h1 className="text-xl font-bold text-gray-900">Invalid Link</h1>
      <p className="text-gray-600">
        This verification link is invalid. It may have already been used.
      </p>
      <Link href="/profile" className="text-sm text-brand-blue hover:underline">
        Back to Profile
      </Link>
    </div>
  );
}

export default function VerifyPage() {
  return (
    <div className="mx-auto max-w-lg px-4">
      <Suspense
        fallback={
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-6 w-6 animate-spin text-brand-blue" />
          </div>
        }
      >
        <VerifyContent />
      </Suspense>
    </div>
  );
}
