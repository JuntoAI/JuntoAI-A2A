import { redirect } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import {
  Shield,
  Target,
  Users,
  Briefcase,
  RefreshCw,
  Building2,
  Search,
  Eye,
  Play,
  ArrowRight,
} from "lucide-react";
import { isLocalMode } from "@/lib/runMode";
import WaitlistForm from "@/components/WaitlistForm";

export const metadata: Metadata = {
  title: "AI Deal Rehearsal for Sales Teams | JuntoAI",
  description:
    "Rehearse high-stakes sales calls with AI agents that push back, stall, and negotiate like real buyers. Simulate objection handling, multi-stakeholder navigation, and discovery calls before the real thing.",
  openGraph: {
    title: "JuntoAI | AI Deal Rehearsal for Sales Teams",
    description:
      "Simulate your next sales call against AI agents that push back, stall, and negotiate like real prospects.",
    url: "/",
    siteName: "JuntoAI",
    type: "website",
  },
  alternates: { canonical: "/" },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "JuntoAI — AI Deal Rehearsal",
  applicationCategory: "Sales Training",
  operatingSystem: "Web",
  description:
    "AI-powered sales rehearsal platform where reps simulate deals against autonomous buyer agents. Covers objection handling, multi-stakeholder deals, and discovery calls.",
  url: "https://app.juntoai.org",
  keywords: "sales rehearsal, deal practice, AI sales training, objection handling, sales enablement",
  author: {
    "@type": "Organization",
    name: "JuntoAI",
    url: "https://juntoai.org",
  },
  offers: {
    "@type": "Offer",
    price: "500",
    priceCurrency: "EUR",
    description: "Starting at $500/month for teams",
  },
};

const SALES_VALUE_PROPS = [
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
      "Simulate selling when the champion loves you but procurement is blocking. Navigate buying committees with up to 4 AI agents.",
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

export default function Home() {
  if (isLocalMode) {
    redirect("/arena");
  }

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

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
                Simulate high-stakes sales calls against AI agents that push back,
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

        {/* Pain / ROI Section */}
        <section className="w-full bg-brand-gray py-16">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center text-center">
              <h2 className="text-2xl font-bold text-brand-charcoal sm:text-3xl">
                Your reps forget training in 2 weeks.
              </h2>
              <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-charcoal/70">
                They need practice, not more slides.
              </p>
            </div>
          </div>
        </section>

        {/* Sales Value Proposition Cards */}
        <section className="w-full bg-brand-offwhite py-16">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="grid gap-6 sm:grid-cols-3">
              {SALES_VALUE_PROPS.map((prop) => {
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

        {/* Glass Box Coaching Section */}
        <section className="w-full bg-brand-offwhite py-16">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-blue/10">
                <Eye className="h-6 w-6 text-brand-blue" />
              </div>
              <h2 className="mt-4 text-2xl font-bold text-brand-charcoal sm:text-3xl">
                Glass Box Coaching
              </h2>
              <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-charcoal/70">
                Managers replay any simulation and see the AI buyer&apos;s inner
                reasoning — why it pushed back, where it almost conceded, what
                triggered the stall. Use it as a coaching conversation starter
                with every rep.
              </p>
            </div>
          </div>
        </section>

        {/* Demo Video Placeholder */}
        <section className="w-full bg-brand-gray py-16">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center">
              <div className="flex h-64 w-full max-w-3xl items-center justify-center rounded-xl border-2 border-dashed border-brand-charcoal/20 bg-white">
                <div className="flex flex-col items-center gap-3 text-brand-charcoal/40">
                  <Play className="h-12 w-12" />
                  <span className="text-sm font-medium">Demo coming soon</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing Signal */}
        <section className="w-full bg-brand-offwhite py-12">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center text-center">
              <p className="text-lg font-semibold text-brand-charcoal">
                Starting at $500/month for teams
              </p>
            </div>
          </div>
        </section>

        {/* Supported By Section */}
        <section className="w-full bg-brand-gray py-10">
          <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col items-center gap-3 text-center">
              <p className="text-xs font-medium uppercase tracking-wider text-brand-charcoal/40">
                Supported By
              </p>
              <div className="flex items-center gap-2 text-brand-charcoal/60">
                <span className="text-sm font-medium">Enterprise Ireland</span>
              </div>
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
                  Ready to see it in action?
                </h2>

                <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-charcoal/70">
                  Pick a scenario, configure the hidden variables, and watch AI
                  agents negotiate in real time.
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
