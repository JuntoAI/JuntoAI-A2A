import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { Clock, MessageSquare, AlertTriangle, DollarSign, Users, Star, BarChart3 } from "lucide-react";
import { backendFetch } from "@/lib/proxy";
import type { SharePayload } from "@/lib/share";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://app.juntoai.org";

const STATUS_STYLES: Record<
  SharePayload["deal_status"],
  { label: string; bg: string; text: string; border: string; dot: string }
> = {
  Agreed: {
    label: "Deal Agreed",
    bg: "bg-green-50",
    text: "text-green-800",
    border: "border-green-500",
    dot: "bg-green-500",
  },
  Blocked: {
    label: "Deal Blocked",
    bg: "bg-yellow-50",
    text: "text-yellow-800",
    border: "border-yellow-500",
    dot: "bg-yellow-500",
  },
  Failed: {
    label: "Negotiation Failed",
    bg: "bg-gray-50",
    text: "text-gray-700",
    border: "border-gray-400",
    dot: "bg-gray-400",
  },
};

function formatElapsed(ms: number): string {
  const totalSeconds = Math.round(ms / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max - 1) + "…";
}

async function fetchSharePayload(slug: string): Promise<SharePayload | null> {
  try {
    const res = await backendFetch(`/api/v1/share/${slug}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Metadata (Task 9.2)
// ---------------------------------------------------------------------------

type PageProps = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const data = await fetchSharePayload(slug);

  if (!data) {
    return { title: "Negotiation Not Found" };
  }

  const title = `${data.scenario_name} — ${data.deal_status}`;
  const description = truncate(data.outcome_text || data.scenario_description, 200);
  const url = `${SITE_URL}/share/${data.share_slug}`;
  const image = data.share_image_url;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url,
      images: image ? [{ url: image }] : undefined,
      type: "article",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: image ? [image] : undefined,
    },
  };
}


// ---------------------------------------------------------------------------
// Page Component (Task 9.1)
// ---------------------------------------------------------------------------

export default async function SharePage({ params }: PageProps) {
  const { slug } = await params;
  const data = await fetchSharePayload(slug);

  if (!data) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
        <h1 className="text-2xl font-bold text-brand-charcoal">
          Negotiation not found
        </h1>
        <p className="mt-2 text-sm text-gray-500">
          This share link may have expired or the negotiation doesn't exist.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex items-center rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        >
          Try JuntoAI A2A
        </Link>
      </div>
    );
  }

  const status = STATUS_STYLES[data.deal_status];
  const arenaUrl = data.scenario_id
    ? `/?scenario=${encodeURIComponent(data.scenario_id)}`
    : "/";

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      {/* Branded header */}
      <header className="mb-6 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <Image
            src="/juntoai_logo_500x500.png"
            alt="JuntoAI logo"
            width={32}
            height={32}
          />
          <span className="text-lg font-semibold text-brand-charcoal">
            JuntoAI A2A
          </span>
        </Link>
        <div className="flex items-center gap-2">
          <Link
            href={arenaUrl}
            className="rounded-lg border border-brand-blue px-4 py-2 text-sm font-semibold text-brand-blue transition-opacity hover:opacity-80"
          >
            Run it yourself
          </Link>
          <Link
            href="https://a2a.juntoai.org/"
            className="rounded-lg bg-brand-blue px-4 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
          >
            Try JuntoAI
          </Link>
        </div>
      </header>

      {/* Main card */}
      <div className={`rounded-xl border-2 ${status.border} ${status.bg} p-6 sm:p-8`}>
        {/* Status badge + scenario name */}
        <div className="mb-4">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${status.text} ${status.bg} border ${status.border}`}
          >
            <span className={`h-2 w-2 rounded-full ${status.dot}`} />
            {status.label}
          </span>
          <h1 className="mt-3 text-2xl font-bold text-brand-charcoal sm:text-3xl">
            {data.scenario_name}
          </h1>
          {data.scenario_description && (
            <p className="mt-1 text-sm text-gray-500">
              {data.scenario_description}
            </p>
          )}
        </div>

        {/* Outcome text */}
        {data.outcome_text && (
          <p className="mb-6 text-sm leading-relaxed text-gray-700">
            {data.outcome_text}
          </p>
        )}

        {/* Metrics row */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {data.final_offer > 0 && (
            <div className="flex items-center gap-2 rounded-lg bg-white/70 p-3">
              <DollarSign className="h-4 w-4 text-gray-400 flex-shrink-0" />
              <div>
                <p className="text-xs text-gray-500">Final Offer</p>
                <p className="text-sm font-semibold text-brand-charcoal">
                  {formatCurrency(data.final_offer)}
                </p>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 rounded-lg bg-white/70 p-3">
            <MessageSquare className="h-4 w-4 text-gray-400 flex-shrink-0" />
            <div>
              <p className="text-xs text-gray-500">Turns</p>
              <p className="text-sm font-semibold text-brand-charcoal">
                {data.turns_completed}
              </p>
            </div>
          </div>
          {data.warning_count > 0 && (
            <div className="flex items-center gap-2 rounded-lg bg-white/70 p-3">
              <AlertTriangle className="h-4 w-4 text-gray-400 flex-shrink-0" />
              <div>
                <p className="text-xs text-gray-500">Warnings</p>
                <p className="text-sm font-semibold text-brand-charcoal">
                  {data.warning_count}
                </p>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2 rounded-lg bg-white/70 p-3">
            <Clock className="h-4 w-4 text-gray-400 flex-shrink-0" />
            <div>
              <p className="text-xs text-gray-500">Elapsed</p>
              <p className="text-sm font-semibold text-brand-charcoal">
                {formatElapsed(data.elapsed_time_ms)}
              </p>
            </div>
          </div>
        </div>

        {/* Evaluation scores */}
        {data.evaluation_scores && (
          <div className="mb-6 border-t border-gray-200 pt-5">
            <div className="mb-3 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-gray-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                Negotiation Evaluation
              </h2>
              <span className="ml-auto flex items-center gap-1 text-lg font-bold text-brand-charcoal">
                <Star className="h-4 w-4 text-yellow-500" />
                {data.evaluation_scores.overall_score}/10
              </span>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {(
                [
                  ["Fairness", data.evaluation_scores.fairness],
                  ["Mutual Respect", data.evaluation_scores.mutual_respect],
                  ["Value Creation", data.evaluation_scores.value_creation],
                  ["Satisfaction", data.evaluation_scores.satisfaction],
                ] as const
              ).map(([label, score]) => (
                <div key={label} className="rounded-lg bg-white/70 p-3 text-center">
                  <p className="text-xs text-gray-500">{label}</p>
                  <p className="text-lg font-bold text-brand-charcoal">{score}<span className="text-sm font-normal text-gray-400">/10</span></p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Public conversation */}
        {data.public_conversation && data.public_conversation.length > 0 && (
          <div className="mb-6 border-t border-gray-200 pt-5">
            <div className="mb-3 flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-gray-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                Public Conversation
              </h2>
            </div>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {data.public_conversation.map((msg, i) => (
                <div key={i} className="rounded-lg bg-white/70 p-3">
                  <div className="mb-1 flex items-center gap-2">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
                        msg.agent_type === "regulator"
                          ? "bg-red-100 text-red-700"
                          : msg.agent_type === "observer"
                            ? "bg-purple-100 text-purple-700"
                            : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {msg.agent_name}
                    </span>
                    <span className="text-xs text-gray-400">Turn {msg.turn_number}</span>
                  </div>
                  <p className="text-sm leading-relaxed text-gray-700">{msg.message}</p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-center text-xs text-gray-400">
              Want to see inner thoughts, metrics, and full analysis?{" "}
              <Link href="https://a2a.juntoai.org/" className="font-medium text-brand-blue hover:underline">
                Get more insights in JuntoAI
              </Link>
            </p>
          </div>
        )}

        {/* Participant summaries */}
        {data.participant_summaries.length > 0 && (
          <div className="border-t border-gray-200 pt-5">
            <div className="mb-3 flex items-center gap-2">
              <Users className="h-4 w-4 text-gray-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
                Participants
              </h2>
            </div>
            <div className="space-y-3">
              {data.participant_summaries.map((p, i) => (
                <div key={i} className="text-sm">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`inline-block flex-shrink-0 rounded px-2 py-0.5 text-xs font-medium ${
                        p.agent_type === "regulator"
                          ? "bg-red-100 text-red-700"
                          : p.agent_type === "observer"
                            ? "bg-purple-100 text-purple-700"
                            : "bg-blue-100 text-blue-700"
                      }`}
                    >
                      {p.name}
                    </span>
                    <span className="text-xs text-gray-400">{p.role}</span>
                  </div>
                  <p className="text-gray-700 leading-relaxed">{p.summary}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Bottom CTAs */}
      <div className="mt-8 flex flex-col items-center gap-4">
        <div className="flex items-center gap-3">
          <Link
            href={arenaUrl}
            className="rounded-lg border border-brand-blue px-6 py-3 text-sm font-semibold text-brand-blue transition-opacity hover:opacity-80"
          >
            Run it yourself
          </Link>
          <Link
            href="https://a2a.juntoai.org/"
            className="rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
          >
            Try JuntoAI
          </Link>
        </div>
        <p className="text-sm text-gray-500">
          Powered by{" "}
          <Link href="/" className="font-medium text-brand-blue hover:underline">
            JuntoAI A2A
          </Link>{" "}
          — AI agents negotiating in real time
        </p>
      </div>
    </div>
  );
}
