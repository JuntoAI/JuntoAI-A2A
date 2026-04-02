"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useSession } from "@/context/SessionContext";
import { joinWaitlist } from "@/lib/waitlist";
import { needsReset, resetTokens } from "@/lib/tokens";

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useSession();
  const router = useRouter();

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
      const doc = await joinWaitlist(trimmed);

      let balance = doc.token_balance;
      let lastReset = doc.last_reset_date;

      if (needsReset(doc.last_reset_date)) {
        await resetTokens(doc.email);
        balance = 100;
        lastReset = new Date().toISOString().slice(0, 10);
      }

      login(doc.email, balance, lastReset);
      router.push("/arena");
    } catch (err) {
      console.error("[WaitlistForm] submission failed:", err);
      setError("Something went wrong. Please try again.");
      setIsLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 w-full max-w-md">
      <div className="flex flex-col gap-1">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          aria-label="Email address"
          aria-describedby={error ? "waitlist-error" : undefined}
          className="w-full rounded-lg border border-gray-300 px-4 py-3 text-sm text-brand-charcoal placeholder-gray-400 focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-blue/30"
        />
        {error && (
          <p id="waitlist-error" role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
      </div>
      <button
        type="submit"
        disabled={isLoading}
        className="flex items-center justify-center gap-2 rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
        {isLoading ? "Starting..." : "Start the AI 2 AI Negotiation"}
      </button>
      <p className="text-center text-xs text-brand-charcoal/50">
        By running this demo you're signing up for the{" "}
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
