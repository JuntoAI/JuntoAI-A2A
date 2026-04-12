import { redirect } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import {
  Handshake,
  Eye,
  SlidersHorizontal,
  Github,
  ArrowRight,
} from "lucide-react";
import { isLocalMode } from "@/lib/runMode";
import ScenarioBanner from "@/components/ScenarioBanner";
import WaitlistForm from "@/components/WaitlistForm";

export const metadata: Metadata = {
  title: "Open Source AI Negotiation Sandbox | JuntoAI",
  description:
    "An open-source AI negotiation engine where autonomous agents find the win-win. Clone the repo, run docker compose up, and explore Glass Box reasoning on localhost.",
  openGraph: {
    title: "JuntoAI | Open Source AI Negotiation Sandbox",
    description:
      "Autonomous AI agents negotiate in real time with transparent reasoning. Open source, config-driven, and ready to run locally.",
    url: "/open-source",
    siteName: "JuntoAI",
    type: "website",
  },
  alternates: { canonical: "/open-source" },
};

const DEV_VALUE_PROPS = [
  {
    icon: Handshake,
    iconBg: "bg-brand-blue/10",
    iconColor: "text-brand-blue",
    title: "Not Zero-Sum",
    description:
      "Agents search for mutual gains, not just concessions. The protocol rewards creative trade-offs that expand the pie for both sides.",
  },
  {
    icon: Eye,
    iconBg: "bg-brand-green/10",
    iconColor: "text-brand-green",
    title: "Glass Box Reasoning",
    description:
      "Every agent streams its inner thoughts before speaking publicly. See exactly why it conceded, bluffed, or walked away.",
  },
  {
    icon: SlidersHorizontal,
    iconBg: "bg-brand-blue/10",
    iconColor: "text-brand-blue",
    title: "One Toggle Changes Everything",
    description:
      "Flip a single hidden variable — a secret competing offer, a budget cut — and watch the entire negotiation shift in real time.",
  },
] as const;

export default function OpenSourcePage() {
  if (isLocalMode) {
    redirect("/arena");
  }

  return (
    <main className="flex min-h-screen flex-col items-center">
      {/* Hero Section */}
      <section className="w-full bg-brand-offwhite pt-20 pb-12">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center text-center">
            <h1 className="text-4xl font-bold tracking-tight text-brand-charcoal sm:text-5xl lg:text-6xl">
              AI Negotiation Sandbox.{" "}
              <span className="text-brand-blue">Find the Win-Win.</span>
            </h1>

            <p className="mt-4 max-w-2xl text-base leading-relaxed text-brand-charcoal/70 sm:text-lg">
              An open-source engine where autonomous AI agents negotiate in real
              time. Config-driven scenarios, transparent reasoning, and a
              protocol that rewards creative trade-offs.
            </p>

            <div id="waitlist" className="mt-8 w-full max-w-md">
              <WaitlistForm />
            </div>
          </div>
        </div>
      </section>

      {/* Scenario Banner */}
      <section className="w-full bg-brand-gray py-4">
        <ScenarioBanner />
      </section>

      {/* Developer Value Proposition Cards */}
      <section className="w-full bg-brand-offwhite py-16">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <div className="grid gap-6 sm:grid-cols-3">
            {DEV_VALUE_PROPS.map((prop) => {
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

      {/* GitHub CTA Section */}
      <section className="w-full bg-brand-gray py-16">
        <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <div
            className="relative overflow-hidden rounded-xl p-8 text-center sm:p-12"
            style={{ background: "var(--gradient)" }}
          >
            <div className="absolute inset-0 bg-white/90" />

            <div className="relative z-10 flex flex-col items-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-charcoal/10">
                <Github className="h-6 w-6 text-brand-charcoal" />
              </div>

              <h2 className="mt-4 text-2xl font-bold text-brand-charcoal sm:text-3xl">
                Built in Public. Join the Community.
              </h2>

              <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-charcoal/70">
                Clone the repo, run{" "}
                <code className="rounded bg-brand-gray px-1.5 py-0.5 text-xs font-medium text-brand-charcoal">
                  docker compose up
                </code>
                , and get the full stack on localhost. Bring your own API keys,
                drop in a scenario JSON, and start experimenting.
              </p>

              <Link
                href="https://github.com/JuntoAI/a2a"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-6 inline-flex items-center gap-2 rounded-lg bg-brand-charcoal px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              >
                <Github className="h-4 w-4" />
                View on GitHub
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
