import { redirect } from "next/navigation";
import type { Metadata } from "next";
import { Handshake, Eye, SlidersHorizontal, Github } from "lucide-react";
import { isLocalMode } from "@/lib/runMode";
import WaitlistForm from "@/components/WaitlistForm";
import ScenarioBanner from "@/components/ScenarioBanner";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "JuntoAI A2A Protocol Sandbox",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  description:
    "A simulation sandbox where autonomous AI agents negotiate real-world scenarios in real time, finding win-win outcomes through transparent reasoning and configurable hidden variables.",
  url: "https://app.juntoai.org",
  author: {
    "@type": "Organization",
    name: "JuntoAI",
    url: "https://juntoai.org",
  },
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "EUR",
    description: "Free access with 100 tokens per day",
  },
};

const VALUE_PROPS = [
  {
    icon: Handshake,
    iconBg: "bg-brand-green/10",
    iconColor: "text-brand-green",
    title: "Not Zero-Sum",
    description:
      "Agents seek mutual benefit, not domination. Watch them find creative compromises.",
  },
  {
    icon: Eye,
    iconBg: "bg-brand-blue/10",
    iconColor: "text-brand-blue",
    title: "Glass Box Reasoning",
    description:
      "See every agent\u2019s inner thoughts before they speak. Understand why they concede or hold firm.",
  },
  {
    icon: SlidersHorizontal,
    iconBg: "bg-brand-green/10",
    iconColor: "text-brand-green",
    title: "One Toggle Changes Everything",
    description:
      "Give an agent a secret competing offer or hidden deadline and watch the entire dynamic shift.",
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

      <main className="flex min-h-screen flex-col items-center bg-brand-offwhite pt-20">
        {/* Hero Section */}
        <section className="mx-auto w-full max-w-[1200px] px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center text-center">
            <h1 className="text-4xl font-bold tracking-tight text-brand-charcoal sm:text-5xl lg:text-6xl">
              AI Negotiation Sandbox.{" "}
              <span className="text-brand-blue">Find the Win&#8209;Win.</span>
            </h1>

            <p className="mt-4 max-w-2xl text-base leading-relaxed text-brand-charcoal/70 sm:text-lg">
              Real negotiations aren&apos;t about one side winning. They&apos;re
              about finding outcomes everyone can live with. JuntoAI A2A
              simulates that process with autonomous AI agents working through
              scenarios in real time.
            </p>

            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-brand-charcoal/50">
              Pick a scenario, flip the hidden variables, and watch how a single
              piece of information reshapes the entire conversation.
            </p>

            <div id="waitlist" className="mt-8 w-full max-w-md">
              <WaitlistForm />
            </div>
          </div>
        </section>

        {/* Scenario Banner — full viewport width breakout */}
        <div className="mt-12 w-full">
          <ScenarioBanner />
        </div>

        {/* Value Proposition Cards */}
        <section className="mx-auto w-full max-w-[1200px] px-4 py-16 sm:px-6 lg:px-8">
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
        </section>

        {/* GitHub Community CTA */}
        <section className="mx-auto w-full max-w-[1200px] px-4 pb-16 sm:px-6 lg:px-8">
          <div
            className="relative overflow-hidden rounded-xl p-8 text-center sm:p-12"
            style={{ background: "var(--gradient)" }}
          >
            {/* Subtle overlay for text readability */}
            <div className="absolute inset-0 bg-white/90" />

            <div className="relative z-10 flex flex-col items-center">
              <Github className="h-10 w-10 text-brand-charcoal" />

              <h2 className="mt-4 text-2xl font-bold text-brand-charcoal sm:text-3xl">
                Built in Public. Join the Community.
              </h2>

              <p className="mt-3 max-w-lg text-sm leading-relaxed text-brand-charcoal/70">
                Clone the repo, run it locally, contribute new negotiation
                scenarios, or build custom agent plugins. The entire stack is
                open source.
              </p>

              <a
                href="https://github.com/JuntoAI/JuntoAI-A2A"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-6 inline-flex items-center gap-2 rounded-lg bg-brand-charcoal px-6 py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              >
                <Github className="h-4 w-4" />
                View on GitHub
              </a>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
