"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CheckCircle2, XCircle, Loader2, AlertTriangle } from "lucide-react";

type VerifyState = "loading" | "success" | "expired" | "invalid";

function VerifyContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<VerifyState>("loading");

  useEffect(() => {
    if (!token) {
      setState("invalid");
      return;
    }

    let cancelled = false;

    async function verify() {
      try {
        const res = await fetch(`/api/v1/profile/verify/${encodeURIComponent(token!)}`);
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
          Your email has been verified successfully. You&apos;ve been upgraded to Tier 2 (50 tokens/day).
        </p>
        <p className="text-sm text-gray-500">
          Log in to see your updated token balance.
        </p>
        <Link
          href="/"
          className="rounded-lg bg-brand-blue px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Go to Login
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
          This verification link has expired. Log in and request a new one from your profile page.
        </p>
        <Link
          href="/"
          className="rounded-lg bg-brand-blue px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Go to Login
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
      <Link href="/" className="text-sm text-brand-blue hover:underline">
        Back to Home
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
