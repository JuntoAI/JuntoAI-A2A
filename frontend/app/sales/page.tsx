import type { Metadata } from "next";
import {
  Target,
  Shield,
  Users,
  MessageSquare,
  Briefcase,
  RefreshCw,
  Building2,
  Search,
  Github,
} from "lucide-react";
import WaitlistForm from "@/components/WaitlistForm";

export const metadata: Metadata = {
  title: "AI Deal Rehearsal for Sales Teams | JuntoAI",
  description:
    "Rehearse high-stakes sales calls with AI agents that behave like real buyers, procurement gatekeepers, and executives. Practice objection handling, multi-stakeholder navigation, and discovery calls before the real thing.",
  openGraph: {
    title: "JuntoAI | AI Deal Rehearsal for Sales Teams",
    description:
      "Practice your next sales call against AI agents that push back, stall, and negotiate like real prospects. Flip a single toggle and watch the entire deal dynamic shift.",
    url: "/sales",
    siteName: "JuntoAI",
    type: "website",
  },
  alternates: { canonical: "/sales" },
};

const VALUE_PROPS = [
  {
    icon: Shield,
    iconBg: "bg-brand-blue/10",
    iconColor: "text-brand-blue",
    title: "Objection Handling",
    description:
      "Face realistic pushback on pricing, timelines, and competitors. Build muscle memory for the objections that kill deals.",
  },
  {
    icon: Target,
    iconBg: "bg-brand-green/10",
    iconColor: "text-brand-green",
    title: "Hidden Variables",
    description:
      "Flip a toggle to give an agent a secret competing offer or budget cut mandate. Watch how one piece of information reshapes the entire deal.",
  },
  {
    icon: Users,
    iconBg: "bg-brand-blue/10",
    iconColor: "text-brand-blue",
    title: "Multi-Stakeholder Navigation",
    description:
      "Practice selling when the champion loves you but procurement is blocking. Navigate buying committees with up to 4 AI agents.",
  },
] as const;

const SCENARIOS = [
  {
    icon: Briefcase,
    title: "SaaS Contract Negotiation",
    description:
      "Negotiate seat-based pricing, implementation fees, and SLA terms against a VP buyer and procurement gatekeeper.",
    difficulty: "Intermediate",
  },
  {
    icon: RefreshCw,
    title: "Renewal / Churn Save",
    description:
      "Retain a dissatisfied customer threatening to cancel. Overcome grievances about support, pricing, and underused features.",
    difficulty: "Intermediate",
  },
  {
    icon: Building2,
    title: "Enterprise Multi-Stakeholder",
    description:
      "Navigate a 4-person buying committee: champion CTO, blocking procurement, legal compliance, and your sales strategy.",
    difficulty: "Advanced",
  },
  {
    icon: Search,
    title: "Discovery / Qualification",
    description:
      "Qualify a guarded prospect by uncovering budget, authority, need, and timeline through strategic questioning.",
    difficulty: "Beginner",
  },
] as const;

export default function SalesPage() {
  return (
    <main className="flex min-h-screen flex-col items-center">
      {/* Hero Section */}
      <section className="w-full bg-brand-offwhite pt-20 pb-12">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center text-center">
            <h1 className="text-4xl font-bold tracking-tight text-brand-charcoal sm:text-5xl lg:text-6xl">
              Rehearse Your Next Deal.{" "}
              <span className="text-brand-blue">Close with Confidence.</span>
            </h1>

            <p className="mt-4 max-w-2xl text-base leading-relaxed text-brand-charcoal/70 sm:text-lg">
              Practice high-stakes sales calls against AI agents that push back,
              stall, and negotiate like real buyers. Build objection-handling
              muscle memory before the call that matters.
            </p>

            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-brand-charcoal/50">
              Flip a single hidden variable and watch the entire deal dynamic
              shift. See exactly how your strategy holds up when the prospect has
              a competing offer you don&apos;t know about.
            </p>

            <div id="waitlist" className="mt-8 w-full max-w-md">
              <WaitlistForm />
            </div>
          </div>
        </div>
      </section>

      {/* Value Props Section */}
      <section className="w-full bg-brand-offwhite py-16">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <div className="grid gap-6 sm:grid-cols-3">
            {VALUE_PROPS.map((prop) => {
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

      {/* Scenario Showcase Section */}
      <section className="w-full bg-brand-gray py-16">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <h2 className="mb-8 text-center text-2xl font-bold text-brand-charcoal sm:text-3xl">
            Four Sales Scenarios. Zero Fluff.
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

      {/* CTA Section */}
      <section className="w-full bg-brand-offwhite py-16">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <div
            className="relative overflow-hidden rounded-xl p-8 text-center sm:p-12"
            style={{ background: "var(--gradient)" }}
          >
            <div className="absolute inset-0 bg-white/90" />

            <div className="relative z-10 flex flex-col items-center">
              <MessageSquare className="h-10 w-10 text-brand-charcoal" />

              <h2 className="mt-4 text-2xl font-bold text-brand-charcoal sm:text-3xl">
                Try a Sales Simulation
              </h2>

              <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-charcoal/70">
                Pick a scenario, configure the hidden variables, and watch AI
                agents negotiate in real time. See their inner reasoning before
                every message.
              </p>

              <div className="mt-6 flex flex-col items-center gap-3 sm:flex-row">
                <a
                  href="/arena"
                  className="inline-flex items-center gap-2 rounded-lg bg-brand-blue px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
                >
                  Open the Arena
                </a>
                <a
                  href="https://github.com/JuntoAI/JuntoAI-A2A"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg bg-brand-charcoal px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
                >
                  <Github className="h-4 w-4" />
                  View on GitHub
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
