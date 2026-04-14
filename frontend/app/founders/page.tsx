import { redirect } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import {
  Rocket,
  FileText,
  ShieldAlert,
  Briefcase,
  Users,
  Handshake,
  Building2,
  ArrowRight,
} from "lucide-react";
import { isLocalMode } from "@/lib/runMode";
import WaitlistForm from "@/components/WaitlistForm";
import FoundersPersonaSetter from "@/components/FoundersPersonaSetter";

export const metadata: Metadata = {
  title: "AI Pitch Rehearsal for Founders | JuntoAI",
  description:
    "Rehearse investor pitches and term sheet negotiations with AI agents that push back like real VCs. Simulate objection handling, due diligence defense, and equity negotiations before the real thing.",
  openGraph: {
    title: "JuntoAI | AI Pitch Rehearsal for Founders",
    description:
      "Simulate your next investor meeting against AI agents that challenge your valuation, question your metrics, and negotiate like real VCs.",
    url: "/founders",
    siteName: "JuntoAI",
    type: "website",
  },
  alternates: { canonical: "/founders" },
};

const FOUNDER_VALUE_PROPS = [
  {
    icon: Rocket,
    iconBg: "bg-brand-blue/10",
    iconColor: "text-brand-blue",
    title: "Pitch Simulation",
    description:
      "Practice your investor pitch against AI VCs that challenge your valuation, TAM, and go-to-market. Get sharper before the meeting that matters.",
  },
  {
    icon: FileText,
    iconBg: "bg-brand-green/10",
    iconColor: "text-brand-green",
    title: "Term Sheet Negotiation",
    description:
      "Negotiate liquidation preferences, anti-dilution clauses, and board seats with AI investors. Understand every clause before you sign.",
  },
  {
    icon: ShieldAlert,
    iconBg: "bg-brand-blue/10",
    iconColor: "text-brand-blue",
    title: "Investor Objection Handling",
    description:
      "Face tough questions on burn rate, unit economics, and competitive moats. Build confidence handling the objections that kill fundraises.",
  },
] as const;

const SCENARIOS = [
  {
    icon: Briefcase,
    title: "Startup Pitch",
    description:
      "Pitch your startup to a skeptical VC partner while a market analyst challenges your assumptions. Defend your vision and close the round.",
    difficulty: "Intermediate",
  },
  {
    icon: Users,
    title: "Co-Founder Equity Split",
    description:
      "Negotiate equity, vesting, and roles with your co-founder. A startup advisor mediates to keep the partnership intact.",
    difficulty: "Intermediate",
  },
  {
    icon: Handshake,
    title: "Term Sheet Negotiation",
    description:
      "Negotiate liquidation preferences, anti-dilution, pro-rata rights, and board composition with a lead investor and legal advisor.",
    difficulty: "Advanced",
  },
  {
    icon: Building2,
    title: "M&A Buyout",
    description:
      "Navigate an acquisition offer as a founder. Negotiate valuation, earnouts, and team retention against a corporate buyer and EU regulator.",
    difficulty: "Advanced",
  },
] as const;

export default function FoundersPage() {
  if (isLocalMode) {
    redirect("/arena");
  }

  return (
    <>
      <FoundersPersonaSetter />

      <main className="flex min-h-screen flex-col items-center">
        {/* Hero Section */}
        <section className="w-full bg-brand-offwhite pt-20 pb-12">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center text-center">
              <h1 className="text-4xl font-bold tracking-tight text-brand-charcoal sm:text-5xl lg:text-6xl">
                Rehearse Your Pitch.{" "}
                <span className="text-brand-blue">Negotiate with Confidence.</span>
              </h1>

              <p className="mt-4 max-w-2xl text-base leading-relaxed text-brand-charcoal/70 sm:text-lg">
                Simulate investor meetings against AI agents that challenge your
                valuation, question your metrics, and negotiate term sheets like
                real VCs. Build fundraising muscle memory before the meeting that
                matters.
              </p>

              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-brand-charcoal/50">
                Flip a single hidden variable — a competing term sheet, a fund
                timeline pressure — and watch the entire negotiation dynamic shift
                in real time.
              </p>

              <div id="waitlist" className="mt-8 w-full max-w-md">
                <WaitlistForm />
              </div>
            </div>
          </div>
        </section>

        {/* Founder Value Proposition Cards */}
        <section className="w-full bg-brand-offwhite py-16">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="grid gap-6 sm:grid-cols-3">
              {FOUNDER_VALUE_PROPS.map((prop) => {
                const Icon = prop.icon;
                return (
                  <div
                    key={prop.title}
                    className="flex flex-col items-center rounded-xl bg-white p-6 text-center shadow-sm"
                  >
                    <div
                      className={`flex h-12 w-12 items-center justify-center rounded-full ${prop.iconBg}`}
                    >
                      <Icon className={`h-6 w-6 ${prop.iconColor}`} />
                    </div>
                    <h3 className="mt-4 text-sm font-semibold text-brand-charcoal">
                      {prop.title}
                    </h3>
                    <p className="mt-2 text-xs leading-relaxed text-brand-charcoal/60">
                      {prop.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Scenario Showcase */}
        <section className="w-full bg-brand-gray py-16">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <h2 className="mb-8 text-center text-2xl font-bold text-brand-charcoal sm:text-3xl">
              Four Founder Scenarios. Real Stakes.
            </h2>
            <div className="grid gap-6 sm:grid-cols-2">
              {SCENARIOS.map((scenario) => {
                const Icon = scenario.icon;
                return (
                  <div
                    key={scenario.title}
                    className="flex gap-4 rounded-xl bg-white p-6 shadow-sm"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-blue/10">
                      <Icon className="h-5 w-5 text-brand-blue" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold text-brand-charcoal">
                          {scenario.title}
                        </h3>
                        <span className="rounded-full bg-brand-gray px-2 py-0.5 text-[10px] font-medium text-brand-charcoal/60">
                          {scenario.difficulty}
                        </span>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-brand-charcoal/60">
                        {scenario.description}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* Bottom CTA Section */}
        <section className="w-full bg-brand-offwhite py-16">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div
              className="relative overflow-hidden rounded-xl p-8 text-center sm:p-12"
              style={{ background: "var(--gradient)" }}
            >
              <div className="absolute inset-0 bg-white/90" />

              <div className="relative z-10 flex flex-col items-center">
                <h2 className="text-2xl font-bold text-brand-charcoal sm:text-3xl">
                  Ready to rehearse your pitch?
                </h2>

                <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-charcoal/70">
                  Pick a scenario, configure the hidden variables, and practice
                  against AI investors that negotiate in real time.
                </p>

                <Link
                  href="/arena"
                  className="mt-6 inline-flex items-center gap-2 rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
                >
                  Try a Free Simulation
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
